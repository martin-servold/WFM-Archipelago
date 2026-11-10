using System.Collections;
using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using TMPro;
using UnityEngine;
using UnityEngine.Localization.Components;

namespace WildfrostArchipelago
{
    /// <summary>
    /// The new challenges in town (step 2, asked by the user 2026-11-08). Each gets a stand-in ChallengeData
    /// made at runtime, used only for display: it's never added to the game's challenge group, so the
    /// game's own ChallengeSystem never listens for, completes or saves it.
    /// - The Challenges board lists them after vanilla's (ChallengeListDisplayBuilder.GetChallengeLists).
    ///   Total ones show their count, per-run ones 0/1, and a sent check shows as completed.
    /// - The end-of-run Town Progress panel (ApPatches.FastTownProgress) shows the ones this run moved,
    ///   after vanilla's: total ones from where they were to where they are, per-run ones only when they
    ///   complete (0/1 to 1/1). Any challenge the run moved shows, in logic or not, as vanilla's do.
    /// Their text is the check's name without "Challenge - ", so it follows the seed's apworld.
    /// </summary>
    internal static partial class NewChallenges
    {
        private const string LocationPrefix = "challenge:ap:";
        private const string NamePrefix = "Challenge - ";
        private const string StandInPrefix = "ap:";
        private const string RunKey = "apChallengeRun";
        private const string RunSeed = "#seed"; // RunKey's entry naming the run (Campaign.Data.Seed) it belongs to
        public const string RewardText = "Archipelago check sent";

        private static readonly Dictionary<string, ChallengeData> standIns = new Dictionary<string, ChallengeData>();
        private static readonly Dictionary<ChallengeData, string> texts = new Dictionary<ChallengeData, string>();

        private static bool IsStandIn(ChallengeData challenge) => challenge != null && texts.ContainsKey(challenge);

        /// <summary>This seed's new challenges, in location order (none with the option off).</summary>
        private static List<string> SeedSlugs()
        {
            var client = ArchipelagoMod.Client;
            if (!On || client == null) return new List<string>();
            return client.LocationKeys.Where(k => k.StartsWith(LocationPrefix, System.StringComparison.Ordinal))
                .Select(k => k.Substring(LocationPrefix.Length)).ToList();
        }

        private static int Goal(string slug) => Totals.TryGetValue(slug, out int target) ? target : 1;

        private static ChallengeData StandIn(string slug)
        {
            string key = LocationPrefix + slug;
            string name = null;
            ArchipelagoMod.Client?.LocationNames?.TryGetValue(key, out name);
            string text = string.IsNullOrEmpty(name) ? slug : name.StartsWith(NamePrefix) ? name.Substring(NamePrefix.Length) : name;
            if (!standIns.TryGetValue(slug, out var challenge) || challenge == null)
            {
                challenge = ScriptableObject.CreateInstance<ChallengeData>();
                challenge.name = StandInPrefix + slug;
                challenge.hideFlags = HideFlags.DontUnloadUnusedAsset;
                challenge.requires = new ChallengeData[0];
                challenge.icon = ChallengeSystem.GetAllChallenges().FirstOrDefault(c => c != null && c.icon != null)?.icon;
                standIns[slug] = challenge;
            }
            challenge.goal = Goal(slug);
            texts[challenge] = text;
            return challenge;
        }

        private static bool Sent(string slug, List<string> done) =>
            done.Contains(slug) || ArchipelagoMod.Client?.CheckSent(LocationPrefix + slug) == true;

        // --- This run's moves, for the end-of-run panel ---

        /// <summary>Remembers where a challenge stood before this run first moved it.</summary>
        private static void RecordRun(string slug, int original)
        {
            int seed = Campaign.Data?.Seed ?? 0;
            var run = SaveSystem.LoadProgressData(RunKey, new Dictionary<string, int>());
            if (!run.TryGetValue(RunSeed, out int runSeed) || runSeed != seed)
                run = new Dictionary<string, int> { { RunSeed, seed } };
            if (run.ContainsKey(slug)) return;
            run[slug] = original;
            SaveSystem.SaveProgressData(RunKey, run);
        }

