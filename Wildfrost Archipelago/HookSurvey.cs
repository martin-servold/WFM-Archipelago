using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using UnityEngine.SceneManagement;

namespace WildfrostArchipelago
{
    /// <summary>
    /// Milestone 2: log-only hooks for every in-run event that could become an Archipelago location,
    /// and a before/after diff of all metaprogression save state so we can see exactly which keys
    /// each vanilla unlock path writes. Nothing here changes game behaviour.
    /// </summary>
    internal static class HookSurvey
    {
        // Progress keys gathered from every SaveSystem.Save/LoadProgressData call site in
        // Assembly-CSharp. Each is loaded with its real type, because LoadProgressData deserializes by T.
        private static readonly string[] StringListKeys =
        {
            "unlocked", "completedChallenges", "petHutUnlocks", "inventorHutUnlocks", "cardsDiscovered",
            "charmsDiscovered", "townNew", "goldHardModeModifiers", "activeHardModeModifiers", "lorePagesInspected",
        };
        private static readonly string[] IntKeys = { "maxStormPoints", "hardModeModifiersUnlocked", "selectedPet", "tutorialProgress" };
        private static readonly string[] BoolKeys = { "stormBellsUnlocked", "tutorialTownDone", "newFinalBoss" };

        private static Dictionary<string, List<string>> lastState;
        private static readonly HashSet<string> seenStats = new HashSet<string>();

        public static void Enable()
        {
            Events.OnSceneChanged += OnSceneChanged;
            Events.OnCampaignStart += OnCampaignStart;
            Events.OnCampaignFinal += OnCampaignFinal;
            Events.OnCampaignEnd += OnCampaignEnd;
            Events.OnBackToMainMenu += OnBackToMainMenu;
            Events.OnMapNodeSelect += OnMapNodeSelect;
            Events.OnEventStart += OnEventStart;
            Events.PreBattleSetUp += OnPreBattleSetUp;
            Events.PostBattle += OnPostBattle;
            Events.OnMinibossIntro += OnMinibossIntro;
            Events.OnEntityFlee += OnEntityFlee;
            Events.OnEntityChosen += OnEntityChosen;
            Events.OnUpgradeGained += OnUpgradeGained;
            Events.OnShopItemPurchase += OnShopItemPurchase;
            Events.OnMuncherFeed += OnMuncherFeed;
            Events.OnPullRewards += OnPullRewards;
            Events.OnTownUnlock += OnTownUnlock;
            Events.OnChallengeCompletedSaved += OnChallengeCompletedSaved;
            Events.OnStatChanged += OnStatChanged;
        }

        public static void Disable()
        {
            Events.OnSceneChanged -= OnSceneChanged;
            Events.OnCampaignStart -= OnCampaignStart;
            Events.OnCampaignFinal -= OnCampaignFinal;
            Events.OnCampaignEnd -= OnCampaignEnd;
            Events.OnBackToMainMenu -= OnBackToMainMenu;
            Events.OnMapNodeSelect -= OnMapNodeSelect;
            Events.OnEventStart -= OnEventStart;
            Events.PreBattleSetUp -= OnPreBattleSetUp;
            Events.PostBattle -= OnPostBattle;
            Events.OnMinibossIntro -= OnMinibossIntro;
            Events.OnEntityFlee -= OnEntityFlee;
            Events.OnEntityChosen -= OnEntityChosen;
            Events.OnUpgradeGained -= OnUpgradeGained;
            Events.OnShopItemPurchase -= OnShopItemPurchase;
            Events.OnMuncherFeed -= OnMuncherFeed;
            Events.OnPullRewards -= OnPullRewards;
            Events.OnTownUnlock -= OnTownUnlock;
            Events.OnChallengeCompletedSaved -= OnChallengeCompletedSaved;
            Events.OnStatChanged -= OnStatChanged;
            lastState = null;
            seenStats.Clear();
        }

        // ---- State diff ----

        public static void ResetBaseline(string reason)
        {
            lastState = null;
            CheckState(reason);
        }

        public static void CheckState(string reason)
        {
            Dictionary<string, List<string>> state;
            try
            {
                state = CaptureState();
            }
            catch (Exception e)
            {
                SurveyLog.Write($"state capture failed @ {reason}: {e.Message}");
                return;
            }

            if (lastState == null)
            {
                SurveyLog.Write($"state baseline @ {reason}:");
                foreach (var kv in state.OrderBy(k => k.Key))
                {
                    SurveyLog.Write($"  {kv.Key} ({kv.Value.Count}) = {string.Join(", ", kv.Value)}");
                }
            }
            else
            {
                foreach (string key in state.Keys.Union(lastState.Keys).OrderBy(k => k))
                {
                    state.TryGetValue(key, out var now);
                    lastState.TryGetValue(key, out var before);
                    now = now ?? new List<string>();
                    before = before ?? new List<string>();
                    var added = now.Except(before).ToList();
                    var removed = before.Except(now).ToList();
                    if (added.Count == 0 && removed.Count == 0) continue;
                    SurveyLog.Write($"state change @ {reason}: {key} +[{string.Join(", ", added)}] -[{string.Join(", ", removed)}]");
                }
            }
            lastState = state;
        }

