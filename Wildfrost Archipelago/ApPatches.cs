using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;

namespace WildfrostArchipelago
{
    /// <summary>
    /// The pool takeover. Each patch only acts while ApMode.Active (the AP profile is loaded), so the
    /// player's own profiles stay vanilla. The decisions themselves live in ApMode.
    /// </summary>
    internal static class ApPatches
    {
        // CharacterRewards.RemoveLockedCards strips these from the run's reward pools at campaign
        // start and load. Vanilla returns the tail of an unlock-ordered list; AP returns every card
        // not yet received. Cards received mid-run join the run's pools at once (ApMode.AddToRun).
        [HarmonyPatch(typeof(MetaprogressionSystem), nameof(MetaprogressionSystem.GetLockedItems))]
        private static class LockedItems
        {
            private static void Postfix(ref List<string> __result)
            {
                if (ApMode.Active) __result = ApMode.LockedCards("Item");
            }
        }

        [HarmonyPatch(typeof(MetaprogressionSystem), nameof(MetaprogressionSystem.GetLockedCompanions))]
        private static class LockedCompanions
        {
            private static void Postfix(ref List<string> __result)
            {
                if (ApMode.Active) __result = ApMode.LockedCards("Companion");
            }
        }

        [HarmonyPatch(typeof(MetaprogressionSystem), nameof(MetaprogressionSystem.GetLockedCharms))]
        private static class LockedCharms
        {
            private static void Postfix(ref List<string> __result)
            {
                if (ApMode.Active) __result = ApMode.LockedCards("Charm");
            }
        }

        // Tribe select and the town hall flags. Tribe select removes the locked classes from the game
        // mode's own ClassData list by object, and those are other instances than References.Classes
        // (Clunk stayed selectable), so every loaded instance of a locked tribe is returned.
        [HarmonyPatch(typeof(MetaprogressionSystem), nameof(MetaprogressionSystem.GetLockedClasses))]
        private static class LockedClasses
        {
            private static void Postfix(ref List<ClassData> __result)
            {
                if (!ApMode.Active) return;
                __result = References.Classes
                    .Concat(AddressableLoader.GetGroup<ClassData>("ClassData"))
                    .Concat(AddressableLoader.GetGroup<GameMode>("GameMode").SelectMany(m => m.classes ?? new ClassData[0]))
                    .Where(c => c != null && ApMode.TribeLocked(c.name))
                    .Distinct()
                    .ToList();
            }
        }

        // Vanilla reads petHutUnlocks; Wolfie (Snoof) has no unlock and is always there, except in seeds
        // that made it an item (ApMode.PetUnlocked). With no pet, the run starts without one (Gain).
        [HarmonyPatch(typeof(MetaprogressionSystem), nameof(MetaprogressionSystem.GetUnlockedPets))]
        private static class UnlockedPets
        {
            private static void Postfix(ref string[] __result)
            {
                if (!ApMode.Active) return;
                __result = MetaprogressionSystem.GetPetDict()
                    .Where(p => ApMode.PetUnlocked(p.Key, p.Value))
                    .Select(p => p.Key)
                    .ToArray();
            }
        }

        // Inside the pet house, a pet without an unlock (Snoof) is always shown, since vanilla always has
        // it; under AP it's an item (seen 2026-11-02). Once the cards are dealt, one not received is
        // taken out of its slot, and the slot gets back the empty look the locked ones have.
        [HarmonyPatch(typeof(PetHutSequence), "CreateCards")]
        private static class PetHutLockedPets
        {
            private static void Postfix(PetHutSequence __instance, ref IEnumerator __result)
            {
                if (ApMode.Active) __result = ThenHideLocked(__result, __instance);
            }

            private static IEnumerator ThenHideLocked(IEnumerator deal, PetHutSequence hut)
            {
                yield return deal;
                var slots = Traverse.Create(hut).Field("cardSlots").GetValue<CardContainer[]>();
                if (slots == null) yield break;
                var pets = MetaprogressionSystem.GetPetDict();
                foreach (var slot in slots.Where(s => s != null))
                {
                    foreach (var card in slot.ToList())
                    {
                        string pet = card?.data?.name;
                        if (pet == null || !pets.TryGetValue(pet, out string unlock) || ApMode.PetUnlocked(pet, unlock)) continue;
                        slot.Remove(card);
                        UnityEngine.Object.Destroy(card.gameObject);
                        var image = slot.GetComponent<UnityEngine.UI.Image>();
                        if (image != null) image.enabled = true;
                    }
                }
            }
        }

        // The pet house's flag in town shows "selectedPet" as a place in the full pet list (GetPetDict
        // order: Snoof, Booshu, Loki, ...), but Gain saves the pet's place among the unlocked ones. In
        // vanilla pets unlock in list order, so the two agree; under AP any mix can be unlocked, and a
        // lone Loki (place 0 of 1) showed Snoof's flag (seen 2026-11-02). Saved as its place in the
        // full list instead.
        [HarmonyPatch(typeof(SelectStartingPet), nameof(SelectStartingPet.Gain))]
        private static class PetHutFlag
        {
            private static void Postfix(SelectStartingPet __instance)
            {
                if (!ApMode.Active || __instance.selectedPetIndex < 0) return;
                var pets = Traverse.Create(__instance).Field("pets").GetValue<List<Entity>>();
                string pet = pets != null && __instance.selectedPetIndex < pets.Count ? pets[__instance.selectedPetIndex]?.data?.name : null;
                int place = MetaprogressionSystem.GetPetDict().Keys.ToList().IndexOf(pet);
                if (place >= 0) SaveSystem.SaveProgressData("selectedPet", place);
            }
        }

        // Everything else that asks "is X unlocked" (special map events, buildings, IsUnlocked)
        // reads this list.
        [HarmonyPatch(typeof(MetaprogressionSystem), nameof(MetaprogressionSystem.GetUnlockedList))]
        private static class UnlockedList
        {
            private static void Postfix(ref List<string> __result)
            {
                if (ApMode.Active) __result = ApMode.UnlockedList(__result ?? new List<string>());
            }
        }

        // Shroomers, Spikers, Bombers (Tribe 1) and Baby Berries, Inkers, Mimiks (Tribe 2) only
        // appear once their tribe challenge is done. Under AP the tribe item unlocks them.
        [HarmonyPatch(typeof(BattleLockData), nameof(BattleLockData.IsLocked))]
        private static class BattleLock
        {
            private static bool Prefix(BattleLockData __instance, ref bool __result)
            {
                if (!ApMode.Active) return true;
                bool? locked = ApMode.BattleLocked(__instance.linkToChallenge?.name);
                if (locked == null) return true;
                __result = locked.Value;
                return false;
            }
        }

        // CheckSave writes each completed challenge's reward into `unlocked` (ignored under AP by
        // UnlockedList) and `townNew`, which plays the town's "new unlock" pop-ups. Drop the pop-ups
        // for rewards the multiworld controls, since they unlock nothing.
        [HarmonyPatch(typeof(ChallengeSystem), "CheckSave")]
        private static class ChallengeRewards
        {
            private static void Postfix()
            {
                if (!ApMode.Active) return;
                var townNew = SaveSystem.LoadProgressData("townNew", new List<string>());
                if (townNew.RemoveAll(ApMode.IsControlledUnlock) > 0) SaveSystem.SaveProgressData("townNew", townNew);
            }
        }

        // Nothing is unlocked at the start of a seed, so a run's reward pools can be empty. A charm
        // node then throws while the map is set up (it reads the name of the charm it didn't draw),
        // so does the Charm Shop event (one item and charms), and item and companion nodes would
        // offer nothing. While a pool the node needs has no card left this run, the node becomes a
        // Bling node instead, remembering what it was ("apWas").
        // Nodes draw when they're entered, not when the map is made (the user's call, 2026-11-02): the
        // map rolls every node at run start, and with a few cards in a pool the shops and boss rewards
        // took them all before any charm node was reached. So a roll at map setup puts its cards back
        // into the deck at once (unseen), and EnterNodeReroll rolls the node again on entry, marking it
        // drawn ("apDrawn"). Every reward node is marked as one ("apCards").
        [HarmonyPatch]
        private static class EmptyPoolNodes
        {
            private static readonly Dictionary<System.Type, string[]> PoolsOfNode = new Dictionary<System.Type, string[]>
            {
                { typeof(CampaignNodeTypeCharm), new[] { "Charms" } },
                { typeof(CampaignNodeTypeCharmShop), new[] { "Items", "Charms" } },
                { typeof(CampaignNodeTypeItem), new[] { "Items" } },
                { typeof(CampaignNodeTypeCompanion), new[] { "Units" } },
                // Shops cope with empty pools (they show fewer things), so they only get re-rolled.
                { typeof(CampaignNodeTypeShop), new string[0] },
                { typeof(CampaignNodeTypeClunkShop), new string[0] },
            };

