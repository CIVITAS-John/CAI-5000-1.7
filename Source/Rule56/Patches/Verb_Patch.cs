using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using CombatAI.Comps;
using HarmonyLib;
using RimWorld;
using Verse;
namespace CombatAI.Patches
{
    public class Verb_Patch
    {
	    private static Verb callerVerb;

        [HarmonyPatch]
        private static class Verb_TryStartCast_Patch
        {
	        public static IEnumerable<MethodBase> TargetMethods()
            {
                HashSet<MethodBase> methods = new HashSet<MethodBase>();
                foreach (Type t in typeof(Verb).AllSubclasses())
                {
                    foreach (MethodInfo method in t.GetMethods(AccessTools.all))
                    {
                        if (method.DeclaringType != null && method.DeclaringType.FullName != null && method.DeclaringType.FullName.StartsWith("CombatExtended"))
                        {
                            continue;
                        }
                        if (method != null && !methods.Contains(method) && !method.IsStatic && method.ReturnType == typeof(bool) && (method.Name.Contains("TryStartCastOn") || method.Name.Contains("TryCastShot")) && !method.IsAbstract && method.HasMethodBody() && method.DeclaringType == t)
                        {
                            Log.Message($"ISMA: Patched verb type {t.FullName}:{method.Name}");
                            methods.Add(method);
                        }
                    }
                }
                foreach (MethodInfo method in typeof(Verb).GetMethods(AccessTools.all))
                {
                    if (method != null && !methods.Contains(method) && !method.IsStatic && method.ReturnType == typeof(bool) && (method.Name.Contains("TryStartCastOn") || method.Name.Contains("TryCastShot")) && !method.IsAbstract && method.HasMethodBody() && method.DeclaringType == typeof(Verb))
                    {
                        Log.Message($"ISMA: Patched verb type {typeof(Verb).FullName}:{method.Name}");
                        methods.Add(method);
                    }
                }
                return methods;
            }

            public static void Prefix(Verb __instance, out bool __state)
            {
                if (__state = __instance != callerVerb)
                {
                    callerVerb = __instance;
                }
            }

            public static void Postfix(Verb __instance, bool __result, bool __state)
            {
                if (__state && __result && __instance.caster != null)
                {
                    if (__instance.CurrentTarget is { IsValid: true, Thing: Pawn targetPawn } && (__instance.caster?.HostileTo(targetPawn) ?? false))
                    {
                        ThingComp_CombatAI comp = targetPawn.AI();
                        if (comp != null)
                        {
                            comp.Notify_BeingTargeted(__instance.caster, __instance);
                        }
                    }
                }
            }
        }
        
        /// <summary>
        /// Shared sight gate. Vanilla target finders, cast position finders and TryStartCastOn all ask
        /// CanHitTargetFrom, so units move closer or pick another target instead of retrying a blocked cast.
        /// </summary>
        [HarmonyPatch(typeof(Verb), nameof(Verb.CanHitTargetFrom))]
        internal static class Verb_CanHitTargetFrom_Patch
        {
            public static void Postfix(Verb __instance, IntVec3 root, LocalTargetInfo targ, ref bool __result)
            {
                if (!__result || !targ.IsValid || __instance is Verb_CastAbility)
                {
                    return;
                }
                IntVec3 cell = targ.HasThing && targ.Thing.Spawned ? targ.Thing.Position : targ.Cell;
                if (IsOutsideSharedSight(__instance, root, cell))
                {
                    __result = false;
                }
            }
        }

        [HarmonyPatch]
        private static class Verb_TryCastNextBurstShot_Patch
        {
	        private static MethodBase mFleckMakerStatic = AccessTools.Method(typeof(FleckMaker), nameof(FleckMaker.Static), new []{typeof(IntVec3), typeof(Map), typeof(FleckDef), typeof(float)});
	        
            public static IEnumerable<MethodBase> TargetMethods()
            {
                HashSet<MethodBase> methods = new HashSet<MethodBase>();
                foreach (Type t in typeof(Verb).AllSubclasses())
                {
                    foreach (MethodInfo method in t.GetMethods(AccessTools.all))
                    {
                        // Transpiler rewrites IL, so keep skipping CE verbs to avoid breaking CE burst-shot internals.
                        // CE targeting and shared sight checks are handled separately in Mod_CE.
                        if (method.DeclaringType != null && method.DeclaringType.FullName != null && method.DeclaringType.FullName.StartsWith("CombatExtended"))
                        {
                            continue;
                        }
                        if (method != null && !methods.Contains(method) && !method.IsStatic && method.Name.Contains("TryCastNextBurstShot") && !method.IsAbstract && method.HasMethodBody() && method.DeclaringType == t)
                        {
                            Log.Message($"ISMA: TryCastNextBurstShot Patched verb type {t.FullName}:{method.Name}");
                            methods.Add(method);
                        }
                    }
                }
                foreach (MethodInfo method in typeof(Verb).GetMethods(AccessTools.all))
                {
                    if (method != null && !methods.Contains(method) && !method.IsStatic && method.Name.Contains("TryCastNextBurstShot") && !method.IsAbstract && method.HasMethodBody() && method.DeclaringType == typeof(Verb))
                    {
                        Log.Message($"ISMA: TryCastNextBurstShot Patched verb type {typeof(Verb).FullName}:{method.Name}");
                        methods.Add(method);
                    }
                }
                return methods;
            }