        private static Dictionary<string, List<string>> CaptureState()
        {
            var state = new Dictionary<string, List<string>>();

            foreach (string key in StringListKeys)
                Capture(state, "save." + key, () => SaveSystem.LoadProgressData<List<string>>(key, null));
            foreach (string key in IntKeys)
                Capture(state, "save." + key, () => SaveSystem.LoadProgressData(key, -1));
            foreach (string key in BoolKeys)
                Capture(state, "save." + key, () => SaveSystem.LoadProgressData(key, false));
            Capture(state, "save.challengeProgress", () => SaveSystem.LoadProgressData<List<ChallengeProgress>>("challengeProgress", null));
            Capture(state, "save.townProgress", () => SaveSystem.LoadProgressData<Progression>("townProgress", null));
            Capture(state, "save.frameLevels", () => SaveSystem.LoadProgressData<Dictionary<string, int>>("frameLevels", null));

            // MetaprogressionSystem.data is internal; it holds the unlock-ordered card/charm lists the
            // GetLocked* methods index into.
            if (AccessTools.Field(typeof(MetaprogressionSystem), "data")?.GetValue(null) is Dictionary<string, object> data)
            {
                foreach (var kv in data)
                {
                    var value = kv.Value;
                    Capture(state, "meta." + kv.Key, () => value);
                }
            }
            Capture(state, "meta.GetUnlockedList()", () => MetaprogressionSystem.GetUnlockedList());
            Capture(state, "meta.GetUnlockedPets()", () => MetaprogressionSystem.GetUnlockedPets());
            Capture(state, "meta.GetLockedClasses()", () => MetaprogressionSystem.GetLockedClasses());
            return state;
        }

        private static void Capture(Dictionary<string, List<string>> state, string key, Func<object> read)
        {
            object value;
            try { value = read(); }
            catch (Exception e) { state[key] = new List<string> { "<error " + e.GetType().Name + ">" }; return; }

            if (value is IEnumerable list && !(value is string) && !(value is IDictionary))
                state[key] = list.Cast<object>().Select(x => SurveyLog.Describe(x)).ToList();
            else if (value is IDictionary dict)
                state[key] = dict.Keys.Cast<object>().Select(k => $"{k}={SurveyLog.Describe(dict[k])}").ToList();
            else
                state[key] = new List<string> { SurveyLog.Describe(value) };
        }

        // ---- Events ----

        private static void OnSceneChanged(Scene scene) => CheckState("scene " + scene.name);
        private static void OnBackToMainMenu() => CheckState("back to main menu");

        private static void OnCampaignStart()
        {
            SurveyLog.Write("campaign start");
            CheckState("campaign start");
        }

        // Fires after OnCampaignEnd on a win (seen in the first survey run), not on reaching the final area.
        private static void OnCampaignFinal() => SurveyLog.Write("campaign final");

        private static void OnCampaignEnd(Campaign.Result result, CampaignStats stats, PlayerData playerData)
        {
            SurveyLog.Write($"campaign end result={result} class={SurveyLog.Name(playerData?.classData)}");
            CheckState("campaign end " + result);
        }

        private static void OnMapNodeSelect(MapNode mapNode) => SurveyLog.Write("map node select " + Node(mapNode?.campaignNode));

        private static void OnEventStart(CampaignNode node, EventRoutine routine) =>
            SurveyLog.Write($"event start {Node(node)} routine={routine?.GetType().Name}");

        private static void OnPreBattleSetUp(CampaignNode node)
        {
            string data = node?.data == null ? "" : string.Join(", ", node.data.Select(kv => $"{kv.Key}={Short(kv.Value)}"));
            SurveyLog.Write($"battle setup {Node(node)} data={{{data}}}");
        }

        private static void OnPostBattle(CampaignNode node) => SurveyLog.Write("post battle " + Node(node));
        private static void OnMinibossIntro(Entity e) => SurveyLog.Write("miniboss intro " + SurveyLog.Card(e));

        private static void OnEntityFlee(Entity e) =>
            SurveyLog.Write($"entity flee {SurveyLog.Card(e)} leader={e?.data?.cardType != null && e.data.cardType.miniboss}");

        private static void OnEntityChosen(Entity e) => SurveyLog.Write("entity chosen " + SurveyLog.Card(e));
        private static void OnUpgradeGained(CardUpgradeData u) => SurveyLog.Write($"upgrade gained {SurveyLog.Name(u)} type={u?.type}");

        private static void OnShopItemPurchase(ShopItem item)
        {
            var entity = item ? item.GetComponentInChildren<Entity>() : null;
            SurveyLog.Write($"shop purchase {SurveyLog.Name(item)} price={item?.price} card={SurveyLog.Card(entity)}");
        }

        private static void OnMuncherFeed(Entity e) => SurveyLog.Write("muncher feed " + SurveyLog.Card(e));

