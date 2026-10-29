#!/usr/bin/env python3
"""Exercise recovered settings migration and quick setup with production C# code."""
from pathlib import Path
import os
import subprocess
import tempfile


SOURCE = Path(__file__).resolve().parents[1] / "Source/Rule56"


def block(source, marker):
    start = source.index(marker)
    opening = source.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


HARNESS = r'''
using System;
using System.Collections.Generic;
using System.Linq;
using CombatAI;
using CombatAI.Gui;
using CombatAI.R;
using RimWorld;
using UnityEngine;
using Verse;

namespace UnityEngine {
    public struct Rect {
        public float height, yMin;
        public Rect TopPartPixels(float size) { return new Rect { height = size }; }
        public Rect BottomPartPixels(float size) { return new Rect { height = size }; }
        public Rect TopHalf() { return new Rect { height = height / 2 }; }
        public Rect BottomHalf() { return TopHalf(); }
    }
    public struct Color { public static Color green, red; }
    public static class GUI { public static Color color; }
    public enum TextAnchor { MiddleCenter, MiddleLeft }
}
namespace RimWorld {
    public enum TechLevel { Undefined, Animal, Neolithic, Medieval, Industrial, Spacer, Ultra, Archotech }
    public static class MessageTypeDefOf { public static readonly object RejectInput = new object(); }
}
namespace Verse {
    public interface IExposable { void ExposeData(); }
    public class ModSettings { public int Writes; public virtual void ExposeData() {} public void Write() { Writes++; } }
    public class ThingDef { public string defName = "Human"; }
    public class PawnKindDef { public string defName = "Colonist"; }
    public class Pawn { public ThingDef def = new ThingDef(); public PawnKindDef kindDef = new PawnKindDef(); }
    public enum LoadSaveMode { Inactive, LoadingVars, Saving }
    public enum LookMode { Undefined, Deep }
    public static class Scribe {
        public static LoadSaveMode mode;
        public static readonly Dictionary<string, object> Values = new Dictionary<string, object>();
    }
    public static class Scribe_Values {
        public static void Look<T>(ref T value, string name, T defaultValue = default(T)) {
            if (Scribe.mode == LoadSaveMode.LoadingVars) {
                value = Scribe.Values.TryGetValue(name, out object stored) ? (T)stored : defaultValue;
            } else if (Scribe.mode == LoadSaveMode.Saving) {
                Scribe.Values[name] = value;
            }
        }
    }
    public static class Scribe_Deep { public static void Look<T>(ref T value, string name) {} }
    public static class Scribe_Collections { public static void Look<T>(ref T value, string name, LookMode mode = LookMode.Undefined) {} }
    public static class Log { public static void Warning(string text) {} public static void Error(string text) { throw new Exception(text); } }
    public static class ListExtensions { public static bool NullOrEmpty<T>(this List<T> list) { return list == null || list.Count == 0; } }
    public class Window { public virtual void DoWindowContents(Rect rect) {} }
    public enum GameFont { Small }
    public static class Text { public static GameFont Font; }
    public static class Widgets {
        public static void Label(Rect rect, string text) {}
        public static bool ButtonText(Rect rect, string text) { return text == Keyed.CombatAI_Apply; }
    }
    public static class Messages { public static int Rejected; public static void Message(string text, object type) { Rejected++; } }
}
namespace CombatAI {
    public static class Finder { public static Settings Settings; }
}
namespace CombatAI.R {
    public static class Keyed {
        public const string CombatAI_Quick_Welcome = "welcome", CombatAI_Quick_Welcome_Description = "welcome description";
        public const string CombatAI_Quick_QuickSetup = "setup", CombatAI_Quick_Difficulty = "difficulty", CombatAI_Apply = "apply";
        public const string CombatAI_Settings_Basic_PerformanceOpt = "performance", CombatAI_Settings_Basic_RandomizedPersonality = "personality";
        public const string CombatAI_Settings_Basic_Sprinting = "sprint", CombatAI_Settings_Basic_Sprinting_Description = "sprint description";
        public const string CombatAI_Settings_Basic_FogOfWar = "fog";
    }
}
namespace CombatAI.Gui {
    public enum GUIFontSize { Medium, Small }
    public static class GUIFont { public static TextAnchor Anchor; public static GUIFontSize Font; }
    public static class GUIUtility { public static void ExecuteSafeGUIAction(Action action) { action(); } }
    public class Listing_Collapsible {
        public bool Expanded;
        public void Begin(Rect rect, string title, bool drawIcon = true) {}
        public void Label(string text) {}
        public void Lambda(float height, Action<Rect> action) { action(new Rect()); }
        public void Line(float height) {}
        public void CheckboxLabeled(string text, ref bool value, string tooltip = null) {}
        public void End(ref Rect rect) {}
    }
    public class Window_QuickSetup : Window {
        readonly Listing_Collapsible collapsible = new Listing_Collapsible();
        readonly Listing_Collapsible collapsible_fogOfWar = new Listing_Collapsible();
        bool presetSelected;
        public bool Closed;
        public Window_QuickSetup(bool hasPreset) { presetSelected = hasPreset; }
        void DoSelected(Rect rect) {}
        void DoDifficultySettings(Rect rect) {}
        void FillCollapsible_FogOfWar(Listing_Collapsible listing) {}
        void Close() { Closed = true; }
        QUICK_SETUP_CONTENTS
    }
}
class Program {
    static void Check(bool condition, string message) { if (!condition) throw new Exception(message); }
    static void EnableDiagnostics(Settings settings) {
        settings.AdvancedUser = settings.Debug = settings.Debug_LogJobs = true;
        settings.Debug_DebugDumpData = settings.Debug_DebugThingsTracker = true;
        settings.Debug_DrawAvoidanceGrid_Danger = settings.Debug_DrawAvoidanceGrid_Proximity = true;
        settings.Debug_DrawShadowCasts = settings.Debug_DrawShadowCastsVectors = settings.Debug_DrawThreatCasts = true;
        settings.Debug_DisablePawnGuiOverlay = settings.Debug_DebugPathfinding = settings.Debug_DebugAvailability = settings.Debug_ValidateSight = true;
    }
    static void CheckDiagnosticsReset(Settings settings) {
        Check(!settings.AdvancedUser && !settings.Debug && !settings.Debug_LogJobs, "advanced and logging reset");
        Check(!settings.Debug_DebugDumpData && !settings.Debug_DebugThingsTracker && !settings.Debug_DrawAvoidanceGrid_Danger && !settings.Debug_DrawAvoidanceGrid_Proximity, "diagnostic output reset");
        Check(!settings.Debug_DrawShadowCasts && !settings.Debug_DrawShadowCastsVectors && !settings.Debug_DrawThreatCasts && !settings.Debug_DisablePawnGuiOverlay, "overlay options reset");
        Check(!settings.Debug_DebugPathfinding && !settings.Debug_DebugAvailability && !settings.Debug_ValidateSight, "validation options reset");
    }
    static Settings Load(float radius, float turret, bool fog, int revision) {
        var settings = new Settings();
        EnableDiagnostics(settings);
        Scribe.mode = LoadSaveMode.LoadingVars;
        Scribe.Values.Clear();
        Scribe.Values["FinishedQuickSetup2.15"] = true;
        Scribe.Values["QuickSetupRevisionCompleted"] = revision;
        Scribe.Values["AdvancedUser.15"] = true;
        Scribe.Values["FogOfWar_Enabled.15"] = fog;
        Scribe.Values["NewSightSystem_Enabled.15"] = true;
        Scribe.Values["NewSightSystem_BaseRadius.15"] = radius;
        Scribe.Values["NewSightSystem_TurretFactor.15"] = turret;
        Scribe.Values["NewSightSystem_ShowSightRing.15"] = false;
        Scribe.Values["Caster_Enabled.15"] = false;
        Scribe.Values["Personalities_Enabled.15"] = false;
        settings.ExposeData();
        return settings;
    }
    static void Main() {
        var fresh = new Settings();
        Check(!fresh.Debug && !fresh.Debug_LogJobs, "release defaults keep job logging off");
        Check(!fresh.NewSightSystem_Enabled && fresh.NewSightSystem_ShowSightRing, "new sight is opt-in with rings available");
        var migrated = Load(42f, 0.7f, true, 0);
        Check(!migrated.FinishedQuickSetup && migrated.QuickSetupRevisionCompleted == Settings.QuickSetupRequiredRevision, "old setup reopens once");
        CheckDiagnosticsReset(migrated);
        Check(migrated.NewSightSystem_Enabled && migrated.NewSightSystem_BaseRadius == 42f && migrated.NewSightSystem_TurretFactor == 0.7f, "sight choices survive migration");
        Check(!migrated.Caster_Enabled && !migrated.Personalities_Enabled && !migrated.NewSightSystem_ShowSightRing, "other preferences survive migration");
        var current = Load(500f, 2f, true, Settings.QuickSetupRequiredRevision);
        Check(current.NewSightSystem_BaseRadius == 60f && current.NewSightSystem_TurretFactor == 1f, "upper bounds clamp");
        Check(current.FinishedQuickSetup && current.AdvancedUser && current.Debug_DebugDumpData, "completed revision preserves advanced choices");
        var disabled = Load(-10f, -5f, false, Settings.QuickSetupRequiredRevision);
        Check(disabled.NewSightSystem_BaseRadius == 10f && disabled.NewSightSystem_TurretFactor == 0.1f, "lower bounds clamp");
        Check(!disabled.NewSightSystem_Enabled, "fog off disables shared sight");
        Scribe.mode = LoadSaveMode.Saving;
        Scribe.Values.Clear();
        current.ExposeData();
        Check((bool)Scribe.Values["NewSightSystem_Enabled.15"] && (float)Scribe.Values["NewSightSystem_BaseRadius.15"] == 60f && (float)Scribe.Values["NewSightSystem_TurretFactor.15"] == 1f && !(bool)Scribe.Values["NewSightSystem_ShowSightRing.15"], "sight preferences serialize");
        var applySettings = new Settings(); EnableDiagnostics(applySettings);
        Finder.Settings = applySettings;
        var rejected = new Window_QuickSetup(false);
        rejected.DoWindowContents(new Rect { height = 500 });
        Check(!rejected.Closed && !applySettings.FinishedQuickSetup && applySettings.Writes == 0 && Messages.Rejected == 1, "apply requires a difficulty preset");
        var accepted = new Window_QuickSetup(true);
        accepted.DoWindowContents(new Rect { height = 500 });
        Check(accepted.Closed && applySettings.FinishedQuickSetup && applySettings.QuickSetupRevisionCompleted == Settings.QuickSetupRequiredRevision && applySettings.Writes == 1, "apply marks the current revision and saves");
        CheckDiagnosticsReset(applySettings);
        Console.WriteLine("PASS: settings migration, bounds, fog coupling, preserved preferences, serialization and quick setup acceptance/reset");
    }
}
'''

contents = block((SOURCE / "Gui/Window_QuickSetup.cs").read_text(), "public override void DoWindowContents(")
harness = HARNESS.replace("QUICK_SETUP_CONTENTS", contents)
with tempfile.TemporaryDirectory(prefix="cai-workshop-settings-") as directory:
    directory = Path(directory)
    (directory / "Harness.cs").write_text(harness)
    (directory / "Settings.cs").write_text((SOURCE / "Settings.cs").read_text(encoding="utf-8-sig"))
    (directory / "Regression.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>')
    env = dict(os.environ, DOTNET_CLI_HOME=str(directory), DOTNET_NOLOGO="1", DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1", DOTNET_CLI_TELEMETRY_OPTOUT="1")
    subprocess.run(["dotnet", "run", "--project", str(directory / "Regression.csproj"), "--configuration", "Release", "--verbosity", "quiet"], check=True, env=env)
