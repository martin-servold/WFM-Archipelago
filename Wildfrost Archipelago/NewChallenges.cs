using System.Collections.Generic;
using System.Linq;
using HarmonyLib;

namespace WildfrostArchipelago
{
    /// <summary>
    /// The challenges made for Archipelago (the apworld's New Challenges option, designed with the user
    /// 2026-11-08): each is the location "challenge:ap:&lt;slug&gt;" (tools/gen_data.py AP_CHALLENGES).
    /// Most read the game's own run stats (CampaignStats, which StatsSystem fills from game events);
    /// a few hook the event or moment they're about. "Total" ones count across runs, kept in the AP
    /// profile's progress data; the rest happen within one run, battle or moment. Every step is
    /// logged with debug on, so a playtest can show what each one saw. Main thread only.
    /// </summary>
    internal static partial class NewChallenges
    {
        private const string DoneKey = "apChallengesDone";
        private const string ProgressKey = "apChallengeProgress";

        // Total counts, across runs (the user's marks in PLAN).
        private static readonly Dictionary<string, int> Totals = new Dictionary<string, int>
        {
            { "charm_merchant", 2 },
            { "shade_sculptor", 2 },
            { "cursed_crowns", 3 },
            { "injure", 3 },
            { "curse_charmed", 2 },
            { "gobblers", 3 },
            { "junk", 20 },
            { "haze", 3 },
            { "ink", 40 },
            { "overburn", 10 },
            { "soulbound", 3 },
            { "bom", 40 },
        };

        // Cards whose first play (CampaignStats "cardsTriggered") completes a challenge.
        private static readonly Dictionary<string, string> TriggerChallenges = new Dictionary<string, string>
        {
            { "OhNo", "icgm" },                 // I.C.G.M
            { "SkullMuffin", "skull_muffin" },
            { "StormbearSpirit", "stormbear" }, // only playable on a snowed enemy
            { "Peppermaton", "moko_totem" },    // Moko Totem
        };

        // Status types (StatusEffectData.type) counted for the Apply challenges. Bom's type is a guess
        // ("vim"); with debug on every status applied is logged, so a playtest can confirm it.
        private static readonly Dictionary<string, string> StatusChallenges = new Dictionary<string, string>
        {
            { "haze", "haze" },
            { "ink", "ink" },
            { "vim", "bom" },
            { "bom", "bom" },
        };

        private const int MuncherFeeds = 3, SpiceStack = 20, CharmsOnCard = 4, BossBling = 200, GnomeItems = 3, FullCrownPrice = 100;

        private static bool On => ApMode.Active && ApMode.NewChallenges;

        private static void Debug(string message) => ArchipelagoMod.Client?.LogDebug("New Challenges: " + message);

        public static void Enable()
        {
            Events.PreBattleSetUp += OnPreBattleSetUp;
            Events.OnBattleWin += OnBattleWin;
        }

        public static void Disable()
        {
            Events.PreBattleSetUp -= OnPreBattleSetUp;
            Events.OnBattleWin -= OnBattleWin;
        }

        /// <summary>Sends this challenge's check, and remembers it for a catch-up if it couldn't go out.</summary>
        private static void Complete(string slug)
        {
            if (!On) return;
            var done = SaveSystem.LoadProgressData(DoneKey, new List<string>());
            if (!done.Contains(slug))
            {
                if (!Totals.ContainsKey(slug)) RecordRun(slug, 0); // a total one records its count in Count
                done.Add(slug);
                SaveSystem.SaveProgressData(DoneKey, done);
                Debug($"{slug} done");
            }
            ArchipelagoMod.Client?.SendLocation("challenge:ap:" + slug);
        }

        /// <summary>Adds to a total challenge, completing it at its target.</summary>
        private static void Count(string slug, int amount = 1)
        {
            if (!On || amount <= 0 || !Totals.TryGetValue(slug, out int target)) return;
            var progress = SaveSystem.LoadProgressData(ProgressKey, new Dictionary<string, int>());
            progress.TryGetValue(slug, out int have);
            if (have >= target) return;
            RecordRun(slug, have);
            have += amount;
            progress[slug] = have;
            SaveSystem.SaveProgressData(ProgressKey, progress);
            Debug($"{slug} {System.Math.Min(have, target)}/{target}");
            if (have >= target) Complete(slug);
        }

