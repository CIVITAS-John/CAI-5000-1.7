#!/usr/bin/env python3
"""Exercise production cover/duck candidates and pawn compatibility accessors (mcs/mono)."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1] / 'Source/Rule56'


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
using System.Collections.Concurrent;
using System.Linq.Expressions;
using System.Reflection;
public class Need {}
public class Pawn { public Pawn_PathFollower pather; }
public class Pawn_PathFollower {}
NEED_CLASS
PATH_CLASS
class IntNeed : Need { private int lastRestTick; public long LastRestTick { get { throw new Exception("field must win"); } } public void Set(int value) { lastRestTick=value; } }
class LongNeed : Need { public long lastRestTick; }
class PropertyNeed : Need { public int LastRestTick { get; set; } }
class DynamicNeed : Need { public object lastRestTick; public object LastRestTick { get; set; } }
class Moving : Pawn_PathFollower { private bool moving; public void Set(bool value) { moving=value; } }
class PropertyMoving : Moving { public bool MovingNow { get; set; } }
class DynamicMoving : Moving { public object MovingNow { get; set; } public bool moving; }
struct IntVec3 {
 public int x; public IntVec3(int value) { x=value; }
 public float DistanceToSquared(IntVec3 other) { return (x-other.x)*(x-other.x); }
 public static bool operator ==(IntVec3 a, IntVec3 b) { return a.x==b.x; }
 public static bool operator !=(IntVec3 a, IntVec3 b) { return a.x!=b.x; }
 public override bool Equals(object other) { return other is IntVec3 && this==(IntVec3)other; }
 public override int GetHashCode() { return x; }
 public override string ToString() { return x.ToString(); }
}
static class Mathf { public static float Clamp(float x, float lo, float hi) { return Math.Min(Math.Max(x,lo),hi); } public static float Abs(float x) { return Math.Abs(x); } }
static class Maths { public static float Sqr(float x) { return x*x; } public static float Sqrt_Fast(float x, int iterations) { return (float)Math.Sqrt(x); } }
class Node { public IntVec3 cell; public float dist, distAbs, Score, Visibility; public bool Reserved; public bool[] Hits; }
static class State { public static Node Current; }
class Metric { public float Score(IntVec3 cell) { return State.Current.Score; } public void Print(IntVec3 cell) {} }
class Grid { public float Get(IntVec3 cell) { return 0; } }
class Interceptors { public Grid grid=new Grid(); }
class Reader { public IntVec3 GetNearestEnemy(IntVec3 cell) { return new IntVec3(0); } public float GetVisibilityToEnemies(IntVec3 cell) { return State.Current.Visibility; } }
class Reservations { public bool CanReserve(object caster, IntVec3 cell) { return !State.Current.Reserved; } }
class Map { public Reservations reservationManager=new Reservations(); }
class Verb { public int Calls; public bool CanHitTargetFrom(IntVec3 cell, IntVec3 target) { Calls++; return true; } }
class Request { public IntVec3 locus=new IntVec3(0); public Verb verb; }
static class Log { public static List<string> Messages=new List<string>(); public static void Message(string message) { Messages.Add(message); } }
class Candidates {
 public Request request=new Request(); public Map map=new Map(); public object caster;
 public Reader sightReader=new Reader(); public Interceptors interceptors=new Interceptors();
 public Metric metric_cover=new Metric(), metric_duck=new Metric();
 public float maxDistSqr=100000, effectiveRange=-1, rootDutyDestDist=-1, bestCellScore=1e8f, bestCellVisibility=1e8f;
 public IntVec3 enemyLoc=new IntVec3(0), dutyDest, bestCell=new IntVec3(-1);
 public int enemiesWarmingUp, bestVisibleTo=256, HitCalls;
 public Action<IntVec3,float> callback;
 public List<Func<IntVec3,bool>> enemyVerbs=new List<Func<IntVec3,bool>>();
 public void AddThreats(int count) { for(int i=0;i<count;i++) { int index=i; enemyVerbs.Add(cell=>{ HitCalls++; return State.Current.Hits[index]; }); } }
 public void Cover(Node node) COVER_BODY
 public void Duck(Node node) DUCK_BODY
 public void Run(Node[] nodes, bool duck) { foreach(var node in nodes) { State.Current=node; if(duck) Duck(node); else Cover(node); } }
}
class Program {
 static void Check(bool ok, string label) { if(!ok) throw new Exception(label); }
 static Node Cell(int id, float score, float visibility, params bool[] hits) { return new Node{cell=new IntVec3(id),Score=score,Visibility=visibility,Hits=hits}; }
 static Candidates Run(Node[] nodes, bool duck, bool diagnostics, int warming=0) {
  var c=new Candidates{enemiesWarmingUp=warming}; c.AddThreats(nodes[0].Hits.Length);
  if(diagnostics) c.callback=(cell,score)=>{};
  c.Run(nodes,duck); return c;
 }
 static void Compare(Node[] nodes, bool duck, int warming=0) {
  Log.Messages.Clear(); var complete=Run(nodes,duck,true,warming); var logs=string.Join("|",Log.Messages.ToArray());
  Log.Messages.Clear(); var fast=Run(nodes,duck,false,warming);
  Check(complete.bestCell==fast.bestCell && complete.bestCellScore.Equals(fast.bestCellScore),"selection and score with/without diagnostics");
  Check(complete.bestVisibleTo==fast.bestVisibleTo && complete.bestCellVisibility.Equals(fast.bestCellVisibility),"secondary selection criteria");
  Check(logs==string.Join("|",Log.Messages.ToArray()),"exploding-score diagnostics preserved");
  Check(fast.HitCalls<=complete.HitCalls,"hit work never increases");
 }
 static void Main() {
  Check(NeedCompat.GetLastRestTick(null)==0,"null need");
  var rest=new IntNeed(); rest.Set(42); Check(NeedCompat.GetLastRestTick(rest)==42,"private int field wins");
  rest.Set(90); Check(NeedCompat.GetLastRestTick(rest)==90,"changed field read through cached accessor");
  Check(NeedCompat.GetLastRestTick(new LongNeed{lastRestTick=1L<<40})==1L<<40,"long precision");
  Check(NeedCompat.GetLastRestTick(new PropertyNeed{LastRestTick=71})==71,"int property fallback");
  var dynamicRest=new DynamicNeed{lastRestTick=8L,LastRestTick=9};
  Check(NeedCompat.GetLastRestTick(dynamicRest)==8,"object field precedence"); dynamicRest.lastRestTick="unsupported";
  Check(NeedCompat.GetLastRestTick(dynamicRest)==9,"unsupported field falls through"); dynamicRest.LastRestTick=12L;
  Check(NeedCompat.GetLastRestTick(dynamicRest)==12,"object property changes"); dynamicRest.LastRestTick=null;
  Check(NeedCompat.GetLastRestTick(dynamicRest)==0,"unsupported property fallback");
  Check(NeedCompat.GetLastRestTick(new Need())==0 && NeedCompat.GetLastRestTick(new Need())==0,"missing members");
  Check(!PawnPathCompatExtras.IsPawnMoving(null) && !PawnPathCompatExtras.IsPawnMoving(new Pawn()),"missing pawn/pather");
  var moving=new Moving(); var pawn=new Pawn{pather=moving}; moving.Set(true);
  Check(PawnPathCompatExtras.IsPawnMoving(pawn),"private moving field"); moving.Set(false);
  Check(!PawnPathCompatExtras.IsPawnMoving(pawn),"movement update");
  var propertyMoving=new PropertyMoving{MovingNow=false}; propertyMoving.Set(true); pawn.pather=propertyMoving;
  Check(!PawnPathCompatExtras.IsPawnMoving(pawn),"property false wins over field true"); propertyMoving.MovingNow=true;
  Check(PawnPathCompatExtras.IsPawnMoving(pawn),"property update and subclass cache isolation");
  var dynamicMoving=new DynamicMoving{MovingNow="unsupported",moving=true}; pawn.pather=dynamicMoving;
  Check(PawnPathCompatExtras.IsPawnMoving(pawn),"object property falls back"); dynamicMoving.MovingNow=false;
  Check(!PawnPathCompatExtras.IsPawnMoving(pawn),"object bool property wins");
  pawn.pather=new Pawn_PathFollower(); Check(!PawnPathCompatExtras.IsPawnMoving(pawn) && !PawnPathCompatExtras.IsPawnMoving(pawn),"missing movement members");

  var cheap=new Candidates(); cheap.request.verb=new Verb(); cheap.maxDistSqr=4;
  cheap.Run(new[]{Cell(3,0,0)},false); Check(cheap.request.verb.Calls==0,"distant cell rejected before hit test");
  var reserved=Cell(1,0,0); reserved.Reserved=true; cheap.Run(new[]{reserved},false);
  Check(cheap.request.verb.Calls==0,"reservation rejected before hit test");
  foreach(bool duck in new[]{false,true}) {
   var nodes=new[]{Cell(1,0,0,false,false,false),Cell(2,0.1f,0,true,true,true)};
   Check(Run(nodes,duck,false).bestCell.x==1,"worse candidate cannot replace winner");
   Check(Run(nodes,duck,false).HitCalls==3,"skip losing candidate hit tests");
   var c=new Candidates(); c.AddThreats(3); var values=new List<float>(); c.callback=(cell,score)=>values.Add(score);
   c.Run(nodes,duck); Check(values.Count==2 && Math.Abs(values[1]-3.1f)<0.00001f,"complete callback scores including losing candidates");
   Compare(nodes,duck);
   Compare(new[]{Cell(1,0.0f,0,false,false),Cell(2,-0.01f,0,true,true),Cell(3,-0.05f,0,false,false)},duck);
  }
  Log.Messages.Clear(); Run(new[]{Cell(1,0,0,false,false),Cell(2,4999.5f,0,true,true)},false,false);
  Check(Log.Messages.Count==1,"losing cover still reports exploding score");
  var rng=new Random(518);
  for(int run=0;run<300;run++) {
   var nodes=new Node[40];
   for(int i=0;i<nodes.Length;i++) {
    float score=(float)(rng.NextDouble()*20-10);
    if(i%7==0) score=5000+(float)(rng.NextDouble()*4-2);
    nodes[i]=Cell(i,score,rng.Next(10),rng.Next(2)==0,rng.Next(2)==0,rng.Next(2)==0);
   }
   Compare(nodes,false,rng.Next(4)); Compare(nodes,true,rng.Next(4));
  }
  Compare(new[]{Cell(0,float.NaN,0,false),Cell(1,float.NegativeInfinity,0,false),Cell(2,float.PositiveInfinity,0,true)},false);
  Compare(new[]{Cell(0,float.NaN,0,false),Cell(1,float.NegativeInfinity,0,false),Cell(2,float.PositiveInfinity,0,true)},true);
  Console.WriteLine("PASS: typed accessor updates/fallbacks, cover/duck selection, callback scores, cheap rejection, diagnostics, and pruned hit work");
 }
}
'''
compat = (ROOT / 'Compatibility/ApiCompat.cs').read_text()
cover = (ROOT / 'CoverPositionFinder.cs').read_text(encoding='utf-8-sig')
for marker, name in [('NEED_CLASS', 'NeedCompat'), ('PATH_CLASS', 'PawnPathCompatExtras')]:
    harness = harness.replace(marker, block(compat, 'public static class ' + name))
for marker, method in [('COVER_BODY', 'TryFindCoverPosition'), ('DUCK_BODY', 'TryFindDuckPosition')]:
    body = block(cover[cover.index('public static bool ' + method):], 'node =>')
    harness = harness.replace(marker, body[body.index('{'):])
with tempfile.TemporaryDirectory(prefix='cai-pawn-position-compat-') as tmp:
    source = Path(tmp) / 'Harness.cs'
    source.write_text(harness)
    exe = Path(tmp) / 'Regression.exe'
    subprocess.run(['mcs', '-out:' + str(exe), str(source)], check=True)
    subprocess.run(['mono', str(exe)], check=True)
