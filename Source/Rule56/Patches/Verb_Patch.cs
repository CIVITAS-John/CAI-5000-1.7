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

            public static bool Prefix(Verb __instance, ref bool __result, out bool __state, object[] __args)
            {
                if (__state = __instance != callerVerb)
                {
                    callerVerb = __instance;
                }
                if (ShouldBlockBySharedSightForVerb(__instance, __args))
                {
                    __result = false;
                    return false;
                }
                return true;
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
				            grid.RevealShotSpot(verb.caster.Position, verb.verbProps.muzzleFlashScale);
			            }
		            }
	            }
            }
        }

        internal static bool ShouldBlockBySharedSightForVerb(Verb verb, object[] args)
        {
            Settings settings = Finder.Settings;
            if (settings == null || !settings.FogOfWar_Enabled || !settings.NewSightSystem_Enabled)
            {
                return false;
            }
            if (verb?.caster == null || verb.verbProps == null || verb.verbProps.IsMeleeAttack)
            {
                return false;
            }
            Map map = verb.caster.Map;
            if (!SightUtility.SupportsMap(map) || !TryGetTargetCell(verb, args, out IntVec3 cell) || !cell.IsValid || !cell.InBounds(map))
            {
                return false;
            }
            SightTracker tracker = map.GetComp_Fast<SightTracker>();
            if (tracker == null)
            {
                return false;
            }
            if (verb.caster is Pawn pawn)
            {
                return pawn.TryGetSightReader(out SightTracker.SightReader reader) && reader != null && reader.GetDynamicFriendlyFlags(cell) == 0;
            }
            Faction faction = verb.caster.Faction;
            return faction != null && tracker.TryGetReader(faction, out SightTracker.SightReader factionReader) && factionReader != null && factionReader.GetDynamicFriendlyFlags(cell) == 0;
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
