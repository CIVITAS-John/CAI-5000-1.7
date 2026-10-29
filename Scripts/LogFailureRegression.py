#!/usr/bin/env python3
"""Exercise production pawn-loading, fresh settings, and dynamic job-stack handling."""
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
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using CombatAI;
using RimWorld;
using Verse;
namespace RimWorld {
 public enum TechLevel { Undefined, Animal, Neolithic, Medieval, Industrial, Spacer, Ultra, Archotech }
 public class Faction { public Pawn leader; public Def def=new Def(); }
}
namespace Verse {
 public interface IExposable { void ExposeData(); }
 public class Def { public string defName="test"; public TechLevel techLevel=TechLevel.Industrial; }
 public struct IntVec3 { public static IntVec3 Invalid; public bool IsValid => false; public float DistanceTo(IntVec3 value) => 0; }
 public class Thing { public Faction Faction; public int PersonalityReads; public bool FailPersonality; public PersonalityTacker.PersonalityResult GetCombatPersonality() { PersonalityReads++; if(FailPersonality || Scribe.mode!=LoadSaveMode.Saving) throw new Exception("personality unavailable"); return default; } }
 public class RaceProperties { public bool Animal; }
 public class Pawn : Thing { public RaceProperties RaceProps=new RaceProperties(); public IntVec3 Position; public MindState mindState; }
 public class MindState { public Duty duty; } public class Duty { public Def def; }
 public class Root { public void Update() {} }
 public enum LoadSaveMode { Inactive, LoadingVars, ResolvingCrossRefs, PostLoadInit, Saving }
 public static class Scribe { public static LoadSaveMode mode; }
 public static class Scribe_Values { public static void Look<T>(ref T value,string key,T fallback=default) {} }
 public static class Scribe_Deep { public static List<string> Keys=new List<string>(); public static Dictionary<string,object> Values=new Dictionary<string,object>(); public static string FailKey; public static void Look<T>(ref T value,string key) { Keys.Add(key); if(key==FailKey) throw new InvalidOperationException("serialization unavailable"); Values[key]=value; } }
 public static class Scribe_TargetInfo { public static void Look(ref object target,string key) {} }
 public enum LookMode { Deep }
 public static class Scribe_Collections { public static object Loaded; public static void Look<T>(ref List<T> value,string key,LookMode mode) { value=(List<T>)Loaded; } }
 public static class Log { public static List<string> Warnings=new List<string>(); public static void Warning(string s) { Warnings.Add(s); } public static void Error(string s) {} public static void ErrorOnce(string s,int key) {} }
 public static class GenTicks { public static int TicksGame; }
 public static class Extensions { public static string Formatted(this string format,params object[] args) => string.Format(format,args); public static bool NullOrEmpty<T>(this List<T> list) => list==null || list.Count==0; }
}
namespace Verse.AI {
 public class ThinkNode {}
 public class Job { public Def def=new Def(); public int loadID; public Target targetA; }
 public class Target { public bool IsValid => false; public IntVec3 Cell; }
}
namespace CombatAI {
 public static class Finder { public static Settings Settings=new Settings(); }
 public static class ThinkNodeDatabase { public static void GetTrace(Verse.AI.ThinkNode node,Pawn pawn,List<string> trace) {} }
 public class Settings {
  const int version=15; public bool Debug=true, Debug_LogJobs=true, Personalities_Enabled=true;
  SETTINGS_FIELDS
  SETTINGS_CTOR
  GET_TECH
  RESET_TECH
  TECH_CLASS
  public void LoadTechSettings() { LOAD_TECH }
 }
 public class PersonalityTacker {
  public struct PersonalityResult { public float Value; public static PersonalityResult Default => new PersonalityResult{Value=1}; public static PersonalityResult From(Settings.FactionTechSettings s) => new PersonalityResult{Value=s.duck}; public static PersonalityResult operator *(PersonalityResult a,float x) => a; public static PersonalityResult operator +(PersonalityResult a,PersonalityResult b) => a; }
  GET_THING
  GET_FACTION
  PersonalityResult GetPawnPersonality(Pawn pawn) { throw new Exception("unexpected leader personality"); }
  PersonalityResult GetFactionPersonality(Faction faction) { throw new Exception("unexpected faction personality"); }
 }
 class AIAgentData {}
 class Pawn_CustomDutyTracker { public Pawn pawn; public Pawn_CustomDutyTracker(Pawn p) { pawn=p; } }
 class Pawn_AbilityCaster { public Pawn pawn; public Pawn_AbilityCaster(Pawn p) { pawn=p; } }
 class CompBase { public virtual void PostExposeData() {} }
 class TestComp : CompBase {
  public Thing parent=new Thing(); public Pawn selPawn=new Pawn(); public AIAgentData data;
  public Pawn_CustomDutyTracker duties; public Pawn_AbilityCaster abilities; public object forcedTarget;
  public bool aiAutoControl,aiSearchAndDestroy,aiSearchAndDestroyMelee;
  POST_EXPOSE
 }
}
class FakeFrame : StackFrame { MethodBase method; public FakeFrame(MethodBase m) { method=m; } public override MethodBase GetMethod() => method; }
class FakeTrace : StackTrace { StackFrame[] frames; public FakeTrace(params StackFrame[] f) { frames=f; } public override StackFrame[] GetFrames() => frames; }
class Program {
 static void Check(bool ok,string name) { if(!ok) throw new Exception(name); }
 public static void Ordinary() {}
 static void Main() {
  var settings=Finder.Settings;
  foreach(TechLevel tech in Enum.GetValues(typeof(TechLevel))) Check(settings.GetTechSettings(tech).tech==tech,"fresh settings cover every tech level");
  Check(settings.GetTechSettings(TechLevel.Animal).duck!=settings.GetTechSettings(TechLevel.Industrial).duck,"fresh settings retain tech differences");
  var saved=Enum.GetValues<TechLevel>().Select(settings.GetTechSettings).ToList(); saved[0].duck=0.372f;
  Scribe_Collections.Loaded=saved; settings.LoadTechSettings(); Check(ReferenceEquals(settings.GetTechSettings(TechLevel.Undefined),saved[0]) && saved[0].duck==0.372f,"loaded custom settings survive");
  var tracker=new PersonalityTacker();
  Check(tracker.GetPersonality((Faction)null).Value==saved[0].duck,"null faction fallback");
  Check(tracker.GetPersonality(new Thing()).Value==saved[0].duck,"factionless thing fallback");
  var faction=new Faction(); Check(tracker.GetPersonality(faction).Value==settings.GetTechSettings(faction.def.techLevel).duck,"ordinary faction settings");
  foreach(var mode in new[]{LoadSaveMode.LoadingVars,LoadSaveMode.ResolvingCrossRefs,LoadSaveMode.PostLoadInit}) {
   Scribe.mode=mode; var comp=new TestComp(); Scribe_Deep.Keys.Clear(); comp.PostExposeData();
   Check(comp.parent.PersonalityReads==0,"loading never reads diagnostic personality");
   Check(comp.data!=null && comp.duties.pawn==comp.selPawn && comp.abilities.pawn==comp.selPawn,"CAI load continues and wires trackers");
   Check(!Scribe_Deep.Keys.Contains("personality") && Scribe_Deep.Keys.Contains("AIAgentData.0"),"only persistent data read");
  }
  Scribe.mode=LoadSaveMode.Saving; var saving=new TestComp(); Scribe_Deep.Keys.Clear(); saving.PostExposeData();
  Check(saving.parent.PersonalityReads==1 && Scribe_Deep.Keys.Contains("personality"),"debug save still emits personality");
  var failed=new TestComp(); failed.parent.FailPersonality=true; Scribe_Deep.Keys.Clear(); Scribe_Deep.Values.Clear(); Log.Warnings.Clear(); failed.PostExposeData();
  Check(Log.Warnings.Count==1 && Scribe_Deep.Keys.Contains("AIAgentData.0") && Scribe_Deep.Keys.Contains("duties2"),"failed diagnostic personality cannot interrupt persistent pawn save");
  Check(Scribe_Deep.Values.TryGetValue("personality",out object fallback) && ((PersonalityTacker.PersonalityResult)fallback).Value==PersonalityTacker.PersonalityResult.Default.Value,"failed personality lookup serializes the diagnostic fallback");
  Scribe_Deep.Keys.Clear(); Log.Warnings.Clear(); Scribe_Deep.FailKey="personality"; bool serializationFailed=false;
  try { new TestComp().PostExposeData(); }
  catch(InvalidOperationException ex) { serializationFailed=ex.Message=="serialization unavailable"; }
  finally { Scribe_Deep.FailKey=null; }
  Check(serializationFailed && Log.Warnings.Count==0 && !Scribe_Deep.Keys.Contains("AIAgentData.0"),"real serialization failure propagates without a misleading lookup warning");
  var dynamicMethod=new DynamicMethod("HarmonyGeneratedJob",typeof(void),Type.EmptyTypes);
  Check(dynamicMethod.DeclaringType==null,"dynamic method has no declaring type");
  var capture=typeof(JobLog).GetMethod("CaptureStackTrace",BindingFlags.Static|BindingFlags.NonPublic);
  var ordinary=typeof(Program).GetMethod("Ordinary");
  var frames=(List<string>)capture.Invoke(null,new object[]{new FakeTrace(new FakeFrame(null),new FakeFrame(dynamicMethod),new FakeFrame(ordinary),new FakeFrame(typeof(Root).GetMethod("Update")),new FakeFrame(ordinary))});
  Check(frames.Count==2 && frames[0]==dynamicMethod.Name && frames[1].Contains("Ordinary"),"unknown frames skipped, dynamic names retained, trace stops at Root");
  var pawn=new Pawn(); var job=new Verse.AI.Job{targetA=new Verse.AI.Target()};
  Check(JobLog.For(pawn,job,(Verse.AI.ThinkNode)null).stacktrace.Count>0,"thinknode overload records stack");
  Check(JobLog.For(pawn,job,"ordered").stacktrace.Count>0,"tag overload records stack");
  Console.WriteLine("PASS: factionless personality, load/save diagnostics and diagnostic failure recovery, fresh/custom tech settings, dynamic/unknown job frames and both job-log callers");
 }
}
'''
settings=(SOURCE/'Settings.cs').read_text(encoding='utf-8-sig')
expose=block(settings,'public override void ExposeData()')
replacements={
 'SETTINGS_FIELDS':'\n'.join(line for line in settings.splitlines() if 'private ' in line and (' FactionSettings ' in line or ' FactionSettings_Undefined ' in line)),
 'SETTINGS_CTOR':block(settings,'public Settings()'),
 'GET_TECH':block(settings,'public FactionTechSettings GetTechSettings('),
 'RESET_TECH':block(settings,'public void ResetTechSettings()'),
 'TECH_CLASS':block(settings,'public class FactionTechSettings'),
 'LOAD_TECH':expose[expose.index('Scribe_Collections.Look(ref FactionSettings'):expose.rfind('}')],
 'GET_THING':block((SOURCE/'PersonalityTacker.cs').read_text(),'public PersonalityResult GetPersonality(Thing thing)'),
 'GET_FACTION':block((SOURCE/'PersonalityTacker.cs').read_text(),'public PersonalityResult GetPersonality(Faction faction)'),
 'POST_EXPOSE':block((SOURCE/'Comps/ThingComp_CombatAI.cs').read_text(),'public override void PostExposeData()'),
}
for marker,value in replacements.items():
    harness=harness.replace(marker,value)
with tempfile.TemporaryDirectory(prefix='cai-log-failures-') as tmp:
    tmp=Path(tmp)
    (tmp/'Harness.cs').write_text(harness)
    (tmp/'JobLog.cs').write_text((SOURCE/'Debugging/JobLog.cs').read_text())
    (tmp/'Regression.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>')
    env = dict(os.environ, DOTNET_CLI_HOME=str(tmp), DOTNET_NOLOGO='1', DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1', DOTNET_CLI_TELEMETRY_OPTOUT='1')
    subprocess.run(['dotnet','run','--project',str(tmp/'Regression.csproj'),'--verbosity','quiet'],check=True,env=env)
