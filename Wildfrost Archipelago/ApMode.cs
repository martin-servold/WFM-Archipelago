using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using HarmonyLib;

namespace WildfrostArchipelago
{
    /// <summary>
    /// Owns the AP rules of the game. Once a slot logs in, the game moves to a profile of its own
    /// for that seed and slot, and while that profile is active the patches in ApPatches hand
    /// unlocks to the multiworld: cards, tribes, pets and events come only from received items,
    /// every challenge is open from the start, and vanilla challenge rewards unlock nothing.
    /// Outside that profile (Default, or before any login) the game is vanilla. Main thread only.
    /// </summary>
    internal static class ApMode
    {
        public const string ProfilePrefix = "Archipelago_";

        // The tribe challenges vanilla locks battles behind (never Basic, which vanilla starts with).
        private static readonly Dictionary<string, string> TribeOfChallenge = new Dictionary<string, string>
        {
            { "Challenge Tribe 1", "Magic" },
            { "Challenge Tribe 2", "Clunk" },
        };
        private static readonly Dictionary<string, string> TribeUnlock = new Dictionary<string, string>
        {
            { "Magic", "Tribe 1" },
            { "Clunk", "Tribe 2" },
        };

        // UnlockData name prefixes the multiworld controls. Saved unlocks with these are ignored.
        private static readonly string[] ControlledPrefixes = { "Tribe ", "Event ", "Pet ", "Item ", "Companion ", "Charm " };

        private static readonly HashSet<string> received = new HashSet<string>();
        private static Dictionary<string, string> cardKinds = new Dictionary<string, string>();
        private static Dictionary<string, List<string>> packs = new Dictionary<string, List<string>>();
        private static Dictionary<string, string> cardTitles;
        private static Dictionary<ChallengeData, ChallengeData[]> savedRequires;
        private static string returnProfile;
        private static bool switchPending;
        private static List<string> grantedUnlocks;
        // Progressive items arrive once per copy under the same key, and a reconnect resends every
        // item, so copies are counted by their index in the slot's item list.
        private static readonly Dictionary<int, string> progressiveByIndex = new Dictionary<int, string>();
        private static int goal;
        private static bool forceStormBells;
        private static bool forceOvercrank;
        // Snowdwellers are an item too in seeds with the starting_tribe option.
        private static bool snowdwellersIsItem;

        /// <summary>The AP profile for this session's slot, or null before the first login.</summary>
        public static string Profile { get; private set; }

        public static bool Active => Profile != null && SaveSystem.Profile == Profile;

        public static void OnConnected(ArchipelagoClient client, string seed, string slot)
        {
            string profile = ProfileName(seed, slot);
            if (Profile != null && Profile != profile)
            {
                client.Log($"This session already plays {Profile}. Restart the game to play {profile}.");
                return;
            }
            goal = client.Goal;
            forceStormBells = client.ForceStormBells;
            forceOvercrank = client.ForceOvercrank;
            snowdwellersIsItem = client.SnowdwellersIsItem;
            cardKinds = client.CardKinds ?? new Dictionary<string, string>();
            packs = client.Packs ?? new Dictionary<string, List<string>>();
            grantedUnlocks = null;
            if (Profile == null)
            {
                Profile = profile;
                client.UsePendingFile(Path.Combine(ArchipelagoMod.Directory, "pending", profile + ".txt"));
            }
            if (Active)
            {
                CatchUpChallenges(client);
                ApplyStormBells();
                CheckGoal(client);
            }
            else
            {
                switchPending = true;
                client.Log($"Switching to profile {profile} at the main menu");
                Tick();
            }
        }