            public static IEnumerable<CodeInstruction> Transpiler(IEnumerable<CodeInstruction> instructions)
            {
	            List<CodeInstruction> codes    = instructions.ToList();
	            bool                  finished = false;
	            for (int i = 0; i < codes.Count; i++)
	            {
		            yield return codes[i];
		            if (!finished)
		            {
			            if (codes[i].opcode == OpCodes.Call && codes[i].OperandIs(mFleckMakerStatic))
			            {
				            finished = true;
				            yield return new CodeInstruction(OpCodes.Ldarg_0);
				            yield return new CodeInstruction(OpCodes.Call, AccessTools.Method(typeof(Verb_TryCastNextBurstShot_Patch), nameof(Verb_TryCastNextBurstShot_Patch.OnShot)));
			            }
		            }
	            }
            }
            

            public static void OnShot(Verb verb)
            {
	            if (verb.verbProps.muzzleFlashScale > 0)
	            {
		            Map map = verb.caster.Map;
		            if (map != null)
		            {
			            MapComponent_FogGrid grid = map.GetComp_Fast<MapComponent_FogGrid>();
			            if (grid != null)
			            {
				            if (SightUtility.NewSightSystemActive)
				            {
					            grid.RevealShotSpot(verb.caster.Position, verb.verbProps.muzzleFlashScale);
				            }
				            else
				            {
					            grid.RevealSpot(verb.caster.Position, Maths.Min(verb.verbProps.muzzleFlashScale, 8f), Rand.Range(120, 360));
				            }
			            }
		            }
	            }
            }
        }

        /// <summary>Gate for CE verbs, whose TryStartCastOn is patched separately in Mod_CE.</summary>
        internal static bool ShouldBlockBySharedSightForVerb(Verb verb, object[] args)
        {
            return verb?.caster != null && TryGetTargetCell(verb, args, out IntVec3 cell) && IsOutsideSharedSight(verb, verb.caster.Position, cell);
        }

        /// <summary>
        ///     Whether a ranged verb fired from <paramref name="root" /> would target a cell that neither the caster's team
        ///     currently sees nor the caster could see itself from there.
        /// </summary>
        internal static bool IsOutsideSharedSight(Verb verb, IntVec3 root, IntVec3 cell)
        {
            if (!SightUtility.NewSightSystemActive)
            {
                return false;
            }
            if (verb?.caster == null || verb.verbProps == null || verb.verbProps.IsMeleeAttack)
            {
                return false;
            }
            Map map = verb.caster.Map;
            if (!SightUtility.SupportsMap(map) || !root.IsValid || !cell.IsValid || !cell.InBounds(map))
            {
                return false;
            }
            SightTracker tracker = map.GetComp_Fast<SightTracker>();
            if (tracker == null || SightUtility.CanSeeCell(verb.caster, root, cell))
            {
                return false;
            }
            // Pawns keep the reader SightTracker assigned at registration; other casters share their faction's.
            SightTracker.SightReader reader = null;
            if (verb.caster is Pawn pawn)
            {
                reader = pawn.AI()?.sightReader;
            }
            else
            {
                tracker.TryGetReader(verb.caster.Faction, out reader);
            }
            return reader != null && reader.GetDynamicFriendlyFlags(cell) == 0;
        }

        private static bool TryGetTargetCell(Verb verb, object[] args, out IntVec3 cell)
        {
            if (args != null)
            {
                foreach (object arg in args)
                {
                    if (TryConvertToCell(arg, out cell))
                    {
                        return true;
                    }
                }
            }
            if (verb != null && TryConvertToCell(verb.CurrentTarget, out cell))
            {
                return true;
            }
            cell = IntVec3.Invalid;
            return false;
        }

        private static bool TryConvertToCell(object value, out IntVec3 cell)
        {
            if (value is IntVec3 position)
            {
                cell = position;
                return true;
            }
            if (value is Thing thing && thing.Spawned)
            {
                cell = thing.Position;
                return true;
            }
            if (value is LocalTargetInfo localTarget && localTarget.IsValid)
            {
                cell = localTarget.HasThing && localTarget.Thing != null && localTarget.Thing.Spawned ? localTarget.Thing.Position : localTarget.Cell;
                return cell.IsValid;
            }
            if (value is TargetInfo target && target.IsValid)
            {
                cell = target.Cell;
                return cell.IsValid;
            }
            cell = IntVec3.Invalid;
            return false;
        }
    }
}
