#!/usr/bin/env python3
"""Check that a fog section update matches a reference version bit for bit (requires csc, mono and git).

Usage: python3 Scripts/FogBlurRegression.py [reference-revision]
Runs ISection.UpdateLocked from the working tree and from the reference revision (default HEAD) on the
same randomized sight, wall, glow, fog-state and temporary-reveal inputs, then compares every pass.
"""
from pathlib import Path
import subprocess
import sys
import tempfile


def method(source, signature):
    start = source.index(signature)
    opening = source.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


HARNESS = r'''
using System;
using System.Collections.Generic;
using System.Text;
using System.Threading;
namespace CombatAI.Compatibility {
    static class GlowGridCompat { public static CombatAI.ColorInt[] GetGlowGrid(object glow) { return ((CombatAI.GlowGrid)glow).Data; } }
}
namespace CombatAI {
struct ColorInt { public int r, g, b; }
struct Vector3 { public float x, y, z; public Vector3(float x, float y, float z) { this.x=x; this.y=y; this.z=z; } }
struct IntVec3 {
    public int x, y, z;
    public IntVec3(int x, int y, int z) { this.x=x; this.y=y; this.z=z; }
    public static IntVec3 operator +(IntVec3 a, IntVec3 b) { return new IntVec3(a.x+b.x, a.y+b.y, a.z+b.z); }
}
static class Extensions { public static IntVec3 ToIntVec3(this Vector3 v) { return new IntVec3((int)v.x, (int)v.y, (int)v.z); } }
static class Mathf {
    public static float Max(float a, float b) { return Math.Max(a, b); }
    public static float Clamp01(float v) { return Math.Min(Math.Max(v, 0f), 1f); }
    public static float Lerp(float a, float b, float t) { t = Clamp01(t); return a + (b - a) * t; }
}
static class Maths {
    public static float Max(float a, float b) { return a > b ? a : b; }
    public static int Max(int a, int b) { return a > b ? a : b; }
    public static float Min(float a, float b) { return a < b ? a : b; }
}
static class GenTicks { public static int TicksGame; }
enum CellFogState : byte { VanillaExplored, VanillaUnexplored, CAIFogged }
struct CellIndices { public int NumGridCells; }
class GlowGrid { public ColorInt[] Data; }
class FogGrid { public bool[] Fogged; public bool IsFogged(int index) { return Fogged[index]; } }
class Map { public CellIndices cellIndices; public FogGrid fogGrid = new FogGrid(); }
class WallGrid { public bool[] Blocks; public bool CanBeSeenOver(int index) { return !Blocks[index]; } }
class ITFloatGrid { public float[] Values; public float Get(int index) { return Values[index]; } }
class SightGrid { public ITFloatGrid gridFog = new ITFloatGrid(); }
class Comp {
    const int SECTION_SIZE = 16;
    const int PADDED_SECTION_SIZE = SECTION_SIZE + 2;
    public readonly int mapSizeX, mapSizeZ;
    public Map map = new Map();
    public WallGrid walls;
    public SightGrid sight = new SightGrid();
    public GlowGrid glow = new GlowGrid();
    public float SkyGlow;
    public CellFogState[] fogState;
    public volatile bool _cachedIsPlayerHome;
    public volatile bool[] _indoorRoomCache;
    public volatile bool[] _indoorProtectCache;
    public int indoorRevision;
    public int ticksGame;
    public void QueueFogChange(int index) {}
    public Comp(int sizeX, int sizeZ) { mapSizeX = sizeX; mapSizeZ = sizeZ; map.cellIndices.NumGridCells = sizeX * sizeZ; }
    /* INDEX */
    public struct ITempCell { public byte u; public byte v; public float val; public int timestamp; public short duration; }
    public class Section {
        public readonly float[] cells = new float[256];
        public readonly List<ITempCell> extraCells = new List<ITempCell>();
        readonly float[] neighborVisibility = new float[PADDED_SECTION_SIZE * PADDED_SECTION_SIZE];
        readonly Comp comp;
        readonly Vector3 pos;
        bool stateChanged;
        public Section(Comp comp, int u, int v) { this.comp = comp; pos = new Vector3(u * SECTION_SIZE, 0, v * SECTION_SIZE); }
        public bool Run() { return UpdateLocked(); }
        /* UPDATE */
    }
}
static class Program {
    static void Fill(Random random, Comp comp, bool withWalls, bool home) {
        int count = comp.mapSizeX * comp.mapSizeZ;
        var values = new float[count];
        for (int i = 0; i < count; i++) {
            double roll = random.NextDouble();
            values[i] = roll < 0.4 ? 0f : roll < 0.5 ? 1f : (float)(random.NextDouble() * 1.3);
        }
        comp.sight.gridFog.Values = values;
        var glow = new ColorInt[count];
        for (int i = 0; i < count; i++) glow[i] = new ColorInt { r = random.Next(256), g = random.Next(256), b = random.Next(256) };
        comp.glow.Data = glow;
        if (withWalls) {
            var blocks = new bool[count];
            for (int i = 0; i < count; i++) blocks[i] = random.NextDouble() < 0.2;
            comp.walls = new WallGrid { Blocks = blocks };
        } else comp.walls = null;
        var vanilla = new bool[count];
        for (int i = 0; i < count; i++) vanilla[i] = random.NextDouble() < 0.3;
        comp.map.fogGrid.Fogged = vanilla;
        comp._cachedIsPlayerHome = home;
        var indoor = new bool[count];
        var protect = new bool[count];
        for (int i = 0; i < count; i++) { indoor[i] = random.NextDouble() < 0.1; protect[i] = random.NextDouble() < 0.1; }
        comp._indoorRoomCache = indoor;
        comp._indoorProtectCache = protect;
    }
    static int Main() {
        var random = new Random(56);
        var output = new StringBuilder();
        int scenario = 0;
        foreach (int size in new[] { 40, 48 })
        foreach (bool withWalls in new[] { true, false })
        foreach (bool home in new[] { false, true })
        foreach (float sky in new[] { 0.2f, 1f }) {
            var comp = new Comp(size, size);
            comp.SkyGlow = sky;
            comp.fogState = new CellFogState[size * size];
            for (int i = 0; i < comp.fogState.Length; i++) comp.fogState[i] = (CellFogState)random.Next(3);
            int sections = (size + 15) / 16;
            var grid = new Comp.Section[sections, sections];
            for (int u = 0; u < sections; u++) for (int v = 0; v < sections; v++) grid[u, v] = new Comp.Section(comp, u, v);
            for (int pass = 0; pass < 6; pass++) {
                Fill(random, comp, withWalls, home);
                GenTicks.TicksGame = comp.ticksGame = 1000 + pass * 10;
                foreach (var section in grid) {
                    section.extraCells.Clear();
                    for (int k = random.Next(4); k > 0; k--)
                        section.extraCells.Add(new Comp.ITempCell { u = (byte)random.Next(16), v = (byte)random.Next(16), val = (float)random.NextDouble(), timestamp = comp.ticksGame - random.Next(60), duration = (short)random.Next(20, 90) });
                }
                long hash = 17;
                for (int u = 0; u < sections; u++)
                for (int v = 0; v < sections; v++) {
                    bool changed = grid[u, v].Run();
                    hash = hash * 31 + (changed ? 1 : 0);
                    foreach (float cell in grid[u, v].cells) hash = hash * 31 + BitConverter.ToInt32(BitConverter.GetBytes(cell), 0);
                }
                foreach (CellFogState state in comp.fogState) hash = hash * 31 + (int)state;
                hash = hash * 31 + comp.indoorRevision;
                output.AppendLine("scenario " + scenario + " size=" + size + " walls=" + withWalls + " home=" + home + " sky=" + sky + " pass " + pass + ": " + hash);
            }
            scenario++;
        }
        Console.Write(output.ToString());
        return 0;
    }
}
}
'''