            private static IEnumerable<MethodBase> TargetMethods() =>
                PoolsOfNode.Keys.Select(t => (MethodBase)AccessTools.Method(t, "SetUp"));

            /// <summary>Whether a node of this type would roll for real now, rather than become Bling.</summary>
            public static bool CanFill(CampaignNodeType type) =>
                type == null || HasForcedCards(type) || !PoolsOfNode.TryGetValue(type.GetType(), out string[] pools) || pools.All(HasCardsLeft);

            // Some item nodes always give a set card (the Lumin Vase pieces), drawing only the rest
            // of their choices from the pool. They have something to give even with the pool empty.
            private static readonly AccessTools.FieldRef<CampaignNodeTypeItem, List<CardData>> Forced =
                AccessTools.FieldRefAccess<CampaignNodeTypeItem, List<CardData>>("force");

            private static bool HasForcedCards(CampaignNodeType type) =>
                type is CampaignNodeTypeItem item && Forced(item)?.Count > 0;

            /// <summary>Set while a re-roll that must keep its node type (it holds a secret card) sets up.</summary>
            public static bool KeepType;

            /// <summary>Set while a node draws on entry: what it draws is shown, so it stays out of the deck.</summary>
            public static bool AtEntry;

            // __state is the node type it stood in for, when it became a Bling node.
            private static bool Prefix(CampaignNodeType __instance, CampaignNode node, ref IEnumerator __result, out string __state)
            {
                __state = null;
                if (!ApMode.Active || KeepType || CanFill(__instance)) return true;
                var gold = FindNodeType("CampaignNodeGold");
                if (gold == null) return true;
                SwapType(node, gold);
                __state = __instance.name;
                __result = gold.SetUp(node);
                return false;
            }

            // SetUp ends by assigning a new node.data, so the marks are written once it has run.
            private static void Postfix(CampaignNodeType __instance, CampaignNode node, ref IEnumerator __result, string __state)
            {
                if (ApMode.Active && PoolsOfNode.ContainsKey(__instance.GetType())) __result = Mark(__result, node, __state ?? __instance.name, KeepType, AtEntry);
            }

            // The map sets up all its nodes at once, so every node's check above can pass before any
            // of them draws, and the last ones to draw then find the deck empty (the charm node
            // indexes its draw without checking; item and companion nodes just come up empty). Such a
            // node becomes Bling after all, unless it must keep its type (a re-roll holding a secret card).
            private static IEnumerator Mark(IEnumerator setUp, CampaignNode node, string type, bool keepType, bool atEntry)
            {
                bool swapped = node.type.name != type;
                bool drewNothing = false;
                while (true)
                {
                    object current;
                    try
                    {
                        if (!setUp.MoveNext()) break;
                        current = setUp.Current;
                    }
                    catch (System.IndexOutOfRangeException) when (!swapped)
                    {
                        drewNothing = true;
                        break;
                    }
                    yield return current;
                }
                if (!swapped && !keepType && node.data != null && EnterNodeReroll.HoldsNothing(node)) drewNothing = true;
                var gold = drewNothing ? FindNodeType("CampaignNodeGold") : null;
                if (gold != null)
                {
                    ArchipelagoMod.Client?.LogDebug($"No {Describe(type)} left for this node when it drew: it gives Bling instead");
                    SwapType(node, gold);
                    swapped = true;
                    yield return gold.SetUp(node);
                }
                string was = swapped ? type : null;
                if (node.data == null) node.data = new Dictionary<string, object>();
                node.data[RolledKey] = true;
                if (was != null) node.data[WasKey] = was;
                if (atEntry) node.data[DrawnKey] = true;
                else ReturnToDeck(EnsurePools(), NamesIn(node));
            }
        }

        private const string RolledKey = "apCards";
        private const string WasKey = "apWas";
        private const string DrawnKey = "apDrawn";

        private static HashSet<string> NamesIn(CampaignNode node)
        {
            var names = new HashSet<string>();
            foreach (var value in node.data?.Values ?? Enumerable.Empty<object>()) CollectNames(value, names, 0);
            return names;
        }

        // A boss rolls its rewards with the map too; like the reward nodes, those go back into the deck,
        // and the boss draws them again when its fight is entered (EnterNodeReroll).
        [HarmonyPatch(typeof(CampaignNodeTypeBoss), nameof(CampaignNodeTypeBoss.GetRewards), typeof(CampaignNode))]
        private static class BossRewardsOnEntry
        {
            private static void Postfix(CampaignNode node)
            {
                if (!ApMode.Active || node?.data == null) return;
                if (EmptyPoolNodes.AtEntry) node.data[DrawnKey] = true;
                else ReturnToDeck(EnsurePools(), NamesIn(node));
            }
        }

        /// <summary>
        /// At 10 storm points AddSecretCardsSystem puts the Lumin Vase pieces (Broken Vase, Lumin
        /// Goop) into rolled nodes once the map is made and makes those nodes glow: in place of one of
        /// an item node's cards, of a shop's item without charms, or of a Charm Shop card. Under AP
        /// that went wrong three ways (all found 2026-10-31): a re-roll threw the piece away; a shop
        /// with no plain item (few item cards yet) got nothing; and an item node that rolled no cards
        /// threw. So a re-roll keeps its piece, the placement makes sure the piece landed, and a
        /// glowing node entered without a piece gets the one that is missing from the run.
        /// </summary>
        private static class SecretCards
        {
            private static readonly string[] Known = { "BrokenVase", "LuminSealant" };

            private static HashSet<string> Names()
            {
                var system = UnityEngine.Resources.FindObjectsOfTypeAll<AddSecretCardsSystem>().FirstOrDefault();
                return new HashSet<string>((system != null ? Traverse.Create(system).Field("cardsToAdd").GetValue<string[]>() : null) ?? Known);
            }

            /// <summary>The secret cards this node holds.</summary>
            public static List<string> In(CampaignNode node)
            {
                var names = new HashSet<string>();
                foreach (var value in node.data?.Values ?? Enumerable.Empty<object>()) CollectNames(value, names, 0);
                return names.Where(Names().Contains).ToList();
            }

            /// <summary>
            /// Into the node, as the game does: an item node gets it added while it has fewer cards
            /// than its choices, otherwise in place of a card (one without charms if there is one);
            /// a shop in place of a plain item, or as an extra one; a Charm Shop in place of a card.
            /// </summary>
            public static void PutBack(CampaignNode node, string card, string message)
            {
                if (In(node).Contains(card)) return;
                var data = AddressableLoader.Get<CardData>("CardData", card);
                if (data == null) return;
                if (node.data.TryGetValue("shopData", out object shopValue) && shopValue is ShopRoutine.Data shop)
                    IntoShop(shop, data);
                else if (node.data.TryGetValue("data", out object charmValue) && charmValue is EventRoutineCharmShop.Data charmShop)
                    IntoCharmShop(charmShop, data);
                else if (node.type is CampaignNodeTypeItem || node.type is CampaignNodeTypeCurseItems)
                    IntoCards(node, card);
                else
                    return;
                ArchipelagoMod.Client?.LogDebug(string.Format(message, data.title));
            }

