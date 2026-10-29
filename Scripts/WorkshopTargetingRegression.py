#!/usr/bin/env python3
"""Exercise production shared-sight hit checks, cast gates and defend-base turret restrictions."""
from pathlib import Path
import os
import subprocess
import tempfile

SOURCE = Path(__file__).resolve().parents[1] / 'Source/Rule56'


def block(source, marker):
    start = source.index(marker)
    opening = source.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


harness = r'''
using System;
using CombatAI;
using CombatAI.Patches;
using RimWorld;
using Verse;
using Verse.AI.Group;
namespace RimWorld {
 public class Faction { public bool PlayerSafe; }
 public class Building_TurretGun : Thing {
  public bool IsMannable=true; public CompMannable Mannable;
 }
 public class CompMannable { public Pawn ManningPawn; }
 public class Verb_CastAbility : Verb {}
}
namespace Verse.AI.Group {
 public class Lord { public object CurLordToil; }
 public class LordToil_DefendBase {}
}
namespace Verse {
 public struct IntVec3 {
  public int x,z; public IntVec3(int x,int z=0) { this.x=x; this.z=z; }
  public static IntVec3 Invalid => new IntVec3(-1,-1);
  public bool IsValid => x>=0 && z>=0;
  public bool InBounds(Map map) => IsValid && x<100 && z<100;
 }
 public class Map { public bool Square=true,IsPlayerHome; public SightTracker Tracker=new SightTracker(); }
 public class Thing { public Map Map; public Faction Faction; public bool Spawned=true; public IntVec3 Position; }
 public class Pawn : Thing { public Lord Lord; public ThingComp_CombatAI Comp; }
 public struct LocalTargetInfo {
  public bool IsValid; public Thing Thing; public IntVec3 Cell; public bool HasThing => Thing!=null;
 }
 public struct TargetInfo { public bool IsValid; public IntVec3 Cell; }
 public class VerbProperties { public bool IsMeleeAttack; }
 public class Verb { public Thing caster; public VerbProperties verbProps=new VerbProperties(); public LocalTargetInfo CurrentTarget; }
 public static class Extensions {
  public static T GetComp_Fast<T>(this Map map) where T:class => map.Tracker as T;
  public static T GetComp_Fast<T>(this Building_TurretGun turret) where T:class => turret.Mannable as T;
  public static ThingComp_CombatAI AI(this Pawn pawn) => pawn.Comp;
  public static bool IsPlayerSafe(this Faction faction) => faction.PlayerSafe;
  public static Lord GetLord(this Pawn pawn) => pawn.Lord;
 }
}
namespace CombatAI {
 public class Settings { public bool FogOfWar_Enabled=true,NewSightSystem_Enabled=true; }
 public static class Finder { public static Settings Settings=new Settings(); }
 public class ThingComp_CombatAI { public SightTracker.SightReader sightReader; }
 public static class SightUtility {
  public static float OwnSight; public static IntVec3 LastRoot; public static int SightCalls;
  NEW_SIGHT_ACTIVE
  internal static bool SupportsMap(Map map) => map!=null && map.Square;
  internal static bool CanSeeCell(Thing thing,IntVec3 root,IntVec3 cell) {
   SightCalls++; LastRoot=root; int dx=root.x-cell.x,dz=root.z-cell.z; return dx*dx+dz*dz<OwnSight*OwnSight;
  }
 }
 public class SightTracker {
  public SightReader FactionReader,FactionlessReader=new SightReader();
  public bool TryGetReader(Faction faction,out SightReader reader) { reader=faction==null?FactionlessReader:FactionReader; return reader!=null; }
  public class SightReader {
   public ulong Flags; public int Calls; public IntVec3 LastCell;
   public ulong GetDynamicFriendlyFlags(IntVec3 cell) { Calls++; LastCell=cell; return Flags; }
  }
 }
}
namespace CombatAI.Patches {
 public class Verb_Patch {
  static Verb callerVerb;
  GATE
  CORE
  GET_TARGET
  CONVERT
  public class Vanilla { VANILLA_PREFIX }
  public class CanHit { CAN_HIT_POSTFIX }
 }
}
class CE { CE_PREFIX }
class TurretPatch { TURRET_PREFIX }
class Program {
 static void Check(bool ok,string name) { if(!ok) throw new Exception(name); }
 static bool CanHit(Verb verb,IntVec3 root,LocalTargetInfo target,bool vanillaResult=true) { bool result=vanillaResult; Verb_Patch.CanHit.Postfix(verb,root,target,ref result); return result; }
 static LocalTargetInfo At(int x,int z) => new LocalTargetInfo{IsValid=true,Cell=new IntVec3(x,z)};
 static void Main() {
  var map=new Map(); var reader=new SightTracker.SightReader();
  var pawn=new Pawn {Map=map,Comp=new ThingComp_CombatAI{sightReader=reader}};
  var verb=new Verb {caster=pawn,CurrentTarget=At(12,8)};
  Check(Verb_Patch.ShouldBlockBySharedSightForVerb(verb,null),"ranged target outside team and own sight blocked");
  reader.Flags=1UL<<63;
  Check(!Verb_Patch.ShouldBlockBySharedSightForVerb(verb,null),"any friendly observer permits a shot, including a high flag bit");
  reader.Flags=0;
  SightUtility.OwnSight=15;
  int readerCalls=reader.Calls;
  Check(!Verb_Patch.ShouldBlockBySharedSightForVerb(verb,null) && reader.Calls==readerCalls,"own sight permits a shot without reading team sight");
  SightUtility.OwnSight=0;
  foreach(var pair in new[]{(false,false),(true,false),(false,true)}) {
   Finder.Settings.FogOfWar_Enabled=pair.Item1; Finder.Settings.NewSightSystem_Enabled=pair.Item2;
   int before=reader.Calls,sightBefore=SightUtility.SightCalls;
   Check(!Verb_Patch.ShouldBlockBySharedSightForVerb(verb,null) && reader.Calls==before && SightUtility.SightCalls==sightBefore,"legacy/disabled fog mode bypasses sight reads");
  }
  Finder.Settings=new Settings();
  verb.verbProps.IsMeleeAttack=true;
  Check(!Verb_Patch.ShouldBlockBySharedSightForVerb(verb,null),"melee unaffected");
  verb.verbProps.IsMeleeAttack=false;
  map.Square=false;
  Check(!Verb_Patch.ShouldBlockBySharedSightForVerb(verb,null),"unsupported rectangular map does not disable ranged weapons");
  map.Square=true;
  pawn.Comp=null;
  Check(!Verb_Patch.ShouldBlockBySharedSightForVerb(verb,null),"pawn without a sight reader defers to ordinary targeting");
  pawn.Comp=new ThingComp_CombatAI{sightReader=reader};
  map.Tracker=null;
  Check(!Verb_Patch.ShouldBlockBySharedSightForVerb(verb,null),"missing tracker defers to ordinary targeting");
  map.Tracker=new SightTracker();
  pawn.Map=null;
  Check(!Verb_Patch.ShouldBlockBySharedSightForVerb(verb,null),"unspawned caster is not queried");
  pawn.Map=map;
  Check(!Verb_Patch.ShouldBlockBySharedSightForVerb(null,null),"missing verb bypasses gate");
  var savedProps=verb.verbProps; verb.verbProps=null;
  Check(!Verb_Patch.ShouldBlockBySharedSightForVerb(verb,null),"missing verb properties bypass gate"); verb.verbProps=savedProps;
  var savedSettings=Finder.Settings; Finder.Settings=null;
  Check(!Verb_Patch.ShouldBlockBySharedSightForVerb(verb,null),"missing settings bypass gate"); Finder.Settings=savedSettings;
  foreach(var target in new object[]{new IntVec3(27,5),new Thing{Position=new IntVec3(27,5)},At(27,5),new TargetInfo{IsValid=true,Cell=new IntVec3(27,5)}}) {
   Check(Verb_Patch.ShouldBlockBySharedSightForVerb(verb,new object[]{false,target}),"argument target shapes are gated");
   Check(reader.LastCell.x==27 && reader.LastCell.z==5,"argument target overrides previous CurrentTarget");
  }
  var moving=new Thing{Position=new IntVec3(40,9)};
  var targetWithThing=new LocalTargetInfo{IsValid=true,Thing=moving,Cell=new IntVec3(1,1)};
  Check(Verb_Patch.ShouldBlockBySharedSightForVerb(verb,new object[]{targetWithThing}) && reader.LastCell.x==40,"spawned target uses its live position");
  Check(Verb_Patch.ShouldBlockBySharedSightForVerb(verb,new object[]{"irrelevant"}) && reader.LastCell.x==12,"unrelated arguments fall back to CurrentTarget");
  int previousCalls=reader.Calls;
  Check(!Verb_Patch.ShouldBlockBySharedSightForVerb(verb,new object[]{new IntVec3(1000,0)}) && reader.Calls==previousCalls,"out of bounds target never reaches reader");
  verb.CurrentTarget=default;
  Check(!Verb_Patch.ShouldBlockBySharedSightForVerb(verb,null),"invalid target does not block unrelated verb calls");
  verb.CurrentTarget=At(12,8);

  var loner=new Pawn{Map=map,Comp=new ThingComp_CombatAI{sightReader=new SightTracker.SightReader()}};
  var lonerVerb=new Verb{caster=loner,CurrentTarget=At(12,0)};
  SightUtility.OwnSight=20;
  Check(!Verb_Patch.ShouldBlockBySharedSightForVerb(lonerVerb,null),"factionless pawn with no allies can shoot what it sees");
  SightUtility.OwnSight=10;
  Check(Verb_Patch.ShouldBlockBySharedSightForVerb(lonerVerb,null),"factionless pawn cannot shoot beyond its own sight");
  SightUtility.OwnSight=0;

  Check(!CanHit(verb,pawn.Position,At(12,8)),"target finders see an unseen target as unhittable");
  readerCalls=reader.Calls;
  Check(!CanHit(verb,pawn.Position,At(12,8),vanillaResult:false) && reader.Calls==readerCalls,"vanilla miss stays a miss without sight reads");
  SightUtility.OwnSight=10;
  Check(!CanHit(verb,new IntVec3(0,0),At(30,0)),"cast position beyond own sight rejected");
  Check(CanHit(verb,new IntVec3(25,0),At(30,0)) && SightUtility.LastRoot.x==25,"cast position finder accepts a closer cell that would see the target");
  SightUtility.OwnSight=0;
  Check(CanHit(new Verb_CastAbility{caster=pawn},pawn.Position,At(12,8)),"abilities are not gated");
  Check(CanHit(verb,pawn.Position,default),"invalid target left to vanilla");
  Check(!CanHit(verb,pawn.Position,targetWithThing) && reader.LastCell.x==40,"hit check uses a spawned target's live position");
  reader.Flags=2;
  Check(CanHit(verb,pawn.Position,At(12,8)),"target seen by an ally stays hittable from anywhere in range");
  reader.Flags=0;

  bool state;
  Verb_Patch.Vanilla.Prefix(verb,out state);
  Check(state,"vanilla cast prefix only tracks the caller and never cancels casts or burst shots");

  var faction=new Faction(); var turret=new Building_TurretGun{Map=map,Faction=faction};
  verb.caster=turret; map.Tracker.FactionReader=reader;
  Check(Verb_Patch.ShouldBlockBySharedSightForVerb(verb,null),"non-pawn uses faction shared sight");
  reader.Flags=7;
  Check(!Verb_Patch.ShouldBlockBySharedSightForVerb(verb,null),"turret can use another observer's sight"); reader.Flags=0;
  turret.Faction=null;
  Check(Verb_Patch.ShouldBlockBySharedSightForVerb(verb,null),"factionless non-pawn has no allies to share sight");
  SightUtility.OwnSight=20;
  Check(!Verb_Patch.ShouldBlockBySharedSightForVerb(verb,null),"factionless non-pawn shoots what it sees"); SightUtility.OwnSight=0;
  turret.Faction=faction;
  map.Tracker.FactionReader=null;
  Check(!Verb_Patch.ShouldBlockBySharedSightForVerb(verb,null),"missing faction reader bypasses gate"); map.Tracker.FactionReader=reader;
  verb.caster=pawn;
  bool result=true;
  Check(!CE.Prefix(verb,ref result,null) && !result,"CE prefix uses same sight gate");
  reader.Flags=1;
  result=true;
  Check(CE.Prefix(verb,ref result,null) && result,"visible CE shot reaches original");
  turret.Mannable=new CompMannable{ManningPawn=new Pawn{Lord=new Lord{CurLordToil=new LordToil_DefendBase()}}};
  Check(!TurretPatch.Prefix(turret),"enemy manned turret in defend-base state cannot fire on an encounter map");
  Finder.Settings.NewSightSystem_Enabled=false;
  Check(!TurretPatch.Prefix(turret),"defend-base rule is independent of optional shared sight mode");
  map.IsPlayerHome=true; Check(TurretPatch.Prefix(turret),"home-map turret unaffected"); map.IsPlayerHome=false;
  faction.PlayerSafe=true; Check(TurretPatch.Prefix(turret),"player-safe faction turret unaffected"); faction.PlayerSafe=false;
  turret.Faction=null; Check(TurretPatch.Prefix(turret),"factionless turret unaffected"); turret.Faction=faction;
  turret.IsMannable=false; Check(TurretPatch.Prefix(turret),"automated turret unaffected"); turret.IsMannable=true;
  turret.Mannable.ManningPawn.Lord.CurLordToil=new object(); Check(TurretPatch.Prefix(turret),"active attack lord state permits fire");
  turret.Mannable.ManningPawn.Lord=null; Check(TurretPatch.Prefix(turret),"no lord permits fire");
  turret.Mannable.ManningPawn=null; Check(TurretPatch.Prefix(turret),"unmanned turret does not trigger defend-base restriction");
  Console.WriteLine("PASS: shared/own sight gate, factionless casters, hit checks for target and cast position finders, ability exemption, target argument forms, mode/map fallbacks, CE cancellation, defend-base turret exceptions");
 }
}
'''
verb_source = (SOURCE / 'Patches/Verb_Patch.cs').read_text()
utility_source = (SOURCE / 'SightUtility.cs').read_text(encoding='utf-8-sig')
replacements = {
    'NEW_SIGHT_ACTIVE': next(line.strip() for line in utility_source.splitlines() if 'static bool NewSightSystemActive' in line),
    'GATE': block(verb_source, 'internal static bool ShouldBlockBySharedSightForVerb('),
    'CORE': block(verb_source, 'internal static bool IsOutsideSharedSight('),
    'GET_TARGET': block(verb_source, 'private static bool TryGetTargetCell('),
    'CONVERT': block(verb_source, 'private static bool TryConvertToCell('),
    'VANILLA_PREFIX': block(verb_source, 'public static void Prefix(Verb __instance, out bool __state)'),
    'CAN_HIT_POSTFIX': block(verb_source, 'public static void Postfix(Verb __instance, IntVec3 root, LocalTargetInfo targ, ref bool __result)'),
    'CE_PREFIX': block((SOURCE / 'Mods/Mod_CE.cs').read_text(encoding='utf-8-sig'), 'public static bool Prefix(Verb __instance,'),
    'TURRET_PREFIX': block((SOURCE / 'Patches/Building_TurretGun_Patch.cs').read_text(encoding='utf-8-sig'), 'public static bool Prefix(Building_TurretGun __instance)'),
}
for marker, value in replacements.items():
    harness = harness.replace(marker, value)
with tempfile.TemporaryDirectory(prefix='cai-workshop-targeting-') as tmp:
    tmp = Path(tmp)
    (tmp / 'Harness.cs').write_text(harness)
    (tmp / 'Regression.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>')
    env = dict(os.environ, DOTNET_CLI_HOME=str(tmp), DOTNET_NOLOGO='1', DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1', DOTNET_CLI_TELEMETRY_OPTOUT='1')
    subprocess.run(['dotnet', 'run', '--project', str(tmp / 'Regression.csproj'), '--verbosity', 'quiet'], check=True, env=env)