        /// <summary>
        /// A pack unlocks its cards (slot_data "packs"). announce is false for the server's starting
        /// inventory and for items resent on reconnect, which are already known. Returns what the
        /// item did, for the received-item toast ("unlocks ...", the bell level), or null.
        /// </summary>
        public static string OnItemReceived(string key, bool announce, int index)
        {
            if (ApEffects.IsEffect(key))
            {
                ApEffects.Received(key, index);
                return null;
            }
            if (key == StormBellKey)
            {
                if (progressiveByIndex.ContainsKey(index)) return null;
                progressiveByIndex[index] = key;
                string bells = "Storm bells: " + DescribeBells();
                if (announce) ArchipelagoMod.Client?.LogDetail(bells);
                if (Active) ApplyStormBells();
                return bells;
            }
            if (!received.Add(key)) return null;
            grantedUnlocks = null;
            if (!packs.TryGetValue(key, out List<string> cards)) return null;

            foreach (string card in cards) received.Add(card);
            string unlocks = "Unlocks " + string.Join(", ", cards.Select(CardTitle));
            if (announce) ArchipelagoMod.Client?.LogDetail(unlocks);
            if (Active) AddToRun(cards);
            return unlocks;
        }

        // Cards received mid-run join this run's reward pools now, if this tribe can draw them.
        // (Run start strips locked cards; see ApPatches.) Nodes rolled before then re-roll when
        // entered.
        private static void AddToRun(List<string> cardKeys)
        {
            var rewards = ApPatches.EnsurePools();
            var pools = References.PlayerData?.classData?.rewardPools;
            if (rewards == null || pools == null) return;
            var added = new List<string>();
            foreach (string key in cardKeys)
            {
                string name = key.Substring("card:".Length);
                foreach (var pool in pools)
                {
                    var file = pool?.list?.FirstOrDefault(f => f != null && f.name == name);
                    if (file == null) continue;
                    ApPatches.AddToDeck(rewards, pool.type, file);
                    added.Add(CardTitle(key));
                    break;
                }
            }
            if (added.Count > 0) ArchipelagoMod.Client?.LogDetail("Joins this run: " + string.Join(", ", added));
        }

        /// <summary>How many received cards this run's tribe can draw. Nodes remember it to know when to re-roll.</summary>
        public static int RunCardCount()
        {
            var pools = References.PlayerData?.classData?.rewardPools;
            if (pools == null) return 0;
            return pools.Where(p => p?.list != null)
                .SelectMany(p => p.list)
                .Where(f => f != null && received.Contains("card:" + f.name))
                .Select(f => f.name)
                .Distinct()
                .Count();
        }

        /// <summary>Whether this run's tribe can draw any received card from the pool type (Items, Units, Charms).</summary>
        public static bool RunHasCards(string poolType)
        {
            var pools = References.PlayerData?.classData?.rewardPools;
            if (pools == null) return true;
            return pools.Where(p => p != null && p.type == poolType && p.list != null)
                .SelectMany(p => p.list)
                .Any(f => f != null && received.Contains("card:" + f.name));
        }

        private static string CardTitle(string cardKey)
        {
            if (cardTitles == null)
            {
                cardTitles = new Dictionary<string, string>();
                foreach (var c in AddressableLoader.GetGroup<CardData>("CardData")) cardTitles[c.name] = c.title;
                foreach (var u in AddressableLoader.GetGroup<CardUpgradeData>("CardUpgradeData")) cardTitles[u.name] = u.title;
            }
            string name = cardKey.Substring("card:".Length);
            return cardTitles.TryGetValue(name, out string title) && !string.IsNullOrEmpty(title) ? title : name;
        }

        /// <summary>Called every frame. Profiles may only change on the main menu, with no run loaded.</summary>
        public static void Tick()
        {
            if (!switchPending || !AtMainMenu()) return;
            switchPending = false;

            var client = ArchipelagoMod.Client;
            returnProfile = SaveSystem.Profile;
            Unchain();
            string reloaded = ProfileSwitch.SetProfile(Profile, false, SetUpProfile);
            client?.LogDebug($"Profile {returnProfile} -> {Profile} (AP rules on)");
            SurveyLog.Write($"AP profile {returnProfile} -> {Profile}; reloaded {reloaded}");
            ApplyStormBells();
            if (client != null)
            {
                CatchUpChallenges(client);
                CheckGoal(client);
            }
        }

