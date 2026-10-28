#!/usr/bin/env python3
"""Exercise production hazard queries and Search and Destroy pursuit decisions."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'Source/Rule56'


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
using System.Collections.Generic;
using CombatAI.Comps;
using Verse;
using RimWorld;
namespace Verse {
 public static class GenTicks { public static int TicksGame; }
 public struct IntVec3 {
  public int x,y,z; public IntVec3(int x,int y,int z) { this.x=x;this.y=y;this.z=z; }
  public static IntVec3 Invalid = new IntVec3(-999,0,-999);
  public bool IsValid { get { return x!=-999; } }
  public bool InBounds(Map m) { return x>=0 && z>=0 && x<100 && z<100; }
  public int DistanceToSquared(IntVec3 b) { return (x-b.x)*(x-b.x)+(z-b.z)*(z-b.z); }
  public float DistanceTo(IntVec3 b) { return (float)Math.Sqrt(DistanceToSquared(b)); }
  public Vector3 ToVector3() { return new Vector3(x,y,z); }
  public static IntVec3 operator +(IntVec3 a,IntVec3 b) { return new IntVec3(a.x+b.x,a.y+b.y,a.z+b.z); }
  public static IntVec3 operator -(IntVec3 a,IntVec3 b) { return new IntVec3(a.x-b.x,a.y-b.y,a.z-b.z); }
  public static bool operator ==(IntVec3 a,IntVec3 b) { return a.x==b.x && a.z==b.z; }
  public static bool operator !=(IntVec3 a,IntVec3 b) { return !(a==b); }
  public override bool Equals(object b) { return b is IntVec3 && this==(IntVec3)b; }
  public override int GetHashCode() { return x*1000+z; }
 }
 public struct Vector3 {
  public float x,y,z; public Vector3(float x,float y,float z) { this.x=x;this.y=y;this.z=z; }
  public float magnitude { get { return (float)Math.Sqrt(x*x+z*z); } }
  public IntVec3 ToIntVec3() { return new IntVec3((int)x,(int)y,(int)z); }
  public static Vector3 operator +(Vector3 a,Vector3 b) { return new Vector3(a.x+b.x,a.y+b.y,a.z+b.z); }
  public static Vector3 operator *(Vector3 a,int n) { return new Vector3(a.x*n,a.y*n,a.z*n); }
  public static Vector3 operator /(Vector3 a,float n) { return new Vector3(a.x/n,a.y/n,a.z/n); }
 }
 public static class GenRadial {
  public static IntVec3[] RadialPattern;
  static GenRadial() { var cells=new List<IntVec3>();for(int x=-3;x<=3;x++)for(int z=-3;z<=3;z++)if(x*x+z*z<=9)cells.Add(new IntVec3(x,0,z));RadialPattern=cells.ToArray(); }
  public static int NumCellsInRadius(float r) { return RadialPattern.Length; }
 }
 public enum ThingRequestGroup { Fire, Projectile }
 public class Faction { public int id; public bool HostileTo(Faction b) { return b==null || id!=b.id; } }
 public class Thing { public IntVec3 Position; public Map Map; public bool Spawned=true; public Faction Faction; public ThingDef def; }
 public class ThingDef { public ProjectileProperties projectile; public bool IsMeleeWeapon; }
 public class ProjectileProperties { public bool flyOverhead; public float explosionRadius; }
 public class Fire : Thing {}
 public class Projectile : Thing { public Thing Launcher; public LocalTargetInfo intendedTarget,usedTarget; public IntVec3 destination; private IntVec3 DestinationCell { get { return destination; } } }
 public struct LocalTargetInfo {
  public Thing Thing; private IntVec3 cell; private bool valid;
  public LocalTargetInfo(Thing t) { Thing=t;cell=IntVec3.Invalid;valid=t!=null; }
  public LocalTargetInfo(IntVec3 c) { Thing=null;cell=c;valid=c.IsValid; }
  public bool IsValid { get { return valid; } }
  public bool HasThing { get { return Thing!=null; } }
  public IntVec3 Cell { get { return HasThing?Thing.Position:cell; } }
  public static bool operator ==(LocalTargetInfo a,LocalTargetInfo b) { return a.Thing==b.Thing && a.Cell==b.Cell && a.valid==b.valid; }
  public static bool operator !=(LocalTargetInfo a,LocalTargetInfo b) { return !(a==b); }
  public override bool Equals(object b) { return b is LocalTargetInfo && this==(LocalTargetInfo)b; }
  public override int GetHashCode() { return Cell.GetHashCode(); }
 }
 public class Lister {
  public List<Thing> fires=new List<Thing>(), projectiles=new List<Thing>(); public int fireQueries,projectileQueries;
  public List<Thing> ThingsInGroup(ThingRequestGroup g) { if(g==ThingRequestGroup.Fire){fireQueries++;return fires;}projectileQueries++;return projectiles; }
 }
 public class ThingGrid {
  public Dictionary<IntVec3,List<Thing>> cells=new Dictionary<IntVec3,List<Thing>>(); private readonly List<Thing> empty=new List<Thing>();
  public List<Thing> ThingsListAt(IntVec3 c) { List<Thing> list;return cells.TryGetValue(c,out list)?list:empty; }
  public void Add(Thing t) { List<Thing> list;if(!cells.TryGetValue(t.Position,out list)){list=new List<Thing>();cells.Add(t.Position,list);}list.Add(t); }
 }
 public class Map { public Lister listerThings=new Lister(); public ThingGrid thingGrid=new ThingGrid(); public AttackTargetsCache attackTargetsCache=new AttackTargetsCache(); public MapComponent_FogGrid fog=new MapComponent_FogGrid(); public T GetComponent<T>() where T:class { return fog as T; } }
 public class Pawn : Thing {
  public Verb CurrentEffectiveVerb=new Verb();public Equipment equipment=new Equipment();public Race RaceProps=new Race();
  public Job CurJob;public JobTracker jobs;public bool Dead,Downed,reachable=true;public MindState mindState=new MindState();public Health health=new Health();
  public Pawn() { jobs=new JobTracker(this); }
  public bool CanReach(Thing t,PathEndMode m,Danger d) { return reachable; }
 }
 public class MindState { public Thing enemyTarget; }
 public class Health { public SummaryHealth summaryHealth=new SummaryHealth(); }
 public class SummaryHealth { public float SummaryHealthPercent=1f; }
 public class Verb { public bool IsMeleeAttack; public VerbProperties verbProps=new VerbProperties(); }
 public class VerbProperties { public ThingDef defaultProjectile; }
 public class Equipment { public Weapon Primary=new Weapon(); }
 public class Weapon { public ThingDef def=new ThingDef(); }
 public class Race { public float baseBodySize=1; public bool IsMechanoid; }
 public class AttackTarget : IAttackTarget { public Thing Thing {get;set;} public bool disabled;public bool ThreatDisabled(Pawn p){return disabled;} }
 public interface IAttackTarget { Thing Thing {get;} bool ThreatDisabled(Pawn p); }
 public class AttackTargetsCache { public List<IAttackTarget> targets=new List<IAttackTarget>();public int queries;public List<IAttackTarget> GetPotentialTargetsFor(Pawn p){queries++;return targets;} }
 public enum PathEndMode { OnCell } public enum Danger { Deadly }
 public class JobDef {} public static class JobDefOf { public static JobDef Goto=new JobDef(); }
 public class Job { public JobDef def; public LocalTargetInfo targetA;public int expiryInterval,startTick,loadID;public bool checkOverrideOnExpire,collideWithPawns;public LocomotionUrgency locomotionUrgency;public bool Is(JobDef d){return def==d;} }
 public static class JobMaker { static int id;public static Job MakeJob(JobDef d,LocalTargetInfo t){return new Job{def=d,targetA=t,loadID=++id};} }
 public class JobTracker { Pawn pawn;public int starts,clears;public JobTracker(Pawn p){pawn=p;}public void ClearQueuedJobs(){clears++;}public void StartJob(Job j,JobCondition c){starts++;pawn.CurJob=j;j.startTick=GenTicks.TicksGame;} }
 public enum JobCondition { InterruptForced } public enum LocomotionUrgency { Sprint,Jog }
}
namespace RimWorld {
 public static class AttackTargetFinder { public static bool IsAutoTargetable(IAttackTarget t){return true;} }
 public static class MechanitorUtility { public static bool InMechanitorCommandRange(Pawn p,LocalTargetInfo t){return t.Cell.x<=40;} }
}
public class MapComponent_FogGrid { public bool fogged;public bool IsFogged(IntVec3 c){return fogged;} }
public static class Finder { public static Settings Settings=new Settings(); }
public class Settings { public bool FogOfWar_Enabled,Enable_Sprinting; }
public static class Mathf { public static float Min(float a,float b){return Math.Min(a,b);} }
public class AgentInfo { public Thing thing; }
public class FocusData { public List<AgentInfo> allies=new List<AgentInfo>();public int scans;public List<AgentInfo>.Enumerator EnumerateAllies(){scans++;return allies.GetEnumerator();} }
public class Focus {
 public Pawn selPawn;public FocusData data=new FocusData();public List<Thing> focusFireCandidates=new List<Thing>();
 private Dictionary<Thing,int> focusFireAllyCounts;
 FOCUS_METHOD
}
public class AgentData { public int LastInterrupted;public bool InterruptedRecently(int n){return GenTicks.TicksGame-LastInterrupted<n;} }
public class Pursuit {
 public Pawn selPawn;public bool IsAIAutoControlled=true,IsPlayerOverriding,aiSearchAndDestroy=true,aiSearchAndDestroyMelee=true,animation;
 public AgentData data=new AgentData();private int searchAndDestroyJobId=-1;private int lastSearchAndDestroyTick=-1;private Thing searchAndDestroyTarget;
 bool IsPerformingMeleeAnimation(Pawn p){return animation;}
 PURSUIT_METHOD
}
class Program {
 static void Check(bool ok,string name){if(!ok)throw new Exception(name);}
 static IntVec3 Cell(int x,int z){return new IntVec3(x,0,z);}
 static Projectile Shot(Map m,LocalTargetInfo target,Faction faction,float radius=2){return new Projectile{Map=m,Launcher=new Thing{Faction=faction},def=new ThingDef{projectile=new ProjectileProperties{explosionRadius=radius}},intendedTarget=target,destination=target.Cell};}
 static void Main(){
  var map=new Map();var pawn=new Pawn{Map=map,Position=Cell(20,20),Faction=new Faction{id=1}};IntVec3 cell;float radius;
  Check(!AreaThreats.TryFindNearbyFire(map,pawn.Position,out cell)&&map.listerThings.fireQueries==0,"empty local fire query avoids map list");
  var first=new Fire{Map=map,Position=Cell(23,20)};var second=new Fire{Map=map,Position=Cell(18,20)};
  map.listerThings.fires.Add(first);map.listerThings.fires.Add(second);map.thingGrid.Add(first);map.thingGrid.Add(second);
  Check(AreaThreats.TryFindNearbyFire(map,pawn.Position,out cell)&&cell==first.Position,"first fire in lister wins despite cell traversal order; radius boundary included");
  var hostile=new Faction{id=2};var friendly=Shot(map,new LocalTargetInfo(pawn.Position),pawn.Faction);
  var landing=new Thing{Map=map,Position=Cell(24,20)};var shot=Shot(map,new LocalTargetInfo(landing),hostile);
  var later=Shot(map,new LocalTargetInfo(Cell(19,20)),hostile);
  map.listerThings.projectiles.Add(friendly);map.listerThings.projectiles.Add(shot);map.listerThings.projectiles.Add(later);
  GenTicks.TicksGame=1;
  Check(AreaThreats.TryFindIncomingProjectile(pawn,out cell,out radius)&&cell==landing.Position&&radius==6,"hostile first dangerous projectile wins");
  landing.Position=Cell(80,80);
  Check(AreaThreats.TryFindIncomingProjectile(pawn,out cell,out radius)&&cell==Cell(19,20)&&map.listerThings.projectileQueries==1,"moving landing target uses live position and shared tick snapshot");
  later.Spawned=false;
  Check(!AreaThreats.TryFindIncomingProjectile(pawn,out cell,out radius),"despawned snapshot projectile ignored");
  landing.Spawned=false;landing.Map=null;
  Check(AreaThreats.TryFindIncomingProjectile(pawn,out cell,out radius)&&cell==Cell(24,20)&&radius==6,"live explosive remains dangerous at its landing cell after target despawns, within the cached tick");
  landing.Spawned=true;landing.Map=new Map();
  Check(AreaThreats.TryFindIncomingProjectile(pawn,out cell,out radius)&&cell==Cell(24,20),"target moving to another map does not remove the local explosive threat");
  landing.Position=pawn.Position;shot.destination=Cell(80,80);
  Check(!AreaThreats.TryFindIncomingProjectile(pawn,out cell,out radius),"off-map target coordinates do not create a threat when the landing cell is far away");
  shot.destination=IntVec3.Invalid;
  Check(!AreaThreats.TryFindIncomingProjectile(pawn,out cell,out radius),"invalid landing cell ignored");
  shot.destination=Cell(24,20);
  landing.Map=map;shot.Launcher.Faction=pawn.Faction;
  Check(!AreaThreats.TryFindIncomingProjectile(pawn,out cell,out radius),"launcher faction stays live");
  var newlyLaunched=Shot(map,new LocalTargetInfo(pawn.Position),hostile);map.listerThings.projectiles.Add(newlyLaunched);
  Check(!AreaThreats.TryFindIncomingProjectile(pawn,out cell,out radius),"same-tick launch delay is bounded by snapshot tick");
  GenTicks.TicksGame++;
  Check(AreaThreats.TryFindIncomingProjectile(pawn,out cell,out radius)&&map.listerThings.projectileQueries==2,"new launch discovered next tick");
  newlyLaunched.intendedTarget=default(LocalTargetInfo);newlyLaunched.usedTarget=new LocalTargetInfo(Cell(19,20));
  Check(AreaThreats.TryFindIncomingProjectile(pawn,out cell,out radius)&&cell==Cell(19,20),"used target fallback remains live");
  newlyLaunched.usedTarget=default(LocalTargetInfo);
  Check(AreaThreats.TryFindIncomingProjectile(pawn,out cell,out radius)&&cell==pawn.Position,"live explosive with no valid target still uses its landing cell");
  var other=new Pawn{Map=new Map(),Position=pawn.Position,Faction=pawn.Faction};
  Check(!AreaThreats.TryFindIncomingProjectile(other,out cell,out radius),"map snapshots are isolated");

  GenTicks.TicksGame=100;var pursuit=new Pursuit{selPawn=new Pawn{Map=new Map(),Position=Cell(10,10)}};var p=pursuit.selPawn;
  var far=new Pawn{Map=p.Map,Position=Cell(30,10)};var near=new Pawn{Map=p.Map,Position=Cell(20,10)};
  p.Map.attackTargetsCache.targets.Add(new AttackTarget{Thing=far});
  Check(pursuit.TrySearchAndDestroy()&&p.jobs.starts==1,"initial pursuit starts");var original=p.CurJob;
  for(int t=110;t<145;t+=10){GenTicks.TicksGame=t;Check(pursuit.TrySearchAndDestroy(),"ongoing pursuit reported during search throttle");}
  Check(p.Map.attackTargetsCache.queries==1&&p.jobs.starts==1&&p.jobs.clears==1,"successive scans do not increase full target-search cadence");
  GenTicks.TicksGame=145;Check(pursuit.TrySearchAndDestroy()&&p.CurJob==original&&p.jobs.starts==1&&p.jobs.clears==1,"same target keeps job/path/queue");
  Check(original.startTick+original.expiryInterval==205&&pursuit.data.LastInterrupted==100,"refresh extends live expiry without interruption timestamp");
  Check(p.Map.attackTargetsCache.queries==2,"target search runs again at previous 45-tick cadence");
  far.Position=Cell(29,10);GenTicks.TicksGame=190;
  Check(pursuit.TrySearchAndDestroy()&&p.CurJob==original,"moving Thing target retains pursuit");
  p.Map.attackTargetsCache.targets.Add(new AttackTarget{Thing=near});GenTicks.TicksGame=235;
  Check(pursuit.TrySearchAndDestroy()&&p.jobs.starts==2&&p.CurJob.targetA.Thing==near,"closer valid target retargets");
  near.Downed=true;GenTicks.TicksGame=280;
  Check(pursuit.TrySearchAndDestroy()&&p.jobs.starts==3&&p.CurJob.targetA.Thing==far,"downed target is not reused");
  // Simulate the pooled current job object being repurposed by another job giver.
  p.CurJob.loadID+=1000;GenTicks.TicksGame=325;
  Check(pursuit.TrySearchAndDestroy()&&p.jobs.starts==4,"pooled job object with a new allocation ID is not treated as owned");
  pursuit.IsPlayerOverriding=true;GenTicks.TicksGame=370;
  Check(!pursuit.TrySearchAndDestroy()&&p.jobs.starts==4,"player override keeps command");
  pursuit.IsPlayerOverriding=false;Finder.Settings.FogOfWar_Enabled=true;p.Map.fog.fogged=true;
  Check(!pursuit.TrySearchAndDestroy()&&p.jobs.starts==4,"fogged target cannot refresh pursuit");
  var focus=new Focus{selPawn=pawn};var a=new Pawn{Map=map};var b=new Pawn{Map=map};Thing selected;
  focus.focusFireCandidates.Add(a);focus.focusFireCandidates.Add(b);
  Check(focus.TryGetFocusFireTarget(out selected)&&selected==a,"equal focus scores preserve candidate order");
  for(int i=0;i<3;i++){focus.data.allies.Add(new AgentInfo{thing=new Pawn{mindState=new MindState{enemyTarget=a}}});}
  for(int i=0;i<4;i++){focus.data.allies.Add(new AgentInfo{thing=new Pawn{mindState=new MindState{enemyTarget=b}}});}
  int scans=focus.data.scans;
  Check(focus.TryGetFocusFireTarget(out selected)&&selected==a&&focus.data.scans==scans+1,"ally support caps at three and is counted in one pass");
  focus.focusFireCandidates.Reverse();
  Check(focus.TryGetFocusFireTarget(out selected)&&selected==b,"capped ally support still preserves first tie");
  a.health.summaryHealth.SummaryHealthPercent=0.1f;
  Check(focus.TryGetFocusFireTarget(out selected)&&selected==a,"wounded enemy wins over otherwise equal supported target");
  b.CurrentEffectiveVerb.verbProps.defaultProjectile=new ThingDef{projectile=new ProjectileProperties{explosionRadius=2}};
  Check(focus.TryGetFocusFireTarget(out selected)&&selected==b,"explosive weapon priority preserves score weighting");
  // The ranged reaction supplies only enemies passing its visibility and CanHitTarget gates.
  focus.focusFireCandidates.Remove(b);
  Check(focus.TryGetFocusFireTarget(out selected)&&selected==a,"ineligible enemy cannot win focus scoring");
  focus.focusFireCandidates.Clear();
  Check(!focus.TryGetFocusFireTarget(out selected)&&selected==null,"no eligible enemies yields no focus target");
  Console.WriteLine("PASS: focus order, ally support cap and scoring; local fire order; shared projectile cache, faction and live targets; pursuit reuse, expiry, retarget and pooled-job ownership");
 }
}
'''
method = block((SOURCE / 'Comps/ThingComp_CombatAI.cs').read_text(), 'private bool TrySearchAndDestroy()')
harness = harness.replace('PURSUIT_METHOD', method.replace('private bool', 'public bool', 1))
focus = block((SOURCE / 'Comps/ThingComp_CombatAI.cs').read_text(), 'private bool TryGetFocusFireTarget(')
# Mono's compiler predates ??=; this spelling has the same semantics for the test harness.
focus = focus.replace('focusFireAllyCounts ??= new Dictionary<Thing, int>();', 'if (focusFireAllyCounts == null) focusFireAllyCounts = new Dictionary<Thing, int>();')
harness = harness.replace('FOCUS_METHOD', focus.replace('private bool', 'public bool', 1))
with tempfile.TemporaryDirectory(prefix='cai-pawn-reactions-') as temporary:
    temporary = Path(temporary)
    (temporary / 'Harness.cs').write_text(harness)
    executable = temporary / 'Regression.exe'
    subprocess.run(['mcs', '-out:' + str(executable), str(temporary / 'Harness.cs'), str(SOURCE / 'Comps/AreaThreats.cs')], check=True)
    subprocess.run(['mono', str(executable)], check=True)