        /// <summary>Resends the challenges done while the check couldn't go out (SendLocation skips sent ones).</summary>
        public static void CatchUp(ArchipelagoClient client)
        {
            if (!ApMode.NewChallenges) return;
            foreach (string slug in SaveSystem.LoadProgressData(DoneKey, new List<string>()))
                client.SendLocation("challenge:ap:" + slug, quiet: true);
        }

        private static bool IsRunStats(CampaignStats stats) => stats != null && stats == StatsSystem.Get();

        private static CampaignNode CurrentNode() =>
            References.Player != null ? Campaign.FindCharacterNode(References.Player) : null;

        private static bool IsBoss(Entity entity)
        {
            string type = entity?.data?.cardType?.name;
            return type == "Boss" || type == "BossSmall";
        }

        private static string CardName(Entity entity) => entity?.data?.name;

        // --- Run stats ---

        [HarmonyPatch(typeof(CampaignStats), nameof(CampaignStats.Add), typeof(string), typeof(string), typeof(int))]
        private static class StatAdded
        {
            private static void Postfix(CampaignStats __instance, string stat, string key, int value)
            {
                if (!On || !IsRunStats(__instance)) return;
                switch (stat)
                {
                    case "friendliesInjured":
                        Count("injure", value);
                        break;
                    case "enemiesKilled":
                        if (key == "Gobbler") Count("gobblers", value);
                        if (key == "Popper") Complete("sheepopper");
                        break;
                    case "friendliesDied":
                        if (key == "Popper") Complete("sheepopper");
                        break;
                    case "enemiesKilledDamageType":
                        Debug($"enemy killed by damage type {key}");
                        if (key == "overload") Count("overburn", value); // Overburn's internal name
                        break;
                    case "statusesApplied":
                        Debug($"applied {value} {key}");
                        if (StatusChallenges.TryGetValue(key ?? "", out string status)) Count(status, value);
                        break;
                    case "cardsTriggered":
                        if (TriggerChallenges.TryGetValue(key ?? "", out string trigger)) Complete(trigger);
                        break;
                    case "cardsMunched":
                        // Each Muncher takes up to two cards: the Munchers fed are counted, marked on their nodes.
                        var node = CurrentNode();
                        if (node?.data == null) break;
                        node.data["apFed"] = true;
                        int fed = References.Campaign?.nodes?.Count(n => n?.data != null && n.data.ContainsKey("apFed")) ?? 0;
                        Debug($"{fed} Munchers fed this run");
                        if (fed >= MuncherFeeds) Complete("muncher");
                        break;
                }
            }
        }

        [HarmonyPatch(typeof(CampaignStats), nameof(CampaignStats.Max), typeof(string), typeof(string), typeof(int))]
        private static class StatMax
        {
            private static void Postfix(CampaignStats __instance, string stat, string key, int value)
            {
                if (!On || !IsRunStats(__instance)) return;
                if (stat == "highestStatusEffect" && key == "spice" && value >= SpiceStack) Complete("spice");
            }
        }

        // --- Events the stats don't cover ---

        // Cursed Crowns, and four or more charms on one card.
        [HarmonyPatch(typeof(StatsSystem), "UpgradeAssigned")]
        private static class UpgradeAssigned
        {
            private static void Postfix(Entity entity, CardUpgradeData upgradeData)
            {
                if (!On || upgradeData == null) return;
                if (upgradeData.name == "CrownCursed") Count("cursed_crowns");
                // StatsSystem hears of it before the charm joins the card's upgrades.
                var upgrades = entity?.data?.upgrades ?? new List<CardUpgradeData>();
                int charms = upgrades.Count(u => u != null && u.type == CardUpgradeData.Type.Charm)
                    + (upgradeData.type == CardUpgradeData.Type.Charm && !upgrades.Contains(upgradeData) ? 1 : 0);
                if (upgradeData.type == CardUpgradeData.Type.Charm) Debug($"{CardName(entity)} has {charms} charms");
                if (charms >= CharmsOnCard) Complete("charms_on_card");
            }
        }

