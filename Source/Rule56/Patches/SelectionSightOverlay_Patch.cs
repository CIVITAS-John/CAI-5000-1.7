using HarmonyLib;
using RimWorld;
using UnityEngine;
using Verse;

namespace CombatAI.Patches
{
    public static class SelectionSightOverlay_Patch
    {
        private static readonly Color SightRingColor = new Color(0.2f, 0.95f, 0.2f, 1f);
        private static int hoveredWeaponOwnerThingId = -1;

        [HarmonyPatch(typeof(GizmoGridDrawer), nameof(GizmoGridDrawer.DrawGizmoGridFor))]
        private static class GizmoGridDrawer_DrawGizmoGridFor_Patch
        {
            public static void Postfix(Gizmo mouseoverGizmo)
            {
                hoveredWeaponOwnerThingId = -1;
                if (!(mouseoverGizmo is Command_VerbTarget command) || command.verb?.caster == null)
                {
                    return;
                }
                Thing caster = command.verb.caster;
                if (caster is Pawn pawn)
                {
                    if (pawn.TryGetAttackVerb() == null)
                    {
                        return;
                    }
                }
                else if (!(caster is Building_TurretGun))
                {
                    return;
                }
                hoveredWeaponOwnerThingId = caster.thingIDNumber;
            }
        }

        [HarmonyPatch(typeof(Pawn), nameof(Pawn.DrawExtraSelectionOverlays))]
        private static class Pawn_DrawExtraSelectionOverlays_Patch
        {
            public static void Postfix(Pawn __instance)
            {
                DrawSightRing(__instance);
            }
        }

        [HarmonyPatch(typeof(Building_TurretGun), nameof(Building_TurretGun.DrawExtraSelectionOverlays))]
        private static class Building_TurretGun_DrawExtraSelectionOverlays_Patch
        {
            public static void Postfix(Building_TurretGun __instance)
            {
                DrawSightRing(__instance);
            }
        }

        private static void DrawSightRing(Thing thing)
        {
            if (!Finder.Settings.FogOfWar_Enabled || !Finder.Settings.NewSightSystem_Enabled || !Finder.Settings.NewSightSystem_ShowSightRing)
            {
                return;
            }
            if (thing == null || !thing.Spawned || !SightUtility.SupportsMap(thing.Map) || thing.thingIDNumber != hoveredWeaponOwnerThingId)
            {
                return;
            }
            float radius = SightUtility.GetSightRadius(thing).sight;
            if (radius > 0.1f)
            {
                GenDraw.DrawRadiusRing(thing.Position, radius, SightRingColor);
            }
        }
    }
}