            private static void IntoCards(CampaignNode node, string card)
            {
                var cards = node.data.TryGetValue("cards", out object value) && value is SaveCollection<string> list
                    ? (list.collection ?? new string[0]).ToList()
                    : new List<string>();
                int choices = Traverse.Create(node.type).Field("choices").GetValue<int>();
                if (cards.Count < System.Math.Max(choices, 1))
                {
                    cards.Add(card);
                }
                else
                {
                    var free = Enumerable.Range(0, cards.Count).Where(i => !node.data.ContainsKey($"upgrades{i}")).ToList();
                    var options = free.Count > 0 ? free : Enumerable.Range(0, cards.Count).ToList();
                    int index = options[UnityEngine.Random.Range(0, options.Count)];
                    cards[index] = card;
                    node.data.Remove($"upgrades{index}");
                }
                node.data["cards"] = new SaveCollection<string>(cards.ToArray());
            }

            private static void IntoShop(ShopRoutine.Data shop, CardData card)
            {
                if (shop.items == null) shop.items = new List<ShopRoutine.Item>();
                var item = new ShopRoutine.Item("Items", card, 0, UnityEngine.Random.Range(0.8f, 1.2f));
                var plain = Enumerable.Range(0, shop.items.Count)
                    .Where(i => shop.items[i].category == "Items" && !(shop.upgrades != null && i < shop.upgrades.Count && shop.upgrades[i]?.Length > 0))
                    .ToList();
                if (plain.Count > 0)
                {
                    int index = plain[UnityEngine.Random.Range(0, plain.Count)];
                    item.priceFactor = shop.items[index].priceFactor;
                    shop.items[index] = item;
                    return;
                }
                // Charms on shop items are kept by index, so a new one gets none.
                if (shop.upgrades != null && shop.upgrades.Count == shop.items.Count) shop.upgrades.Add(new string[0]);
                shop.items.Add(item);
            }

            private static void IntoCharmShop(EventRoutineCharmShop.Data shop, CardData card)
            {
                if (shop.cards == null) shop.cards = new List<EventRoutineCharmShop.UpgradedCard>();
                var upgraded = new EventRoutineCharmShop.UpgradedCard
                {
                    cardDataName = card.name,
                    upgradeNames = new string[0],
                    price = UnityEngine.Mathf.RoundToInt(card.value * UnityEngine.Random.Range(0.8f, 1.2f)),
                    priceFactor = 1f,
                    purchased = false,
                };
                if (shop.cards.Count > 0) shop.cards[UnityEngine.Random.Range(0, shop.cards.Count)] = upgraded;
                else shop.cards.Add(upgraded);
            }

            /// <summary>A glowing node without a piece gets the one missing from the run, if any.</summary>
            public static void Repair(CampaignNode node)
            {
                if (!node.glow || node.cleared || In(node).Count > 0) return;
                var given = CardsGivenOut();
                if (given.Contains("LuminVase")) return;
                string missing = Names().FirstOrDefault(c => !given.Contains(c));
                if (missing != null) PutBack(node, missing, "This glowing node had lost its {0}: put back");
            }

            // The placement: an item node with no cards threw before placing anything (and stopped
            // the other piece too), and a shop without a plain item got nothing.
            [HarmonyPatch(typeof(AddSecretCardsSystem), "AddCardToNode")]
            private static class Placement
            {
                private static System.Exception Finalizer(System.Exception __exception, CampaignNode node, string cardName)
                {
                    if (!ApMode.Active || node?.data == null) return __exception;
                    if (__exception != null && !(__exception is System.ArgumentOutOfRangeException || __exception is System.IndexOutOfRangeException))
                        return __exception;
                    PutBack(node, cardName, "Placed {0} in a glowing node (the game couldn't)");
                    return null;
                }
            }
        }

        private static CampaignNodeType FindNodeType(string name) =>
            AddressableLoader.GetGroup<CampaignNodeType>("CampaignNodeType").FirstOrDefault(t => t.name == name);

        // Entering a reward node that hasn't drawn yet rolls it now, from what this run hasn't shown,
        // and a Bling node that stood in for one turns back into it if it can be filled. A stand-in
        // that stays Bling says so, since its map icon shows the node it replaced. A boss draws its
        // rewards when its fight is entered. Cleared nodes are left alone.
        [HarmonyPatch(typeof(Campaign), "EnterNode")]
        private static class EnterNodeReroll
        {
            private static void Postfix(CampaignNode node, ref IEnumerator __result)
            {
                if (!ApMode.Active || node == null || node.cleared || node.data == null) return;
                if (node.type is CampaignNodeTypeBoss && node.data.ContainsKey("rewards") && !node.data.ContainsKey(DrawnKey))
                {
                    DrawBossRewards(node);
                    return;
                }
                bool undrawn = node.data.ContainsKey(RolledKey) && !node.data.ContainsKey(DrawnKey) && !Opened(node);
                if (undrawn)
                {
                    __result = Reroll(node, __result);
                    return;
                }
                SecretCards.Repair(node);
                if (node.data.ContainsKey(WasKey)) __result = AnnounceBling(node, __result);
            }

            // A chest or charm opened (or a shop visited) before the game was quit is saved that way,
            // and continuing enters it again: its cards were already seen, so it keeps them, or a
            // re-roll undid the shop's purchases. (Saves from before draws on entry have no apDrawn.)
            internal static bool Opened(CampaignNode node) =>
                node.data.TryGetValue("open", out object open) && open is bool isOpen && isOpen
                || node.data.TryGetValue("openCount", out object count) && System.Convert.ToInt32(count) > 0;

            // An item or companion node that drew no cards (it drew from the wrong pools before the
            // RunRewards fix, or lost the map setup's race for the last cards) rolls again rather
            // than open empty.
            internal static bool HoldsNothing(CampaignNode node) =>
                (node.type is CampaignNodeTypeItem || node.type is CampaignNodeTypeCompanion)
                && (!node.data.TryGetValue("cards", out object cards) || !(cards is SaveCollection<string> list) || list.Count == 0);

            private static IEnumerator Reroll(CampaignNode node, IEnumerator enter)
            {
                var was = node.data.TryGetValue(WasKey, out object name) ? FindNodeType(name as string) : null;
                var secrets = SecretCards.In(node);
                // SetUp replaces node.data; clearing it first keeps old keys from leaking into one that adds.
                node.data.Clear();
                if (was != null) SwapType(node, was);
                // What it rolled with the map already went back into the deck then (Mark), or, in a run
                // continued from a save, the rebuilt pools left it in. Putting it back again here gave
                // out cards shown since, twice (a boss offered charms already in the deck, 2026-11-02).
                EnsurePools();
                ArchipelagoMod.Client?.LogDebug($"Entered this {Describe(node.type.name)} node: it draws now");
                // A node holding a secret card stays what it is even with its pool empty.
                EmptyPoolNodes.KeepType = secrets.Count > 0;
                EmptyPoolNodes.AtEntry = true;
                IEnumerator setUp;
                try
                {
                    setUp = node.type.SetUp(node);
                }
                finally
                {
                    EmptyPoolNodes.KeepType = EmptyPoolNodes.AtEntry = false;
                }
                yield return setUp;
                foreach (string card in secrets) SecretCards.PutBack(node, card, "Kept {0} in the re-rolled node");
                SecretCards.Repair(node);
                yield return AnnounceBling(node, enter);
            }

            // The rewards rolled with the map went back into the deck then (BossRewardsOnEntry); drawn now.
            private static void DrawBossRewards(CampaignNode node)
            {
                EnsurePools();
                node.data.Remove("rewards");
                EmptyPoolNodes.AtEntry = true;
                try
                {
                    CampaignNodeTypeBoss.GetRewards(node);
                }
                finally
                {
                    EmptyPoolNodes.AtEntry = false;
                }
            }

            private static IEnumerator AnnounceBling(CampaignNode node, IEnumerator enter)
            {
                if (node.data.TryGetValue(WasKey, out object was))
                {
                    ArchipelagoMod.Client?.LogDebug($"No {Describe(was as string)} left this run: this node gives Bling instead");
                }
                yield return enter;
            }
        }

        private static readonly Dictionary<string, string> NodeDescriptions = new Dictionary<string, string>
        {
            { "CampaignNodeItem", "item" },
            { "CampaignNodeCompanion", "companion" },
            { "CampaignNodeCharm", "charm" },
            { "CampaignNodeCharmShop", "Charm Merchant" },
            { "CampaignNodeShop", "shop" },
            { "CampaignNodeClunkShop", "Clunk shop" },
        };