def run(source, directory, name):
    code = HARNESS.replace('/* INDEX */', method(source, 'private int CellIndexOrInvalid('))
    code = code.replace('/* UPDATE */', method(source, 'private bool UpdateLocked()'))
    program = directory / (name + '.cs')
    executable = directory / (name + '.exe')
    program.write_text(code)
    # UpdateLocked uses local functions, which mcs cannot compile.
    subprocess.run(['csc', '-nologo', '-warn:0', '-out:' + str(executable), str(program)], check=True)
    return subprocess.run(['mono', str(executable)], check=True, timeout=60, capture_output=True, text=True).stdout.splitlines()


def main():
    root = Path(__file__).resolve().parents[1]
    reference = sys.argv[1] if len(sys.argv) > 1 else 'HEAD'
    current = (root / 'Source/Rule56/MapComponent_FogGrid.cs').read_text()
    previous = subprocess.run(['git', 'show', reference + ':Source/Rule56/MapComponent_FogGrid.cs'], cwd=root, check=True, capture_output=True, text=True).stdout
    with tempfile.TemporaryDirectory(prefix='cai-fog-blur-') as temporary:
        directory = Path(temporary)
        expected = run(previous, directory, 'Reference')
        actual = run(current, directory, 'Current')
    mismatches = [(e, a) for e, a in zip(expected, actual) if e != a]
    if len(expected) != len(actual) or mismatches or not expected:
        for e, a in mismatches[:5]:
            print('expected ' + e + '\n  actual ' + a)
        print('section updates match ' + reference + ': FAIL')
        return 1
    print('section updates match ' + reference + ' over ' + str(len(expected)) + ' randomized passes: PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