        private static void OnPullRewards(object caller, ref string type, ref int amount, ref List<DataFile> list)
        {
            string names = list == null ? "null" : string.Join(", ", list.Take(15).Select(SurveyLog.Name));
            SurveyLog.Write($"pull rewards caller={caller?.GetType().Name} type={type} amount={amount} -> {list?.Count ?? 0}: {names}");
        }

        private static void OnTownUnlock(UnlockData unlock)
        {
            SurveyLog.Write($"town unlock {SurveyLog.Name(unlock)} type={unlock?.type}");
            CheckState("town unlock " + SurveyLog.Name(unlock));
        }

        private static void OnChallengeCompletedSaved(ChallengeData challenge)
        {
            SurveyLog.Write($"challenge completed {SurveyLog.Name(challenge)} reward={SurveyLog.Name(challenge?.reward)}");
            CheckState("challenge completed " + SurveyLog.Name(challenge));
        }

        // Stats fire constantly mid-battle; log only the first change of each stat/key pair so the
        // survey shows which counters exist without drowning the log.
        private static void OnStatChanged(string stat, string key, int oldValue, int newValue)
        {
            if (seenStats.Add(stat + "/" + key))
                SurveyLog.Write($"stat first change {stat}/{key} {oldValue}->{newValue}");
        }

        private static string Node(CampaignNode node) =>
            node == null ? "null" : $"{node.name}#{node.id} area={node.areaIndex} tier={node.tier} type={SurveyLog.Name(node.type)} final={node.finalNode}";

        private static string Short(object o)
        {
            string s = SurveyLog.Describe(o);
            return s.Length > 120 ? s.Substring(0, 120) + "..." : s;
        }

        // ---- Harmony: unlock and achievement paths that have no Events hook ----

        [HarmonyPatch(typeof(AchievementsSystem), nameof(AchievementsSystem.Achieve))]
        private static class AchievePatch
        {
            private static void Prefix(string achievementId) => SurveyLog.Write("achievement " + achievementId);
        }

        [HarmonyPatch(typeof(ChallengeProgressSystem), nameof(ChallengeProgressSystem.AddProgress))]
        private static class ChallengeProgressPatch
        {
            private static void Postfix(string challengeName, int add) =>
                SurveyLog.Write($"challenge progress {challengeName} +{add} = {ChallengeProgressSystem.GetProgress(challengeName)}");
        }

        [HarmonyPatch(typeof(ChallengeSystem), nameof(ChallengeSystem.SetAsComplete))]
        private static class ChallengeCompletePatch
        {
            private static void Prefix(ChallengeData challengeData) =>
                SurveyLog.Write($"challenge set complete {SurveyLog.Name(challengeData)} reward={SurveyLog.Name(challengeData?.reward)}");
        }

        [HarmonyPatch(typeof(MetaprogressionSystem), nameof(MetaprogressionSystem.SetUnlocksReady))]
        private static class UnlocksReadyPatch
        {
            private static void Prefix(string unlockName) => SurveyLog.Write("unlocks ready " + unlockName);
        }

        // These are what filter reward pools, so they're the takeover point for AP-controlled pools.
        // Log each result only when it changes.
        private static readonly Dictionary<string, string> lastLocked = new Dictionary<string, string>();

        private static void LogLocked(string what, IEnumerable values)
        {
            // These patches stay applied with debug off; skip building the line then.
            if (!ArchipelagoMod.DebugMode) return;
            string joined = values == null ? "null" : string.Join(", ", values.Cast<object>().Select(SurveyLog.Name));
            if (lastLocked.TryGetValue(what, out string prev) && prev == joined) return;
            lastLocked[what] = joined;
            SurveyLog.Write($"{what} -> {joined}");
        }

        [HarmonyPatch(typeof(MetaprogressionSystem), nameof(MetaprogressionSystem.GetLockedItems))]
        private static class LockedItemsPatch
        {
            private static void Postfix(List<string> __result) => LogLocked("GetLockedItems", __result);
        }

        [HarmonyPatch(typeof(MetaprogressionSystem), nameof(MetaprogressionSystem.GetLockedCompanions))]
        private static class LockedCompanionsPatch
        {
            private static void Postfix(List<string> __result) => LogLocked("GetLockedCompanions", __result);
        }

        [HarmonyPatch(typeof(MetaprogressionSystem), nameof(MetaprogressionSystem.GetLockedCharms))]
        private static class LockedCharmsPatch
        {
            private static void Postfix(List<string> __result) => LogLocked("GetLockedCharms", __result);
        }

        [HarmonyPatch(typeof(MetaprogressionSystem), nameof(MetaprogressionSystem.GetLockedClasses))]
        private static class LockedClassesPatch
        {
            private static void Postfix(List<ClassData> __result) => LogLocked("GetLockedClasses", __result);
        }

        [HarmonyPatch(typeof(MetaprogressionSystem), nameof(MetaprogressionSystem.GetUnlockedPets))]
        private static class UnlockedPetsPatch
        {
            private static void Postfix(string[] __result) => LogLocked("GetUnlockedPets", __result);
        }
    }
}
