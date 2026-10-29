using System;
using System.Collections.Generic;
using CombatAI.Comps;
using RimWorld;
using UnityEngine;
using Verse;
namespace CombatAI
{
    public static class SightUtility
    {
        private const float DOWNED_SIGHT_FACTOR = 0.35f;
        private const int DOWNED_MIN_SIGHT = 2;
        private const float NEW_SIGHT_TURRET_FACTOR = 0.5f;
        internal const int NEW_SIGHT_RADIUS_REFRESH_TICKS = 45;
        private static StatDef cachedNightVisionEfficiencyStat;
        private static StatDef cachedNightVisionEfficiencyApparelStat;
        private static bool nightVisionStatsResolved;

        internal static bool NewSightSystemActive => Finder.Settings != null && Finder.Settings.FogOfWar_Enabled && Finder.Settings.NewSightSystem_Enabled;
        /// <summary>Rectangular maps, including vehicle interiors, cannot use the square-grid fallback.</summary>
        internal static bool SupportsMap(Map map)
        {
            return map != null && map.Size.x == map.Size.z;
        }

        public static float GetSightRadius_Fast(Thing thing)
        {
            return GetSightRadius_Cached(thing).sight;
        }

        private static SightGrid.ISightRadius GetSightRadius_Cached(Thing thing)
        {
            bool unifiedSight = NewSightSystemActive;
            int expiry = unifiedSight ? NEW_SIGHT_RADIUS_REFRESH_TICKS : 12000;
            if (!TKVCache<Thing, SightGrid.ISightRadius, SightGrid.ISightRadius>.TryGet(thing, out SightGrid.ISightRadius radius, expiry)
                || radius.usesNewSightSystem != unifiedSight)
            {
                radius = GetSightRadius(thing);
                TKVCache<Thing, SightGrid.ISightRadius, SightGrid.ISightRadius>.Put(thing, radius);
            }
            return radius;
        }

        /// <summary>
        ///     Whether <paramref name="thing" /> would see <paramref name="cell" /> from <paramref name="root" /> under the
        ///     unified sight system. Line of sight is not checked.
        /// </summary>
        internal static bool CanSeeCell(Thing thing, IntVec3 root, IntVec3 cell)
        {
            float range = GetLitSightRadius(thing, root, cell);
            return root.DistanceToSquared(cell) < range * range;
        }

        /// <summary>
        ///     Unified sight radius from <paramref name="root" /> toward <paramref name="cell" />, scaled by the lighting
        ///     at both ends like the sight grid.
        /// </summary>
        internal static float GetLitSightRadius(Thing thing, IntVec3 root, IntVec3 cell)
        {
            SightGrid.ISightRadius radius = GetSightRadius_Cached(thing);
            MapComponent_FogGrid fogComp = thing.Map?.GetComp_Fast<MapComponent_FogGrid>();
            if (fogComp == null)
            {
                return radius.sight;
            }
            byte[] glowBuckets = fogComp.SightGlowBuckets;
            return radius.sight * SightGrid.GetSightGlowCoefficient(fogComp.GetSightGlowBucket(root, glowBuckets), fogComp.GetSightGlowBucket(cell, glowBuckets), radius.nightVisionReduction);
        }

