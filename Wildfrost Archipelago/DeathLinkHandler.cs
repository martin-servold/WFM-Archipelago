using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;

namespace WildfrostArchipelago
{
    /// <summary>
    /// DeathLink (slot_data "death_link"). A received death hits the leader for
    /// death_link_damage_percent of its max health (asked by the user 2026-11-07, after Slay the
    /// Spire 2's AP). At 100 (the default, and older seeds) the leader flees: in a battle, the
    /// battle is lost; on the map, the run ends there the way a lost battle ends it. Below 100 the
    /// hit waits for the player's turn in a battle (units heal after every battle, so a hit on the
    /// map would do nothing), and a hit that takes the leader to 0 makes it flee. A death the leader
    /// survives (0 included) also adds a Gunk Fruit to the run's deck for good, and to the hand in a
    /// battle (the user's idea 2026-11-07, after Spire 2's Death Fragments). In a shop or event a
    /// death waits until the player is back on the map or in a battle.
    /// Losing a run sends a death, unless the loss was a received death. Main thread only; AP
    /// profile only.
    /// </summary>
    internal static class DeathLinkHandler
    {
        private static readonly List<(string source, string cause)> pending = new List<(string, string)>();
        private static bool fleeing;

        private static int DamagePercent => ArchipelagoMod.Client?.DeathLinkDamagePercent ?? 100;

        public static void Received(string source, string cause)
        {
            if (!ApMode.Active || !InRun())
            {
                ArchipelagoMod.Client?.Log($"DeathLink from {source} ignored: no run in progress");
                return;
            }
            if (DamagePercent <= 0)
            {
                ShowPrompt(Describe(source, cause) + " A Gunk Fruit joins your deck!");
                StartGunk(PlayerTurn());
                return;
            }
            pending.Add((source, cause));
            Tick();
            if (pending.Count > 0)
                ArchipelagoMod.Client?.Log(DamagePercent >= 100
                    ? $"DeathLink from {source}: your leader flees once you're back on the map or in a battle"
                    : $"DeathLink from {source}: your leader takes {DamagePercent}% of its health in your next battle");
        }

        /// <summary>Every frame: a waiting death strikes in a battle (or, at 100%, on the map).</summary>
        public static void Tick()
        {
            if (pending.Count == 0 || fleeing) return;
            bool flee = DamagePercent >= 100;
            bool inBattle = flee ? InBattle() : PlayerTurn();
            if (!inBattle && !(flee && OnMap())) return;
            var runner = UnityEngine.Object.FindObjectOfType<ArchipelagoOverlay>();
            if (runner == null) return;
            var (source, cause) = pending[0];
            pending.RemoveAt(0);

            var battle = Battle.instance;
            var leaderUnit = inBattle ? battle.minibosses.FirstOrDefault(e => e != null && e.owner == battle.player) : null;
            string leader = leaderUnit?.data?.title
                ?? References.PlayerData?.inventory?.deck?.FirstOrDefault(c => c != null && c.cardType != null && c.cardType.miniboss)?.title
                ?? "Your leader";
            if (!flee && leaderUnit != null)
            {
                int damage = Math.Max(1, (int)Math.Ceiling(leaderUnit.hp.max * DamagePercent / 100.0));
                leaderUnit.hp.current = Math.Max(0, leaderUnit.hp.current - damage);
                leaderUnit.PromptUpdate();
                if (leaderUnit.hp.current > 0)
                {
                    ShowPrompt(Describe(source, cause) + $" {leader} takes {damage} damage, and a Gunk Fruit joins your deck!");
                    StartGunk(true);
                    return;
                }
            }
            pending.Clear();
            fleeing = true;
            ShowPrompt(Describe(source, cause) + $" {leader} flees!");
            if (inBattle) battle.EnemyWin();
            else runner.StartCoroutine(EndRunOnMap());
        }

        // The card Gunkback and friends hand out ("Deadweight"): it clogs the hand.
        private const string GunkFruit = "Deadweight";

        private static void StartGunk(bool inBattle)
        {
            var runner = UnityEngine.Object.FindObjectOfType<ArchipelagoOverlay>();
            if (runner != null) runner.StartCoroutine(AddGunk(inBattle));
        }

        // As the game's own "gain card" console command does it: a copy in the run's deck, and in a
        // battle a card made from it straight into the hand.
        private static IEnumerator AddGunk(bool inBattle)
        {
            var data = AddressableLoader.Get<CardData>("CardData", GunkFruit);
            var deck = References.PlayerData?.inventory?.deck;
            if (data == null || deck == null)
            {
                ArchipelagoMod.Client?.Log("DeathLink: couldn't add the Gunk Fruit");
                yield break;
            }
            var copy = data.Clone(true);
            deck.Add(copy);
            var battle = Battle.instance;
            var player = battle?.player;
            if (!inBattle || battle == null || player == null || player.handContainer == null) yield break;
            var card = CardManager.Get(copy, battle.playerCardController, player, true, true);
            card.entity.flipper.FlipDownInstant();
            card.transform.localPosition = new UnityEngine.Vector3(-100f, 0f, 0f);
            yield return card.UpdateData(false);
            player.handContainer.Add(card.entity);
            player.handContainer.TweenChildPositions();
            ActionQueue.Add(new ActionReveal(card.entity, 0f), false);
            ActionQueue.Add(new ActionRunEnableEvent(card.entity), false);
            yield return ActionQueue.Wait(true);
        }

        private static string Describe(string source, string cause) =>
            $"DeathLink from {source}" + (string.IsNullOrEmpty(cause) ? "." : $": {cause}");

        private static void ShowPrompt(string text)
        {
            var runner = UnityEngine.Object.FindObjectOfType<ArchipelagoOverlay>();
            if (runner != null) runner.StartCoroutine(ApPatches.ShowPrompt(text));
            else ArchipelagoMod.Client?.Log(text);
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

        // A partial hit lands on the player's turn, not while the units are acting.
        private static bool PlayerTurn() => Battle.instance != null && Battle.instance.phase == Battle.Phase.Play;

        /// <summary>From OnCampaignEnd while the AP profile is active.</summary>
        public static void RunEnded(Campaign.Result result)
        {
            bool sendDeath = result == Campaign.Result.Lose && !fleeing;
            fleeing = false;
            pending.Clear();
            if (!sendDeath) return;
            string leader = References.PlayerData?.inventory?.deck?.FirstOrDefault(c => c != null && c.cardType != null && c.cardType.miniboss)?.title;
            ArchipelagoMod.Client?.SendDeath(leader == null ? null : $"{leader} was defeated.");
        }
    }
}
