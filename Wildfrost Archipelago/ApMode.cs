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
        private static int forceStormPoints;
        private static bool forceOvercrank;
        private static bool reverseBells;
        private static int bellLevels = 7;
        private static bool gameSpeedUp;
        // Every item key in the seed (slot_data item_keys).
        private static HashSet<string> seedItems = new HashSet<string>();
        private static bool leaderReroll;
        private static bool noPossessedFinalBoss;
        private static int trueFinalPoints = 10;
        private static bool newChallenges;
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
            forceStormPoints = client.ForceStormPoints;
            forceOvercrank = client.ForceOvercrank;
            reverseBells = client.ReverseBells;
            bellLevels = client.StormBellLevels;
            gameSpeedUp = client.GameSpeedUp;
            seedItems = new HashSet<string>(client.ItemKeyValues);
            leaderReroll = client.LeaderReroll;
            noPossessedFinalBoss = client.NoPossessedFinalBoss;
            trueFinalPoints = client.TrueFinalPoints;
            newChallenges = client.NewChallenges;
            snowdwellersIsItem = client.SnowdwellersIsItem;
            cardKinds = client.CardKinds ?? new Dictionary<string, string>();
            packs = client.Packs ?? new Dictionary<string, List<string>>();
            // The seed's tribes (slot_data "tribes"); older seeds have the vanilla three.
            var tribes = client.SeedTribes;
            clanNames = tribes == null ? new Dictionary<string, string>(VanillaClanNames)
                : tribes.Where(t => t.Class != null).ToDictionary(t => t.Class, t => t.Name ?? t.Class);
            reusesOf = client.Reuses ?? new Dictionary<string, HashSet<string>>();
            tribeReuses.Clear();
            tribeDraws = tribes == null ? new Dictionary<string, HashSet<string>>()
                : tribes.Where(t => t.Class != null).ToDictionary(t => t.Class, t =>
                    new HashSet<string>((t.General ? new[] { "General", t.Class } : new[] { t.Class }).Concat(t.Shares)));
            leftOutTribes = new HashSet<string>(client.LeftOutTribes ?? new List<string>());
            // slot_data "tribes" came with 0.5.0, so a seed without it is older and keeps the battle tribe locks.
            battleTribeLocks = tribes == null;
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
            if (cardTitles.TryGetValue(name, out string title) && !string.IsNullOrEmpty(title)) return title;
            // Not there when the titles were first read: another mod's cards can load later (the user's report,
            // 2026-11-25: Pokefrost cards showed as websiteofsites.wildfrost.pokefrost.slowpoke). Look it up again.
            title = SafeTitle(() => AddressableLoader.Get<CardData>("CardData", name)?.title)
                    ?? SafeTitle(() => AddressableLoader.Get<CardUpgradeData>("CardUpgradeData", name)?.title);
            if (string.IsNullOrEmpty(title)) return name;
            cardTitles[name] = title;
            return title;
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
        //
        // Seeds with 11 levels (slot_data storm_bell_levels; decided by the user 2026-11-06) step by
        // two storm points: 2, 4, ... 20, and the 11th bell is Overcrank (22). Vanilla caps the bells
        // at 10, so the cap is lifted to 20 for those seeds (ApPatches.StormPointCap). Older seeds,
        // with fewer levels, keep the 7 steps above.
        private const string StormBellKey = "storm_bell";
        private const int EvenStepLevels = 11;

        /// <summary>Bell levels in this seed; the last one is Overcrank (normal) or no bells (reverse).</summary>
        public static int OvercrankBells => bellLevels;

        /// <summary>Whether this seed's bells go up in steps of two storm points, past vanilla's 10.</summary>
        public static bool EvenSteps => bellLevels >= EvenStepLevels;

        /// <summary>The most storm points bells can be rung to without Overcrank: 20 in even-step AP seeds, else vanilla's 10.</summary>
        public static int StormPointLimit => Active && EvenSteps ? 20 : 10;

        public static int StormBells => progressiveByIndex.Values.Count(k => k == StormBellKey);

        /// <summary>The storm point cap these many bells give (normal mode); the Overcrank level adds the lever, not points.</summary>
        private static int CapFor(int bells) => EvenSteps
            ? 2 * System.Math.Min(bells, bellLevels - 1)
            : System.Math.Min(10, 4 + bells);

        // The town's bell screen reads these keys when it opens.
        private static void ApplyStormBells()
        {
            int bells = StormBells;
            if (reverseBells)
            {
                // Every bell and the lever are there from the start; the floor is RequiredStormPoints.
                SaveSystem.SaveProgressData("stormBellsUnlocked", true);
                SaveSystem.SaveProgressData("maxStormPoints", EvenSteps ? 20 : 10);
                return;
            }
            SaveSystem.SaveProgressData("stormBellsUnlocked", bells >= 1);
            SaveSystem.SaveProgressData("maxStormPoints", CapFor(System.Math.Max(bells, 1)));
            if (bells < OvercrankBells && SaveSystem.LoadProgressData("stormPointOvercrank", false))
            {
                SaveSystem.SaveProgressData("stormPointOvercrank", false);
            }
        }

        /// <summary>Whether the seed lets F6 speed the game up (game_speed_up).</summary>
        public static bool SpeedUpAllowed => gameSpeedUp;

        /// <summary>Whether the leader select screen offers rerolls (leader_reroll).</summary>
        public static bool LeaderRerollOn => leaderReroll;

        /// <summary>Whether the Final Boss keeps its default deck (disable_possessed_final_boss).</summary>
        public static bool NoPossessedFinalBoss => noPossessedFinalBoss;

        /// <summary>The True Final Boss's storm point threshold this seed (vanilla 10; lower when its mod extensions
        /// leave too few storm bells to reach 10, the user's call 2026-11-15).</summary>
        public static int TrueFinalPoints => trueFinalPoints;

        /// <summary>Whether the challenges made for Archipelago are checks this seed (new_challenges; NewChallenges.cs).</summary>
        public static bool NewChallenges => newChallenges;

        // --- Reverse Storm Bells (slot_data progression_direction 1; designed with the user 2026-11-05) ---
        // Runs start Overcranked, and each Progressive Storm Bell lowers the floor a step: Overcranked,
        // 10, 9, 8, 7, 6, 5, then no bells (even-step seeds: Overcranked, 20, 18, ... 2, then no bells).
        // The floor is a minimum, not a level: a run may ring more (with a warning that it could ring
        // less). The True Final Boss only comes on a no-bell run.
        public static bool ReverseBells => reverseBells;

        /// <summary>Reverse: the storm point floor (the ringable top while Overcranked is required, 0 at the bottom).</summary>
        private static int ReverseFloor
        {
            get
            {
                int bells = StormBells;
                if (bells >= OvercrankBells) return 0;
                if (EvenSteps) return bells == 0 ? 20 : 22 - 2 * bells;
                return bells == 0 ? 10 : 11 - bells;
            }
        }

        /// <summary>Reverse: the floor for the bell board's label; while Overcranked is required, every bell (22, or 10 in older seeds' terms).</summary>
        public static int ReverseFloorPoints => StormBells == 0 ? (EvenSteps ? 22 : 10) : ReverseFloor;

        /// <summary>What the bells require, for messages: "Overcranked", "7 storm points" or "no bells".</summary>
        public static string ReverseFloorText => StormBells == 0 ? "Overcranked" : ReverseFloor == 0 ? "no bells" : $"{ReverseFloor} storm points";

        /// <summary>Whether a run of this clan must start Overcranked (force_storm_bells_up_to 22, once the lever is unlocked).</summary>
        public static bool RequiresOvercrank(string clan) => reverseBells ? StormBells == 0 : forceOvercrank && ForcedBells(clan) >= OvercrankBells;

        /// <summary>Storm points a run of this clan must start with (force_storm_bells_up_to: the limit, up to that), or 0.</summary>
        public static int RequiredStormPoints(string clan)
        {
            if (reverseBells) return ReverseFloor;
            int bells = ForcedBells(clan);
            return forceStormPoints > 0 && bells >= 1 ? System.Math.Min(CapFor(bells), forceStormPoints) : 0;
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
            double companions = PackCount(clan, "Companion"), items = PackCount(clan, "Item"), charms = PackCount(clan, "Charm");
            int needCompanions = Get(kit, "Companion"), needItems = Get(kit, "Item"), needCharms = Get(kit, "Charm");
            int extra = Get(kit, "extra"), perPack = Get(kit, "charms_per_pack");
            if (!AtLeast(companions, needCompanions) || !AtLeast(items, needItems) || !AtLeast(charms, needCharms)) return false;
            for (int inPacks = 0; inPacks <= extra; inPacks++)
            {
                if (AtLeast(companions + items, needCompanions + needItems + inPacks)
                    && AtLeast(charms, needCharms + perPack * (extra - inPacks))) return true;
            }
            return false;
        }

        private static int Get(Dictionary<string, int> kit, string key) => kit.TryGetValue(key, out int value) ? value : 0;

        /// <summary>Packs' worth against a whole number needed, allowing for the rounding of fractions.</summary>
        public static bool AtLeast(double have, int need) => have >= need - 1e-9;

        /// <summary>
        /// What a run of this clan draws from (General and its own, and the clans it shares): received packs of a
        /// kind, or ("") all packs, or (Charm) charms, which are items one by one in newer seeds and packs in older
        /// ones. For a tribe whose pools reuse other clans' cards, such a pack counts by the share of its cards the
        /// tribe can be offered, and such a charm whole, as the apworld's DrawnCount does (2026-11-27).
        /// </summary>
        public static double PackCount(string clan, string kind)
        {
            var draws = Draws(clan);
            var reused = TribeReuses(clan);
            double total = 0;
            foreach (string key in received)
            {
                string[] parts = key.Split(':');
                if (parts.Length < 3) continue;
                if (parts[0] == "charm")
                {
                    if (kind == "Charm" && (draws.Contains(parts[1]) || reused.Contains(parts[2]))) total += 1;
                }
                else if (parts[0] == "pack" && (kind == "" || parts[2] == kind))
                {
                    if (draws.Contains(parts[1])) total += 1;
                    else if (reused.Count > 0 && packs.TryGetValue(key, out var cards) && cards.Count > 0)
                        total += cards.Count(c => reused.Contains(c.StartsWith("card:") ? c.Substring(5) : c)) / (double)cards.Count;
                }
            }
            return total;
        }

        /// <summary>Whether this many of an item have been received (Progressive Storm Bells count their copies).</summary>
        public static bool Has(string key, int count = 1) =>
            key == StormBellKey ? StormBells >= count : count <= 1 && received.Contains(key);

        private static string DescribeBells()
        {
            int bells = StormBells;
            if (reverseBells) return $"reverse, runs start from {ReverseFloorText}" + (ReverseFloor == 0 ? " (True Final Boss)" : "");
            if (bells == 0) return "locked";
            if (bells >= OvercrankBells) return $"{CapFor(bells)} storm points and Overcrank";
            return $"{CapFor(bells)} storm points" + (CapFor(bells) >= 10 ? " (True Final Boss)" : "");
        }

        // --- Goal ---
        // A qualifying win per clan, saved in the AP profile so it survives restarts.
        private const string GoalClansKey = "apGoalClans";
        private static readonly Dictionary<string, string> VanillaClanNames = new Dictionary<string, string>
        {
            { "Basic", "Snowdwellers" },
            { "Magic", "Shademancers" },
            { "Clunk", "Clunkmasters" },
        };
        // This seed's tribes by ClassData name: the vanilla three and its extensions' (slot_data "tribes"; a win
        // with any of them counts toward the goal, the user's call 2026-11-16), and the vanilla clan whose pools
        // each extension tribe shares.
        private static Dictionary<string, string> clanNames = new Dictionary<string, string>(VanillaClanNames);
        // The clans each tribe's runs draw from: General (unless its pools leave it out), its own, and those it
        // shares (vanilla clans, or a mod's shared pool clans; the user's call, 2026-11-27).
        private static Dictionary<string, HashSet<string>> tribeDraws = new Dictionary<string, HashSet<string>>();

        // Per extension clan, the other clans' cards its pools hold (slot_data "reuses"), and per tribe all of those
        // its runs can be offered: a pack counts by the share of its cards in there, a charm whole (2026-11-27).
        private static Dictionary<string, HashSet<string>> reusesOf = new Dictionary<string, HashSet<string>>();
        private static readonly Dictionary<string, HashSet<string>> tribeReuses = new Dictionary<string, HashSet<string>>();

        private static HashSet<string> TribeReuses(string tribe)
        {
            if (!tribeReuses.TryGetValue(tribe, out var cards))
                tribeReuses[tribe] = cards = new HashSet<string>(Draws(tribe).Where(reusesOf.ContainsKey).SelectMany(c => reusesOf[c]));
            return cards;
        }

        private static HashSet<string> Draws(string tribe) =>
            tribeDraws.TryGetValue(tribe, out var draws) ? draws : new HashSet<string> { "General", tribe };
        // Tribes of the seed's mods that its Tribes option left out (slot_data "left_out_tribes"): always locked.
        private static HashSet<string> leftOutTribes = new HashSet<string>();

        /// <summary>Tribes of the seed's mods that its Tribes option left out: locked, not unknown.</summary>
        public static IEnumerable<string> LeftOutTribes => leftOutTribes;

        /// <summary>Pack groups for the tracker: General, the vanilla clans the seed's tribes draw from (their own,
        /// or shared: a Modded Only seed has no vanilla tribe but still their packs; 2026-11-24), then the
        /// seed's other tribes.</summary>
        public static IEnumerable<string> PackClans
        {
            get
            {
                // And the clans of this seed's other packs: those holding cards a tribe's pools reuse.
                var drawn = new HashSet<string>(clanNames.Keys.SelectMany(Draws)
                    .Concat(packs.Keys.Select(k => k.Split(':')).Where(p => p.Length >= 3).Select(p => p[1])));
                // General, the vanilla clans, the seed's other tribes, then the mods' shared pool clans.
                return VanillaClanNames.Keys.Prepend("General").Where(drawn.Contains)
                    .Concat(clanNames.Keys.Where(c => !VanillaClanNames.ContainsKey(c) && drawn.Contains(c)))
                    .Concat(drawn.Where(c => c != "General" && !clanNames.ContainsKey(c) && !VanillaClanNames.ContainsKey(c))
                        .OrderBy(c => c, System.StringComparer.Ordinal))
                    .Distinct();
            }
        }

        /// <summary>The seed's tribes by ClassData name.</summary>
        public static IEnumerable<string> SeedTribeClasses => clanNames.Keys;
        private static readonly string[] GoalText =
        {
            "win a run", "beat the True Final Boss", "beat the True Final Boss Overcranked",
        };

        private static string GoalDescription =>
            GoalText[System.Math.Min(goal, 2)] + (clansRequired >= clanNames.Count ? " with each clan" : $" with {clansRequired} of the {clanNames.Count} clans");

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
            string clans = string.Join(", ", done.Select(c => clanNames.TryGetValue(c, out string n) ? n : c));
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
            if (clanNames.Keys.Count(done.Contains) >= clansRequired) client.SendGoal(quiet);
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
            WildfrostArchipelago.NewChallenges.CatchUp(client);
        }

        // --- Queries used by ApPatches. Only called while Active. ---

        /// <summary>Card names of one kind (Item, Companion, Charm) the multiworld hasn't sent yet.</summary>
        public static List<string> LockedCards(string kind) =>
            cardKinds.Where(p => p.Value == kind && !received.Contains(p.Key))
                .Select(p => p.Key.Substring("card:".Length))
                .ToList();

        // An extension's tribe has no game unlock to reuse, so tribe select hides it (GetLockedClasses) until its
        // item arrives (the user's call, 2026-11-16).
        public static bool TribeLocked(string className) =>
            leftOutTribes.Contains(className)
            || (TribeUnlock.ContainsKey(className) || snowdwellersIsItem && className == "Basic"
                || clanNames.ContainsKey(className) && !VanillaClanNames.ContainsKey(className))
               && !received.Contains("tribe:" + className);

        /// <summary>Null when the lock isn't one of the tribe locks (then vanilla decides).</summary>
        // Under AP no battle waits for a tribe (the user's call, 2026-11-25): every battle can come up in every
        // run, as the apworld's logic expects. Seeds from before 0.5.0 keep the locks (the user's call, 2026-11-27):
        // their logic waits for the tribe item, and opening the battles sooner put checks on the map that the
        // Checks tab counted as out of logic (the user's 0.4.1 async on the 0.5.0 client).
        public static bool? BattleLocked(string challengeName) =>
            challengeName != null && TribeOfChallenge.TryGetValue(challengeName, out string tribe)
                ? battleTribeLocks && TribeLocked(tribe)
                : (bool?)null;

        private static bool battleTribeLocks;

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