        /// <summary>
        /// The new challenges this run moved, as (stand-in, from, to), and forgets them so they show once.
        /// Main thread; for the end-of-run panel.
        /// </summary>
        public static List<(ChallengeData challenge, int from, int to)> TakeRunProgress()
        {
            var moved = new List<(ChallengeData, int, int)>();
            if (!On) return moved;
            var run = SaveSystem.LoadProgressData(RunKey, new Dictionary<string, int>());
            if (run.Count == 0) return moved;
            SaveSystem.SaveProgressData(RunKey, new Dictionary<string, int>());
            if (Campaign.Data != null && (!run.TryGetValue(RunSeed, out int seed) || seed != Campaign.Data.Seed)) return moved;
            var progress = SaveSystem.LoadProgressData(ProgressKey, new Dictionary<string, int>());
            var done = SaveSystem.LoadProgressData(DoneKey, new List<string>());
            foreach (string slug in SeedSlugs())
            {
                if (!run.TryGetValue(slug, out int from)) continue;
                int to = Totals.ContainsKey(slug)
                    ? System.Math.Min(progress.TryGetValue(slug, out int have) ? have : 0, Goal(slug))
                    : done.Contains(slug) ? 1 : 0;
                if (to > from) moved.Add((StandIn(slug), from, to));
            }
            Debug($"this run moved {moved.Count}: {string.Join(", ", moved.Select(m => $"{m.Item1.name} {m.Item2}->{m.Item3}"))}");
            return moved;
        }

        // --- The town's Challenges board ---

        [HarmonyPatch(typeof(ChallengeListDisplayBuilder), "GetChallengeLists")]
        private static class Board
        {
            // The lists are out parameters, so the postfix takes them by ref.
            private static void Postfix(ref List<ChallengeData> inProgressChallenges, ref List<ChallengeData> completedChallenges,
                ref List<ChallengeData> lockedChallenges, ref List<ChallengeProgress> challengeProgress)
            {
                try
                {
                    // Vanilla's hidden challenges show as "Locked" until done. On AP every challenge is open and
                    // a check the player should know about (the hints panel names them anyway; the user, 2026-11-08),
                    // so they join the in-progress list, after vanilla's other ones.
                    if (ApMode.Active && lockedChallenges != null && inProgressChallenges != null && lockedChallenges.Count > 0)
                    {
                        Debug($"board: unhiding {string.Join(", ", lockedChallenges.Where(c => c != null).Select(c => c.name))}");
                        inProgressChallenges.AddRange(lockedChallenges.Where(c => c != null));
                        lockedChallenges.Clear();
                    }
                    var slugs = SeedSlugs();
                    Debug($"board: {slugs.Count} of ours (AP {ApMode.Active}, option {ApMode.NewChallenges}), vanilla lists "
                        + $"{inProgressChallenges?.Count.ToString() ?? "null"} in progress, {completedChallenges?.Count.ToString() ?? "null"} completed, "
                        + $"{challengeProgress?.Count.ToString() ?? "null"} progress");
                    if (slugs.Count == 0 || inProgressChallenges == null || completedChallenges == null) return;
                    // A profile with no vanilla progress yet has no progress list (seen 2026-11-08, a fresh seed).
                    if (challengeProgress == null) challengeProgress = new List<ChallengeProgress>();
                    var progress = SaveSystem.LoadProgressData(ProgressKey, new Dictionary<string, int>());
                    var done = SaveSystem.LoadProgressData(DoneKey, new List<string>());
                    foreach (string slug in slugs)
                    {
                        var challenge = StandIn(slug);
                        if (Sent(slug, done))
                        {
                            completedChallenges.Add(challenge);
                            continue;
                        }
                        inProgressChallenges.Add(challenge);
                        int have = Totals.ContainsKey(slug) && progress.TryGetValue(slug, out int n) ? System.Math.Min(n, challenge.goal) : 0;
                        challengeProgress.RemoveAll(p => p?.challengeName == challenge.name);
                        challengeProgress.Add(new ChallengeProgress(challenge.name, have));
                    }
                    Debug($"board now {inProgressChallenges.Count} in progress, {completedChallenges.Count} completed");
                }
                catch (System.Exception e)
                {
                    ArchipelagoMod.Client?.LogDebug("New Challenges board: " + e);
                }
            }
        }

