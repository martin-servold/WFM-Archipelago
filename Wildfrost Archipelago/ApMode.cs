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

        /// <summary>Which cards each pack item unlocks this seed (slot_data "packs").</summary>
        public static IReadOnlyDictionary<string, List<string>> Packs => packs;
        private static Dictionary<string, string> cardTitles;
        private static Dictionary<ChallengeData, ChallengeData[]> savedRequires;
        private static string returnProfile;

        /// <summary>The player's own profile, which the seed's profile was switched from (null when not switched).</summary>
        public static string ReturnProfile => returnProfile;
        private static bool switchPending;
        private static List<string> grantedUnlocks;
        // Progressive items arrive once per copy under the same key, and a reconnect resends every
        // item, so copies are counted by their index in the slot's item list.
        private static readonly Dictionary<int, string> progressiveByIndex = new Dictionary<int, string>();
        private static int goal;
        private static int clansRequired = 3;
        private static List<ArchipelagoClient.BellKit> bellKits;
        private static bool forceStormBells;
        private static bool forceOvercrank;
        private static bool gameSpeedUp;
        // Every item key in the seed (slot_data item_keys).
        private static HashSet<string> seedItems = new HashSet<string>();
        private static bool leaderReroll;
        // Snowdwellers are an item too in seeds with the starting_tribe option.
        private static bool snowdwellersIsItem;

        /// <summary>The AP profile for this session's slot, or null before the first login.</summary>
        public static string Profile { get; private set; }

        /// <summary>Another seed's profile a login came for during a run, where there's no safe switch, or null.</summary>
        public static string BlockedProfile { get; private set; }

        /// <summary>Accepted logins this session, so the connect popup can wait for a fresh one.</summary>
        public static int Logins { get; private set; }

        public static bool Active => Profile != null && SaveSystem.Profile == Profile;

        /// <summary>
        /// A login. Another seed than the one loaded (a re-seeded lobby, or a second multiworld) is
        /// switched to at the main menu: this one is left as on mod unload (Exit), the client forgets
        /// its checks, and the login carries on as a first one. Each seed keeps its own offline queue
        /// file, so nothing queued is lost. False during a run, where there's no safe switch: the caller
        /// disconnects, or this seed's checks would be resent to the other room and its items applied here.
        /// </summary>
        public static bool OnConnected(ArchipelagoClient client, string seed, string slot)
        {
            string profile = ProfileName(seed, slot);
            if (Profile != null && Profile != profile)
            {
                if (!AtMainMenu())
                {
                    BlockedProfile = profile;
                    client.Log($"This session plays {Profile}. Go back to the main menu and connect again to play {profile}.");
                    return false;
                }
                client.Log($"Leaving {Profile} for {profile}");
                Exit();
                client.ForgetSeed();
                ApUi.ForgetSeed();
            }
            BlockedProfile = null;
            Logins++;
            goal = client.Goal;
            clansRequired = client.ClansRequired;
            bellKits = client.BellKits;
            forceStormBells = client.ForceStormBells;
            forceOvercrank = client.ForceOvercrank;
            gameSpeedUp = client.GameSpeedUp;
            seedItems = new HashSet<string>(client.ItemKeyValues);
            leaderReroll = client.LeaderReroll;
            snowdwellersIsItem = client.SnowdwellersIsItem;
            cardKinds = client.CardKinds ?? new Dictionary<string, string>();
            packs = client.Packs ?? new Dictionary<string, List<string>>();
            grantedUnlocks = null;
            if (Profile == null)
            {
                Profile = profile;
                // In the save folder, which a Workshop update doesn't touch. Queues from before that
                // (in the mod folder) are moved over once.
                string pending = Path.Combine(ConnectionConfig.SaveFolder, "pending", profile + ".txt");
                string old = Path.Combine(ArchipelagoMod.Directory, "pending", profile + ".txt");
                try
                {
                    if (File.Exists(old) && !File.Exists(pending))
                    {
                        Directory.CreateDirectory(Path.GetDirectoryName(pending));
                        File.Move(old, pending);
                    }
                }
                catch (System.Exception e)
                {
                    UnityEngine.Debug.LogWarning(ArchipelagoMod.LogPrefix + "Moving the offline queue failed: " + e.Message);
                }
                client.UsePendingFile(pending);
            }
            if (Active)
            {
                CatchUpChallenges(client);
                ApplyStormBells();
                CheckGoal(client, quiet: true);
            }
            else
            {
                switchPending = true;
                client.Log($"Switching to profile {profile} at the main menu");
                Tick();
            }
            return true;
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
            // A pack unlocks its cards; a charm (an item one by one since 2026-11-02, "charm:<clan>:<card>") its own.
            List<string> cards = packs.TryGetValue(key, out List<string> inPack) ? inPack
                : key.StartsWith("charm:") ? new List<string> { "card:" + key.Substring(key.LastIndexOf(':') + 1) }
                : null;
            if (cards == null) return null;

            foreach (string card in cards) received.Add(card);
            string unlocks = "Unlocks " + string.Join(", ", cards.Select(CardTitle));
            if (announce) ArchipelagoMod.Client?.LogDetail(unlocks);
            if (Active) AddToRun(cards);
            return unlocks;
        }

        // Cards received mid-run join this run's reward pools now, if this tribe can draw them.
        // (Run start strips locked cards; see ApPatches.) Nodes draw when entered, so they see them.
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

        /// <summary>Whether this run's tribe can draw any received card from the pool type (Items, Units, Charms).</summary>
        public static bool RunHasCards(string poolType)
        {
            var pools = References.PlayerData?.classData?.rewardPools;
            if (pools == null) return true;
            return pools.Where(p => p != null && p.type == poolType && p.list != null)
                .SelectMany(p => p.list)
                .Any(f => f != null && received.Contains("card:" + f.name));
        }

        public static string CardTitle(string cardKey)
        {
            if (cardTitles == null)
            {
                // Some upgrades (crowns, tokens) have no title string, and their getter throws.
                var titles = new Dictionary<string, string>();
                foreach (var c in AddressableLoader.GetGroup<CardData>("CardData")) titles[c.name] = SafeTitle(() => c.title);
                foreach (var u in AddressableLoader.GetGroup<CardUpgradeData>("CardUpgradeData")) titles[u.name] = SafeTitle(() => u.title);
                cardTitles = titles;
            }
            string name = cardKey.Substring("card:".Length);
            return cardTitles.TryGetValue(name, out string title) && !string.IsNullOrEmpty(title) ? title : name;
        }

        private static string SafeTitle(System.Func<string> title)
        {
            try { return title(); }
            catch (System.Exception) { return null; }
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
                CheckGoal(client, quiet: true);
            }
        }

        /// <summary>"Play without Archipelago": a login that comes in late doesn't switch the profile.</summary>
        public static void StayOffline() => switchPending = false;

        /// <summary>Mod unload, or leaving for another seed: put the game back the way it was.</summary>
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

        internal static bool AtMainMenu() =>
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

        /// <summary>Whether the seed lets F6 speed the game up (game_speed_up).</summary>
        public static bool SpeedUpAllowed => gameSpeedUp;

        /// <summary>Whether the leader select screen offers rerolls (leader_reroll).</summary>
        public static bool LeaderRerollOn => leaderReroll;

        /// <summary>Whether a run of this clan must start Overcranked (force_overcrank, once the lever is unlocked).</summary>
        public static bool RequiresOvercrank(string clan) => forceOvercrank && ForcedBells(clan) >= OvercrankBells;

        /// <summary>Storm points a run of this clan must start with (force_storm_bells), or 0.</summary>
        public static int RequiredStormPoints(string clan)
        {
            int bells = ForcedBells(clan);
            return forceStormBells && bells >= 1 ? System.Math.Min(10, 4 + bells) : 0;
        }

        /// <summary>
        /// The bell levels the force options hold a run of this clan to: those received, but only as far
        /// as the clan's packs carry them (slot_data bell_kits; decided by the user 2026-11-02). Without
        /// that, a seed handing out every bell before any pack forced Overcranked runs from the first
        /// fight. Older seeds have no bell_kits and force every bell received.
        /// </summary>
        public static int ForcedBells(string clan)
        {
            int bells = StormBells;
            if (bellKits == null) return bells;
            int carried = 0;
            foreach (var kit in bellKits)
            {
                if (kit.Alternatives.Any(alt => HasPacks(clan, alt))) carried = System.Math.Max(carried, kit.MaxBells);
            }
            return System.Math.Min(bells, carried);
        }

        // A kit: companion and item packs and charms, plus the forced "extra": each one more companion or
        // item pack, or charms_per_pack more charms (rules.packs in the apworld). Seeds from before
        // charms were items give a plain "total" of packs instead.
        private static bool HasPacks(string clan, Dictionary<string, int> kit)
        {
            if (kit.ContainsKey("total")) return kit.All(c => PackCount(clan, c.Key == "total" ? "" : c.Key) >= c.Value);
            int companions = PackCount(clan, "Companion"), items = PackCount(clan, "Item"), charms = PackCount(clan, "Charm");
            int needCompanions = Get(kit, "Companion"), needItems = Get(kit, "Item"), needCharms = Get(kit, "Charm");
            int extra = Get(kit, "extra"), perPack = Get(kit, "charms_per_pack");
            if (companions < needCompanions || items < needItems || charms < needCharms) return false;
            for (int inPacks = 0; inPacks <= extra; inPacks++)
            {
                if (companions + items >= needCompanions + needItems + inPacks && charms >= needCharms + perPack * (extra - inPacks)) return true;
            }
            return false;
        }

        private static int Get(Dictionary<string, int> kit, string key) => kit.TryGetValue(key, out int value) ? value : 0;

        /// <summary>
        /// What a run of this clan draws from (General and its own): received packs of a kind, or ("")
        /// all packs, or (Charm) charms, which are items one by one in newer seeds and packs in older ones.
        /// </summary>
        public static int PackCount(string clan, string kind) => received.Count(key =>
        {
            string[] parts = key.Split(':');
            if (parts.Length < 3 || parts[1] != "General" && parts[1] != clan) return false;
            if (parts[0] == "charm") return kind == "Charm";
            return parts[0] == "pack" && (kind == "" || parts[2] == kind);
        });

        /// <summary>Whether this many of an item have been received (Progressive Storm Bells count their copies).</summary>
        public static bool Has(string key, int count = 1) =>
            key == StormBellKey ? StormBells >= count : count <= 1 && received.Contains(key);

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

        private static string GoalDescription =>
            GoalText[System.Math.Min(goal, 2)] + (clansRequired >= ClanNames.Count ? " with each clan" : $" with {clansRequired} of the {ClanNames.Count} clans");

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
                ? $"Goal ({GoalDescription}): {System.Math.Min(done.Count, clansRequired)}/{clansRequired} [{clans}]"
                : $"This win doesn't count for the goal ({GoalDescription})");
            if (client != null) CheckGoal(client);
        }

        // Also on login (quiet: a goal reached before isn't news, and one queued offline is announced
        // when the queue goes out), for a goal the client couldn't send.
        private static void CheckGoal(ArchipelagoClient client, bool quiet = false)
        {
            var done = SaveSystem.LoadProgressData(GoalClansKey, new List<string>());
            if (ClanNames.Keys.Count(done.Contains) >= clansRequired) client.SendGoal(quiet);
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

        // A pet with no unlock (Wolfie, Snoof) is always there, unless the seed has it as an item (from
        // 2026-11-02 every pet is one).
        public static bool PetUnlocked(string pet, string unlockName) =>
            received.Contains("pet:" + pet) || unlockName == null && !seedItems.Contains("pet:" + pet);

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
                   $"Goal: {GoalDescription}, done [{string.Join(", ", SaveSystem.LoadProgressData(GoalClansKey, new List<string>()))}].";
        }
    }
}