        private static string Describe(string nodeType) =>
            nodeType != null && NodeDescriptions.TryGetValue(nodeType, out string text) ? text : nodeType;

        // Just the type. CampaignNode.SetType also resets the node's zone name and hides it again.
        private static void SwapType(CampaignNode node, CampaignNodeType type) =>
            AccessTools.Property(typeof(CampaignNode), nameof(CampaignNode.type)).SetValue(node, type, null);

        // The populator sets up one node of each linked pair and copies its data to the other
        // (CopyData). A stand-in's partner then held Bling data under its reward type, and the
        // continue screen threw reading its cards. The partner becomes Bling too.
        [HarmonyPatch(typeof(CampaignNode), nameof(CampaignNode.CopyData))]
        private static class LinkedStandIn
        {
            private static void Postfix(CampaignNode __instance, CampaignNode otherNode)
            {
                if (ApMode.Active && otherNode?.data != null && otherNode.data.ContainsKey(WasKey) && __instance.type != otherNode.type)
                {
                    SwapType(__instance, otherNode.type);
                }
            }
        }

        // A stand-in gives 1 Bling, not the Bling node's usual roll (decided by the user 2026-11-02): the
        // stand-ins were most of the early Bling, which bought charms and fed the Greed Charm. The amount
        // is read when the node is entered, so it's set then; real Bling nodes keep their roll.
        [HarmonyPatch(typeof(CampaignNodeTypeGold), nameof(CampaignNodeTypeGold.Run))]
        private static class StandInBling
        {
            private const int Amount = 1;

            private static void Prefix(CampaignNode node)
            {
                if (ApMode.Active && node?.data != null && node.data.ContainsKey(WasKey)) node.data["amount"] = Amount;
            }
        }

        // Saves made before that fix: a node with stand-in data loads as the Bling node it is.
        [HarmonyPatch(typeof(CampaignNodeSaveData), nameof(CampaignNodeSaveData.Load))]
        private static class StandInSaveRepair
        {
            private static void Postfix(CampaignNode __result)
            {
                if (!ApMode.Active || __result?.data == null || !__result.data.ContainsKey(WasKey) || __result.type?.name == "CampaignNodeGold") return;
                var gold = FindNodeType("CampaignNodeGold");
                if (gold != null) SwapType(__result, gold);
            }
        }

        // Map icons come from the node type when the map is built. A Bling stand-in shows the node it
        // replaced, so the map looks like vanilla and the node's real contents are a surprise only
        // when there is nothing left to give (EnterNodeReroll says so).
        // Item and companion icons also pick a bigger sprite by how many cards the node holds, and a
        // stand-in holds none, so it showed the small one: it gets the original's card count meanwhile.
        [HarmonyPatch(typeof(MapNew), "CreateNode")]
        private static class StandInIcon
        {
            private static void Prefix(CampaignNode campaignNode, out CampaignNodeType __state)
            {
                __state = null;
                if (!ApMode.Active || campaignNode?.data == null || !campaignNode.data.TryGetValue(WasKey, out object was)) return;
                var original = FindNodeType(was as string);
                if (original == null) return;
                __state = campaignNode.type;
                SwapType(campaignNode, original);
                int cards = CardCount(original);
                if (cards > 0 && !campaignNode.data.ContainsKey(IconCardsKey))
                {
                    campaignNode.data[IconCardsKey] = new SaveCollection<string>(Enumerable.Repeat("Junk", cards).ToArray());
                    lent.Add(campaignNode);
                }
            }

            private static void Postfix(CampaignNode campaignNode, CampaignNodeType __state)
            {
                if (__state == null) return;
                SwapType(campaignNode, __state);
                if (lent.Remove(campaignNode)) campaignNode.data.Remove(IconCardsKey);
            }

            private const string IconCardsKey = "cards";
            private static readonly HashSet<CampaignNode> lent = new HashSet<CampaignNode>();

            // What a real node of this type holds: its choices plus its set cards.
            private static int CardCount(CampaignNodeType type)
            {
                if (!(type is CampaignNodeTypeItem) && !(type is CampaignNodeTypeCompanion)) return 0;
                var t = Traverse.Create(type);
                return t.Field("choices").GetValue<int>() + (t.Field("force").GetValue<List<CardData>>()?.Count ?? 0);
            }
        }

        // Hovering a node shows its label. A reward node's label (a stand-in's: the node it replaced)
        // says when entering it now would give Bling, so the player knows before choosing the path, and
        // a battle's says whether its check for this tribe was sent (CheckMarker). The label's own
        // text is kept, so the added line changes as cards arrive and checks are sent.
        [HarmonyPatch(typeof(MapNode), "Hover")]
        private static class MapLabel
        {
            private static readonly ConditionalWeakTable<TextMeshFitter, string> originalText = new ConditionalWeakTable<TextMeshFitter, string>();

            private static void Postfix(MapNode __instance)
            {
                var node = __instance.campaignNode;
                if (!ApMode.Active || node?.data == null) return;
                string line = StandInLine(node) ?? CheckMarker.LabelLine(node);
                var label = Traverse.Create(__instance).Field("label").GetValue<MapNodeLabel>();
                var fitter = label == null ? null : Traverse.Create(label).Field("textFitter").GetValue<TextMeshFitter>();
                if (fitter == null) return;
                if (!originalText.TryGetValue(fitter, out string text))
                {
                    if (line == null) return;
                    text = fitter.text;
                    originalText.Add(fitter, text);
                }
                fitter.text = line != null ? $"{text}\n<size=70%>{line}</size>" : text;
            }

            private static string StandInLine(CampaignNode node)
            {
                if (node.cleared) return null;
                if (node.data.TryGetValue(WasKey, out object was))
                {
                    return EmptyPoolNodes.CanFill(FindNodeType(was as string)) ? null : $"No {Describe(was as string)} left: Bling";
                }
                // A node that draws when entered (EnterNodeReroll) gives Bling if its pool is empty by
                // then; one holding a secret card keeps its type.
                bool undrawn = node.data.ContainsKey(RolledKey) && !node.data.ContainsKey(DrawnKey) && !EnterNodeReroll.Opened(node);
                if (undrawn && SecretCards.In(node).Count == 0)
                {
                    return EmptyPoolNodes.CanFill(node.type) ? null : $"No {Describe(node.type.name)} left: Bling";
                }
                // An empty node from before empty draws became stand-ins re-rolls on entry, and gives
                // Bling if there is still nothing to draw.
                bool empty = EnterNodeReroll.HoldsNothing(node) && !EnterNodeReroll.Opened(node) && SecretCards.In(node).Count == 0;
                return empty && !EmptyPoolNodes.CanFill(node.type) ? $"No {Describe(node.type.name)} left: Bling" : null;
            }
        }

        // In-battle hints (redraw bell, aimless enemies, reactions, wave bell, charms, crowns,
        // injuries) count per profile until the player has done each thing enough, so a fresh AP
        // profile would teach a player who has finished the game. These systems are created with
        // the run, so they are stopped from subscribing to anything when they start.
        [HarmonyPatch]
        private static class TutorialHints
        {
            private static IEnumerable<MethodBase> TargetMethods() =>
                new[]
                {
                    typeof(DynamicTutorialSystem), typeof(DynamicReactionTutorialSystem), typeof(DynamicWaveBellTutorialSystem),
                    typeof(TutorialCharmSystem), typeof(TutorialCrownSystem), typeof(TutorialInjurySystem),
                }.Select(t => (MethodBase)AccessTools.DeclaredMethod(t, "OnEnable")).Where(m => m != null);

            private static bool Prefix() => !ApMode.Active;
        }

        // Each run's pools are a deck: drawn cards leave it, and vanilla reshuffles the whole pool in
        // when it runs out. Vanilla pools are big enough that this rarely happens; AP pools of a few
        // cards would offer the same cards at every node. So under AP a card pool is only shuffled
        // in once per run, and each card is offered at most once (cards received mid-run are added
        // to the deck by AddToDeck). Modifier pools (the boss reward bells) refill as usual, but
        // without the bells this run has already shown (PoolRefill.Postfix).
        private static readonly ConditionalWeakTable<CharacterRewards.Pool, object> shuffledIn =
            new ConditionalWeakTable<CharacterRewards.Pool, object>();