	    public static SightGrid.ISightRadius GetSightRadius(Thing thing)
        {
            bool                   unifiedSight = NewSightSystemActive;
            bool                   isSmartPawn = false;
            SightGrid.ISightRadius result;
            ThingComp_Sighter      sighter = thing.GetComp_Fast<ThingComp_Sighter>();
            if (sighter != null)
            {
                result = GetSightRadius_Sighter(sighter);
                Faction f = thing.Faction;

                if (f != null && (f.IsPlayerSafe() || (!f.HostileTo(Faction.OfPlayer) && Finder.Settings.FogOfWar_Allies)))
                {
                    result.fog = unifiedSight ? result.sight : Maths.Max(Mathf.CeilToInt(GetFogRadius(thing, result.sight) * Finder.Settings.FogOfWar_RangeMultiplier), 3);
                }
            }
            else if (thing is Pawn pawn)
            {
                result = GetSightRadius_Pawn(pawn);
                Faction f = thing.Faction;
                isSmartPawn = !unifiedSight && !pawn.RaceProps.Animal && !(pawn.Dead || pawn.Downed);
                if (f != null && (f.IsPlayerSafe() || (!f.HostileTo(Faction.OfPlayer) && Finder.Settings.FogOfWar_Allies)))
                {
                    if (pawn.RaceProps.Animal)
                    {
                        if (!Finder.Settings.FogOfWar_Animals)
                        {
                            goto finalize;
                        }
                        if (Finder.Settings.FogOfWar_AnimalsSmartOnly && pawn.RaceProps.trainability == TrainabilityDefOf.None)
                        {
                            goto finalize;
                        }
                    }
                    result.fog = unifiedSight ? result.sight : Maths.Max(Mathf.CeilToInt(GetFogRadius(thing, result.sight) * Finder.Settings.FogOfWar_RangeMultiplier), 3);
                }
            }
            else if (thing is Building_Turret turret)
            {
                result = GetSightRadius_Turret(turret);
                if (Finder.Settings.FogOfWar_Turrets || turret.GetComp_Fast<CompMannable>() is CompMannable mannable && mannable.MannedNow)
                {
                    Faction f = thing.Faction;

                    if (f != null && (f.IsPlayerSafe() || (!f.HostileTo(Faction.OfPlayer) && Finder.Settings.FogOfWar_Allies)))
                    {
                        result.fog = unifiedSight ? result.sight : Maths.Max(Mathf.CeilToInt(GetFogRadius(thing, result.sight) * Finder.Settings.FogOfWar_RangeMultiplier), 3);
                    }
                }
            }
            else
            {
                throw new Exception($"ISMA: GetSightRadius got an object that is niether a pawn, turret nor does it have sighter. {thing}");
            }
        finalize:
            if (isSmartPawn)
            {
                result.scan  = result.scan + 16;
                result.sight = result.sight + 8;
            }
            result.createdAt = GenTicks.TicksGame;
            result.usesNewSightSystem = unifiedSight;
            result.nightVisionReduction = unifiedSight ? GetNightVisionLutReduction(thing) : 0f;
            return result;
        }

        private static SightGrid.ISightRadius GetSightRadius_Pawn(Pawn pawn)
        {
            SightGrid.ISightRadius result = new SightGrid.ISightRadius();
            if (NewSightSystemActive)
            {
                float radius = Mathf.Max(GetFogRadius(pawn, Finder.Settings.NewSightSystem_BaseRadius), GetMinimumSightRadiusForDefeatSensitiveMap(pawn));
                result.sight = Mathf.CeilToInt(Mathf.Max(radius, 3f));
                result.scan = result.sight;
                ApplyDownedSightPenalty(pawn, ref result);
                return result;
            }
            if (pawn.RaceProps.Animal && pawn.Faction == null)
            {
                result.sight = Mathf.FloorToInt(Mathf.Clamp(pawn.BodySize * 3f, 2f, 10f));
                result.scan  = result.sight;
                return result;
            }
            Verb verb = pawn.TryGetAttackVerb();
            if (verb == null || !verb.Available())
            {
                result.sight = 4;
                result.scan  = 0;
                return result;
            }
            if (pawn.RaceProps.Insect || pawn.RaceProps.IsMechanoid || pawn.RaceProps.Animal)
            {
                if (verb.IsMeleeAttack)
                {
                    result.sight = 10;
                    result.scan  = 0;
                    return result;
                }
                result.scan  = Mathf.CeilToInt(verb.EffectiveRange + 10f);
                result.sight = Maths.Max((int)verb.EffectiveRange, 5);
                return result;
            }
            if (verb.IsMeleeAttack)
            {
                SkillRecord melee = pawn.skills?.GetSkill(SkillDefOf.Melee) ?? null;
                if (melee != null)
                {
                    result.sight = Maths.Max((int)(Mathf.Clamp(melee.Level, 5, 13) * ((pawn.equipment?.Primary?.def.IsMeleeWeapon ?? null) != null ? 1.5f : 0.85f)), 15);
                    result.scan  = Maths.Max(result.sight, 15);
                }
                else
                {
                    result.sight = 5;
                    result.scan  = 0;
                }
                return result;
            }
            result.scan  = Mathf.CeilToInt(verb.EffectiveRange);
            result.sight = Mathf.CeilToInt(verb.EffectiveRange * 0.75f);
            SkillRecord shooting = pawn.skills?.GetSkill(SkillDefOf.Shooting) ?? null;
            float       skill    = 5;
            if (shooting != null)
            {
                skill = shooting.Level;
            }
            result.sight = Mathf.CeilToInt(Maths.Max(result.sight * Mathf.Clamp(skill / 7.5f, 0.778f, 1.425f), 4));
            return result;
        }