        /// <summary>"Play without Archipelago": a login that comes in late doesn't switch the profile.</summary>
        public static void StayOffline() => switchPending = false;

        /// <summary>Mod unload: put the game back the way it was.</summary>
        public static void Exit()
        {
            bool wasActive = Active;
            Restore();
            if (wasActive && AtMainMenu() && returnProfile != null)
            {
                ProfileSwitch.SetProfile(returnProfile, false, null);
            }
            // Mid-run there is no safe switch. The profile choice isn't saved, so the next game
            // start is back on the player's own profile.
            Profile = null;
            returnProfile = null;
            switchPending = false;
            received.Clear();
            progressiveByIndex.Clear();
            ApEffects.Reset();
            grantedUnlocks = null;
        }

        private static bool AtMainMenu() =>
            // Fully qualified: the game has its own global SceneManager class that shadows Unity's.
            UnityEngine.SceneManagement.SceneManager.GetSceneByName("MainMenu").isLoaded;

        private static string ProfileName(string seed, string slot)
        {
            var name = new StringBuilder(ProfilePrefix);
            foreach (char c in slot + "_" + seed)
            {
                name.Append(char.IsLetterOrDigit(c) || c == '-' || c == '_' ? c : '_');
            }
            return name.Length > 64 ? name.ToString(0, 64) : name.ToString();
        }

        // Runs after SetProfile, before the game systems reload, so they see these values.
        private static void SetUpProfile()
        {
            // A new profile has no saved "version", and the game's compatibility check (normally run
            // at game start) treats that as an ancient save and resets its progress, which would wipe
            // the tutorial flags below. Run it now, so it stamps the version first.
            AccessTools.Method(typeof(VersionCompatibility), "GameStart")?.Invoke(null, null);

            // A blank profile forces the tutorial run. 2 is what a finished tutorial leaves.
            if (SaveSystem.LoadProgressData("tutorialProgress", 0) != 0) return;
            SaveSystem.SaveProgressData("tutorialProgress", 2);
            foreach (string key in new[] { "tutorialTownDone", "tutorialCharmDone", "tutorialCrownDone", "tutorialInjuryDone" })
            {
                SaveSystem.SaveProgressData(key, true);
            }
            SurveyLog.Write("AP profile is new: tutorial marked done");
        }

        // --- Storm bells ---
        // Vanilla: the first win unlocks the bells with a cap of 5 storm points, each win with the
        // bells at the cap adds a point up to 10 (the True Final Boss threshold), and Overcrank
        // unlocks once every bell has been gilded by a True Final Boss win. Under AP each
        // Progressive Storm Bell is one of those steps, and wins change nothing (ApPatches).
        private const string StormBellKey = "storm_bell";
        public const int OvercrankBells = 7;

        public static int StormBells => progressiveByIndex.Values.Count(k => k == StormBellKey);

        // The town's bell screen reads these keys when it opens.
        private static void ApplyStormBells()
        {
            int bells = StormBells;
            SaveSystem.SaveProgressData("stormBellsUnlocked", bells >= 1);
            SaveSystem.SaveProgressData("maxStormPoints", System.Math.Min(10, 4 + System.Math.Max(bells, 1)));
            if (bells < OvercrankBells && SaveSystem.LoadProgressData("stormPointOvercrank", false))
            {
                SaveSystem.SaveProgressData("stormPointOvercrank", false);
            }
        }

        /// <summary>Whether every run must start Overcranked (force_overcrank, once the lever is unlocked).</summary>
        public static bool RequiresOvercrank => forceOvercrank && StormBells >= OvercrankBells;

        /// <summary>Storm points every run must start with (force_storm_bells), or 0.</summary>
        public static int RequiredStormPoints =>
            forceStormBells && StormBells >= 1 ? System.Math.Min(10, 4 + StormBells) : 0;

        private static string DescribeBells()
        {
            int bells = StormBells;
            if (bells == 0) return "locked";
            if (bells >= OvercrankBells) return "10 storm points and Overcrank";
            return $"{System.Math.Min(10, 4 + bells)} storm points" + (bells >= 6 ? " (True Final Boss)" : "");
        }

