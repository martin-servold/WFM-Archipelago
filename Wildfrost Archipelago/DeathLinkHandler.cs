using System.Collections;
using System.Linq;

namespace WildfrostArchipelago
{
    /// <summary>
    /// DeathLink (slot_data "death_link"). A received death makes the leader flee: in a battle, the
    /// battle is lost; on the map, the run ends there the way a lost battle ends it. In a shop or
    /// event it waits until the player is back on the map or in a battle. Losing a run sends a
    /// death, unless the loss was a received death. Main thread only; AP profile only.
    /// </summary>
    internal static class DeathLinkHandler
    {
        private static string pendingSource, pendingCause;
        private static bool fleeing;

        public static void Received(string source, string cause)
        {
            if (!ApMode.Active || !InRun())
            {
                ArchipelagoMod.Client?.Log($"DeathLink from {source} ignored: no run in progress");
                return;
            }
            pendingSource = source;
            pendingCause = cause;
            Tick();
            if (pendingSource != null) ArchipelagoMod.Client?.Log($"DeathLink from {source}: your leader flees once you're back on the map or in a battle");
        }

        /// <summary>Every frame: a waiting death strikes in a battle, or on the map.</summary>
        public static void Tick()
        {
            if (pendingSource == null) return;
            bool inBattle = InBattle();
            if (!inBattle && !OnMap()) return;
            string source = pendingSource, cause = pendingCause;
            pendingSource = pendingCause = null;
            fleeing = true;

            var battle = Battle.instance;
            string leader = inBattle ? battle.minibosses.FirstOrDefault(e => e != null && e.owner == battle.player)?.data?.title : null;
            leader = leader ?? References.PlayerData?.inventory?.deck?.FirstOrDefault(c => c != null && c.cardType != null && c.cardType.miniboss)?.title ?? "Your leader";
            string text = $"DeathLink from {source}" + (string.IsNullOrEmpty(cause) ? "." : $": {cause}") + $" {leader} flees!";
            var runner = UnityEngine.Object.FindObjectOfType<ArchipelagoOverlay>();
            if (runner == null) return;
            runner.StartCoroutine(ApPatches.ShowPrompt(text));
            if (inBattle) battle.EnemyWin();
            else runner.StartCoroutine(EndRunOnMap());
        }

        // What Battle.Run does after a lost battle: Campaign.BattleEnd ends the campaign as a loss,
        // the journal marks the leader killed, and the CampaignEnd scene shows the defeat screen.
        private static IEnumerator EndRunOnMap()
        {
            yield return new UnityEngine.WaitForSeconds(2.5f);
            if (References.Campaign == null) yield break;
            References.Campaign.End(Campaign.Result.Lose);
            JournalNameHistory.MostRecentNameKilled();

            // The defeat screen (DefeatSequence) tells a win from a loss by References.Battle's winner,
            // and on the map there is no battle. Hand it a stand-in whose winner isn't the player.
            // Inactive, so the components never wake up.
            UnityEngine.GameObject holder = null;
            if (References.Battle == null)
            {
                holder = new UnityEngine.GameObject("AP DeathLink defeat");
                holder.SetActive(false);
                var standIn = holder.AddComponent<Battle>();
                standIn.winner = holder.AddComponent<Character>();
                References.Battle = standIn;
            }
            yield return SceneManager.Load("CampaignEnd", SceneType.Temporary);
            if (holder == null) yield break;
            yield return SceneManager.WaitUntilUnloaded("CampaignEnd");
            if (References.Battle != null && References.Battle.gameObject == holder) References.Battle = null;
            UnityEngine.Object.Destroy(holder);
        }

        // Shops and events load their own active scene over the map.
        public static bool OnMap() => SceneManager.ActiveSceneName == "MapNew" && SceneManager.HasNoActiveJobs;

        // Fully qualified: the game has its own global SceneManager class that shadows Unity's.
        private static bool InRun() => UnityEngine.SceneManagement.SceneManager.GetSceneByName("Campaign").isLoaded;

        // Play and Battle are the player's and the units' turns; Init is still setting up.
        private static bool InBattle()
        {
            var battle = Battle.instance;
            return battle != null && (battle.phase == Battle.Phase.Play || battle.phase == Battle.Phase.Battle);
        }

        /// <summary>From OnCampaignEnd while the AP profile is active.</summary>
        public static void RunEnded(Campaign.Result result)
        {
            bool sendDeath = result == Campaign.Result.Lose && !fleeing;
            fleeing = false;
            pendingSource = pendingCause = null;
            if (!sendDeath) return;
            string leader = References.PlayerData?.inventory?.deck?.FirstOrDefault(c => c != null && c.cardType != null && c.cardType.miniboss)?.title;
            ArchipelagoMod.Client?.SendDeath(leader == null ? null : $"{leader} was defeated.");
        }
    }
}
