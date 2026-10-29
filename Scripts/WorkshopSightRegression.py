#!/usr/bin/env python3
"""Exercise recovered sight/fog behavior using production methods (mcs and mono)."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1] / "Source/Rule56"


def block(source, marker):
    start = source.index(marker)
    opening = source.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


HARNESS = r'''
using System;
using System.Collections.Generic;
using CombatAI;
using RimWorld;
using Verse;
using UnityEngine;
namespace UnityEngine {
 public static class Mathf {
  public static int CeilToInt(float x) { return (int)Math.Ceiling(x); }
  public static int FloorToInt(float x) { return (int)Math.Floor(x); }
  public static int RoundToInt(float x) { return (int)Math.Round(x); }
  public static float Clamp(float x,float lo,float hi) { return Math.Min(Math.Max(x,lo),hi); }
  public static int Clamp(int x,int lo,int hi) { return Math.Min(Math.Max(x,lo),hi); }
  public static float Clamp01(float x) { return Clamp(x,0,1); }
  public static float Max(float x,float y) { return Math.Max(x,y); }
  public static int Max(int x,int y) { return Math.Max(x,y); }
  public static int Min(int x,int y) { return Math.Min(x,y); }
  public static float Lerp(float a,float b,float t) { return a+(b-a)*Clamp01(t); }
 }
}
namespace Verse {
 public static class GenTicks { public static int TicksGame=100; }
 public struct IntVec3 {
  public int x,z; public IntVec3(int x,int y,int z) { this.x=x;this.z=z; }
  public bool IsValid { get { return x>=0 && z>=0; } }
  public bool InBounds(Map m) { return x>=0 && z>=0 && x<m.Size.x && z<m.Size.z; }
  public int DistanceToSquared(IntVec3 o) { return (x-o.x)*(x-o.x)+(z-o.z)*(z-o.z); }
 }
 public class Thing {
  public Faction Faction=Faction.OfPlayer; public int thingIDNumber; public Map Map,MapHeld;
  public Dictionary<Type,object> Comps=new Dictionary<Type,object>();
  public Dictionary<StatDef,float> Stats=new Dictionary<StatDef,float>();
  public T GetComp_Fast<T>() where T:class { object c; return Comps.TryGetValue(typeof(T),out c)?(T)c:null; }
  public float GetStatValue(StatDef s) { float v;return Stats.TryGetValue(s,out v)?v:0; }
 }
 public class Pawn:Thing {
  public RaceProperties RaceProps=new RaceProperties(); public bool Dead,Downed; public float BodySize=1;
  public Verb Attack=new Verb(); public Skills skills=new Skills(); public Health health=new Health();
  public Needs needs=new Needs(); public Equipment equipment=new Equipment();
  public Verb TryGetAttackVerb() { return Attack; }
 }
 public class RaceProperties { public bool Animal,Insect,IsMechanoid; public object trainability=new object(); }
 public class Verb { public bool IsMeleeAttack; public float EffectiveRange=20; public bool Available() { return true; } }
 public class Skills { public SkillRecord GetSkill(object def) { return new SkillRecord(); } }
 public class Equipment { public ThingWithDef Primary; }
 public class ThingWithDef { public Def def=new Def(); }
 public class Def { public bool IsMeleeWeapon; }
 public class Health { public Capacities capacities=new Capacities(); }
 public class Capacities { public float Sight=1;public float GetLevel(object c) { return c==PawnCapacityDefOf.Sight?Sight:1; } }
 public class Needs { public Rest rest=new Rest(); }
 public class Rest { public float CurLevel=1; public int LastRestTick=-99999; }
 public class Map {
  public IntVec3 Size=new IntVec3(12,0,12); public bool IsPlayerHome;
  public MapGeneratorDef generatorDef=new MapGeneratorDef(); public GlowGrid glowGrid=new GlowGrid();
  public FogGrid fogGrid=new FogGrid(); internal MapComponent_FogGrid Fog;
  public T GetComp_Fast<T>() where T:class { return Fog as T; }
 }
 public class MapGeneratorDef { public bool defeatRequiresCantReachUnfogged; }
 public class GlowGrid { public float Value; public int Calls;public float GroundGlowAt(IntVec3 c) { Calls++; return Value; } }
 public class FogGrid { public int Calls; public bool IsFogged(int i) { Calls++; return true; } }
 public struct CellIndices { public int NumGridCells;public int CellToIndex(IntVec3 c) { return c.z*12+c.x; } }
 public class StatDef { }
 public static class DefDatabase<T> where T:class {
  public static readonly Dictionary<string,T> Values=new Dictionary<string,T>();
  public static T GetNamedSilentFail(string n) { T v; return Values.TryGetValue(n,out v)?v:null; }
 }
}
namespace RimWorld {
 public class Faction { public static readonly Faction OfPlayer=new Faction();public bool Safe=true;
  public bool IsPlayerSafe() { return Safe; }public bool HostileTo(Faction f) { return !Safe; } }
 public class Building_Turret:Thing { public Verb AttackVerb=new Verb(); }
 public class CompMannable { public bool MannedNow;public Pawn ManningPawn; }
 public class SkillRecord { public int Level=5; }
 public static class SkillDefOf { public static readonly object Melee=new object(),Shooting=new object(); }
 public static class TrainabilityDefOf { public static readonly object None=new object(); }
 public static class PawnCapacityDefOf { public static readonly object Sight=new object(),Consciousness=new object(),Hearing=new object(); }
}
namespace CombatAI.Compatibility {
 public static class NeedCompatExtras { public static float GetCurLevel(Rest rest) { return rest.CurLevel; } }
 public static class NeedCompat { public static int GetLastRestTick(Rest rest) { return rest==null?-99999:rest.LastRestTick; } }
}
namespace CombatAI.Comps { public class ThingComp_Sighter { public int SightRadius=15; } }
namespace CombatAI {
 static class Maths {
  public static int Max(int a,int b) {return Math.Max(a,b);}
  public static float Max(float a,float b) {return Math.Max(a,b);}
  public static float Max(float a,float b,float c) {return Max(a,Max(b,c));}
  public static float Min(float a,float b) {return Math.Min(a,b);}
  public static float Min(float a,float b,float c) {return Min(a,Min(b,c));}
  public static float Sqr(float a) {return a*a;}
 }
 static class Finder { public static readonly Settings Settings=new Settings(); }
 class Settings {
  public bool FogOfWar_Enabled=true,NewSightSystem_Enabled,FogOfWar_Allies=true,FogOfWar_Animals=true,FogOfWar_AnimalsSmartOnly;
  public bool FogOfWar_Turrets=true,FogOfWar_DisableOnPlayerMap,FogOfWar_IndoorVisible;
  public float FogOfWar_RangeMultiplier=2,NewSightSystem_BaseRadius=30;
 }
 static class TKVCache<T,K,V> {
  static readonly Dictionary<T,V> values=new Dictionary<T,V>();static readonly Dictionary<T,int> ticks=new Dictionary<T,int>();
  public static bool TryGet(T key,out V value,int expiry=-1) {
   return values.TryGetValue(key,out value) && GenTicks.TicksGame-ticks[key]<expiry;
  }
  public static void Put(T key,V value) { values[key]=value;ticks[key]=GenTicks.TicksGame; }
 }
 public class SightGrid {
  const int SIGHT_GLOW_BUCKET_COUNT=16;
  static readonly float[] sightGlowCoeffLut=BuildSightGlowCoeffLut();
  SIGHT_RADIUS
  LUT_METHOD
  COEFFICIENT_METHOD
  public static float Glow(byte source,byte target,float nightVision) { return GetSightGlowCoefficient(source,target,nightVision); }
 }
 enum CellFogState:byte { VanillaExplored,VanillaUnexplored,CAIFogged }
 class MapComponent_FogGrid {
  const int SIGHT_GLOW_BLOCK_SIZE=6,SIGHT_GLOW_BUCKET_COUNT=16,SIGHT_GLOW_REFRESH_INTERVAL=15;
  const int SHOT_REVEAL_COOLDOWN_TICKS=20,SHOT_REVEAL_DURATION_TICKS=90;
  readonly int mapSizeX=12,mapSizeZ=12,sightGlowBlocksX=2,sightGlowBlocksZ=2;readonly bool supportsMap=true;
  byte[] sightGlowBuckets;int sightGlowLastRefreshTick=-9999,ticksGame;
  int[] shotRevealLastTick=new int[144]; readonly object _lockerSpots=new object();
  readonly List<ITempSpot> spotsQueued=new List<ITempSpot>();
  public Map map=new Map();public CellIndices cellIndices=new CellIndices{NumGridCells=144};
  public GlowGrid glow; public CellFogState[] fogState=new CellFogState[144];
  bool _cachedIsPlayerHome;bool[] _indoorRoomCache;
  public MapComponent_FogGrid() { for(int i=0;i<shotRevealLastTick.Length;i++)shotRevealLastTick[i]=-9999; }
  struct ITempSpot { public IntVec3 center;public float radius;public int duration; }
  FOG_METHODS
  public void Refresh() { ticksGame=GenTicks.TicksGame;RefreshSightGlowCacheIfNeeded(); }
  public byte[] Snapshot { get { return sightGlowBuckets; } }
  internal byte[] SightGlowBuckets { get { return sightGlowBuckets; } }
  public int Reveals { get { return spotsQueued.Count; } }
  public float LastRadius { get { return spotsQueued[spotsQueued.Count-1].radius; } }
  public int LastDuration { get { return spotsQueued[spotsQueued.Count-1].duration; } }
 }
}
class Program {
 static void Check(bool ok,string message) {if(!ok)throw new Exception(message);}
 static void Near(float actual,float expected,string message) {Check(Math.Abs(actual-expected)<.001f,message+": "+actual+" != "+expected);}
 static void Main() {
  // Stat defs load before any map exists in game; night vision lookups resolve them once.
  var night=new StatDef();var apparel=new StatDef();
  DefDatabase<StatDef>.Values["NightVisionEfficiency"]=night;
  DefDatabase<StatDef>.Values["NightVisionEfficiency_Apparel"]=apparel;
  var settings=Finder.Settings;var pawn=new Pawn();
  var legacy=SightUtility.GetSightRadius(pawn);
  Check(legacy.sight==20 && legacy.scan==36 && legacy.fog==24,"legacy weapon range and separate fog multiplier");
  Near(SightUtility.GetSightRadius_Fast(pawn),legacy.sight,"legacy fast sight");
  settings.NewSightSystem_Enabled=true;
  var unified=SightUtility.GetSightRadius(pawn);
  Check(unified.sight==30 && unified.scan==30 && unified.fog==30,"unified sight and fog independent of weapon range");
  Near(SightUtility.GetSightRadius_Fast(pawn),30,"fast cache invalidates on enabling");
  settings.NewSightSystem_BaseRadius=50;
  GenTicks.TicksGame+=45;
  Near(SightUtility.GetSightRadius_Fast(pawn),50,"new sight settings refresh promptly");
  settings.NewSightSystem_Enabled=false;
  Near(SightUtility.GetSightRadius_Fast(pawn),legacy.sight,"fast cache invalidates on disabling");
  settings.NewSightSystem_Enabled=true;settings.FogOfWar_Enabled=false;
  Near(SightUtility.GetSightRadius(pawn).sight,legacy.sight,"unified sight requires fog");
  settings.FogOfWar_Enabled=true;settings.NewSightSystem_BaseRadius=30;
  var turret=new Building_Turret();var turretSight=SightUtility.GetSightRadius(turret);
  Check(turretSight.sight==15 && turretSight.scan==15 && turretSight.fog==15,"turret factor applies to all ranges");
  pawn.Downed=true;var downed=SightUtility.GetSightRadius(pawn);
  Check(downed.sight==2 && downed.scan==2 && downed.fog==2,"downed pawn retains minimum unified sight");
  pawn.MapHeld=new Map();pawn.MapHeld.generatorDef.defeatRequiresCantReachUnfogged=true;
  Check(SightUtility.GetSightRadius(pawn).sight==3,"encounter minimum applied before downed reduction");
  pawn.Downed=false;pawn.health.capacities.Sight=.1f;
  Near(SightUtility.GetSightRadius(pawn).sight,8,"encounter map minimum prevents defeat lockout");
  pawn.MapHeld.IsPlayerHome=true;
  Check(SightUtility.GetSightRadius(pawn).sight<8,"encounter minimum does not apply at home");
  pawn.Stats[night]=.4f;pawn.Stats[apparel]=.8f;
  Near(SightUtility.GetNightVisionLutReduction(pawn),.8f,"strongest available night vision stat");
  turret.Comps[typeof(CompMannable)]=new CompMannable{ManningPawn=pawn};
  Near(SightUtility.GetNightVisionLutReduction(turret),.8f,"manning pawn night vision");
  Near(SightGrid.Glow(0,0,0),.5f,"darkness halves radius");
  Near(SightGrid.Glow(15,0,0),.7f,"observer illumination contributes");
  Near(SightGrid.Glow(0,15,0),.9f,"illuminated targets easier to see");
  Near(SightGrid.Glow(0,0,.5f),.75f,"partial night vision reduces darkness penalty");
  Near(SightGrid.Glow(0,0,1),1,"full night vision removes darkness penalty");
  var fog=new MapComponent_FogGrid();fog.map.glowGrid.Value=0;fog.Refresh();
  var old=fog.Snapshot;Check(old[0]==0,"initial darkness bucket");
  fog.map.glowGrid.Value=1;GenTicks.TicksGame+=14;fog.Refresh();
  Check(fog.Snapshot==old,"lighting refresh bounded while paused");
  GenTicks.TicksGame++;fog.Refresh();
  Check(fog.Snapshot!=old && old[0]==0 && fog.Snapshot[0]==15,"published lighting snapshots remain immutable");
  settings.FogOfWar_RangeMultiplier=8;
  var cell=new IntVec3(1,0,1);fog.RevealShotSpot(cell,0);
  Near(fog.LastRadius,1.4f,"shot reveal bypasses fog range multiplier");
  Check(fog.LastDuration==90 && fog.Reveals==1,"fixed brief shot reveal");
  GenTicks.TicksGame+=19;fog.RevealShotSpot(cell,6);Check(fog.Reveals==1,"rapid repeated shot throttled");
  fog.RevealShotSpot(new IntVec3(2,0,1),6);Near(fog.LastRadius,3,"cooldown independent per cell");
  GenTicks.TicksGame++;fog.RevealShotSpot(cell,6);Check(fog.Reveals==3,"shot allowed at cooldown boundary");
  fog.RevealShotSpot(new IntVec3(-1,0,0),1);fog.RevealShotSpot(new IntVec3(12,0,0),1);
  Check(fog.Reveals==3,"invalid shot cells ignored");
  fog.RevealSpot(cell,2,120);Near(fog.LastRadius,16,"general reveals retain multiplier");
  Check(!fog.IsFogged(-1) && !fog.IsFogged(144),"invalid fog indices ignored");
  settings.FogOfWar_DisableOnPlayerMap=true;Check(!fog.IsFogged(new IntVec3(12,0,0)),"invalid fog coordinates ignored");
  settings.FogOfWar_RangeMultiplier=2;settings.NewSightSystem_Enabled=false;
  var legacyPawn=new Pawn();legacyPawn.Downed=true;var legacyDowned=SightUtility.GetSightRadius(legacyPawn);
  Check(legacyDowned.sight==12 && legacyDowned.scan==20 && legacyDowned.fog==6,"legacy downed pawn keeps weapon sight and only fog shrinks");
  legacyPawn.Downed=false;legacyPawn.needs.rest.LastRestTick=GenTicks.TicksGame-10;
  Check(SightUtility.GetSightRadius(legacyPawn).fog==6,"legacy fog shrinks for a pawn that just slept");
  settings.NewSightSystem_Enabled=true;
  var unifiedRested=SightUtility.GetSightRadius(legacyPawn);
  Check(unifiedRested.sight==30 && unifiedRested.fog==30 && unifiedRested.nightVisionReduction==0,"unified sight ignores recent sleep");
  Near(SightUtility.GetSightRadius(pawn).nightVisionReduction,.8f,"night vision cached with unified sight radius");
  var litFog=new MapComponent_FogGrid();litFog.map.glowGrid.Value=0;GenTicks.TicksGame+=15;litFog.Refresh();
  var seer=new Pawn{Map=new Map{Fog=litFog}};var origin=new IntVec3(0,0,0);
  Near(SightUtility.GetLitSightRadius(seer,origin,origin),15,"darkness halves the lit sight radius");
  Check(SightUtility.CanSeeCell(seer,origin,new IntVec3(14,0,0)) && !SightUtility.CanSeeCell(seer,origin,new IntVec3(15,0,0)),"own sight uses the strict lit radius");
  var nightSeer=new Pawn{Map=seer.Map};nightSeer.Stats[night]=1;
  Check(SightUtility.CanSeeCell(nightSeer,origin,new IntVec3(29,0,0)),"night vision restores own sight in darkness");
  Near(SightUtility.GetLitSightRadius(new Pawn(),origin,origin),30,"no fog component leaves sight unscaled");
  Console.WriteLine("PASS: legacy/unified ranges, mode cache invalidation, downed/encounter sight, legacy downed/sleep fog, night vision caching, lit own sight, lighting snapshots, shot cooldown and fog guards");
 }
}
'''


def main():
    utility = (ROOT / "SightUtility.cs").read_text(encoding="utf-8-sig")
    grid = (ROOT / "SightGrid.cs").read_text(encoding="utf-8-sig")
    fog = (ROOT / "MapComponent_FogGrid.cs").read_text()
    methods = [
        "public byte GetSightGlowBucket(IntVec3 cell)",
        "internal byte GetSightGlowBucket(IntVec3 cell, byte[] buckets)",
        "private void RefreshSightGlowCacheIfNeeded()",
        "public bool IsFogged(IntVec3 cell)",
        "public bool IsFogged(int index)",
        "public void RevealSpot(",
        "public void RevealShotSpot(",
    ]
    harness = HARNESS.replace("SIGHT_RADIUS", block(grid, "public struct ISightRadius"))
    harness = harness.replace("LUT_METHOD", block(grid, "private static float[] BuildSightGlowCoeffLut"))
    harness = harness.replace("COEFFICIENT_METHOD", block(grid, "internal static float GetSightGlowCoefficient"))
    harness = harness.replace("FOG_METHODS", "\n".join(block(fog, marker) for marker in methods))
    with tempfile.TemporaryDirectory(prefix="cai-workshop-sight-") as tmp:
        directory = Path(tmp)
        (directory / "SightUtility.cs").write_text(utility)
        (directory / "Harness.cs").write_text(harness)
        exe = directory / "Regression.exe"
        subprocess.run(["mcs", "-warn:0", "-out:" + str(exe), str(directory / "Harness.cs"), str(directory / "SightUtility.cs")], check=True)
        subprocess.run(["mono", str(exe)], check=True)


if __name__ == "__main__":
    main()
