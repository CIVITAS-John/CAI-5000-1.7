using System;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.CompilerServices;
using RimWorld;
using Verse;

namespace CombatAI.Comps
{
    // Main-thread reaction queries. Weak keys let unloaded maps and their snapshots be collected.
    internal static class AreaThreats
    {
        private sealed class ProjectileSnapshot
        {
            internal int tick = -1;
            internal readonly List<Projectile> dangerous = new List<Projectile>();
        }

        private static readonly ConditionalWeakTable<Map, ProjectileSnapshot> snapshots = new ConditionalWeakTable<Map, ProjectileSnapshot>();
        // RimWorld keeps the landing-cell getter private; bind it once for reaction queries.
        private static readonly Func<Projectile, IntVec3> getDestinationCell = (Func<Projectile, IntVec3>)Delegate.CreateDelegate(
            typeof(Func<Projectile, IntVec3>), typeof(Projectile).GetProperty("DestinationCell", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic).GetGetMethod(true));

        internal static bool TryFindNearbyFire(Map map, IntVec3 position, out IntVec3 fireCell)
        {
            fireCell = IntVec3.Invalid;
            int cellCount = GenRadial.NumCellsInRadius(3f);
            for (int i = 0; i < cellCount; i++)
            {
                IntVec3 cell = position + GenRadial.RadialPattern[i];
                if (!cell.InBounds(map)) continue;
                List<Thing> things = map.thingGrid.ThingsListAt(cell);
                for (int j = 0; j < things.Count; j++)
                {
                    if (!(things[j] is Fire)) continue;
                    // A single lister sweep preserves first-threat order without repeating a
                    // map-wide lookup for every nearby fire. Pawns far from fire avoid it entirely.
                    List<Thing> fires = map.listerThings.ThingsInGroup(ThingRequestGroup.Fire);
                    for (int k = 0; k < fires.Count; k++)
                    {
                        if (fires[k].Position.DistanceToSquared(position) <= 9f)
                        {
                            fireCell = fires[k].Position;
                            return true;
                        }
                    }
                    return false;
                }
            }
            return false;
        }

        internal static bool TryFindIncomingProjectile(Pawn pawn, out IntVec3 landingCell, out float dangerRadius)
        {
            landingCell = IntVec3.Invalid;
            dangerRadius = 0f;
            Map map = pawn.Map;
            ProjectileSnapshot snapshot = snapshots.GetValue(map, _ => new ProjectileSnapshot());
            int tick = GenTicks.TicksGame;
            if (snapshot.tick != tick)
            {
                snapshot.dangerous.Clear();
                List<Thing> projectiles = map.listerThings.ThingsInGroup(ThingRequestGroup.Projectile);
                for (int i = 0; i < projectiles.Count; i++)
                {
                    if (!(projectiles[i] is Projectile projectile)) continue;
                    var properties = projectile.def?.projectile;
                    if (properties != null && (properties.flyOverhead || properties.explosionRadius > 0f))
                    {
                        snapshot.dangerous.Add(projectile);
                    }
                }
                snapshot.tick = tick;
            }

            // Membership is shared for this tick: a new launch is discovered by the next tick.
            // Positions, factions and target validity stay live, including moving Thing targets.
            for (int i = 0; i < snapshot.dangerous.Count; i++)
            {
                Projectile projectile = snapshot.dangerous[i];
                if (!projectile.Spawned || projectile.Map != map) continue;
                if (projectile.Launcher?.Faction != null && !projectile.Launcher.Faction.HostileTo(pawn.Faction)) continue;
                LocalTargetInfo target = projectile.intendedTarget.IsValid ? projectile.intendedTarget : projectile.usedTarget;
                // Losing the target does not cancel a launched explosive's flight or detonation.
                IntVec3 cell = !target.IsValid || target.HasThing && (!target.Thing.Spawned || target.Thing.Map != map)
                    ? getDestinationCell(projectile)
                    : target.Cell;
                if (!cell.InBounds(map)) continue;
                float radius = projectile.def.projectile.explosionRadius + 4f;
                if (cell.DistanceTo(pawn.Position) < radius)
                {
                    landingCell = cell;
                    dangerRadius = radius;
                    return true;
                }
            }
            return false;
        }
    }
}