        private static readonly AccessTools.FieldRef<CharacterRewards.Pool, List<DataFile>> Deck =
            AccessTools.FieldRefAccess<CharacterRewards.Pool, List<DataFile>>("current");

        [HarmonyPatch(typeof(CharacterRewards.Pool), "Populate")]
        private static class PoolRefill
        {
            private static bool Prefix(CharacterRewards.Pool __instance)
            {
                if (!ApMode.Active || !IsCardPool(__instance)) return true;
                if (shuffledIn.TryGetValue(__instance, out _)) return false;
                shuffledIn.Add(__instance, null);
                return true;
            }

            // A bell pool that ran out was shuffled in whole again, and a boss offered a bell an
            // earlier boss had shown (Noomlin twice, 2026-11-02). Those stay out unless every bell
            // has been shown.
            private static void Postfix(CharacterRewards.Pool __instance)
            {
                if (!ApMode.Active || IsCardPool(__instance)) return;
                var deck = Deck(__instance);
                if (deck == null || deck.Count == 0) return;
                var seen = CardsGivenOut(shownOnly: true);
                var shown = deck.Where(f => f != null && seen.Contains(f.name)).ToList();
                if (shown.Count == 0 || shown.Count == deck.Count) return;
                foreach (var file in shown) deck.Remove(file);
                ArchipelagoMod.Client?.LogDebug($"Boss reward pool refilled without {shown.Count} already shown");
            }
        }

        private static bool IsCardPool(CharacterRewards.Pool pool) =>
            pool.list != null && pool.list.Any(f => f is CardData || f is CardUpgradeData);

        private static bool RefillBlocked(CharacterRewards.Pool pool) =>
            ApMode.Active && shuffledIn.TryGetValue(pool, out _) && IsCardPool(pool);

        /// <summary>A card received mid-run: into the pool, and into the deck if it was already shuffled.</summary>
        public static void AddToDeck(CharacterRewards rewards, string poolType, DataFile file)
        {
            var pools = PoolLookup(rewards);
            if (pools == null || !pools.TryGetValue(poolType, out CharacterRewards.Pool pool))
            {
                rewards.Add(poolType, new[] { file });
                return;
            }
            if (pool.list == null || !pool.list.Contains(file)) pool.Add(file);
            var deck = Deck(pool);
            if (shuffledIn.TryGetValue(pool, out _) && !deck.Contains(file)) deck.Insert(UnityEngine.Random.Range(0, deck.Count + 1), file);
        }

        /// <summary>
        /// The run's rewards with its pools built. Continuing a saved run doesn't rebuild them
        /// (every node was rolled when the map was made, so vanilla never draws again), and a
        /// re-roll or a card received mid-run then drew from nothing. Built here as a new run
        /// does, which also strips the cards not received yet. A new run's pools have given out
        /// nothing, but this run's have: the cards in the deck and on the map's nodes are taken
        /// out again, or a re-rolled shop offered a card a reward node already had.
        /// </summary>
        public static CharacterRewards EnsurePools()
        {
            var rewards = RunRewards();
            var classData = References.PlayerData?.classData;
            if (rewards == null || classData == null) return rewards;
            var pools = PoolLookup(rewards);
            if (pools == null || pools.Count == 0)
            {
                rewards.Populate(classData);
                rewards.RemoveLockedCards();
                var seen = CardsGivenOut(shownOnly: true);
                pools = PoolLookup(rewards);
                foreach (var pool in pools?.Values ?? Enumerable.Empty<CharacterRewards.Pool>())
                {
                    var taken = pool.list?.Where(f => f != null && seen.Contains(f.name)).ToList();
                    if (taken?.Count > 0) pool.PullOut(taken);
                }
                ArchipelagoMod.Client?.LogDebug($"Run reward pools rebuilt; {seen.Count} cards already in the deck or on the map left out");
            }
            return rewards;
        }

        // Names of the cards this run has given out: the deck (and its charms) and what the map nodes
        // hold, whatever shape their data takes (card lists, shop stock, single names, boss rewards).
        // shownOnly: just the nodes that drew on entry (or were opened or cleared); the others' rolls
        // went back into the deck.
        private static HashSet<string> CardsGivenOut(bool shownOnly = false)
        {
            var names = new HashSet<string>();
            var inventory = References.PlayerData?.inventory;
            if (inventory != null)
            {
                foreach (var card in inventory.deck.Concat(inventory.reserve))
                {
                    names.Add(card.name);
                    foreach (var charm in card.upgrades ?? new List<CardUpgradeData>()) names.Add(charm.name);
                }
                foreach (var charm in inventory.upgrades ?? new List<CardUpgradeData>()) names.Add(charm.name);
            }
            foreach (var node in Campaign.instance?.nodes ?? new List<CampaignNode>())
            {
                if (node?.data == null) continue;
                if (shownOnly && !node.cleared && !node.data.ContainsKey(DrawnKey) && !EnterNodeReroll.Opened(node)) continue;
                foreach (var value in node.data.Values) CollectNames(value, names, 0);
            }
            return names;
        }

        private static void CollectNames(object value, HashSet<string> names, int depth)
        {
            if (value == null || depth > 4) return;
            switch (value)
            {
                case string name:
                    names.Add(name);
                    return;
                case SaveCollection<string> list:
                    foreach (var name in list.collection ?? new string[0]) names.Add(name);
                    return;
                case ShopRoutine.Data shop:
                    foreach (var item in shop.items ?? new List<ShopRoutine.Item>()) names.Add(item.cardDataName);
                    foreach (var charm in shop.charms ?? new List<string>()) names.Add(charm);
                    return;
                case IDictionary dictionary:
                    foreach (var inner in dictionary.Values) CollectNames(inner, names, depth + 1);
                    return;
                case IEnumerable many:
                    foreach (var inner in many) CollectNames(inner, names, depth + 1);
                    return;
                case UnityEngine.Object _:
                    return;
            }
            // The game's own save objects, such as a boss node's rewards (a charm reward holds its
            // charm's name in upgradeName): their public fields.
            var type = value.GetType();
            if (type.Assembly != typeof(CampaignNode).Assembly) return;
            foreach (var field in type.GetFields(BindingFlags.Public | BindingFlags.Instance))
                CollectNames(field.GetValue(value), names, depth + 1);
        }

        /// <summary>
        /// Cards a node rolled with the map go back into the deck at once: it hasn't shown them, and it
        /// draws again when entered. Only for card pools already shuffled in (the others still hold
        /// every card for their first draw) and for the bell pools, which vanilla shuffles in itself.
        /// Bells drawn at setup used to stay out, and with each boss drawing twice the bell pool ran
        /// out and was shuffled in whole again (2026-11-02).
        /// </summary>
        private static void ReturnToDeck(CharacterRewards rewards, HashSet<string> names)
        {
            if (names.Count == 0) return;
            foreach (var pool in PoolLookup(rewards)?.Values ?? Enumerable.Empty<CharacterRewards.Pool>())
            {
                if (IsCardPool(pool) && !shuffledIn.TryGetValue(pool, out _)) continue;
                var deck = Deck(pool);
                foreach (var file in pool.list?.Where(f => f != null && names.Contains(f.name)).Distinct().ToList() ?? new List<DataFile>())
                {
                    if (!deck.Contains(file)) deck.Insert(UnityEngine.Random.Range(0, deck.Count + 1), file);
                }
            }
        }

        // The run's rewards are on the player, where reward nodes draw from. Not any CharacterRewards
        // in the scene: the gnome traveller (Curse Items) adds its own to the Campaign object at map
        // setup, with every tribe's items, and keeps it for the run. Finding that one instead, cards
        // received mid-run joined its pools, the empty-pool check looked at it, and a treasure drew
        // from the player's empty deck and came up empty (2026-10-31).
        private static CharacterRewards RunRewards() => References.Player != null ? References.Player.GetComponent<CharacterRewards>() : null;

