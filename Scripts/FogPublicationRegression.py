#!/usr/bin/env python3
"""Exercise production fog publication, settling, and native writes with mcs/mono."""
from pathlib import Path
import subprocess
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
using System.Linq.Expressions;
using System.Reflection;
using System.Threading;
struct NativeBuffer {
    public bool[] Data;
    public void Set(int index, bool value) { Data[index] = value; }
}
class FogGrid { private NativeBuffer fogGrid; public FogGrid(bool[] data) { Replace(data); } public void Replace(bool[] data) { fogGrid = new NativeBuffer { Data=data }; } }
class Map { public readonly FogGrid fogGrid; public Map(bool[] data) { fogGrid = new FogGrid(data); } }
class Material {
    public int Uploads;
    public float Value;
    public Action DuringUpload;
    public void SetFloatArray(string name, float[] cells) { Uploads++; Value=cells[0]; if (DuringUpload != null) DuringUpload(); }
}
class Fog {
    readonly int mapSizeX=51, mapSizeZ=51;
    public readonly object fogLock = new object();
    public int stateRevision;
    public readonly Map map;
        Action<int,bool> _nativeFogWriter;
    public Fog(bool[] data) { map = new Map(data); }
    /* INDEX */
    /* WRITE */
    public int Index(int x, int z) { return CellIndexOrInvalid(x,z); }
    public void Write(int index, bool value) { WriteNativeFogBit(index,value); }
    public class RenderSection {
        public readonly Fog comp;
        public readonly Material mat = new Material();
        public readonly float[] cells = new float[256];
        public volatile bool dirty=true;
        public bool clear;
        public volatile int settledRevision=-1;
        bool stateChanged;
        public RenderSection(Fog comp) { this.comp=comp; }
        public bool NextChanged, NextStateChanged;
        public int NextIndex;
        public float NextValue;
        bool UpdateLocked() { stateChanged=NextStateChanged; if (NextChanged) cells[NextIndex]=NextValue; return NextChanged; }
        /* UPDATE */
        /* APPLY */
    }
}
class Program {
    static void Assert(bool value, string message) { if (!value) throw new Exception(message); }
    static void Main() {
        var data = new bool[2601];
        var fog = new Fog(data);
        // A 51-cell map leaves three cells in its last CAI 16-cell section.
        Assert(fog.Index(50,50)==2600 && fog.Index(51,0)==-1 && fog.Index(0,51)==-1, "partial section padding aliases valid cells");
        Assert(fog.Index(-1,1)==-1 && fog.Index(51,1)==-1 && fog.Index(0,1)==51, "neighbor row wraps at map edge");
        Console.WriteLine("partial edge sections and row boundaries: PASS");
        fog.Write(4,true); Assert(data[4], "native true write failed");
        fog.Write(4,false); Assert(!data[4], "native false write failed");
        var replacement = new bool[2601]; fog.map.fogGrid.Replace(replacement);
        fog.Write(5,true); Assert(replacement[5] && !data[5], "writer retained replaced native storage");
        Console.WriteLine("cached native writer follows field replacement: PASS");
        var section = new Fog.RenderSection(fog);
        section.NextChanged=true; section.NextValue=0.25f; section.Update();
        section.NextChanged=false; section.Update(); section.ApplyFogged(); section.ApplyFogged();
        Assert(section.mat.Uploads==1 && section.mat.Value==0.25f, "unchanged render data uploaded twice");
        var attempting = new ManualResetEvent(false);
        var updated = new ManualResetEvent(false);
        Thread worker = null;
        section.dirty=true;
        section.mat.DuringUpload = () => {
            worker = new Thread(() => { attempting.Set(); lock(fog.fogLock) { section.cells[0]=0.75f; section.dirty=true; } updated.Set(); });
            worker.Start(); attempting.WaitOne();
            Assert(!updated.WaitOne(20), "worker modified cells during upload");
        };
        section.ApplyFogged(); worker.Join(); section.mat.DuringUpload=null;
        Assert(section.dirty, "worker publication lost when upload cleared dirty");
        section.ApplyFogged();
        Assert(section.mat.Value==0.75f && !section.dirty && section.mat.Uploads==3, "latest worker publication not uploaded");
        Console.WriteLine("synchronized render publication and upload only on change: PASS");
        var clearing = new Fog.RenderSection(fog);
        clearing.ApplyFogged();
        Assert(clearing.clear, "all-zero upload not marked clear");
        clearing.NextChanged=true; clearing.NextIndex=255; clearing.NextValue=0.5f; clearing.Update(); clearing.ApplyFogged();
        Assert(!clearing.clear, "upload with fog in the last cell marked clear");
        clearing.NextValue=0f; clearing.Update(); clearing.ApplyFogged();
        Assert(clearing.clear, "upload back to all zero not marked clear");
        Console.WriteLine("clear flag follows the uploaded cells: PASS");
        var settling = new Fog.RenderSection(fog);
        fog.stateRevision=7;
        settling.NextChanged=true; settling.Update();
        Assert(settling.settledRevision==-1, "section settled on a pass that changed cells");
        settling.NextChanged=false; settling.NextStateChanged=true; settling.Update();
        Assert(settling.settledRevision==-1, "section settled on a pass that changed fog state");
        settling.NextStateChanged=false; settling.Update();
        Assert(settling.settledRevision==7, "unchanged pass did not settle at the current revision");
        fog.stateRevision++;
        Assert(settling.settledRevision!=fog.stateRevision, "revision bump left section settled");
        Console.WriteLine("sections settle only after a pass with no changes: PASS");
    }
}
'''


def main():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'Source/Rule56/MapComponent_FogGrid.cs').read_text()
    code = HARNESS.replace('/* INDEX */', method(source, 'private int CellIndexOrInvalid('))
    code = code.replace('/* WRITE */', method(source, 'private void WriteNativeFogBit('))
    code = code.replace('/* UPDATE */', method(source, 'public void Update()'))
    code = code.replace('/* APPLY */', method(source, 'public void ApplyFogged()'))
    with tempfile.TemporaryDirectory(prefix='cai-fog-publication-') as temporary:
        program = Path(temporary) / 'Regression.cs'
        executable = Path(temporary) / 'Regression.exe'
        program.write_text(code)
        subprocess.run(['mcs', '-warn:0', '-out:' + str(executable), str(program)], check=True)
        subprocess.run(['mono', str(executable)], check=True, timeout=20)


if __name__ == '__main__':
    main()