        // A board entry: vanilla's Assign points its localized labels at the challenge's string keys, which a
        // stand-in hasn't got. Ours writes the text itself, with the labels' localizing turned off.
        [HarmonyPatch(typeof(ChallengeEntry), nameof(ChallengeEntry.Assign))]
        private static class BoardEntry
        {
            private static readonly AccessTools.FieldRef<ChallengeEntry, ChallengeData> Challenge =
                AccessTools.FieldRefAccess<ChallengeEntry, ChallengeData>("challenge");
            private static readonly AccessTools.FieldRef<ChallengeEntry, LocalizeStringEvent> Text =
                AccessTools.FieldRefAccess<ChallengeEntry, LocalizeStringEvent>("text");
            private static readonly AccessTools.FieldRef<ChallengeEntry, LocalizeStringEvent> Reward =
                AccessTools.FieldRefAccess<ChallengeEntry, LocalizeStringEvent>("rewardText");
            private static readonly AccessTools.FieldRef<ChallengeEntry, UnityEngine.UI.Image> RewardIcon =
                AccessTools.FieldRefAccess<ChallengeEntry, UnityEngine.UI.Image>("rewardIcon");
            private static readonly AccessTools.FieldRef<ChallengeEntry, UnityEngine.UI.Image> Background =
                AccessTools.FieldRefAccess<ChallengeEntry, UnityEngine.UI.Image>("background");

            // Soft blue against vanilla's orange.
            private static readonly Color InProgressColor = new Color(0.45f, 0.68f, 0.95f);

            private static bool Prefix(ChallengeEntry __instance, ChallengeData challenge, bool completed)
            {
                if (!IsStandIn(challenge)) return true;
                Challenge(__instance) = challenge;
                SetLabel(Text(__instance), texts[challenge]);
                if (completed) SetLabel(Reward(__instance), RewardText);
                var icon = RewardIcon(__instance);
                if (icon != null) icon.sprite = challenge.icon;
                // In progress ones get a different colour, so they stand out from vanilla's; completed ones keep
                // vanilla's, so every completed challenge looks the same (the user, 2026-11-08).
                var background = Background(__instance);
                if (background != null && !completed) background.color = InProgressColor;
                return false;
            }

            private static void SetLabel(LocalizeStringEvent label, string text)
            {
                if (label == null) return;
                label.enabled = false;
                var tmp = label.GetComponent<TMP_Text>();
                if (tmp != null) tmp.text = text;
            }
        }

        // The end-of-run panel reads a challenge's text and reward text through these, from its string keys.
        [HarmonyPatch(typeof(ChallengeData), nameof(ChallengeData.text), MethodType.Getter)]
        private static class StandInText
        {
            private static bool Prefix(ChallengeData __instance, ref string __result)
            {
                if (!IsStandIn(__instance)) return true;
                __result = texts[__instance];
                return false;
            }
        }

        [HarmonyPatch(typeof(ChallengeData), nameof(ChallengeData.rewardText), MethodType.Getter)]
        private static class StandInRewardText
        {
            private static bool Prefix(ChallengeData __instance, ref string __result)
            {
                if (!IsStandIn(__instance)) return true;
                __result = RewardText;
                return false;
            }
        }
    }
}