        private static IDictionary<string, CharacterRewards.Pool> PoolLookup(CharacterRewards rewards) =>
            rewards == null ? null : AccessTools.Field(typeof(CharacterRewards), "poolLookup")?.GetValue(rewards) as IDictionary<string, CharacterRewards.Pool>;

        // Whether this run can still draw a card of the pool type. Before the run's rewards exist,
        // whether any received card fits the tribe. A continued run has no pools until something
        // builds them, so they are built here, as entering a node would: the map labels asked before
        // that, fell back to the received cards, and missed that those were all in the deck already
        // (seen 2026-10-31).
        private static bool HasCardsLeft(string poolType)
        {
            var pools = PoolLookup(References.Player != null ? EnsurePools() : RunRewards());
            if (pools == null || !pools.TryGetValue(poolType, out CharacterRewards.Pool pool)) return ApMode.RunHasCards(poolType);
            return (RefillBlocked(pool) ? Deck(pool) : pool.list)?.Count > 0;
        }

        // Pool.Pull loops until it has itemCount cards, refilling from the pool's list, and without
        // duplicates it needs that many different cards. Vanilla pools are always big enough; AP
        // pools can be empty or hold two charms when a shop wants three, and then the run start hangs
        // forever. Cap the request at the number of different cards that can be drawn.
        [HarmonyPatch(typeof(CharacterRewards.Pool), nameof(CharacterRewards.Pool.Pull), typeof(int), typeof(bool))]
        private static class PoolPull
        {
            private static void Prefix(CharacterRewards.Pool __instance, ref int itemCount, bool allowDuplicates) =>
                itemCount = ApMode.Active ? DrawableCount(__instance, itemCount, allowDuplicates, null) : itemCount;
        }

        [HarmonyPatch(typeof(CharacterRewards.Pool), nameof(CharacterRewards.Pool.Pull), typeof(int), typeof(bool), typeof(System.Predicate<DataFile>))]
        private static class PoolPullMatching
        {
            private static void Prefix(CharacterRewards.Pool __instance, ref int itemCount, bool allowDuplicates, System.Predicate<DataFile> match) =>
                itemCount = ApMode.Active ? DrawableCount(__instance, itemCount, allowDuplicates, match) : itemCount;
        }

        // GetFromOriginalList has the same loop, over the whole pool rather than the deck.
        [HarmonyPatch(typeof(CharacterRewards.Pool), nameof(CharacterRewards.Pool.GetFromOriginalList), typeof(int), typeof(bool))]
        private static class PoolOriginal
        {
            private static void Prefix(CharacterRewards.Pool __instance, ref int itemCount, bool allowDuplicates) =>
                itemCount = ApMode.Active ? DrawableCount(__instance, itemCount, allowDuplicates, null, fromDeck: false) : itemCount;
        }

        [HarmonyPatch(typeof(CharacterRewards.Pool), nameof(CharacterRewards.Pool.GetFromOriginalList), typeof(int), typeof(bool), typeof(System.Predicate<DataFile>))]
        private static class PoolOriginalMatching
        {
            private static void Prefix(CharacterRewards.Pool __instance, ref int itemCount, bool allowDuplicates, System.Predicate<DataFile> match) =>
                itemCount = ApMode.Active ? DrawableCount(__instance, itemCount, allowDuplicates, match, fromDeck: false) : itemCount;
        }

        private static int DrawableCount(CharacterRewards.Pool pool, int itemCount, bool allowDuplicates, System.Predicate<DataFile> match, bool fromDeck = true)
        {
            // Without refills only the deck is left; otherwise the whole pool can be shuffled in.
            bool blocked = fromDeck && RefillBlocked(pool);
            var drawable = ((blocked ? Deck(pool) : pool.list) ?? new List<DataFile>()).Where(f => match == null || match(f)).ToList();
            if (drawable.Count == 0) return 0;
            if (allowDuplicates) return blocked ? System.Math.Min(itemCount, drawable.Count) : itemCount;
            return System.Math.Min(itemCount, drawable.Distinct().Count());
        }

        // A boss node rolls its rewards when the map is set up, and the random charm reward indexes
        // the first charm it draws without checking there is one. With no charm for this run that
        // throws; the reward is dropped instead (the reward screen shows however many there are).
        [HarmonyPatch(typeof(BossRewardDataRandomCharm), nameof(BossRewardDataRandomCharm.Pull))]
        private static class BossRandomCharm
        {
            private static System.Exception Finalizer(System.Exception __exception, ref BossRewardData.Data __result)
            {
                if (!(__exception is System.IndexOutOfRangeException) || !ApMode.Active) return __exception;
                __result = null;
                return null;
            }
        }

        [HarmonyPatch(typeof(CampaignNodeTypeBoss), nameof(CampaignNodeTypeBoss.GetRewards), typeof(BossRewardPool))]
        private static class BossRewards
        {
            private static void Postfix(List<BossRewardData.Data> __result)
            {
                if (ApMode.Active) __result?.RemoveAll(d => d == null);
            }
        }

        // The end-of-run Town Progress panel names each completed challenge's vanilla reward, which
        // unlocks nothing under AP. The overlay shows what the check actually found.
        [HarmonyPatch(typeof(ChallengeProgressDisplay), nameof(ChallengeProgressDisplay.SetRewardText))]
        private static class ChallengeRewardText
        {
            private static void Postfix(ChallengeProgressDisplay __instance)
            {
                if (ApMode.Active && __instance.text != null) __instance.text.text = "Archipelago check sent";
            }
        }

        // The same panel fills one challenge at a time, about 2.5 to 4.5 seconds each, and the end
        // screen waits for it. Under AP every challenge is open from the start, so a run moves many
        // of them and the screen took a minute or more (2026-11-03). The same sequence with shorter
        // timings: a 1.5s fill, so the bar reads before it says check sent (the user's call), a short
        // hold on completed ones, and almost no gap between them.
        [HarmonyPatch(typeof(ChallengeProgressSequence), nameof(ChallengeProgressSequence.Start))]
        private static class FastTownProgress
        {
            private const float Gap = 0.05f, FillTime = 1.5f, CompletedHold = 0.5f;

            private static readonly AccessTools.FieldRef<ChallengeProgressSequence, ChallengeProgressDisplay> Prefab =
                AccessTools.FieldRefAccess<ChallengeProgressSequence, ChallengeProgressDisplay>("progressPrefab");
            private static readonly AccessTools.FieldRef<ChallengeProgressSequence, UnityEngine.Transform> Group =
                AccessTools.FieldRefAccess<ChallengeProgressSequence, UnityEngine.Transform>("progressGroup");
            private static readonly AccessTools.FieldRef<ChallengeProgressSequence, List<ChallengeProgressDisplay>> Panels =
                AccessTools.FieldRefAccess<ChallengeProgressSequence, List<ChallengeProgressDisplay>>("panels");
            private static readonly MethodInfo SetRunning = AccessTools.PropertySetter(typeof(ChallengeProgressSequence), "running");
            private static readonly MethodInfo UpdatePanelPositions = AccessTools.Method(typeof(ChallengeProgressSequence), "UpdatePanelPositions");

            private static bool Prefix(ChallengeProgressSequence __instance, ref IEnumerator __result)
            {
                if (!ApMode.Active || SetRunning == null || UpdatePanelPositions == null) return true;
                __result = Run(__instance);
                return false;
            }

            private static IEnumerator Run(ChallengeProgressSequence sequence)
            {
                SetRunning.Invoke(sequence, new object[] { true });
                try
                {
                    var moved = UnityEngine.Object.FindObjectOfType<ChallengeProgressSystem>()?.progress?
                        .Where(p => p.currentValue > p.originalValue).ToList() ?? new List<ChallengeProgress>();
                    foreach (var progress in moved)
                    {
                        yield return AddDisplay(sequence, progress);
                        yield return new UnityEngine.WaitForSeconds(Gap);
                    }
                }
                finally
                {
                    SetRunning.Invoke(sequence, new object[] { false });
                }
            }

