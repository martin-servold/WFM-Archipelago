using System.Collections;
using System.Collections.Generic;
using HarmonyLib;
using UnityEngine;

namespace WildfrostArchipelago
{
    /// <summary>
    /// Leader rerolls (slot_data "leader_reroll", decided by the user 2026-11-02): some checks need a
    /// particular kind of leader (a Demonize one, say), so the leader select screen offers rerolls, with
    /// a button (ApUi) and R. Unlimited: a limit only pushed players to start and forfeit runs for new
    /// leaders (vanilla), which costs a loss (DeathLink, the win streak) as well as time. The leaders come from the screen's seed (the
    /// run's, Campaign.Data.Seed) whenever it deals them, including on coming back from tribe select,
    /// so a reroll moves that seed on by one (the run's seed plus rerolls used) and deals again.
    /// SelectLeader.Reroll (the debug console's "reroll") deals unseeded, which coming back undid,
    /// and leaves the cards face down. Rerolls done are counted in the AP profile with the run's seed,
    /// and reopening the screen deals from the same moved seed. Main thread only.
    /// </summary>
    internal static class LeaderReroll
    {
        private const string UsedKey = "apLeaderRerolls";

        private static SelectLeader leaders;
        private static CharacterSelectScreen screen;
        // The tribes the screen's Run was given, to run it again for fresh leader pools.
        private static List<ClassData> tribes;

        /// <summary>Whether the leader choice is on screen and can be rerolled now (the button shows).</summary>
        public static bool Showing =>
            ApMode.Active && ApMode.LeaderRerollOn && leaders != null && screen != null
            && leaders.running && leaders.isActiveAndEnabled && !PetPickerOpen;

        public static void Try()
        {
            if (!Showing || leaders.generating || InspectSystem.IsActive()) return;
            int used = Used + 1;
            SaveSystem.SaveProgressData(UsedKey, $"{Seed}:{used}");
            leaders.SetSeed(Seed + used);
            screen.StartCoroutine(Deal());
        }

        // As the tribe select does it: Run (fresh leader pools, and the moved seed from the postfix
        // below), deal from the seed, then turn the cards face up. Without the fresh pools the reroll
        // dealt from pools the first deal had drawn from, and reopening the screen (fresh pools) showed
        // other leaders (seen 2026-11-02). Run on the screen, not the leaders: GenerateLeaders starts
        // with the leaders' StopAllCoroutines, which stopped this before the flip.
        private static IEnumerator Deal()
        {
            CardPopUp.Clear();
            if (tribes != null) leaders.Run(tribes);
            yield return leaders.GenerateLeaders(true);
            leaders.FlipUpLeaders();
        }

        private static bool PetPickerOpen =>
            Traverse.Create(screen).Field("petSelection").GetValue<SelectStartingPet>()?.running == true;

        private static int Seed => Campaign.Data?.Seed ?? 0;

        // "seed:used" for the run being picked; another seed means a new run, with none used.
        private static int Used
        {
            get
            {
                string saved = SaveSystem.LoadProgressData(UsedKey, "");
                int colon = saved.IndexOf(':');
                return colon > 0 && saved.Substring(0, colon) == Seed.ToString()
                    && int.TryParse(saved.Substring(colon + 1), out int used) ? used : 0;
            }
        }

        [HarmonyPatch(typeof(SelectLeader), nameof(SelectLeader.Run))]
        private static class LeaderScreenOpened
        {
            private static void Postfix(SelectLeader __instance, List<ClassData> tribes)
            {
                leaders = __instance;
                LeaderReroll.tribes = tribes;
                screen = Object.FindObjectOfType<CharacterSelectScreen>();
                // The game deals right after Run. A run with rerolls used deals its last ones again
                // (the screen set the run's own seed when it opened).
                if (ApMode.Active && Used > 0) leaders.SetSeed(Seed + Used);
            }
        }
    }
}