        // A Crown for 100 or more Bling, and the Charm Merchant's upgraded cards.
        [HarmonyPatch(typeof(StatsSystem), "ShopItemPurchase")]
        private static class ShopPurchase
        {
            private static void Postfix(ShopItem item)
            {
                if (!On || item == null) return;
                string node = CurrentNode()?.type?.name;
                Debug($"bought at {node}: price {item.GetPrice()}, price factor {item.priceFactor}, crown {item.GetComponent<CrownHolderShop>() != null}, card {item.GetComponent<Card>() != null}");
                // A Crown for 100 Bling or more: with the bell that raises shop prices, crowns go 80, 90, 100, 110
                // over a run's four shops (the user's description, 2026-11-08).
                if (item.GetComponent<CrownHolderShop>() != null && item.GetPrice() >= FullCrownPrice) Complete("full_price_crown");
                if (node == "CampaignNodeCharmShop" && item.GetComponent<Card>() != null) Count("charm_merchant");
                TakeCursed(item.GetComponent<Entity>(), "bought");
            }
        }

        // Shade Sculptor: copying a Clunker. Copy runs on picking the card and again on confirming;
        // CopyRoutine only on confirming, with the card in toCopy.
        [HarmonyPatch(typeof(EventRoutineCopyItem), "CopyRoutine")]
        private static class SculptorCopy
        {
            private static readonly AccessTools.FieldRef<EventRoutineCopyItem, Entity> ToCopy =
                AccessTools.FieldRefAccess<EventRoutineCopyItem, Entity>("toCopy");

            private static void Prefix(EventRoutineCopyItem __instance)
            {
                var entity = ToCopy(__instance);
                if (!On) return;
                Debug($"Shade Sculptor copies {CardName(entity)} ({entity?.data?.cardType?.name})");
                if (entity?.data?.cardType?.name == "Clunker") Count("shade_sculptor");
            }
        }

        // Gnome Traveller: all three items taken at one visit (counted on the node).
        [HarmonyPatch(typeof(EventRoutineCurseItems), "TakeCard")]
        private static class GnomeTake
        {
            private static void Prefix()
            {
                var node = CurrentNode();
                if (!On || node?.data == null) return;
                int taken = (node.data.TryGetValue("apTaken", out object value) && value is int n ? n : 0) + 1;
                node.data["apTaken"] = taken;
                Debug($"Gnome Traveller item {taken} taken");
                if (taken >= GnomeItems) Complete("gnome_traveller");
            }
        }

        // A card that comes with a curse (negative) charm: the storm bell that curses card rewards
        // (ScriptDowngradeCardRewards) puts them on reward, shop and Charm Merchant cards. Picked from a
        // reward node (EntityChosen) or bought (ShopPurchase).
        private static void TakeCursed(Entity entity, string how)
        {
            var curses = entity?.data?.upgrades?.Where(u => u != null && u.type == CardUpgradeData.Type.Charm && u.tier < 0).ToList();
            if (!On || curses == null || curses.Count == 0) return;
            Debug($"{how} {CardName(entity)} with {string.Join(", ", curses.Select(u => u.name))}");
            Count("curse_charmed");
        }

        [HarmonyPatch(typeof(StatsSystem), "EntityChosen")]
        private static class CardChosen
        {
            private static void Postfix(Entity entity) => TakeCursed(entity, "took");
        }

        // A Gunk Fruit played on a boss.
        [HarmonyPatch(typeof(StatsSystem), "EntityTriggered")]
        private static class Triggered
        {
            private static void Postfix(ref Trigger trigger)
            {
                if (!On || CardName(trigger?.entity) != "Deadweight") return;
                bool onBoss = trigger.targets != null && trigger.targets.Any(IsBoss);
                Debug($"Gunk Fruit played on {string.Join(", ", trigger.targets?.Select(CardName) ?? new string[0])}");
                if (onBoss) Complete("gunk_boss");
            }
        }

