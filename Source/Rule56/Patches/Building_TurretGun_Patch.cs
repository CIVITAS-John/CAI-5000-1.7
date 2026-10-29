using HarmonyLib;
using RimWorld;
using Verse;
using Verse.AI.Group;
namespace CombatAI.Patches
{
    public static class Building_TurretGun_Patch
    {
        [HarmonyPatch(typeof(Building_TurretGun), nameof(Building_TurretGun.SpawnSetup))]
        private static class Building_TurretGun_SpawnSetup_Patch
        {
            public static void Postfix(Building_TurretGun __instance)
            {
                __instance.Map.GetComp_Fast<TurretTracker>().Register(__instance);
            }
        }

        [HarmonyPatch(typeof(Building_TurretGun), nameof(Building_TurretGun.DeSpawn))]
        private static class Building_TurretGun_DeSpawn_Patch
        {
            public static void Prefix(Building_TurretGun __instance)
            {
                __instance.Map.GetComp_Fast<TurretTracker>().DeRegister(__instance);
            }
        }

        [HarmonyPatch(typeof(Building_TurretGun), nameof(Building_TurretGun.TryStartShootSomething))]
        private static class Building_TurretGun_TryStartShootSomething_Patch
        {
            public static bool Prefix(Building_TurretGun __instance)
            {
                if (__instance.Map.IsPlayerHome || __instance.Faction == null || __instance.Faction.IsPlayerSafe() || !__instance.IsMannable)
                {
                    return true;
                }
                Pawn operatorPawn = __instance.GetComp_Fast<CompMannable>()?.ManningPawn;
                return !(operatorPawn?.GetLord()?.CurLordToil is LordToil_DefendBase);
            }
        }
    }
}