            private static IEnumerator AddDisplay(ChallengeProgressSequence sequence, ChallengeProgress progress)
            {
                var challenge = AddressableLoader.Get<ChallengeData>("ChallengeData", progress.challengeName);
                if (challenge == null) yield break;
                var panel = UnityEngine.Object.Instantiate(Prefab(sequence), Group(sequence));
                Panels(sequence).Insert(0, panel);
                UpdatePanelPositions.Invoke(sequence, null);
                panel.Assign(challenge);
                panel.SetFill(progress.originalValue, challenge.goal);

                int fillTo = System.Math.Min(challenge.goal, progress.currentValue);
                Events.InvokeProgressStart(UnityEngine.Mathf.Clamp01((float)progress.originalValue / challenge.goal));
                panel.animator.SetBool("Increasing", true);
                LeanTween.value(panel.gameObject, progress.originalValue, fillTo, FillTime).setEaseOutQuad()
                    .setOnUpdate((float value) =>
                    {
                        panel.SetFill(value, challenge.goal);
                        panel.SetRemainingText(challenge, value);
                    });
                yield return new UnityEngine.WaitForSeconds(FillTime);
                panel.animator.SetBool("Increasing", false);
                Events.InvokeProgressStop();
                if (fillTo < challenge.goal) yield break;
                Events.InvokeProgressDing();
                panel.animator.SetTrigger("Ping");
                panel.SetRewardText(challenge);
                yield return new UnityEngine.WaitForSeconds(CompletedHold);
            }
        }

        // Bell levels come from Progressive Storm Bells (ApMode.ApplyStormBells), not from wins.
        // This also skips gilding the bells used in a True Final Boss win, which in vanilla is what
        // unlocks Overcrank.
        [HarmonyPatch(typeof(StormBellUnlockSystem), "CampaignEnd")]
        private static class StormBellWins
        {
            private static bool Prefix() => !ApMode.Active;
        }

        [HarmonyPatch(typeof(StormBellManager), "Awake")]
        private static class OvercrankLever
        {
            private static void Postfix(StormBellManager __instance)
            {
                if (!ApMode.Active) return;
                var lever = Traverse.Create(__instance).Field("overcranker").GetValue<UnityEngine.GameObject>();
                if (lever != null) lever.SetActive(ApMode.StormBells >= ApMode.OvercrankBells);
            }
        }

        // force_storm_bells: a new run only starts once the rung bells reach the storm point limit;
        // force_overcrank: and, with every bell level, once the Overcrank lever is pulled.
        // The bells are set on the selection screen itself, so that is where it's checked: when a
        // leader is picked, and again when the screen begins the run.
        // The forced level follows the picked leader's tribe's packs (ApMode.ForcedBells).
        private static string StormPointsShortfall(CharacterSelectScreen screen)
        {
            if (!ApMode.Active) return null;
            var leader = Traverse.Create(screen).Field("leaderSelection").GetValue<SelectLeader>()?.current;
            string clan = leader?.data?.classData?.name;
            if (clan == null) return null;
            int need = ApMode.RequiredStormPoints(clan);
            int have = need == 0 ? 0 : StormBellManager.GetCurrentStormPoints(StormBellManager.GetActiveStormBells());
            if (have < need) return $"This seed plays runs at full storm strength, as far as this tribe's packs carry it. Ring storm bells worth {need} points before starting (now {have}).";
            if (ApMode.RequiresOvercrank(clan) && !SaveSystem.LoadProgressData("stormPointOvercrank", false))
                return "This seed plays runs Overcranked once a tribe's packs carry it. Pull the Overcrank lever before starting.";
            return null;
        }

        /// <summary>The game's prompt box for a few seconds (run it as a coroutine), and the overlay.</summary>
        public static IEnumerator ShowPrompt(string text)
        {
            ArchipelagoMod.Client?.Log(text);
            // 7 wide: at 5 the longer trap and boon texts were cut off after three lines.
            PromptSystem.Create(Prompt.Anchor.Mid, 0f, 0f, 7f, Prompt.Emote.Type.Explain, Prompt.Emote.Position.Above);
            PromptSystem.SetTextAction(() => text);
            yield return new UnityEngine.WaitForSeconds(5f);
            PromptSystem.Hide();
        }

        // Picking a leader calls Continue, which opens the pet picker: block there, before anything
        // else has changed, so the player is still on the leader screen.
        [HarmonyPatch(typeof(CharacterSelectScreen), "Continue")]
        private static class ForcedStormPointsAtLeader
        {
            private static bool Prefix(CharacterSelectScreen __instance)
            {
                var pets = Traverse.Create(__instance).Field("petSelection").GetValue<SelectStartingPet>();
                if (pets == null || pets.running || pets.selectedPetIndex >= 0) return true;
                string shortfall = StormPointsShortfall(__instance);
                if (shortfall == null) return true;
                __instance.StartCoroutine(ShowPrompt(shortfall));
                return false;
            }
        }

        // Backstop for bells switched off after the leader was picked (or a run with no pet picker).
        [HarmonyPatch(typeof(CharacterSelectScreen), "ContinueRoutine")]
        private static class ForcedStormPointsAtSelection
        {
            private static bool Prefix(CharacterSelectScreen __instance, ref IEnumerator __result)
            {
                string shortfall = StormPointsShortfall(__instance);
                if (shortfall == null) return true;
                __result = ShowPrompt(shortfall);
                // Continue has already closed the pet picker, and Back has no step for that state,
                // which left the screen stuck. Reopen the picker, as Continue does on the way in.
                var screen = Traverse.Create(__instance);
                var pets = screen.Field("petSelection").GetValue<SelectStartingPet>();
                var leader = screen.Field("leaderSelection").GetValue<SelectLeader>()?.current;
                if (pets != null && leader != null && pets.CanRun)
                {
                    pets.Run(leader.entity);
                    screen.Method("SetTitlePet").GetValue();
                }
                return false;
            }
        }

        // Town challenge stones. Under AP a stone means "a check still to do": the slot under it shows
        // what the multiworld has given, which isn't tied to the challenge any more. Vanilla removes a
        // completed challenge's stone; under AP it stays, saying "Check sent".
        private const string CheckSentText = "Check sent";

        private static bool ChallengeDone(ChallengeData challenge) =>
            SaveSystem.LoadProgressData("completedChallenges", new List<string>()).Contains(challenge.name);

        private static ChallengeProgressDisplay CreateStone(ChallengeDisplayCreator creator, ChallengeData challenge)
        {
            var creatorData = Traverse.Create(creator);
            var prefab = creatorData.Field("displayPrefab").GetValue<ChallengeProgressDisplay>();
            var parent = creatorData.Field("displayParent").GetValue<UnityEngine.Transform>() ?? creator.transform;
            if (prefab == null) return null;
            var stone = UnityEngine.Object.Instantiate(prefab, parent);
            stone.Assign(challenge);
            stone.SetFill(challenge.goal, challenge.goal);
            if (stone.text != null) stone.text.text = CheckSentText;
            return stone;
        }

        [HarmonyPatch(typeof(ChallengeDisplayCreator), nameof(ChallengeDisplayCreator.Check))]
        private static class CheckSentStone
        {
            // Check can run more than once for a slot; one "Check sent" stone per creator.
            private static readonly ConditionalWeakTable<ChallengeDisplayCreator, ChallengeProgressDisplay> shown =
                new ConditionalWeakTable<ChallengeDisplayCreator, ChallengeProgressDisplay>();

            private static void Postfix(ChallengeDisplayCreator __instance)
            {
                if (shown.TryGetValue(__instance, out var old))
                {
                    if (old != null) UnityEngine.Object.Destroy(old.gameObject);
                    shown.Remove(__instance);
                }
                var challenge = __instance.challenge;
                if (!ApMode.Active || challenge == null || challenge.reward == null || !challenge.reward.IsActive || !ChallengeDone(challenge)) return;
                var stone = CreateStone(__instance, challenge);
                if (stone != null) shown.Add(__instance, stone);
            }
        }