        // --- Goal ---
        // A qualifying win per clan, saved in the AP profile so it survives restarts.
        private const string GoalClansKey = "apGoalClans";
        private static readonly Dictionary<string, string> ClanNames = new Dictionary<string, string>
        {
            { "Basic", "Snowdwellers" },
            { "Magic", "Shademancers" },
            { "Clunk", "Clunkmasters" },
        };
        private static readonly string[] GoalText =
        {
            "win a run", "beat the True Final Boss", "beat the True Final Boss Overcranked",
        };

        /// <summary>A won run (AP profile). trueWin: the True Final Boss was beaten.</summary>
        public static void RunWon(string clan, bool trueWin, bool overcranked)
        {
            var client = ArchipelagoMod.Client;
            bool counts = goal == 0 || (trueWin && (goal == 1 || overcranked));
            var done = SaveSystem.LoadProgressData(GoalClansKey, new List<string>());
            if (counts && !done.Contains(clan))
            {
                done.Add(clan);
                SaveSystem.SaveProgressData(GoalClansKey, done);
            }
            string clans = string.Join(", ", done.Select(c => ClanNames.TryGetValue(c, out string n) ? n : c));
            client?.Log(counts
                ? $"Goal ({GoalText[System.Math.Min(goal, 2)]} with each clan): {done.Count}/{ClanNames.Count} [{clans}]"
                : $"This win doesn't count for the goal ({GoalText[System.Math.Min(goal, 2)]} with each clan)");
            if (client != null) CheckGoal(client);
        }

        // Also on login, for a goal reached while offline or before the client could send it.
        private static void CheckGoal(ArchipelagoClient client)
        {
            var done = SaveSystem.LoadProgressData(GoalClansKey, new List<string>());
            if (ClanNames.Keys.All(done.Contains)) client.SendGoal();
        }

        // Challenges are unchained: ChallengeSystem.OnEnable only activates challenges whose
        // `requires` are complete, so clear them (in memory) before it reloads.
        private static void Unchain()
        {
            if (savedRequires != null) return;
            savedRequires = new Dictionary<ChallengeData, ChallengeData[]>();
            foreach (var challenge in AddressableLoader.GetGroup<ChallengeData>("ChallengeData"))
            {
                savedRequires[challenge] = challenge.requires;
                challenge.requires = new ChallengeData[0];
            }
        }

        private static void Restore()
        {
            if (savedRequires == null) return;
            foreach (var pair in savedRequires)
            {
                if (pair.Key != null) pair.Key.requires = pair.Value;
            }
            savedRequires = null;
        }

        // Challenges completed while the client couldn't send (offline, or the game closed first).
        // SendLocation skips the ones the server already has.
        private static void CatchUpChallenges(ArchipelagoClient client)
        {
            foreach (string name in SaveSystem.LoadProgressData("completedChallenges", new List<string>()))
            {
                client.SendLocation("challenge:" + name, quiet: true);
            }
        }

        // --- Queries used by ApPatches. Only called while Active. ---

        /// <summary>Card names of one kind (Item, Companion, Charm) the multiworld hasn't sent yet.</summary>
        public static List<string> LockedCards(string kind) =>
            cardKinds.Where(p => p.Value == kind && !received.Contains(p.Key))
                .Select(p => p.Key.Substring("card:".Length))
                .ToList();

        public static bool TribeLocked(string className) =>
            (TribeUnlock.ContainsKey(className) || snowdwellersIsItem && className == "Basic") && !received.Contains("tribe:" + className);

        /// <summary>Null when the lock isn't one of the tribe locks (then vanilla decides).</summary>
        public static bool? BattleLocked(string challengeName) =>
            challengeName != null && TribeOfChallenge.TryGetValue(challengeName, out string tribe)
                ? TribeLocked(tribe)
                : (bool?)null;

        public static bool PetUnlocked(string pet, string unlockName) =>
            unlockName == null || received.Contains("pet:" + pet);