        // An enemy killed by Soulbound Skulls. The skulls don't hit the enemy: they soulbind an ally and give
        // a random enemy "Take 100 Damage When Soulbound Unit Sacrificed" (a StatusEffectApplyXWhenUnitIsKilled),
        // and the enemy takes the damage when the ally is sacrificed (seen in Player.log, 2026-11-08).
        // The effect's Check coroutine deals it through StatusEffectApplyX.Run, which is patched here: while that
        // runs, its targets are marked, and when it ends each keeps the hit it was dealt. A kill counts only if it
        // happens inside the run or the enemy's last hit is still that one, so a soulbound enemy killed by an
        // ordinary attack doesn't count.
        private static readonly Dictionary<Entity, Hit> SoulboundHits = new Dictionary<Entity, Hit>();

        private static bool IsSoulbound(StatusEffectData effect) =>
            effect is StatusEffectApplyXWhenUnitIsKilled && effect.name != null && effect.name.Contains("Soulbound");

        [HarmonyPatch(typeof(StatusEffectApplyX), "Run", typeof(List<Entity>), typeof(int))]
        private static class SoulboundRun
        {
            private static void Postfix(StatusEffectApplyX __instance, List<Entity> __0, ref System.Collections.IEnumerator __result)
            {
                if (!On || !IsSoulbound(__instance) || __0 == null) return;
                __result = Track(__result, __0.Where(e => e != null).ToList());
            }

            private static System.Collections.IEnumerator Track(System.Collections.IEnumerator run, List<Entity> targets)
            {
                foreach (var target in targets) SoulboundHits[target] = null;
                Debug($"Soulbound Skulls strike {string.Join(", ", targets.Select(CardName))}");
                while (run.MoveNext()) yield return run.Current;
                foreach (var target in targets)
                    if (target != null && SoulboundHits.ContainsKey(target)) SoulboundHits[target] = target.lastHit;
            }
        }

        [HarmonyPatch(typeof(StatsSystem), "EntityKilled")]
        private static class Killed
        {
            private static void Postfix(Entity entity)
            {
                var battle = Battle.instance;
                if (!On || entity == null || battle == null || entity.owner == battle.player) return;
                if (!SoulboundHits.TryGetValue(entity, out Hit struck)) return;
                SoulboundHits.Remove(entity);
                var hit = entity.lastHit;
                bool bySkulls = struck == null || ReferenceEquals(struck, hit);
                Debug($"soulbound {CardName(entity)} killed by {(bySkulls ? "the skulls" : "something else")}: hit by {CardName(hit?.attacker)} for {hit?.damage}, type {hit?.damageType}");
                if (bySkulls) Count("soulbound");
            }
        }

        // Recycling Junk: Recycle destroys the Junk it collected when its card triggers.
        [HarmonyPatch(typeof(StatusEffectRecycle), nameof(StatusEffectRecycle.RunPreTriggerEvent))]
        private static class Recycle
        {
            private static readonly AccessTools.FieldRef<StatusEffectRecycle, List<Entity>> ToDestroy =
                AccessTools.FieldRefAccess<StatusEffectRecycle, List<Entity>>("toDestroy");

            private static void Prefix(StatusEffectRecycle __instance, out int __state) =>
                __state = ToDestroy(__instance)?.Count(e => CardName(e) == "Junk") ?? 0;

            private static void Postfix(bool __result, int __state)
            {
                if (!On || !__result || __state <= 0) return;
                Debug($"recycled {__state} Junk");
                Count("junk", __state);
            }
        }

        // Reaching a boss holding 200+ Bling.
        private static void OnPreBattleSetUp(CampaignNode node)
        {
            SoulboundHits.Clear();
            if (!On || node?.type == null || !node.type.name.Contains("Boss")) return;
            int bling = References.PlayerData?.inventory?.gold.Value ?? 0;
            Debug($"boss reached with {bling} Bling");
            if (bling >= BossBling) Complete("bling_boss");
        }

        // A battle won with the Egg still on the board.
        private static void OnBattleWin()
        {
            var battle = Battle.instance;
            if (!On || battle == null) return;
            if (Battle.GetCardsOnBoard(battle.player).Any(e => e != null && e.IsAliveAndExists() && CardName(e) == "Egg")) Complete("egg");
        }
    }
}
