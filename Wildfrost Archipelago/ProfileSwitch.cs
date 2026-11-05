using System;
using System.Collections.Generic;
using System.Linq;
using Deadpan.Enums.Engine.Components.Modding;
using HarmonyLib;
using UnityEngine;

namespace WildfrostArchipelago
{
    /// <summary>
    /// Switches the save profile mid-session. SaveSystem.SetProfile only changes the folder: game
    /// systems that read progress data at startup keep the old profile's copy in memory and write
    /// it into the new profile on their next save. On the first test that made one win on a blank
    /// profile complete six "win a run" challenges (lifetime stats from Default), and carried
    /// Default's challenge progress and card frames over. So after switching, those systems reload.
    /// </summary>
    internal static class ProfileSwitch
    {
        // GameSystems whose OnEnable loads per-profile data (found in the IL). Their OnDisable undoes
        // everything OnEnable subscribes, so toggling enabled is a clean reload.
        private static readonly HashSet<string> ReloadOnEnable = new HashSet<string>
        {
            "CardDiscoverSystem",
            "CardFramesSystem",
            "ChallengeSystem",
            "ChallengeProgressSystem",
            "DynamicTutorialSystem",
            "DynamicReactionTutorialSystem",
            "DynamicWaveBellTutorialSystem",
            "TutorialCharmSystem",
            "TutorialCrownSystem",
            "TutorialInjurySystem",
        };

        /// <summary>
        /// Main menu only (no campaign in memory). prepare runs on the new profile before the
        /// systems reload, to seed save keys they read. Returns what was reloaded, for the log.
        /// </summary>
        public static string SetProfile(string profile, bool remember, Action prepare)
        {
            SaveSystem.SetProfile(profile, remember);
            prepare?.Invoke();

            var reloaded = new List<string>();
            foreach (var system in UnityEngine.Object.FindObjectsOfType<GameSystem>())
            {
                // ChallengeSystem.OnEnable adds one of these per active custom-check challenge, and
                // OnDisable doesn't remove them, so the old profile's would stay and double up.
                if (system is ChallengeListenerSystem) UnityEngine.Object.Destroy(system);
            }
            foreach (var system in UnityEngine.Object.FindObjectsOfType<GameSystem>())
            {
                if (system is ChallengeListenerSystem) continue;
                string type = system.GetType().Name;
                if (type == "OverallStatsSystem")
                {
                    // Lifetime stats load on Events.OnGameStart, which only fires once.
                    AccessTools.Method(system.GetType(), "GameStart").Invoke(system, null);
                    reloaded.Add(type);
                }
                else if (ReloadOnEnable.Contains(type) && system.enabled)
                {
                    system.enabled = false;
                    system.enabled = true;
                    reloaded.Add(type);
                }
            }
            return string.Join(", ", reloaded);
        }
    }

    /// <summary>
    /// The enabled mods are saved per profile ("lastSavedMods" in Save.sav), but the game only reads
    /// them at startup, which is always on the player's own profile (the seed's profile is never
    /// remembered). So mods turned on or off on a seed's profile are also saved to the player's own,
    /// or the next launch would undo them (decided by the user 2026-11-05).
    /// </summary>
    [HarmonyPatch(typeof(WildfrostMod), "SetLastMods")]
    internal static class LastModsToOwnProfile
    {
        private static void Postfix(WildfrostMod[] enabled)
        {
            string own = ApMode.ReturnProfile;
            if (!ApMode.Active || own == null || enabled == null) return;
            try
            {
                // Saver.SaveValue takes the folder, so this writes the other profile's Save.sav
                // without switching to it.
                var saver = AccessTools.Field(typeof(SaveSystem), "progressSaver").GetValue(null);
                var save = AccessTools.Method(saver.GetType(), "SaveValue").MakeGenericMethod(typeof(string[]));
                string[] guids = enabled.Select(m => m.GUID).ToArray();
                save.Invoke(saver, new object[] { "lastSavedMods", guids, SaveSystem.profileFolder + "/" + own, "" });
                ArchipelagoMod.Client?.LogDebug($"Enabled mods also saved to profile {own}");
            }
            catch (Exception e)
            {
                ArchipelagoMod.Client?.LogDebug($"Couldn't save the enabled mods to profile {own}: {e.Message}");
            }
        }
    }
}