        public static bool IsControlledUnlock(string unlockName) =>
            unlockName != null && ControlledPrefixes.Any(unlockName.StartsWith);

        /// <summary>
        /// The unlock list the game sees: saved unlocks the multiworld doesn't control, every town
        /// building and journal page (town meta areas only showcase unlocks, so they are all open),
        /// and the vanilla unlock names of everything received.
        /// </summary>
        public static List<string> UnlockedList(List<string> saved)
        {
            if (grantedUnlocks == null) grantedUnlocks = BuildGrantedUnlocks();
            var list = saved.Where(n => !IsControlledUnlock(n)).ToList();
            foreach (string n in grantedUnlocks)
            {
                if (!list.Contains(n)) list.Add(n);
            }
            return list;
        }

        private static List<string> BuildGrantedUnlocks()
        {
            var granted = AddressableLoader.GetGroup<UnlockData>("UnlockData")
                .Where(u => u.type == UnlockData.Type.BuildingStarted || u.type == UnlockData.Type.BuildingFinished
                            || u.type == UnlockData.Type.JournalPage)
                .Select(u => u.name)
                .ToList();

            foreach (var pair in TribeUnlock)
            {
                if (received.Contains("tribe:" + pair.Key)) granted.Add(pair.Value);
            }

            // MetaprogressionSystem.data lists each kind in unlock order: entry i is unlock "<Kind> i+1".
            if (AccessTools.Field(typeof(MetaprogressionSystem), "data")?.GetValue(null) is Dictionary<string, object> data)
            {
                GrantOrdered(granted, data, "events", "Event ", "event:");
                GrantOrdered(granted, data, "items", "Item ", "card:");
                GrantOrdered(granted, data, "companions", "Companion ", "card:");
                if (data.TryGetValue("charms", out object charms) && charms is Dictionary<string, string> charmDict)
                {
                    granted.AddRange(charmDict.Where(p => received.Contains("card:" + p.Value)).Select(p => p.Key));
                }
                if (data.TryGetValue("pets", out object pets) && pets is Dictionary<string, string> petDict)
                {
                    granted.AddRange(petDict.Where(p => p.Value != null && received.Contains("pet:" + p.Key)).Select(p => p.Value));
                }
            }
            return granted;
        }

        private static void GrantOrdered(List<string> granted, Dictionary<string, object> data, string list, string unlockPrefix, string keyPrefix)
        {
            if (!data.TryGetValue(list, out object value) || !(value is List<string> names)) return;
            for (int i = 0; i < names.Count; i++)
            {
                if (received.Contains(keyPrefix + names[i])) granted.Add(unlockPrefix + (i + 1));
            }
        }

        /// <summary>F11: a summary of what the AP rules currently give the game, through the patched methods.</summary>
        public static string Describe()
        {
            if (!Active) return Profile == null ? "AP rules off (not logged in yet)" : $"AP rules off (profile {SaveSystem.Profile}, waiting for {Profile})";
            var none = new List<UnlockData>();
            int cards = cardKinds.Count;
            int locked = MetaprogressionSystem.GetLockedItems(none).Count + MetaprogressionSystem.GetLockedCompanions(none).Count
                         + MetaprogressionSystem.GetLockedCharms(none).Count;
            string classes = string.Join(", ", MetaprogressionSystem.GetLockedClasses().Select(c => c.name));
            string pets = string.Join(", ", MetaprogressionSystem.GetUnlockedPets());
            int open = AddressableLoader.GetGroup<ChallengeData>("ChallengeData").Count(c => c.requires == null || c.requires.Length == 0);
            return $"AP rules on. Cards unlocked {cards - locked}/{cards}. Locked tribes: [{classes}]. Pets: [{pets}]. " +
                   $"Received {received.Count} items. Open challenges {open}. Storm bells: {DescribeBells()}. " +
                   $"Goal: {GoalText[System.Math.Min(goal, 2)]} with each clan, done [{string.Join(", ", SaveSystem.LoadProgressData(GoalClansKey, new List<string>()))}].";
        }
    }
}
