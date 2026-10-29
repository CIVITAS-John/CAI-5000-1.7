using CombatAI.R;
using UnityEngine;
using Verse;
namespace CombatAI.Gui
{
    /// <summary>Fog of war and unified sight controls shared by the mod settings and quick setup windows.</summary>
    public static class NewSightSettings
    {
        /// <summary>Fog of war toggle. Enabling fog turns the unified sight system on; disabling fog turns it off.</summary>
        public static void DrawFogToggle(Listing_Collapsible collapsible)
        {
            bool fogWasEnabled = Finder.Settings.FogOfWar_Enabled;
            collapsible.CheckboxLabeled(Keyed.CombatAI_Settings_Basic_FogOfWar_Enable, ref Finder.Settings.FogOfWar_Enabled);
            if (fogWasEnabled != Finder.Settings.FogOfWar_Enabled)
            {
                Finder.Settings.NewSightSystem_Enabled = Finder.Settings.FogOfWar_Enabled;
            }
        }

        public static void DrawOptions(Listing_Collapsible collapsible)
        {
            bool fogEnabled = Finder.Settings.FogOfWar_Enabled;
            collapsible.CheckboxLabeled(Keyed.CombatAI_Settings_Basic_FogOfWar_NewSight_Enable, ref Finder.Settings.NewSightSystem_Enabled, Keyed.CombatAI_Settings_Basic_FogOfWar_NewSight_Enable_Description, disabled: !fogEnabled);
            if (!fogEnabled)
            {
                collapsible.Label($"<color=#aaaaaa>{Keyed.CombatAI_Settings_Basic_FogOfWar_NewSight_RequireFog}</color>");
            }
            collapsible.Label(Keyed.CombatAI_Settings_Basic_FogOfWar_NewSight_BaseRadius);
            string readout = Keyed.CombatAI_Settings_Basic_FogOfWar_NewSight_BaseRadius_Readout.Formatted(Mathf.RoundToInt(Finder.Settings.NewSightSystem_BaseRadius));
            if (SightUtility.NewSightSystemActive)
            {
                collapsible.Lambda(25, rect =>
                {
                    Widgets.HorizontalSlider(rect, ref Finder.Settings.NewSightSystem_BaseRadius, new FloatRange(Settings.NewSightSystem_MinBaseRadius, Settings.NewSightSystem_MaxBaseRadius), readout, 0.05f);
                }, useMargins: true);
            }
            else
            {
                collapsible.Label($"<color=#aaaaaa>{readout}</color>");
            }
            collapsible.CheckboxLabeled(Keyed.CombatAI_Settings_Basic_FogOfWar_NewSight_ShowRing, ref Finder.Settings.NewSightSystem_ShowSightRing, Keyed.CombatAI_Settings_Basic_FogOfWar_NewSight_ShowRing_Description, disabled: !fogEnabled);
        }
    }
}
