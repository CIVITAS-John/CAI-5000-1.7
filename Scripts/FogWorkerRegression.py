#!/usr/bin/env python3
"""Run the production fog worker against lightweight sections (requires mcs and mono).

Usage: python3 Scripts/FogWorkerRegression.py [path/to/MapComponent_FogGrid.cs]
The optional source path lets the same behavior check reproduce an older version.
"""

from pathlib import Path
import subprocess
import sys
import tempfile


def worker_method(source):
    start = source.index("private void OffThreadLoop()")
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
class Worker {
    const int SECTION_SIZE = 16;
    readonly object _lockerSpots = new object();
    readonly List<ITempSpot> spotsQueued = new List<ITempSpot>();
    readonly List<Vector3> spotBuffer = new List<Vector3>();
    readonly object map = new object();
    readonly AsyncActions asyncActions = new AsyncActions();
    readonly ISection[][] grid2d;
    public volatile bool alive = true;
    public volatile bool ready = true;
    public int Updates;
    int ticksGame, screenMinU, screenMinV, screenMaxU, screenMaxV, backgroundNextU, backgroundNextV;
    float tickRateMultiplier;
    public Worker(float multiplier, int delay) {
        tickRateMultiplier = multiplier;
        grid2d = new ISection[2][];
        for (int u = 0; u < 2; u++) {
            grid2d[u] = new ISection[2];
            for (int v = 0; v < 2; v++) grid2d[u][v] = new ISection(this, delay);
        }
    }
    public Thread Start() {
        var thread = new Thread(OffThreadLoop);
        thread.IsBackground = true;
        thread.Start();
        return thread;
    }
    public void KillAsync() { asyncActions.Alive = false; }
    class ISection {
        readonly Worker owner;
        readonly int delay;
        public readonly List<ITempCell> extraCells = new List<ITempCell>();
        public ISection(Worker owner, int delay) { this.owner = owner; this.delay = delay; }
        public void Update() {
            if (delay > 0) Thread.Sleep(delay);
            Interlocked.Increment(ref owner.Updates);
        }
    }
    struct ITempSpot { public IntVec3 center; public float radius; public int duration; }
    struct ITempCell { public byte u, v; public float val; public int timestamp; public short duration; }
    /* PRODUCTION_METHOD */
}
class Program {
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
    static int Main() {
        bool passed = Check("normal speed, fast sections", 1, 0, true);
        passed &= Check("triple speed, fast sections", 3, 0, true);
        passed &= Check("paused, fast sections", 0, 0, true);
        passed &= Check("normal speed, slow sections", 1, 3, true);
        passed &= Check("becomes ready after startup", 1, 0, false);
        passed &= Check("async shutdown stops worker", 1, 0, true, true);
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
        program.write_text(HARNESS.replace("/* PRODUCTION_METHOD */", worker_method(source.read_text())))
        subprocess.run(["mcs", "-warn:0", "-out:" + str(executable), str(program)], check=True)
        return subprocess.run(["mono", str(executable)], timeout=20).returncode


if __name__ == "__main__":
    sys.exit(main())