        // The balloon's Daily Voyage is a fixed deck and tribe of the day, outside the multiworld's
        // items, so under AP it would hand out checks for free (the user asked to block it, 2026-10-31).
        // Selecting the balloon says so instead of starting or continuing one.
        [HarmonyPatch(typeof(BuildingBalloon), nameof(BuildingBalloon.Select))]
        private static class NoDailyVoyage
        {
            private static bool Prefix(BuildingBalloon __instance)
            {
                if (!ApMode.Active) return true;
                __instance.StartCoroutine(ShowPrompt("Daily Voyages are off while playing Archipelago."));
                return false;
            }
        }

        // The charm shrine's stones open by unlocked reward charm, which under AP shows what the
        // multiworld has given; that stays. A stone whose challenge is done and is a check gets the
        // "Check sent" banner the town's other challenge stones have (asked for by the user, 2026-10-31).
        [HarmonyPatch(typeof(ChallengeShrineSequence), "OnEnable")]
        private static class ShrineBanners
        {
            // In the snow below the stones' ground line, scaled to fit it. The shrine is a world-space
            // canvas, so the gap is in world units. Its stones are laid out after OnEnable, but their
            // container ("Challenge Stones") is already sized, and its bottom edge is the ground.
            private const float BannerScale = 0.5f, BelowGround = 0.1f;

            private static void Postfix(ChallengeShrineSequence __instance)
            {
                if (!ApMode.Active) return;
                var bannerPrefab = UnityEngine.Resources.FindObjectsOfTypeAll<ChallengeDisplayCreator>()
                    .Select(c => Traverse.Create(c).Field("displayPrefab").GetValue<ChallengeProgressDisplay>())
                    .FirstOrDefault(p => p != null);
                if (bannerPrefab == null) return;
                foreach (var stone in Traverse.Create(__instance).Field("challengeStones").GetValue<ChallengeStone[]>() ?? new ChallengeStone[0])
                {
                    var challenge = stone?.challenge;
                    if (challenge == null || !ChallengeDone(challenge) || ArchipelagoMod.Client?.IsLocation("challenge:" + challenge.name) != true) continue;
                    if (stone.GetComponentInChildren<ChallengeProgressDisplay>(true) != null) continue;
                    AddBanner(stone, bannerPrefab, challenge);
                }
            }

            private static void AddBanner(ChallengeStone stone, ChallengeProgressDisplay prefab, ChallengeData challenge)
            {
                var banner = UnityEngine.Object.Instantiate(prefab, stone.transform);
                banner.Assign(challenge);
                banner.SetFill(challenge.goal, challenge.goal);
                if (banner.text != null) banner.text.text = CheckSentText;
                // The stones size themselves around their children; the banner mustn't count, or it
                // lifts the stone off the ground.
                var layout = banner.gameObject.GetComponent<UnityEngine.UI.LayoutElement>() ?? banner.gameObject.AddComponent<UnityEngine.UI.LayoutElement>();
                layout.ignoreLayout = true;
                banner.transform.localScale = UnityEngine.Vector3.one * BannerScale;
                if (banner.transform is UnityEngine.RectTransform rect) rect.pivot = new UnityEngine.Vector2(0.5f, 1f);
                // The stones are moved into place after this, carrying the banner, so it keeps itself on the ground.
                banner.gameObject.AddComponent<OnGround>().gap = BelowGround;
                // The snow in front of the stones would cover it: drawn above everything around it.
                var parentCanvas = stone.GetComponentInParent<UnityEngine.Canvas>();
                var canvas = banner.gameObject.GetComponent<UnityEngine.Canvas>() ?? banner.gameObject.AddComponent<UnityEngine.Canvas>();
                canvas.overrideSorting = true;
                if (parentCanvas != null) canvas.sortingLayerID = parentCanvas.sortingLayerID;
                canvas.sortingOrder = (parentCanvas != null ? parentCanvas.sortingOrder : 0) + 100;
            }
        }

        /// <summary>
        /// Keeps a shrine banner just below its stone's lowest block, which stands on the ground. Run
        /// each frame, after the game has laid the stones out (their pieces aren't placed yet in
        /// OnEnable, and the stones move afterwards, carrying the banner).
        /// </summary>
        private class OnGround : UnityEngine.MonoBehaviour
        {
            public float gap;
            private readonly UnityEngine.Vector3[] corners = new UnityEngine.Vector3[4];

            private void LateUpdate()
            {
                var stone = transform.parent;
                if (stone == null) return;
                float bottom = float.MaxValue;
                foreach (var image in stone.GetComponentsInChildren<UnityEngine.UI.Image>())
                {
                    if (image.transform.IsChildOf(transform)) continue;
                    ((UnityEngine.RectTransform)image.transform).GetWorldCorners(corners);
                    bottom = UnityEngine.Mathf.Min(bottom, corners[0].y);
                }
                if (bottom == float.MaxValue) return;
                transform.position = new UnityEngine.Vector3(stone.position.x, bottom - gap, stone.position.z);
            }
        }

        // The miner (IcebreakerHutSequence) has three challenges and one stone, showing the one after
        // however many of its rewards are unlocked. Under AP that count follows received items, and
        // the challenges are unchained, so all three are shown, stacked upward from its stone.
        [HarmonyPatch(typeof(IcebreakerHutSequence), "SetCurrentChallenge")]
        private static class MinerStones
        {
            private static readonly List<UnityEngine.GameObject> extra = new List<UnityEngine.GameObject>();

            private static void Postfix(IcebreakerHutSequence __instance)
            {
                foreach (var go in extra) if (go != null) UnityEngine.Object.Destroy(go);
                extra.Clear();
                if (!ApMode.Active) return;
                var hut = Traverse.Create(__instance);
                var challenges = hut.Field("challenges").GetValue<ChallengeData[]>();
                var creator = hut.Field("challengeDisplayCreator").GetValue<ChallengeDisplayCreator>();
                if (challenges == null || creator == null) return;

                // The creator's own stone shows the first one not done yet (or "Check sent" if all are).
                var first = challenges.FirstOrDefault(c => c != null && !ChallengeDone(c)) ?? challenges.LastOrDefault();
                if (first != null && creator.challenge != first)
                {
                    foreach (var display in creator.GetComponentsInChildren<ChallengeProgressDisplay>(true)) UnityEngine.Object.Destroy(display.gameObject);
                    var parent = Traverse.Create(creator).Field("displayParent").GetValue<UnityEngine.Transform>();
                    if (parent != null) foreach (var display in parent.GetComponentsInChildren<ChallengeProgressDisplay>(true)) UnityEngine.Object.Destroy(display.gameObject);
                    creator.challenge = first;
                    creator.Check();
                }

                int row = 1;
                foreach (var challenge in challenges.Where(c => c != null && c != first))
                {
                    var stone = ChallengeDone(challenge) ? CreateStone(creator, challenge) : CreateProgressStone(creator, challenge);
                    if (stone == null) continue;
                    var rect = stone.transform as UnityEngine.RectTransform;
                    float height = rect != null ? rect.rect.height * rect.localScale.y : 1f;
                    stone.transform.localPosition += new UnityEngine.Vector3(0f, row * height * 1.1f, 0f);
                    extra.Add(stone.gameObject);
                    row++;
                }
            }

            private static ChallengeProgressDisplay CreateProgressStone(ChallengeDisplayCreator creator, ChallengeData challenge)
            {
                var stone = CreateStone(creator, challenge);
                if (stone == null) return null;
                var progress = SaveSystem.LoadProgressData<List<ChallengeProgress>>("challengeProgress", null)?
                    .FirstOrDefault(p => p != null && p.challengeName == challenge.name)?.currentValue ?? 0;
                stone.Assign(challenge);
                stone.SetFill(progress, challenge.goal);
                return stone;
            }
        }

        // Log what a run actually draws from, so a test doesn't need to play far to see it worked.
        [HarmonyPatch(typeof(CharacterRewards), "RemoveLockedCards")]
        private static class RewardPoolsLog
        {
            private static void Postfix(CharacterRewards __instance)
            {
                if (!ApMode.Active || __instance != RunRewards()) return;
                var pools = PoolLookup(__instance);
                if (pools == null) return;
                string sizes = string.Join(", ", pools.Select(p => $"{p.Key} {p.Value.list?.Count}"));
                ArchipelagoMod.Client?.LogDebug("Run reward pools: " + sizes);
            }
        }
    }
}
