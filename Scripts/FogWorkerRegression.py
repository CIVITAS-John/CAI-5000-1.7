#!/usr/bin/env python3
"""Run the production fog worker against lightweight sections (requires mcs and mono).

Usage: python3 Scripts/FogWorkerRegression.py [path/to/MapComponent_FogGrid.cs]
The optional source path lets the same behavior check reproduce an older version.
"""

from pathlib import Path
import subprocess
import sys
import tempfile


def worker_method(source, signature="private void OffThreadLoop()"):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


HARNESS = r"""
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading;

static class Mathf {
    public static int Clamp(int value, int min, int max) { return Math.Min(Math.Max(value, min), max); }
    public static int CeilToInt(float value) { return (int)Math.Ceiling(value); }
    public static int FloorToInt(float value) { return (int)Math.Floor(value); }
    public static float Clamp01(float value) { return Math.Min(Math.Max(value, 0f), 1f); }
}
struct Vector3 {}
struct IntVec3 {
    public int x, z;
    public bool InBounds(object map) { return true; }
    public float DistanceTo_Fast(IntVec3 other) { return 0; }
}
static class GenTicks { public static int TicksGame; }
static class Finder { public static readonly Settings Settings = new Settings(); }
class Settings { public bool FogOfWar_Enabled = true; }
class AsyncActions { public volatile bool Alive = true; }
static class ShadowCastingUtility {
    public static void CastWeighted(object map, IntVec3 center, Action<IntVec3, int, int, float> action,
        int radius, int carry, List<Vector3> buffer) {}
}
static class ListExtensions {
    public static T Pop<T>(this List<T> list) {
        int index = list.Count - 1;
        T value = list[index];
        list.RemoveAt(index);
        return value;
    }
}
class ITFloatGrid {
    public readonly HashSet<long> Hot = new HashSet<long>();
    public bool IsBlockCold(int bx, int bz) { return !Hot.Contains(((long)bx << 32) | (uint)bz); }
}
class Sight { public ITFloatGrid gridFog = new ITFloatGrid(); }
class Worker {
    const int SECTION_SIZE = 16;
    public int stateRevision;
    public Sight sight = new Sight();
    public bool Settle;
    readonly object _lockerSpots = new object();
    readonly object fogLock = new object();
    readonly List<ITempSpot> spotsQueued = new List<ITempSpot>();
    readonly List<Vector3> spotBuffer = new List<Vector3>();
    readonly object map = new object();
    readonly AsyncActions asyncActions = new AsyncActions();
    readonly ISection[][] grid2d;
    public volatile bool alive = true;
    public volatile bool ready = true;
    public int Updates;
    public static Worker Observed;
    public int StopAfterPasses;
    public int Passes;
    public bool Duplicate;
    public readonly HashSet<ISection> SeenThisPass = new HashSet<ISection>();
    public readonly HashSet<ISection> SeenEver = new HashSet<ISection>();
    public void BeginPass() {
        if (StopAfterPasses == 0) return;
        if (Passes++ >= StopAfterPasses) { alive = false; ready = false; }
        SeenThisPass.Clear();
    }
    int ticksGame, screenMinU, screenMinV, screenMaxU, screenMaxV, backgroundNextU, backgroundNextV;
    float tickRateMultiplier;
    public Worker(float multiplier, int delay, int size = 2) {
        tickRateMultiplier = multiplier;
        grid2d = new ISection[size][];
        for (int u = 0; u < size; u++) {
            grid2d[u] = new ISection[size];
            for (int v = 0; v < size; v++) grid2d[u][v] = new ISection(this, delay);
        }
    }
    public Thread Start() {
        var thread = new Thread(OffThreadLoop);
        thread.IsBackground = true;
        thread.Start();
        return thread;
    }
    public void KillAsync() { asyncActions.Alive = false; }
    public ISection Section(int u, int v) { return grid2d[u][v]; }
    public int Size { get { return grid2d.Length; } }
    // Runs the given number of passes on a fresh thread and returns per-section update counts.
    public int[,] RunPasses(int passes) {
        foreach (var column in grid2d) foreach (var section in column) section.Count = 0;
        alive = true; ready = true; Passes = 0; StopAfterPasses = passes;
        Observed = this;
        Thread thread = Start();
        bool stopped = thread.Join(1500);
        Observed = null;
        if (!stopped) { alive = false; thread.Join(500); return null; }
        var counts = new int[Size, Size];
        for (int u = 0; u < Size; u++) for (int v = 0; v < Size; v++) counts[u, v] = grid2d[u][v].Count;
        return counts;
    }
    public class ISection {
        readonly Worker owner;
        readonly int delay;
        public readonly List<ITempCell> extraCells = new List<ITempCell>();
        public volatile int settledRevision = -1;
        public int Count;
        public ISection(Worker owner, int delay) { this.owner = owner; this.delay = delay; }
        public void Update() {
            if (delay > 0) Thread.Sleep(delay);
            if (owner.StopAfterPasses > 0) {
                if (!owner.SeenThisPass.Add(this)) owner.Duplicate = true;
                owner.SeenEver.Add(this);
            }
            Interlocked.Increment(ref owner.Updates);
            Count++;
            if (owner.Settle) settledRevision = owner.stateRevision;
        }
    }
    struct ITempSpot { public IntVec3 center; public float radius; public int duration; }
    public struct ITempCell { public byte u, v; public float val; public int timestamp; public short duration; }
    /* PRODUCTION_METHOD */
    /* SETTLED_METHOD */
}
class PassStopwatch {
    readonly Stopwatch watch = new Stopwatch();
    public static long Frequency { get { return Stopwatch.Frequency; } }
    public long ElapsedTicks { get { return watch.ElapsedTicks; } }
    public void Restart() { watch.Restart(); if (Worker.Observed != null) Worker.Observed.BeginPass(); }
}
class Program {
    const bool HasSettledCheck = /* HAS_SETTLED */;
    static int? backgroundWork;
    static bool Coverage(float multiplier) {
        var worker = new Worker(multiplier, 0, 6);
        worker.StopAfterPasses = 4;
        Worker.Observed = worker;
        Thread thread = worker.Start();
        bool stopped = thread.Join(1500);
        Worker.Observed = null;
        bool bounded = worker.Updates > 4 * 4 && worker.Updates <= 4 * 36;
        bool stableBudget = !backgroundWork.HasValue || backgroundWork.Value == worker.Updates;
        backgroundWork = worker.Updates;
        bool passed = stopped && !worker.Duplicate && worker.SeenEver.Count == 36 && bounded && stableBudget;
        Console.WriteLine("unique updates and eventual offscreen refresh, multiplier=" + multiplier + ": " + (passed ? "PASS" : "FAIL")
            + " (updates=" + worker.Updates + ", sections=" + worker.SeenEver.Count + ", duplicate=" + worker.Duplicate + ")");
        if (!stopped) { worker.alive = false; thread.Join(500); }
        return passed;
    }
    static bool Check(string name, float multiplier, int delay, bool startReady, bool killAsync = false) {
        var worker = new Worker(multiplier, delay);
        worker.ready = startReady;
        Thread thread = worker.Start();
        if (!startReady) { Thread.Sleep(130); worker.ready = true; }
        var deadline = Stopwatch.StartNew();
        // More updates than the entire four-section grid can receive in one pass.
        while (Volatile.Read(ref worker.Updates) < 24 && deadline.ElapsedMilliseconds < 1500)
            Thread.Sleep(5);
        bool progressed = Volatile.Read(ref worker.Updates) >= 24;
        if (killAsync) worker.KillAsync();
        else worker.alive = false;
        bool stopped = thread.Join(500);
        Console.WriteLine(name + ": " + (progressed && stopped ? "PASS" : "FAIL")
            + " (updates=" + worker.Updates + ", stopped=" + stopped + ")");
        if (!stopped) { thread.Abort(); thread.Join(500); }
        return progressed && stopped;
    }
    static bool Expect(int[,] counts, Func<int, int, int> expected, string name) {
        bool passed = counts != null;
        string detail = counts == null ? "worker did not stop" : "";
        for (int u = 0; passed && u < counts.GetLength(0); u++)
            for (int v = 0; passed && v < counts.GetLength(1); v++)
                if (counts[u, v] != expected(u, v)) { passed = false; detail = "section " + u + "," + v + " updated " + counts[u, v] + " times, expected " + expected(u, v); }
        Console.WriteLine(name + ": " + (passed ? "PASS" : "FAIL") + (detail.Length > 0 ? " (" + detail + ")" : ""));
        return passed;
    }
    static bool Settling() {
        // Six passes cover all 36 sections with the 16-section background budget.
        var worker = new Worker(1, 0, 6);
        worker.Settle = true;
        bool passed = Expect(worker.RunPasses(6), (u, v) => 1, "settled cold sections update once, then skip");
        worker.stateRevision++;
        passed &= Expect(worker.RunPasses(6), (u, v) => 1, "state revision wakes every section once");
        worker.sight.gridFog.Hot.Add((2L << 32) | 2);
        passed &= Expect(worker.RunPasses(4), (u, v) => Math.Abs(u - 2) <= 1 && Math.Abs(v - 2) <= 1 ? 4 : 0, "sight on a block keeps it and its neighbors updating");
        worker.sight.gridFog.Hot.Clear();
        worker.RunPasses(6);
        worker.Section(5, 5).extraCells.Add(new Worker.ITempCell());
        passed &= Expect(worker.RunPasses(4), (u, v) => u == 5 && v == 5 ? 4 : 0, "pending temporary reveals keep a section updating");
        return passed;
    }
    static int Main() {
        bool passed = Check("normal speed, fast sections", 1, 0, true);
        passed &= Check("triple speed, fast sections", 3, 0, true);
        passed &= Check("paused, fast sections", 0, 0, true);
        passed &= Check("normal speed, slow sections", 1, 3, true);
        passed &= Check("becomes ready after startup", 1, 0, false);
        passed &= Check("async shutdown stops worker", 1, 0, true, true);
        passed &= Coverage(0);
        passed &= Coverage(1);
        passed &= Coverage(3);
        if (HasSettledCheck) passed &= Settling();
        return passed ? 0 : 1;
    }
}
"""


def main():
    root = Path(__file__).resolve().parents[1]
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "Source/Rule56/MapComponent_FogGrid.cs"
    with tempfile.TemporaryDirectory(prefix="cai-fog-regression-") as temporary:
        directory = Path(temporary)
        program = directory / "FogWorkerRegression.cs"
        executable = directory / "FogWorkerRegression.exe"
        text = source.read_text()
        # Older sources predate settled-section skipping; run only the checks they support.
        has_settled = "private bool IsSettled(" in text
        harness = HARNESS.replace("/* PRODUCTION_METHOD */", worker_method(text).replace("Stopwatch", "PassStopwatch"))
        harness = harness.replace("/* SETTLED_METHOD */", worker_method(text, "private bool IsSettled(") if has_settled else "")
        program.write_text(harness.replace("/* HAS_SETTLED */", "true" if has_settled else "false"))
        subprocess.run(["mcs", "-warn:0", "-out:" + str(executable), str(program)], check=True)
        return subprocess.run(["mono", str(executable)], timeout=20).returncode


if __name__ == "__main__":
    sys.exit(main())
