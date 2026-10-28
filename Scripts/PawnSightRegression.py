#!/usr/bin/env python3
"""Exercise production sight completion and environment enumerators with lightweight stubs.

Requires mcs and mono. No RimWorld installation or running game is needed.
"""
from pathlib import Path
import subprocess
import tempfile


def block(source, marker):
    start = source.index(marker)
    opening = source.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


HARNESS = r"""
using System;
using System.Collections.Generic;
using CombatAI;
using Verse;
namespace Verse {
    public interface IExposable { void ExposeData(); }
    public static class Rand { public static int Int = 0; }
    public struct IntVec3 {
        public int x, z;
        public IntVec3(int x, int z = 0) { this.x = x; this.z = z; }
        public int DistanceToSquared(IntVec3 p) { int dx = x - p.x, dz = z - p.z; return dx * dx + dz * dz; }
    }
    public class Thing {
        public int thingIDNumber;
        public bool Spawned = true, Dormant, Hostile;
        public IntVec3 Position;
        public int DormancyCalls, HostilityCalls;
        public bool IsDormant() { DormancyCalls++; return Dormant; }
        public bool HostileTo(Thing observer) { HostilityCalls++; return Hostile; }
    }
    public class Pawn : Thing { public IntVec3 Predicted; public int PredictionCalls; }
}
static class PawnPathUtility {
    public static IntVec3 GetMovingShiftedPosition(Pawn pawn, int ticks) { pawn.PredictionCalls++; return pawn.Predicted; }
}
class ThingsMap {
    public readonly List<Thing> Things = new List<Thing>();
    public readonly int[] Calls = new int[64];
    public void GetThings(ulong flags, List<Thing> result) {
        result.Clear();
        for (int b = 0; b < 64; b++) if ((flags & (1UL << b)) != 0) {
            Calls[b]++;
            foreach (var thing in Things) if (thing.thingIDNumber % 64 == b) result.Add(thing);
        }
    }
}
class Tracker { public readonly ThingsMap factionedUInt64Map = new ThingsMap(); }
class Receiver {
    public readonly List<AIEnvAgentInfo> Seen = new List<AIEnvAgentInfo>();
    public readonly List<bool> Hostile = new List<bool>();
    public void Notify_Enemy(AIEnvAgentInfo info) { Seen.Add(info); Hostile.Add(true); }
    public void Notify_Ally(AIEnvAgentInfo info) { Seen.Add(info); Hostile.Add(false); }
}
class Grid {
    readonly List<Thing> thingBuffer1 = new List<Thing>();
    readonly List<SpottingCandidate> spottingCandidates = new List<SpottingCandidate>();
    readonly List<int> spottedCandidateOrder = new List<int>();
    readonly int[] spottingBucketStarts = new int[64], spottingBucketCounts = new int[64];
    ulong expandedSpottingBuckets;
    public readonly Tracker sightTracker = new Tracker();
    public struct ISpotRecord { public ulong flag; public IntVec3 cell; public int state; }
    public class IBucketableThing {
        public Thing thing = new Thing();
        public Receiver ai = new Receiver();
        public readonly List<ISpotRecord> spottings = new List<ISpotRecord>();
    }
    public void Run(IBucketableThing item) { NotifySpottings(item); }
    /* CANDIDATE */
    /* NOTIFY */
    /* EXPAND */
}
class Program {
    static void Require(bool value, string message) { if (!value) throw new Exception(message); }
    static void Compare(Grid grid, Grid.IBucketableThing item) {
        // Independent reference: visit every record and every thing in original bucket order.
        var expected = new List<AIEnvAgentInfo>();
        foreach (var record in item.spottings) for (int bucket = 0; bucket < 64; bucket++) {
            if ((record.flag & (1UL << bucket)) == 0) continue;
            foreach (var thing in grid.sightTracker.factionedUInt64Map.Things) {
                if (thing.thingIDNumber % 64 != bucket || thing == item.thing || !thing.Spawned) continue;
                bool close = thing.Position.DistanceToSquared(record.cell) < 225;
                var pawn = thing as Pawn;
                if (!close && pawn != null) close = pawn.Predicted.DistanceToSquared(record.cell) < 255;
                if (!close || thing.Dormant) continue;
                int index = expected.FindIndex(info => info.thing == thing);
                var next = new AIEnvAgentInfo(thing, (AIEnvAgentState)record.state);
                if (index < 0) expected.Add(next);
                else expected[index] = expected[index].Combine(next);
            }
        }
        Array.Clear(grid.sightTracker.factionedUInt64Map.Calls, 0, 64);
        foreach (var thing in grid.sightTracker.factionedUInt64Map.Things) {
            thing.DormancyCalls = thing.HostilityCalls = 0;
            if (thing is Pawn) ((Pawn)thing).PredictionCalls = 0;
        }
        item.ai = new Receiver();
        grid.Run(item);
        Require(item.ai.Seen.Count == expected.Count, "candidate identity or duplicate notification");
        for (int i = 0; i < expected.Count; i++) {
            Require(item.ai.Seen[i].thing == expected[i].thing, "first-success ordering");
            Require(item.ai.Seen[i].state == expected[i].state, "per-record range or merged state");
            Require(item.ai.Hostile[i] == expected[i].thing.Hostile, "hostility classification");
        }
        foreach (int calls in grid.sightTracker.factionedUInt64Map.Calls) Require(calls <= 1, "re-expanded bucket");
        foreach (var thing in grid.sightTracker.factionedUInt64Map.Things) {
            Require(thing.DormancyCalls <= 1 && thing.HostilityCalls <= 1, "repeated candidate fact");
            if (thing is Pawn) Require(((Pawn)thing).PredictionCalls <= 1, "repeated path prediction");
        }
    }
    static Grid.ISpotRecord Record(ulong flags, int position, AIEnvAgentState state) {
        return new Grid.ISpotRecord { flag = flags, cell = new IntVec3(position), state = (int)state };
    }
    static void Sight() {
        var grid = new Grid();
        var item = new Grid.IBucketableThing();
        var map = grid.sightTracker.factionedUInt64Map;
        // Two colliding actual things, a high bucket, and a candidate that first fails distance.
        map.Things.Add(new Pawn { thingIDNumber = 1, Position = new IntVec3(100), Predicted = new IntVec3(20), Hostile = true });
        map.Things.Add(new Thing { thingIDNumber = 65, Position = new IntVec3(0) });
        map.Things.Add(new Thing { thingIDNumber = 63, Position = new IntVec3(0), Hostile = true });
        map.Things.Add(new Thing { thingIDNumber = 129, Position = new IntVec3(0), Dormant = true });
        map.Things.Add(new Thing { thingIDNumber = 193, Position = new IntVec3(0), Spawned = false });
        item.thing.thingIDNumber = 257; map.Things.Add(item.thing);
        ulong flags = (1UL << 1) | (1UL << 63);
        item.spottings.Add(Record(flags, 0, AIEnvAgentState.visible));
        item.spottings.Add(Record(flags, 15, AIEnvAgentState.nearby));
        item.spottings.Add(Record(flags, 30, AIEnvAgentState.visible));
        item.spottings.Add(Record(flags, 0, AIEnvAgentState.visible));
        Compare(grid, item);
        Require(item.ai.Seen[0].thing.thingIDNumber == 65, "collision representative was lost");
        Require(item.ai.Seen[2].state == (AIEnvAgentState.visible | AIEnvAgentState.nearby), "late moving candidate must acquire both states");
        // Reuse the same caches after positions, dormancy and hostility change between scans.
        map.Things[0].Hostile = false; map.Things[3].Dormant = false;
        ((Pawn)map.Things[0]).Predicted = new IntVec3(1000);
        Compare(grid, item);
        item.spottings.Clear(); Compare(grid, item);
        // Strict distance boundary for non-pawns, plus unknown-state records.
        item.spottings.Add(Record(1UL << 1, 15, AIEnvAgentState.unknown));
        Compare(grid, item);
        Require(item.ai.Seen.Count == 0, "strict 225 distance predicate changed");
        Console.WriteLine("collisions, state merging, late matches, strict range, ordering, cache reuse: PASS");
        var random = new Random(71);
        for (int iteration = 0; iteration < 100; iteration++) {
            map.Things.Clear(); item.spottings.Clear();
            for (int i = 0; i < 90; i++) {
                Thing thing = i % 3 == 0 ? (Thing)new Thing() : new Pawn();
                thing.thingIDNumber = i + 1; thing.Position = new IntVec3(random.Next(120), random.Next(120));
                thing.Hostile = i % 2 == 0; thing.Dormant = i % 11 == 0; thing.Spawned = i % 17 != 0;
                if (thing is Pawn) ((Pawn)thing).Predicted = new IntVec3(random.Next(120), random.Next(120));
                map.Things.Add(thing);
            }
            for (int i = 0; i < 100; i++) item.spottings.Add(new Grid.ISpotRecord {
                flag = (1UL << random.Next(64)) | (1UL << random.Next(64)),
                cell = new IntVec3(random.Next(120), random.Next(120)), state = random.Next(4) });
            Compare(grid, item);
        }
        Console.WriteLine("100 randomized scans against independent record-by-record oracle: PASS");
    }
    static void Enumerators() {
        var env = new AIEnvThings();
        var values = new List<AIEnvAgentInfo> {
            new AIEnvAgentInfo(new Thing(), AIEnvAgentState.visible),
            new AIEnvAgentInfo(new Thing(), AIEnvAgentState.visible | AIEnvAgentState.nearby),
            new AIEnvAgentInfo(new Thing(), AIEnvAgentState.nearby) };
        env.ClearAndAddRange(new HashSet<AIEnvAgentInfo>(values));
        foreach (AIEnvAgentState state in new[] { AIEnvAgentState.unknown, AIEnvAgentState.visible, AIEnvAgentState.nearby, AIEnvAgentState.visible | AIEnvAgentState.nearby, AIEnvAgentState.melee }) {
            AIEnvThings.Enumerator fast = env.GetFastEnumerator(state);
            var legacy = env.GetEnumerator(state);
            int count = 0;
            while (legacy.MoveNext()) {
                Require(fast.MoveNext() && fast.Current.Equals(legacy.Current), "enumerator filtering/order"); count++;
            }
            Require(!fast.MoveNext(), "fast enumerator extra elements");
            fast.Reset(); int repeated = 0; while (fast.MoveNext()) repeated++;
            Require(count == repeated, "enumerator reset");
        }
        Require(typeof(AIEnvThings.Enumerator).IsValueType, "fast enumerator must remain concrete struct");
        Require(!typeof(AIEnvThings.AIThingEnum).IsValueType, "legacy public enumerator class changed");
        Console.WriteLine("concrete and legacy enumerators preserve filtering, order and reset: PASS");
    }
    static void Main() { Sight(); Enumerators(); }
}
"""


def main():
    root = Path(__file__).resolve().parents[1]
    source_root = root / "Source/Rule56"
    sight = (source_root / "SightGrid.cs").read_text()
    harness = HARNESS.replace("/* CANDIDATE */", block(sight, "private struct SpottingCandidate"))
    harness = harness.replace("/* NOTIFY */", block(sight, "private void NotifySpottings("))
    harness = harness.replace("/* EXPAND */", block(sight, "private void ExpandSpottingBucket("))
    with tempfile.TemporaryDirectory(prefix="cai-pawn-sight-") as temporary:
        directory = Path(temporary)
        program, executable = directory / "PawnSight.cs", directory / "PawnSight.exe"
        program.write_text(harness)
        sources = [source_root / "Data" / name for name in ("AIEnvThings.cs", "AIEnvAgentInfo.cs", "AIEnvAgentState.cs")]
        subprocess.run(["mcs", "-langversion:latest", "-warn:0", "-out:" + str(executable), str(program), *map(str, sources)], check=True)
        subprocess.run(["mono", str(executable)], check=True, timeout=20)


if __name__ == "__main__":
    main()
