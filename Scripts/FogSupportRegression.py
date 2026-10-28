#!/usr/bin/env python3
"""Exercise production queue lifecycle, scheduled doors, and cached glow accessors."""
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
using System.Reflection;
using System.Threading;
using CombatAI;
namespace Verse {
 public static class GenTicks { public static int TicksGame; }
 public static class Log { public static void Error(string s) { throw new Exception(s); } }
 public struct ColorInt { public int value; }
}
class TickManager { public int TicksGame; }
static class Find { public static TickManager TickManager = new TickManager(); }
enum ThingRequestGroup { Door }
class Thing { }
class Building_Door : Thing { public bool Spawned = true, Destroyed; public int Position; }
class Lister { public List<Thing> doors = new List<Thing>(); public int queries;
 public List<Thing> ThingsInGroup(ThingRequestGroup group) { queries++; return doors; } }
class Map { public Lister listerThings = new Lister(); }
class Base { public virtual void MapComponentUpdate() {} }
class Walls : Base {
 public Map map = new Map(); public int updates; private int lastDoorUpdateTick = -1;
 void RecalculateCell(int position, Thing door) { updates++; }
 WALL_METHOD
}
GLOW_CLASS
class FieldGlow { private Verse.ColorInt[] glowGrid; public FieldGlow(Verse.ColorInt[] a) { glowGrid=a; } public void Replace(Verse.ColorInt[] a) { glowGrid=a; } }
class PropertyGlow { public Verse.ColorInt[] GlowGrid { get; set; } }
class FallbackGlow { public object glowGrid = new object(); public Verse.ColorInt[] GlowGrid { get; set; } }
class MissingGlow {}
class Program {
 static void Check(bool ok, string name) { if (!ok) throw new Exception(name); }
 static void Main() {
  var queue = new AsyncActions(); var seen = new List<int>();
  for(int i=0;i<100;i++) { int n=i; queue.EnqueueMainThreadAction(()=>seen.Add(n)); }
  queue.ExecuteMainThreadActions();
  Check(seen.Count==100,"main queue drained"); for(int i=0;i<100;i++) Check(seen[i]==i,"main FIFO");
  seen.Clear(); using(var done=new ManualResetEvent(false)) {
   for(int i=0;i<100;i++) { int n=i; queue.EnqueueOffThreadAction(()=>seen.Add(n)); }
   queue.EnqueueOffThreadAction(()=>done.Set()); queue.Start(); queue.Start();
   Check(done.WaitOne(3000),"worker drains pre-start queue");
   for(int i=0;i<100;i++) Check(seen[i]==i,"worker FIFO");
  }
  queue.Kill(); queue.Kill(); queue.EnqueueMainThreadAction(()=>{throw new Exception("dead main ran");});
  queue.EnqueueOffThreadAction(()=>{throw new Exception("dead worker ran");}); queue.ExecuteMainThreadActions(); queue.Start();
  var neverStarted=new AsyncActions(); neverStarted.EnqueueMainThreadAction(()=>{throw new Exception("cleared action ran");});
  neverStarted.Kill(); neverStarted.ExecuteMainThreadActions(); neverStarted.Start();
  var selfKill=new AsyncActions(); using(var done=new ManualResetEvent(false)) {
   selfKill.EnqueueOffThreadAction(()=>{selfKill.Kill(); done.Set();}); selfKill.Start();
   Check(done.WaitOne(3000),"worker can kill itself");
  }
  var walls=new Walls(); walls.map.listerThings.doors.Add(new Building_Door());
  Find.TickManager.TicksGame=30; for(int i=0;i<500;i++) walls.MapComponentUpdate();
  Check(walls.updates==1 && walls.map.listerThings.queries==1,"paused scheduled tick once");
  Find.TickManager.TicksGame=31; walls.MapComponentUpdate(); Check(walls.updates==1,"non-scheduled tick");
  walls.map.listerThings.doors.Add(new Building_Door()); Find.TickManager.TicksGame=60; walls.MapComponentUpdate();
  Check(walls.updates==3,"new maintained doors included");
  walls.map.listerThings.doors.Clear(); Find.TickManager.TicksGame=90; walls.MapComponentUpdate(); Check(walls.updates==3,"removed doors excluded");
  var a=new Verse.ColorInt[1]; var b=new Verse.ColorInt[2]; var field=new FieldGlow(a);
  Check(GlowGridCompat.GetGlowGrid(field)==a,"private field"); field.Replace(b);
  Check(GlowGridCompat.GetGlowGrid(field)==b,"replacement array");
  Check(GlowGridCompat.GetGlowGrid(new FieldGlow(a))==a,"same type different instance");
  Check(GlowGridCompat.GetGlowGrid(new PropertyGlow{GlowGrid=a})==a,"property fallback");
  Check(GlowGridCompat.GetGlowGrid(new FallbackGlow{GlowGrid=b})==b,"wrong field type fallback");
  Check(GlowGridCompat.GetGlowGrid(new MissingGlow())==null,"missing member");
  Check(GlowGridCompat.GetGlowGrid(new MissingGlow())==null,"cached missing member");
  Console.WriteLine("PASS: queue FIFO/lifecycle, paused door refresh, glow accessors and replacement");
 }
}
'''
harness = harness.replace('WALL_METHOD', block((SOURCE/'WallGrid.cs').read_text(encoding='utf-8-sig'), 'public override void MapComponentUpdate()'))
harness = harness.replace('GLOW_CLASS', block((SOURCE/'Compatibility/ApiCompat.cs').read_text(), 'public static class GlowGridCompat'))
harness = harness.replace('using CombatAI;', 'using CombatAI;\nusing Verse;')
with tempfile.TemporaryDirectory(prefix='cai-fog-support-') as tmp:
    source = Path(tmp)/'Harness.cs'
    source.write_text(harness)
    exe = Path(tmp)/'Regression.exe'
    subprocess.run(['mcs', '-out:'+str(exe), str(source), str(SOURCE/'AsyncActions.cs')], check=True)
    subprocess.run(['mono', str(exe)], check=True)
