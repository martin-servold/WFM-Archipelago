using System.Collections;
using System.Collections.Generic;
using System.Linq;

namespace WildfrostArchipelago
{
    /// <summary>
    /// Filler with an effect: Bling (gain 25-50), traps and boons (decided by the user 2026-10-31).
    /// Bling changes apply during a run; battle effects wait for the player's turn in the next battle
    /// and run through the game's ActionQueue. Each copy is told apart by its index in the slot's
    /// item list, since a reconnect resends every item: the highest index handled and the effects
    /// still waiting are saved in the AP profile. Main thread only.
    /// </summary>
    internal static class ApEffects
    {
        private const string HandledKey = "apEffectsHandled";
        private const string PendingKey = "apEffectsPending";
        private const int BlingMin = 25, BlingMax = 50;
        private const float SlapcrackersHitDelay = 0.75f;

        private static readonly Dictionary<string, string> Descriptions = new Dictionary<string, string>
        {
            { "bling", "Bling" },
            { "trap:lose_bling", "Bling Thief Trap" },
            { "trap:slapcrackers", "Slapcrackers Trap: one of your rows takes 1 damage x4" },
            { "trap:berry_bell", "Berry Bell Trap: an enemy row gains 1 health" },
            { "trap:demonize", "Demonize Trap: one of your units is Demonized" },
            { "trap:teeth", "Teeth Trap: an enemy gains 1 Teeth" },
            { "boon:slapcrackers", "Slapcrackers Boon: an enemy row takes 1 damage x4" },
            { "boon:pinkberry", "Pinkberry Juice Boon: a unit gains 4 health" },
            { "boon:kill", "Kill Enemy Boon" },
            { "boon:demonize", "Demonize Boon: an enemy is Demonized" },
        };

        // Arrived before the AP profile was loaded (items come in right after login).
        private static readonly List<KeyValuePair<int, string>> unsaved = new List<KeyValuePair<int, string>>();
        private static List<string> pending;

        public static bool IsEffect(string key) => Descriptions.ContainsKey(key);

        public static void Received(string key, int index)
        {
            unsaved.Add(new KeyValuePair<int, string>(index, key));
            Tick();
        }

        public static void Reset()
        {
            unsaved.Clear();
            pending = null;
        }

        /// <summary>Every frame.</summary>
        public static void Tick()
        {
            if (!ApMode.Active) return;
            if (pending == null) pending = SaveSystem.LoadProgressData(PendingKey, new List<string>());

            if (unsaved.Count > 0)
            {
                int handled = SaveSystem.LoadProgressData(HandledKey, 0);
                foreach (var item in unsaved.OrderBy(i => i.Key).Where(i => i.Key > handled))
                {
                    pending.Add(item.Value);
                    handled = item.Key;
                }
                unsaved.Clear();
                SaveSystem.SaveProgressData(HandledKey, handled);
                Save();
            }
            if (pending.Count == 0) return;

            // Bling belongs to a run, and is only changed on the map, where the run is saved straight
            // after: the run's Bling is saved with the campaign, and only at the game's own save points,
            // while the pending list is saved at once, so quitting before the next one lost the Bling.
            var bling = pending.Where(k => k == "bling" || k == "trap:lose_bling").ToList();
            if (bling.Count > 0 && References.Player != null && DeathLinkHandler.OnMap())
            {
                foreach (string key in bling)
                {
                    pending.Remove(key);
                    ChangeBling(key == "bling");
                }
                Campaign.PromptSave();
                Save();
            }

            var battle = Battle.instance;
            if (battle == null || battle.phase != Battle.Phase.Play || !ActionQueue.Empty) return;
            var effects = pending.Where(k => k.StartsWith("trap:") || k.StartsWith("boon:")).Where(k => k != "trap:lose_bling").ToList();
            if (effects.Count == 0) return;
            foreach (string key in effects)
            {
                pending.Remove(key);
                ActionQueue.Add(new ActionSequence(Run(key)));
            }
            Save();
        }

        private static void Save() => SaveSystem.SaveProgressData(PendingKey, pending);

        private static void ChangeBling(bool gain)
        {
            var player = References.Player;
            int amount = UnityEngine.Random.Range(BlingMin, BlingMax + 1);
            int have = player.data?.inventory?.gold.Value ?? 0;
            if (gain) player.GainGold(amount);
            else player.SpendGold(amount = System.Math.Min(amount, have));
            ArchipelagoMod.Client?.Log(gain ? $"Bling: +{amount}" : $"Bling Thief Trap: -{amount} Bling");
        }

