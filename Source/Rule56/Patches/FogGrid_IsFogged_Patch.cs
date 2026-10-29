using System;
using System.Linq.Expressions;
using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;
using RimWorld;
using Verse;

namespace CombatAI.Patches
{
    [HarmonyPatch]
    public static class FogGrid_IsFogged_Patch
    {
        internal static FieldInfo mapField;

        // Compiled field accessor — replaces reflection on the hot path.
        // Expression.Lambda.Compile() produces IL equivalent to a direct field read.
        private static Func<FogGrid, Map> _getMap;

        [ThreadStatic]
        private static int ignoreVanillaUnexploredOnMapEdgeCounter;

        // When > 0, ALL IsFogged calls return false — overrides both vanilla fog and CAI fog.
        // Use this for enemy AI operations (siege blueprint placement) that must succeed even in
        // areas the player has never explored.
        [ThreadStatic]
        private static int suppressAllFogCounter;

        public static bool IgnoreVanillaUnexploredOnMapEdge => ignoreVanillaUnexploredOnMapEdgeCounter > 0;

        public static bool SuppressAllFog => suppressAllFogCounter > 0;

        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        private static Map GetMap(FogGrid fogGrid)
        {
            return _getMap != null ? _getMap(fogGrid) : mapField?.GetValue(fogGrid) as Map;
        }

        public static void PushIgnoreVanillaUnexploredOnMapEdge()
        {
            ignoreVanillaUnexploredOnMapEdgeCounter++;
        }

        public static void PopIgnoreVanillaUnexploredOnMapEdge()
        {
            if (ignoreVanillaUnexploredOnMapEdgeCounter > 0)
            {
                ignoreVanillaUnexploredOnMapEdgeCounter--;
            }
        }

        public static void PushSuppressAllFog()
        {
            suppressAllFogCounter++;
        }

        public static void PopSuppressAllFog()
        {
            if (suppressAllFogCounter > 0)
            {
                suppressAllFogCounter--;
            }
        }

        static FogGrid_IsFogged_Patch()
        {
            var fogGridType = typeof(FogGrid);
            mapField = fogGridType.GetField("map", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
            if (mapField != null)
            {
                try
                {
                    var param = Expression.Parameter(typeof(FogGrid), "fg");
                    _getMap   = Expression.Lambda<Func<FogGrid, Map>>(Expression.Field(param, mapField), param).Compile();
                }
                catch { /* fall back to reflection */ }
            }
        }

        [HarmonyPostfix]
        [HarmonyPatch(typeof(FogGrid), nameof(FogGrid.IsFogged), new Type[] { typeof(int) })]
        public static void Postfix_Int(FogGrid __instance, int index, ref bool __result)
        {
            try
            {
                // Full suppress: used by siege blueprint placement so enemies can build in
                // areas the player has never explored (both vanilla fog and CAI fog ignored).
                if (SuppressAllFog) { __result = false; return; }
                if (!Finder.Settings.FogOfWar_Enabled) return;
                Map map = GetMap(__instance);
                if (map == null) return;
                if (IgnoreVanillaUnexploredOnMapEdge)
                {
                    IntVec3 edgeCell;
                    try { edgeCell = map.cellIndices.IndexToCell(index); }
                    catch { edgeCell = IntVec3.Invalid; }
                    if (edgeCell.IsValid && edgeCell.OnEdge(map))
                    {
                        __result = false;
                    }
                }
            }
            catch { /* swallow to avoid breaking vanilla calls */ }
        }

        [HarmonyPostfix]
        [HarmonyPatch(typeof(FogGrid), nameof(FogGrid.IsFogged), new Type[] { typeof(IntVec3) })]
        public static void Postfix_Cell(FogGrid __instance, IntVec3 c, ref bool __result)
        {
            try
            {
                if (SuppressAllFog) { __result = false; return; }
                if (!Finder.Settings.FogOfWar_Enabled) return;
                Map map = GetMap(__instance);
                if (map == null) return;
                if (IgnoreVanillaUnexploredOnMapEdge && c.OnEdge(map))
                {
                    __result = false;
                }
            }
            catch { }
        }
    }
}