        private static SightGrid.ISightRadius GetSightRadius_Turret(Building_Turret turret)
        {
            SightGrid.ISightRadius result = new SightGrid.ISightRadius();
            if (NewSightSystemActive)
            {
                result.sight = Mathf.CeilToInt(Mathf.Max(Finder.Settings.NewSightSystem_BaseRadius * NEW_SIGHT_TURRET_FACTOR, 3f));
                result.scan = result.sight;
                return result;
            }
            Verb                   verb   = turret.AttackVerb;
            if (verb != null)
            {
                result.sight = Mathf.CeilToInt(verb.EffectiveRange);
                result.scan  = Mathf.CeilToInt(verb.EffectiveRange);
            }
            return result;
        }

        private static SightGrid.ISightRadius GetSightRadius_Sighter(ThingComp_Sighter sighter)
        {
            SightGrid.ISightRadius result = new SightGrid.ISightRadius();
            result.sight = sighter.SightRadius;
            result.scan  = result.sight;
            return result;
        }

        private static float GetFogRadius(Thing thing, float sightRadius)
        {
            Pawn pawn = thing as Pawn;
            if (pawn == null)
            {
                CompMannable mannable = thing.GetComp_Fast<CompMannable>();
                if (mannable != null)
                {
                    pawn = mannable.ManningPawn;
                }
            }
            if (pawn != null)
            {
                // Unified mode also uses this radius as sight, so only legacy fog shrinks for pawns that just slept.
                if (pawn.Downed || !NewSightSystemActive && GenTicks.TicksGame - CombatAI.Compatibility.NeedCompat.GetLastRestTick(pawn.needs?.rest) < 120)
                {
                    return 3;
                }
                float vision        = Maths.Sqr(pawn.health.capacities?.GetLevel(PawnCapacityDefOf.Sight) ?? 1f);
                float consciousness = Maths.Sqr(pawn.health.capacities?.GetLevel(PawnCapacityDefOf.Consciousness) ?? 1f);
                float hearing       = Mathf.Lerp(0.80f, 1f, pawn.health.capacities?.GetLevel(PawnCapacityDefOf.Hearing) ?? 1f);
                float rest          = Mathf.Lerp(0.40f, 1f, pawn.needs?.rest == null ? 1f : CombatAI.Compatibility.NeedCompatExtras.GetCurLevel(pawn.needs.rest));
                float mul           = Mathf.Clamp(Maths.Min(rest, Maths.Min(hearing, vision, consciousness)) * 0.80f + Maths.Max(rest, Maths.Max(hearing, vision, consciousness)) * 0.20f, 0.15f, 2.5f);
                return Maths.Max(Maths.Max(sightRadius, 10) * mul, 3);
            }
            return sightRadius;
        }

        private static void ApplyDownedSightPenalty(Pawn pawn, ref SightGrid.ISightRadius result)
        {
            if (pawn == null || !pawn.Downed) return;
            result.sight = Mathf.Max(DOWNED_MIN_SIGHT, Mathf.CeilToInt(result.sight * DOWNED_SIGHT_FACTOR));
            if (result.scan > 0)
                result.scan = Mathf.Max(DOWNED_MIN_SIGHT, Mathf.CeilToInt(result.scan * DOWNED_SIGHT_FACTOR));
            result.scan = Mathf.Min(result.scan, result.sight);
        }

        internal static float GetNightVisionLutReduction(Thing thing)
        {
            Pawn pawn = thing as Pawn;
            if (pawn == null && thing is Building_Turret turret)
                pawn = turret.GetComp_Fast<CompMannable>()?.ManningPawn;
            if (pawn == null) return 0f;
            if (!nightVisionStatsResolved)
            {
                nightVisionStatsResolved = true;
                cachedNightVisionEfficiencyStat = DefDatabase<StatDef>.GetNamedSilentFail("NightVisionEfficiency");
                cachedNightVisionEfficiencyApparelStat = DefDatabase<StatDef>.GetNamedSilentFail("NightVisionEfficiency_Apparel");
            }
            float efficiency = 0f;
            if (cachedNightVisionEfficiencyStat != null)
                efficiency = Mathf.Max(efficiency, pawn.GetStatValue(cachedNightVisionEfficiencyStat));
            if (cachedNightVisionEfficiencyApparelStat != null)
                efficiency = Mathf.Max(efficiency, pawn.GetStatValue(cachedNightVisionEfficiencyApparelStat));
            return Mathf.Clamp01(efficiency);
        }

        private static float GetMinimumSightRadiusForDefeatSensitiveMap(Pawn pawn)
        {
            Map map = pawn?.MapHeld;
            if (map == null || map.IsPlayerHome || pawn.Faction == null || !pawn.Faction.IsPlayerSafe()) return 0f;
            return map.generatorDef != null && map.generatorDef.defeatRequiresCantReachUnfogged ? 8f : 0f;
        }

        public static void ClearCache()
        {
        }
    }
}