        private static IEnumerator Run(string key)
        {
            var battle = Battle.instance;
            if (battle == null) yield break;
            Announce(key);
            switch (key)
            {
                case "trap:slapcrackers": yield return Slapcrackers(battle.player); break;
                case "boon:slapcrackers": yield return Slapcrackers(battle.enemy); break;
                case "trap:berry_bell": AddHealth(RandomRow(battle.enemy), 1); break;
                case "boon:pinkberry": AddHealth(Pick(Units(battle.player)), 4); break;
                case "trap:demonize": yield return Status(Pick(Units(battle.player)), "demonize", "Demonize"); break;
                case "boon:demonize": yield return Status(Pick(Units(battle.enemy)), "demonize", "Demonize"); break;
                case "trap:teeth": yield return Status(Pick(Units(battle.enemy)), "teeth", "Teeth"); break;
                case "boon:kill":
                    var target = Pick(Units(battle.enemy).Where(e => !IsBossLike(e)));
                    if (target != null) yield return target.Kill(DeathType.Normal);
                    break;
            }
            // The game moves units up into empty slots at the end of each turn (Battle.UpdateBoard).
            // These effects come between turns, so without this a unit they killed left a gap until
            // the player's next card.
            if (Battle.instance != battle) yield break;
            foreach (var side in new[] { battle.enemy, battle.player })
            {
                if (UpdateBoard.Invoke(battle, new object[] { side }) is IEnumerator update) yield return update;
            }
        }

        private static readonly System.Reflection.MethodInfo UpdateBoard = HarmonyLib.AccessTools.Method(typeof(Battle), "UpdateBoard");

        private static void Announce(string key)
        {
            string text = Descriptions[key] + "!";
            var runner = UnityEngine.Object.FindObjectOfType<ArchipelagoOverlay>();
            if (runner != null) runner.StartCoroutine(ApPatches.ShowPrompt(text));
        }

        private static List<Entity> Units(Character owner) =>
            Battle.GetCardsOnBoard(owner).Where(e => e != null && e.IsAliveAndExists()).ToList();

        private static Entity Pick(IEnumerable<Entity> units)
        {
            var list = units.ToList();
            return list.Count == 0 ? null : list[UnityEngine.Random.Range(0, list.Count)];
        }

        private static List<Entity> RandomRow(Character owner)
        {
            var rows = Units(owner).GroupBy(e => Battle.instance.GetRowIndices(e).FirstOrDefault()).ToList();
            return rows.Count == 0 ? new List<Entity>() : rows[UnityEngine.Random.Range(0, rows.Count)].ToList();
        }

        // Bosses, small bosses (Frost Guardian, Bam/Boo) and minibosses (leaders) are never picked.
        private static bool IsBossLike(Entity entity)
        {
            string type = entity.data?.cardType?.name;
            return type == "Boss" || type == "BossSmall" || type == "Miniboss" || type == "Leader";
        }

        // Aimless: each of the four hits picks a unit in the row anew. No attacker, so nothing
        // retaliates (Teeth and the like hit back at the attacker).
        private static IEnumerator Slapcrackers(Character owner)
        {
            var row = RandomRow(owner);
            for (int i = 0; i < 4; i++)
            {
                var target = Pick(row.Where(e => e != null && e.IsAliveAndExists()));
                if (target == null) yield break;
                // Spaced out like the card's own hits, so each one reads on its own.
                if (i > 0) yield return new UnityEngine.WaitForSeconds(SlapcrackersHitDelay);
                yield return new Hit(null, target, 1) { canRetaliate = false }.Process();
            }
        }

        private static void AddHealth(IEnumerable<Entity> units, int amount)
        {
            foreach (var unit in units.Where(u => u != null))
            {
                unit.hp.max += amount;
                unit.hp.current += amount;
                unit.PromptUpdate();
            }
        }

        private static void AddHealth(Entity unit, int amount)
        {
            if (unit != null) AddHealth(new[] { unit }, amount);
        }

        private static IEnumerator Status(Entity target, string type, string name)
        {
            if (target == null) yield break;
            var effects = AddressableLoader.GetGroup<StatusEffectData>("StatusEffectData");
            var data = effects.FirstOrDefault(s => s != null && s.name == name) ?? effects.FirstOrDefault(s => s != null && s.type == type);
            if (data == null)
            {
                ArchipelagoMod.Client?.LogDebug($"No status effect {name} found");
                yield break;
            }
            yield return StatusEffectSystem.Apply(target, null, data, 1);
        }
    }
}
