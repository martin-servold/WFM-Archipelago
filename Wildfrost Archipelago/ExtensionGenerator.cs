using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using Newtonsoft.Json.Linq;

namespace WildfrostArchipelago
{
    /// <summary>
    /// What the game has loaded, as ExtensionGenerator reads it (ExtensionMaker fills it from the live game).
    /// Plain data only, no game types, so the generator can also run outside the game.
    /// </summary>
    internal class GameContent
    {
        public class Pool
        {
            public string Name;
            public string Type;          // RewardPool.type: "Units", "Items", "Charms", ...
            public List<string> Cards = new List<string>();
        }

        public class Clan
        {
            public string Name;
            public List<Pool> Pools = new List<Pool>();
            public List<string> Leaders = new List<string>();
            public List<string> StartDeck = new List<string>();  // CardData names, each once, in deck order
        }

        public class Battle
        {
            public int Tier;
            public string Name;          // BattleData name
            public string Shown;         // its in-game name
        }

        public class Challenge
        {
            public string Name;
            public int Goal;
            public string Title;
            public string Text;
        }

        public class Effects
        {
            public string Kind;          // card type, or the charm's upgrade type
            public HashSet<string> Applies = new HashSet<string>();
            public HashSet<string> Traits = new HashSet<string>();
        }

        public List<string> LoadedMods = new List<string>();                // GUIDs
        public List<Clan> Clans = new List<Clan>();                         // the game's order
        public List<Battle> Battles = new List<Battle>();                   // by tier, in each tier's order
        public List<Challenge> Challenges = new List<Challenge>();
        public List<KeyValuePair<string, int>> Bells = new List<KeyValuePair<string, int>>();  // name, storm points
        public List<string> Pets = new List<string>();
        public Dictionary<string, string> Titles = new Dictionary<string, string>();          // cards first, then charms
        public Dictionary<string, Effects> CardEffects = new Dictionary<string, Effects>();   // cards, then charms
    }

    /// <summary>
    /// Writes a mod's extension file (PLAN.md §10) from what the game has loaded: the mod's cards (by reward
    /// pool: clan and kind) dealt into its own packs, its charms, pets and tribes as items, its battles (one
    /// check per run tribe) and challenges as locations, its storm bells, and what it removes from the base
    /// game. Run again to update a file: IDs already given keep their numbers, and what a creator wrote by
    /// hand stays (each challenge's rule, region, excluded, name and text, tribe names, themed packs' cards,
    /// and the groups). This replaced tools/make_extension.py (the user's call, 2026-11-24).
    ///
    /// The mod's content is what the base game (base.wildfrost.json) doesn't have and is named after the
    /// mod's GUID ("&lt;GUID&gt;.&lt;name&gt;"; unprefixed content counts when no other loaded mod's GUID names it), so
    /// other mods can stay loaded. What's removed can't be told apart by mod, though.
    /// </summary>
    internal static class ExtensionGenerator
    {
        public const int IdBase = 100000, BlockSize = 2000;   // apworld/wildfrost/extensions.py
        public const int PackSize = 3;

        private static readonly Dictionary<string, string> KindOfPool =
            new Dictionary<string, string> { { "Units", "Companion" }, { "Items", "Item" }, { "Charms", "Charm" } };
        // The Snow pools are general (every tribe draws from them), so they count as General.
        private static readonly Dictionary<string, string> ClanOfPool = new Dictionary<string, string>
            { { "General", "General" }, { "Snow", "General" }, { "Basic", "Basic" }, { "Magic", "Magic" }, { "Clunk", "Clunk" } };
        private static readonly string[] ClanLabelOrder = { "General", "Basic", "Magic", "Clunk" };
        private static readonly Dictionary<string, string> ClanLabel = new Dictionary<string, string>
            { { "General", "General" }, { "Basic", "Snowdweller" }, { "Magic", "Shademancer" }, { "Clunk", "Clunkmaster" } };
        private static readonly string[][] RunTribes =
            { new[] { "Basic", "Snowdwellers" }, new[] { "Magic", "Shademancers" }, new[] { "Clunk", "Clunkmasters" } };
        private static readonly Dictionary<int, int> AreaOfTier = new Dictionary<int, int>
            { { 0, 0 }, { 1, 0 }, { 2, 0 }, { 3, 1 }, { 4, 1 }, { 5, 1 }, { 6, 2 }, { 7, 2 }, { 8, 2 } };
        private static readonly HashSet<int> BossTiers = new HashSet<int> { 2, 5, 7, 8 };
        private const int TrueFinalTier = 8;   // extensions.TRUE_FINAL_TIER
        private static readonly Dictionary<string, string> TrueFinalBattles =
            new Dictionary<string, string> { { "Final Final Boss", "True Final Boss" } };

        // The base game's clans and pools, which base.wildfrost.json doesn't list.
        private static readonly HashSet<string> BaseClans = new HashSet<string> { "Basic", "Magic", "Clunk", "Tutorial" };
        private static readonly HashSet<string> BasePools = new HashSet<string>(
            new[] { "General", "Snow", "Basic", "Magic", "Clunk" }
                .SelectMany(c => new[] { c + "UnitPool", c + "ItemPool", c + "CharmPool" })
                .Concat(new[] { "GeneralModifierPool" }));
        // Challenges in the game that base.wildfrost.json leaves out (Win a Daily Voyage).
        private static readonly string[] ExtraBaseChallenges = { "Challenge Charm 14" };
        // "Area 1 Battle - The Snowbo Squad (Snowdwellers)" without its " (tribe)".
        private static string WithoutTribe(string name)
        {
            int open = name.LastIndexOf(" (", StringComparison.Ordinal);
            return open < 0 ? name : name.Substring(0, open);
        }
        private static readonly string[] HandFields = { "name", "rule", "region", "excluded", "text", "true_final" };
        // Which of a mod's cards join our groups (the user's list, 2026-11-24): (group, test on the card's pool kind and
        // effects). Groups not here (shroom, frenzy, sacrifice) take a mod's cards only when the creator adds them.
        private static readonly (string Group, Func<string, GameContent.Effects, bool> Joins)[] GroupJoins =
        {
            ("shell", (kind, e) => e.Applies.Contains("Shell") && kind == "Item" && !e.Traits.Contains("Consume")),
            ("spice", (kind, e) => e.Applies.Contains("Spice")),
            ("teeth", (kind, e) => e.Applies.Contains("Teeth")),
            ("block", (kind, e) => e.Applies.Contains("Block") && !e.Traits.Contains("Consume")),
            ("clunkers", (kind, e) => e.Kind == "Clunker"),
            ("summon", (kind, e) => e.Traits.Contains("Summon")),
        };
        // Groups the base file no longer has (2026-11-24): an old file's entries for them are dropped on a rerun, or
        // they'd become the mod's own new groups.
        private static readonly HashSet<string> RetiredGroups = new HashSet<string> { "demonize", "haze" };

        public class Failure : Exception
        {
            public Failure(string message) : base(message) { }
        }

        /// <summary>
        /// A mod's ID block: the first 4 bytes of the SHA-256 of its GUID (with "#&lt;salt&gt;" when the salt isn't 0).
        /// The same as block_for in apworld/wildfrost/extensions.py, which checks it (the user's call, 2026-11-24).
        /// </summary>
        public static long BlockFor(string guid, int salt)
        {
            string text = salt == 0 ? guid : guid + "#" + salt.ToString(CultureInfo.InvariantCulture);
            using (var sha = System.Security.Cryptography.SHA256.Create())
            {
                var hash = sha.ComputeHash(Encoding.UTF8.GetBytes(text));
                return ((long)hash[0] << 24) | ((long)hash[1] << 16) | ((long)hash[2] << 8) | hash[3];
            }
        }

        /// <summary>The extension file's text. old: the existing file to update, or null.</summary>
        public static string Generate(GameContent game, JObject baseDoc, JObject old, string guid, string mod, int salt,
                                      string version, List<string> notes, out string summary)
        {
            long block = BlockFor(guid, salt);
            var oldItems = new List<JObject>();
            if (old?["ap_items"] is JObject oldItemTree)
                foreach (var kind in oldItemTree.Properties())
                    foreach (var r in kind.Value.Children<JObject>())
                    {
                        var row = (JObject)r.DeepClone();
                        row["kind"] = kind.Name;
                        // Short pack rows (from 2026-11-25) leave the clan and kind to the key.
                        string[] keyParts = ((string)row["key"] ?? "").Split(':');
                        if (kind.Name == "Pack" && keyParts.Length == 4)
                        {
                            if (row["clan"] == null) row["clan"] = keyParts[1];
                            if (row["card_kind"] == null) row["card_kind"] = keyParts[2];
                        }
                        oldItems.Add(row);
                    }
            var oldLocations = RowsOf(old?["ap_locations"]);
            // IDs of keys the mod no longer has: never given out again (found in review, 2026-11-24: they were
            // only kept for one rerun). A key that comes back gets its own ID back.
            var oldRetired = new[] { "items", "locations" }.Select(space =>
                (old?["retired"]?[space] as JObject)?.Properties().ToDictionary(p => p.Name, p => (long)p.Value)
                ?? new Dictionary<string, long>()).ToArray();
            // A new salt moves the mod to a new block: every ID moves with it, in the same order. The old block is
            // the old file's salt's (files from before 2026-11-25 also wrote it as "id_block").
            long? oldBlock = old == null ? (long?)null
                : old["id_block"] != null ? (long)old["id_block"]
                : BlockFor(guid, (int?)old["id_salt"] ?? 0);
            if (oldBlock != null && oldBlock != block)
            {
                long shift = (block - oldBlock.Value) * BlockSize;
                foreach (var r in oldItems.Concat(oldLocations)) r["id"] = (long)r["id"] + shift;
                foreach (var space in oldRetired)
                    foreach (var key in space.Keys.ToList()) space[key] += shift;
                notes.Add($"new ID block {block} (id_salt {salt}): every ID changed, so raise the version; " +
                          "seeds made with the old file need the old file");
            }

            var others = game.LoadedMods.Where(g => g != guid).Select(g => g + ".").ToList();
            bool Ours(string name) => name.StartsWith(guid + ".", StringComparison.Ordinal)
                                      || !others.Any(p => name.StartsWith(p, StringComparison.Ordinal));

            // The base game, from base.wildfrost.json.
            var baseCards = new Dictionary<string, string>();   // name -> section (companions, items, charms)
            var baseClanOf = new Dictionary<string, string>();  // name -> its clan (General, Basic, Magic, Clunk)
            foreach (var section in ((JObject)baseDoc["cards"]).Properties())
                foreach (var clan in ((JObject)section.Value).Properties())
                    foreach (var c in clan.Value)
                    {
                        baseCards[((string)c["key"]).Substring(5)] = section.Name;
                        baseClanOf[((string)c["key"]).Substring(5)] = clan.Name;
                    }
            var baseBattleRows = baseDoc["ap_locations"]["battles"].Children<JObject>().ToList();
            var baseBattleKeys = new HashSet<string>(baseBattleRows.Select(r => (string)r["key"]));
            var baseBattleNames = new HashSet<string>(baseBattleKeys.Select(k => k.Split(':')[2]));
            var baseChallenges = baseDoc["ap_locations"]["challenges"].Select(r => ((string)r["key"]).Substring(10))
                .Where(c => !c.StartsWith("ap:")).Concat(ExtraBaseChallenges).ToList();
            var basePets = new HashSet<string>(baseDoc["ap_items"]["Pet"].Select(r => ((string)r["key"]).Substring(4)));
            var baseBells = baseDoc["bells"].Select(b => (string)b["name"]).ToList();

            // New tribes (the user's calls, 2026-11-16): each ClassData the base game doesn't have. Its own pools
            // are the ones the base game doesn't have; "shares" is the vanilla clan whose pools it also draws from.
            var oldTribeNames = oldItems.Where(r => (string)r["kind"] == "Tribe")
                .ToDictionary(r => ((string)r["key"]).Substring(6), r => (string)r["name"]);
            var tribes = new List<Tribe>();
            var skippedTribes = new List<GameContent.Clan>();
            foreach (var clan in game.Clans.Where(c => !BaseClans.Contains(c.Name) && Ours(c.Name)))
            {
                // A ClassData with no leaders can't be picked at tribe select (Another Snowfall's Villan, a template).
                if (clan.Leaders.Count == 0)
                {
                    notes.Add($"skipped tribe {clan.Name}: it has no leaders, so it can't be played");
                    skippedTribes.Add(clan);
                    continue;
                }
                var t = new Tribe
                {
                    Key = clan.Name, Clan = clan,
                    // "TerrariaAliens" reads "Terraria Aliens"; the creator may rename it.
                    Name = oldTribeNames.TryGetValue(clan.Name, out var n) ? n
                        : Regex.Replace(clan.Name.Substring(clan.Name.LastIndexOf('.') + 1), "(?<=[a-z])(?=[A-Z])", " "),
                };
                // What it draws (the user's calls, 2026-11-27): a vanilla clan's pools, General's (a mod's tribe can
                // leave them out) and pools of the mod's own, sorted out below into its own and shared ones.
                foreach (var pool in clan.Pools.Where(p => p != null && KindOfPool.ContainsKey(p.Type)))
                {
                    if (!BasePools.Contains(pool.Name)) t.Pools.Add(pool);
                    else if (ClanOf(pool.Name) is string vanilla)
                    {
                        if (vanilla == "General") t.General = true;
                        else if (!t.Shares.Contains(vanilla)) t.Shares.Add(vanilla);
                    }
                }
                tribes.Add(t);
            }
            var tribeKeys = new HashSet<string>(tribes.Select(t => t.Key));

            // A pool of the mod's own that several of its tribes draw is a clan of its own (the user's call,
            // 2026-11-27: Another Snowfall's 21 tribes all draw "EnemyItemPool" and the like), named after the pool:
            // "EnemyItemPool", "EnemyUnitPool" and "EnemyCharmPool" make one clan, "<GUID>.pool.Enemy". A pool only
            // one tribe draws stays that tribe's own.
            string FamilyOf(string pool) => Regex.Replace(pool, "(Item|Unit|Charm)Pool$", "");
            var usersOfPool = new Dictionary<string, HashSet<string>>();
            foreach (var t in tribes)
                foreach (var pool in t.Pools)
                {
                    if (!usersOfPool.TryGetValue(pool.Name, out var users)) usersOfPool[pool.Name] = users = new HashSet<string>();
                    users.Add(t.Key);
                }
            var oldPoolClans = old?["clans"] as JObject;
            var poolClans = new Dictionary<string, string>();   // clan -> its packs' label
            var poolsOfClan = new Dictionary<string, List<GameContent.Pool>>();
            foreach (var t in tribes)
                foreach (var pool in t.Pools.Where(p => usersOfPool[p.Name].Count > 1).ToList())
                {
                    string family = FamilyOf(pool.Name);
                    string key = $"{guid}.pool.{family}";
                    if (!poolClans.ContainsKey(key))
                    {
                        // "QueenGloberry" reads "Queen Globerry"; the creator may rename it.
                        poolClans[key] = (string)oldPoolClans?[key] ?? Regex.Replace(family, "(?<=[a-z])(?=[A-Z])", " ");
                        poolsOfClan[key] = new List<GameContent.Pool>();
                    }
                    if (!poolsOfClan[key].Any(p => p.Name == pool.Name)) poolsOfClan[key].Add(pool);
                    if (!t.Shares.Contains(key)) t.Shares.Add(key);
                    t.Pools.Remove(pool);
                }

            // Every card in the clans' pools (Tutorial's aside), with the first pool it's in. A new tribe's own pools
            // come after: their cards are the tribe's.
            var pooled = new Dictionary<string, GameContent.Pool>();
            var skippedClans = new HashSet<string>(skippedTribes.Select(c => c.Name));
            foreach (var clan in game.Clans.Where(c => c.Name != "Tutorial" && !tribeKeys.Contains(c.Name) && !skippedClans.Contains(c.Name)))
                foreach (var pool in clan.Pools.Where(p => p != null && KindOfPool.ContainsKey(p.Type)))
                    foreach (var name in pool.Cards)
                        if (!pooled.ContainsKey(name)) pooled[name] = pool;
            foreach (var t in tribes)
                foreach (var pool in t.Clan.Pools.Where(p => BasePools.Contains(p.Name) && KindOfPool.ContainsKey(p.Type)))
                    foreach (var name in pool.Cards)
                        if (!pooled.ContainsKey(name)) pooled[name] = pool;

            string Title(string name) => game.Titles.TryGetValue(name, out var title) ? title : name;

            // Cards the mod adds, by the reward pool they're in.
            var cards = new List<JObject>();
            foreach (var kv in pooled.OrderBy(kv => kv.Key, StringComparer.Ordinal))
            {
                if (baseCards.ContainsKey(kv.Key) || !Ours(kv.Key)) continue;
                var clan = ClanOf(kv.Value.Name);
                if (clan == null)
                {
                    notes.Add($"skipped {kv.Key}: its pool {kv.Value.Name} isn't a clan's or General");
                    continue;
                }
                cards.Add(new JObject { ["key"] = "card:" + kv.Key, ["name"] = Title(kv.Key),
                                        ["kind"] = KindOfPool[kv.Value.Type], ["clan"] = clan });
            }
            // A shared pool clan's cards, then a tribe's own: those only in the mod's own pools (a card a vanilla pool
            // has keeps that clan; the vanilla cards a mod's pool reuses stay in their vanilla packs, a bonus logic
            // doesn't count for the tribe, the user's call, 2026-11-27).
            var filed = new HashSet<string>(cards.Select(c => ((string)c["key"]).Substring(5)));
            foreach (var pc in poolsOfClan)
                foreach (var pool in pc.Value)
                    foreach (var name in pool.Cards)
                        if (!string.IsNullOrEmpty(name) && !baseCards.ContainsKey(name) && filed.Add(name))
                            cards.Add(new JObject { ["key"] = "card:" + name, ["name"] = Title(name),
                                                    ["kind"] = KindOfPool[pool.Type], ["clan"] = pc.Key });
            // A shared pool clan with none of the mod's own cards (only vanilla ones) gets no packs, and isn't a clan.
            // Its pools go back to each tribe's own, so the cards they reuse are still listed (reuses).
            foreach (var empty in poolClans.Keys.Where(k => !cards.Any(c => (string)c["clan"] == k)).ToList())
            {
                poolClans.Remove(empty);
                foreach (var t in tribes.Where(t => t.Shares.Remove(empty)))
                    t.Pools.AddRange(poolsOfClan[empty].Where(p => usersOfPool[p.Name].Contains(t.Key)));
            }
            foreach (var t in tribes)
                foreach (var pool in t.Pools)
                    foreach (var name in pool.Cards)
                        if (!string.IsNullOrEmpty(name) && !baseCards.ContainsKey(name) && filed.Add(name))
                            cards.Add(new JObject { ["key"] = "card:" + name, ["name"] = Title(name),
                                                    ["kind"] = KindOfPool[pool.Type], ["clan"] = t.Key });

            var items = new List<JObject>();
            var labels = ClanLabelOrder.Select(c => new KeyValuePair<string, string>(c, ClanLabel[c]))
                .Concat(tribes.Select(t => new KeyValuePair<string, string>(t.Key, t.Name)))
                .Concat(poolClans).ToList();
            foreach (var t in tribes)
            {
                var row = new JObject { ["key"] = "tribe:" + t.Key, ["name"] = t.Name, ["kind"] = "Tribe" };
                // One clan as a plain name, as files before 2026-11-27 had it; several as a list.
                if (t.Shares.Count == 1) row["shares"] = t.Shares[0];
                else if (t.Shares.Count > 1) row["shares"] = new JArray(t.Shares);
                if (!t.General) row["general"] = false;
                items.Add(row);
            }
            // Packs: themed packs (a "cards" list the creator wrote) keep their cards and name; the rest of the clan and
            // kind's cards get a pack per PackSize (found in review, 2026-11-24: counting themed cards too left more plain
            // packs than plain cards, which the apworld refuses).
            var oldPacks = oldItems.Where(r => (string)r["kind"] == "Pack").ToDictionary(r => (string)r["key"]);
            foreach (var label in labels)
                foreach (var kind in new[] { "Item", "Companion" })
                {
                    var ofGroup = new HashSet<string>(cards.Where(c => (string)c["clan"] == label.Key && (string)c["kind"] == kind)
                                                           .Select(c => (string)c["key"]));
                    var packs = new List<KeyValuePair<int, JObject>>();
                    var themed = new HashSet<string>();
                    // A tribe named after its mod ("Terraria Aliens") isn't prefixed twice.
                    string shown = label.Value.StartsWith(mod, StringComparison.Ordinal) ? label.Value : $"{mod} {label.Value}";
                    foreach (var p in oldPacks.Values.Where(p => (string)p["clan"] == label.Key && (string)p["card_kind"] == kind
                                                                 && p["cards"] is JArray))
                    {
                        var kept = p["cards"].Select(c => (string)c).Where(c => ofGroup.Contains(c) && !themed.Contains(c)).ToList();
                        if (kept.Count == 0)
                        {
                            notes.Add($"themed pack {p["key"]} has none of its cards left: it's a plain pack again");
                            continue;
                        }
                        themed.UnionWith(kept);
                        bool numbered = int.TryParse(((string)p["key"]).Substring(((string)p["key"]).LastIndexOf('-') + 1), out int index);
                        string usual = numbered ? $"{shown} {kind} Pack {index}" : null;
                        packs.Add(new KeyValuePair<int, JObject>(index, new JObject
                        {
                            ["key"] = p["key"], ["name"] = p["name"] ?? usual, ["usualName"] = usual, ["kind"] = "Pack",
                            ["clan"] = label.Key, ["card_kind"] = kind, ["cards"] = new JArray(kept),
                        }));
                    }
                    int plain = (ofGroup.Count - themed.Count + PackSize - 1) / PackSize;
                    for (int i = 1; plain > 0; i++)
                    {
                        string key = $"pack:{label.Key}:{kind}:{mod}-{i}";
                        if (packs.Any(p => (string)p.Value["key"] == key)) continue;
                        packs.Add(new KeyValuePair<int, JObject>(i, new JObject { ["key"] = key, ["name"] = $"{shown} {kind} Pack {i}",
                                                                                  ["usualName"] = $"{shown} {kind} Pack {i}",
                                                                                  ["kind"] = "Pack", ["clan"] = label.Key, ["card_kind"] = kind }));
                        plain--;
                    }
                    items.AddRange(packs.OrderBy(p => p.Key).Select(p => p.Value));
                }
            foreach (var c in cards.Where(c => (string)c["kind"] == "Charm"))
                items.Add(new JObject { ["key"] = $"charm:{c["clan"]}:{((string)c["key"]).Substring(5)}", ["name"] = c["name"],
                                        ["kind"] = "Charm", ["clan"] = c["clan"], ["card"] = c["key"] });
            foreach (var pet in game.Pets.Where(p => !basePets.Contains(p) && Ours(p)))
                items.Add(new JObject { ["key"] = "pet:" + pet, ["name"] = Title(pet) + " Pet", ["kind"] = "Pet" });

            // Battles: each map tier's, as a check per vanilla run tribe.
            var battles = new List<JObject>();
            foreach (var b in game.Battles)
            {
                int area = AreaOfTier.TryGetValue(b.Tier, out var a) ? a : 2;
                bool boss = BossTiers.Contains(b.Tier);
                foreach (var rt in RunTribes)
                {
                    string shown = TrueFinalBattles.TryGetValue(b.Name, out var tf) ? tf : b.Shown;
                    var row = new JObject
                    {
                        ["key"] = $"battle:{area}:{b.Name}:{rt[0]}",
                        ["name"] = $"Area {area + 1} {(boss ? "Boss" : "Battle")} - {shown} ({rt[1]})",
                        ["title"] = shown, ["area"] = area, ["tier"] = b.Tier, ["boss"] = boss, ["run_tribe"] = rt[0],
                    };
                    // A battle in the True Final Boss's tier is a True Final Boss fight: its bells, and only in seeds
                    // whose goal goes there (the user's call, 2026-11-24; the apworld requires the flag).
                    if (b.Tier == TrueFinalTier) row["true_final"] = true;
                    battles.Add(row);
                }
            }
            var locations = new List<JObject>();
            foreach (var b in battles.Where(b => !baseBattleKeys.Contains((string)b["key"]) && Ours(((string)b["key"]).Split(':')[2])))
            {
                locations.Add(b);
                // A boss's "#2" is a twin, always in the seed, as the base game's bosses' are (the user's call, 2026-11-27:
                // Another Snowfall replaces every boss, and its seeds lost all 18 boss "#2"s). Any other battle's is a
                // spare, only in a seed short of checks for its items (written as "spares").
                var second = new JObject { ["key"] = b["key"] + "#2" };
                if ((bool)b["boss"]) second["twin"] = true;
                locations.Add(second);
            }
            // Each tribe's battle checks (the user's call, 2026-11-16: full checks, like a vanilla clan's): every base
            // battle and the mod's own, as a Snowdweller run's, with the bosses' "#2" as twins (always in the seed).
            // A base battle the loaded game no longer has (removed) is left out: its checks could never come up.
            var inGame = new HashSet<string>(game.Battles.Select(b => b.Name));
            var templates = baseBattleRows.Where(r => (string)r["run_tribe"] == "Basic" && inGame.Contains(((string)r["key"]).Split(':')[2]))
                .Concat(locations.Where(l => ((string)l["key"]).StartsWith("battle:") && (string)l["run_tribe"] == "Basic")).ToList();
            foreach (var t in tribes)
                foreach (var r in templates)
                {
                    string rk = (string)r["key"];
                    string key = rk.Substring(0, rk.LastIndexOf(':')) + ":" + t.Key;
                    var row = new JObject
                    {
                        ["key"] = key, ["name"] = ((string)r["name"]).Replace("(Snowdwellers)", $"({t.Name})"),
                        ["area"] = r["area"], ["tier"] = r["tier"], ["boss"] = r["boss"], ["run_tribe"] = t.Key,
                    };
                    if (r["title"] != null) row["title"] = r["title"];
                    if ((bool?)r["true_final"] == true) row["true_final"] = true;
                    locations.Add(row);
                    if ((bool)r["boss"]) locations.Add(new JObject { ["key"] = key + "#2", ["twin"] = true });
                }
            foreach (var ch in game.Challenges.Where(c => !baseChallenges.Contains(c.Name) && Ours(c.Name))
                         .OrderBy(c => c.Name, StringComparer.Ordinal))
            {
                string desc = ch.Text.Replace("{0}", ch.Goal.ToString(CultureInfo.InvariantCulture));
                locations.Add(new JObject { ["key"] = "challenge:" + ch.Name,
                                            ["name"] = "Challenge - " + (string.IsNullOrEmpty(ch.Title) ? desc : ch.Title),
                                            ["text"] = desc, ["region"] = "Area 1", ["rule"] = JValue.CreateNull(),
                                            // Filler only until its creator writes what it needs (the user's call,
                                            // 2026-11-26): a plain export can't make a seed unwinnable.
                                            ["excluded"] = true });
                // Its spare "#2", only in a seed short of checks for its items (written as "spares").
                locations.Add(new JObject { ["key"] = $"challenge:{ch.Name}#2" });
            }

            var bells = new JArray(game.Bells.Where(b => !baseBells.Contains(b.Key) && Ours(b.Key))
                .Select(b => new JObject { ["name"] = b.Key, ["points"] = b.Value }));

            // What the mod takes out of the base game (with other mods loaded, theirs too).
            var gameBattles = new HashSet<string>(game.Battles.Select(b => b.Name));
            var gameChallenges = new HashSet<string>(game.Challenges.Select(c => c.Name));
            var gameBells = new HashSet<string>(game.Bells.Select(b => b.Key));
            var removes = new JObject();
            void Removed(string what, IEnumerable<string> names)
            {
                var list = names.OrderBy(n => n, StringComparer.Ordinal).ToList();
                if (list.Count > 0) removes[what] = new JArray(list);
            }
            Removed("cards", baseCards.Where(kv => kv.Value != "charms" && !pooled.ContainsKey(kv.Key)).Select(kv => kv.Key));
            Removed("charms", baseCards.Where(kv => kv.Value == "charms" && !pooled.ContainsKey(kv.Key)).Select(kv => kv.Key));
            Removed("battles", baseBattleNames.Where(n => !gameBattles.Contains(n)));
            Removed("challenges", baseChallenges.Where(c => !gameChallenges.Contains(c) && c.StartsWith("Challenge ")));
            Removed("bells", baseBells.Where(n => !gameBells.Contains(n)));
            // Pets the game no longer has (Another Snowfall replaces the base game's, 2026-11-27).
            var gamePets = new HashSet<string>(game.Pets);
            Removed("pets", basePets.Where(p => !gamePets.Contains(p)));
            // The apworld refuses a file that leaves a boss tier with no boss (the user's call, 2026-11-26: every run's
            // map deals one from each; bosses may go if the tier keeps a base one or one of the mod's own): say so now.
            var removedBattles = new HashSet<string>((removes["battles"] ?? new JArray()).Select(n => (string)n));
            var ownBossTiers = new HashSet<int>(battles.Where(b => !baseBattleKeys.Contains((string)b["key"])
                                                                   && Ours(((string)b["key"]).Split(':')[2])
                                                                   && ((bool)b["boss"] || (bool?)b["true_final"] == true))
                                                       .Select(b => (int)b["tier"]));
            var emptyTiers = baseBattleRows.Where(r => (bool)r["boss"] || (bool?)r["true_final"] == true)
                .GroupBy(r => (int)r["tier"])
                .Where(g => g.All(r => removedBattles.Contains(((string)r["key"]).Split(':')[2])) && !ownBossTiers.Contains(g.Key))
                .Select(g => $"map tier {g.Key} ({string.Join(", ", g.Select(r => ((string)r["key"]).Split(':')[2]).Distinct())})")
                .ToList();
            if (emptyTiers.Count > 0)
                notes.Add($"Archipelago won't load this file: it removes every boss of {string.Join("; ", emptyTiers)}, and " +
                          "every run's map needs one there. Keep one, or add a boss of your own in that tier");
            if (removes.Count > 0 && others.Count > 1)  // others has this mod, and others besides
                notes.Add("other mods are loaded: 'removes' lists what any of them took out, not just this mod");

            // Effects (the user's calls, 2026-11-15): each card lists what it applies, for the "applies" rule form
            // (which also counts clans whose leaders apply it), and the mod's cards join our groups by GroupJoins.
            // What the creator added to groups by hand stays.
            var groups = new Dictionary<string, List<string>>();
            if (old?["groups"] is JObject oldGroups)
                foreach (var g in oldGroups.Properties().Where(g => !g.Name.StartsWith("applies:") && !RetiredGroups.Contains(g.Name)))
                    groups[g.Name] = g.Value.Select(v => (string)v).ToList();
            var joined = new SortedDictionary<string, List<string>>(StringComparer.Ordinal);
            void Join(string group, string entry)
            {
                if (!groups.TryGetValue(group, out var list)) groups[group] = list = new List<string>();
                if (!list.Contains(entry)) list.Add(entry);
            }
            GameContent.Effects EffectsOf(string name) =>
                game.CardEffects.TryGetValue(name, out var e) ? e : new GameContent.Effects { Kind = "" };
            foreach (var c in cards)
            {
                string name = ((string)c["key"]).Substring(5);
                var e = EffectsOf(name);
                foreach (var g in GroupJoins)
                    if (g.Joins((string)c["kind"], e))
                    {
                        Join(g.Group, name);
                        if (!joined.TryGetValue(g.Group, out var list)) joined[g.Group] = list = new List<string>();
                        list.Add(name);
                    }
            }
            foreach (var c in cards)
            {
                var e = EffectsOf(((string)c["key"]).Substring(5));
                if (e.Applies.Count > 0) c["applies"] = Sorted(e.Applies);
                if (e.Traits.Count > 0) c["traits"] = Sorted(e.Traits);
            }
            var groupTree = new JObject();
            foreach (var g in groups.Where(g => g.Value.Count > 0).OrderBy(g => g.Key, StringComparer.Ordinal))
                groupTree[g.Key] = new JArray(g.Value);
            // Its tribes' leaders and what they apply, for ["applies", ...] (as the base file's "leaders").
            var leaders = new JObject();
            foreach (var t in tribes.Where(t => t.Clan.Leaders.Count > 0))
                leaders[t.Key] = new JArray(t.Clan.Leaders.Select(n =>
                {
                    var e = EffectsOf(n);
                    var row = new JObject { ["key"] = n };
                    if (e.Applies.Count > 0) row["applies"] = Sorted(e.Applies);
                    if (e.Traits.Count > 0) row["traits"] = Sorted(e.Traits);
                    return row;
                }));
            if (joined.Count > 0)
                notes.Add("joined our groups: " + string.Join("; ", joined.Select(g => $"{g.Key}: {string.Join(", ", g.Value)}")));

            // IDs: kept for keys the old file had, the next free one in the block for new keys.
            long low = IdBase + block * BlockSize, high = low + BlockSize;
            var retired = new JObject();
            foreach (var (space, rows, oldRows, wasRetired) in new[] { ("items", items, oldItems, oldRetired[0]),
                                                                        ("locations", locations, oldLocations, oldRetired[1]) })
            {
                var oldByKey = new Dictionary<string, JObject>();
                foreach (var r in oldRows) oldByKey[(string)r["key"]] = r;
                var used = new HashSet<long>(oldRows.Select(r => (long)r["id"]).Concat(wasRetired.Values));
                var stillRetired = new Dictionary<string, long>(wasRetired);
                long next = low;
                foreach (var row in rows)
                {
                    string key = (string)row["key"];
                    if (stillRetired.TryGetValue(key, out long back))
                    {
                        row["id"] = back;  // a key that came back
                        stillRetired.Remove(key);
                        continue;
                    }
                    if (oldByKey.TryGetValue(key, out var previous))
                    {
                        row["id"] = previous["id"];
                        // What the creator wrote by hand stays.
                        if (key.StartsWith("challenge:"))
                        {
                            foreach (var field in HandFields)
                                if (previous.ContainsKey(field)) row[field] = previous[field].DeepClone();
                            // Only a challenge new to the file starts filler only; one already there keeps what it had.
                            if (!previous.ContainsKey("excluded")) row.Remove("excluded");
                        }
                        if ((string)row["kind"] == "Tribe") row["name"] = previous["name"];
                        // A battle's name is written only when the creator changed it (the user's call, 2026-11-25:
                        // the apworld makes it from the title and the tribe's name, so a renamed tribe renames its
                        // battles). Older files have every name written; one that differs only in the tribe is ours.
                        if (key.StartsWith("battle:") && previous["name"] != null
                            && WithoutTribe((string)previous["name"]) != WithoutTribe((string)row["name"]))
                        {
                            row["name"] = previous["name"];
                            row["keepName"] = true;
                        }
                        continue;
                    }
                    while (used.Contains(next)) next++;
                    if (next >= high) throw new Failure($"block {block} is full ({low}-{high - 1})");
                    row["id"] = next;
                    used.Add(next);
                }
                var gone = oldByKey.Keys.Except(rows.Select(r => (string)r["key"])).OrderBy(k => k, StringComparer.Ordinal).ToList();
                if (gone.Count > 0) notes.Add("no longer in the game (their IDs stay retired): " + string.Join(", ", gone));
                foreach (var key in gone) stillRetired[key] = (long)oldByKey[key]["id"];
                if (stillRetired.Count > 0)
                    retired[space] = new JObject(stillRetired.OrderBy(r => r.Value).Select(r => new JProperty(r.Key, r.Value)));
                var sorted = rows.OrderBy(r => (long)r["id"]).ToList();
                rows.Clear();
                rows.AddRange(sorted);
            }

            // Nested (the user's layout, 2026-11-15): cards by kind then clan, items by kind, battles and challenges.
            var sections = new[] { new[] { "Companion", "companions" }, new[] { "Item", "items" }, new[] { "Charm", "charms" } };
            var cardTree = new JObject();
            foreach (var s in sections)
            {
                var ofKind = cards.Where(c => (string)c["kind"] == s[0]).ToList();
                if (ofKind.Count == 0) continue;
                var byClan = new JObject();
                foreach (var c in ofKind)
                {
                    var row = (JObject)c.DeepClone();
                    string clan = (string)row["clan"];
                    row.Remove("kind");
                    row.Remove("clan");
                    if (byClan[clan] == null) byClan[clan] = new JArray();
                    ((JArray)byClan[clan]).Add(row);
                }
                cardTree[s[1]] = byClan;
            }
            var itemTree = new JObject();
            foreach (var item in items)
            {
                var row = (JObject)item.DeepClone();
                string kind = (string)row["kind"];
                row.Remove("kind");
                // Short rows (the user's call, 2026-11-25): the apworld reads a pack's clan and kind, and a charm's clan
                // and card, from the key, and names them as here. A themed pack's own name is still written.
                if (kind == "Pack")
                {
                    row.Remove("clan");
                    row.Remove("card_kind");
                    if ((string)row["name"] == (string)row["usualName"]) row.Remove("name");
                    row.Remove("usualName");
                }
                else if (kind == "Charm")
                {
                    row.Remove("clan");
                    row.Remove("card");
                    row.Remove("name");
                }
                if (itemTree[kind] == null) itemTree[kind] = new JArray();
                ((JArray)itemTree[kind]).Add(row);
            }
            var locationTree = new JObject();
            void Section(string name, IEnumerable<JToken> rows)
            {
                var list = rows.ToList();
                if (list.Count > 0) locationTree[name] = new JArray(list);
            }
            bool Second(JObject l) => ((string)l["key"]).EndsWith("#2");
            // Short battle rows (the user's call, 2026-11-25): the apworld works out the area and run tribe from the key,
            // a base game battle's tier, boss and title from its own, and the name; no tribe locks.
            JObject Short(JObject l)
            {
                var row = new JObject { ["key"] = l["key"], ["id"] = l["id"] };
                if (l["keepName"] != null) row["name"] = l["name"];
                if (!baseBattleNames.Contains(((string)l["key"]).Split(':')[2]))
                {
                    if (l["keepName"] == null) row["title"] = l["title"];
                    row["tier"] = l["tier"];
                    if ((bool)l["boss"]) row["boss"] = true;
                    if ((bool?)l["true_final"] == true) row["true_final"] = true;
                }
                return row;
            }
            Section("battles", locations.Where(l => ((string)l["key"]).StartsWith("battle:") && !Second(l)).Select(Short));
            Section("challenges", locations.Where(l => ((string)l["key"]).StartsWith("challenge:") && !Second(l)));
            var twins = new JObject();
            var spares = new JObject();
            foreach (var l in locations.Where(Second))
            {
                string original = ((string)l["key"]).Substring(0, ((string)l["key"]).Length - 2);
                (l["twin"] != null ? twins : spares)[original] = l["id"];
            }
            if (twins.Count > 0) locationTree["twins"] = twins;
            if (spares.Count > 0) locationTree["spares"] = spares;

            var doc = new JObject
            {
                ["format"] = 1, ["mod"] = mod, ["guid"] = guid, ["version"] = version,
            };
            if (salt != 0) doc["id_salt"] = salt;
            if (poolClans.Count > 0) doc["clans"] = JObject.FromObject(poolClans);
            // Cards of other clans that each of the mod's clans' own pools also hold (the user's calls, 2026-11-27:
            // Another Snowfall's Enemy pools reuse base-game cards): the apworld counts a pack by the share of its cards
            // a tribe can be offered, and keeps those packs in a seed with the tribe.
            var clanOfCard = cards.ToDictionary(c => ((string)c["key"]).Substring(5), c => (string)c["clan"]);
            var reuses = new JObject();
            // Each clan's pools, and the clans whose cards its runs draw anyway (not listed again).
            var poolsOf = poolsOfClan.Where(pc => poolClans.ContainsKey(pc.Key))
                .Select(pc => (pc.Key, pc.Value, Drawn: new HashSet<string> { pc.Key }))
                .Concat(tribes.Select(t => (t.Key, t.Pools, Drawn: new HashSet<string>(t.Shares.Append(t.Key).Concat(t.General ? new[] { "General" } : new string[0])))));
            foreach (var (clan, pools, drawnAnyway) in poolsOf)
            {
                var other = pools.SelectMany(p => p.Cards).Where(n => !string.IsNullOrEmpty(n)).Distinct()
                    .Where(n => (clanOfCard.TryGetValue(n, out var c) || baseClanOf.TryGetValue(n, out c)) && !drawnAnyway.Contains(c))
                    .ToList();
                if (other.Count > 0) reuses[clan] = Sorted(other);
            }
            if (reuses.Count > 0) doc["reuses"] = reuses;
            doc["cards"] = cardTree;
            doc["ap_items"] = itemTree;
            doc["ap_locations"] = locationTree;
            if (leaders.Count > 0) doc["leaders"] = leaders;
            // Its tribes' starting decks, for ["starts_with", card] (the user's call, 2026-11-24).
            var decks = new JObject();
            foreach (var t in tribes.Where(t => t.Clan.StartDeck.Count > 0))
                decks[t.Key] = new JArray(t.Clan.StartDeck);
            if (decks.Count > 0) doc["start_decks"] = decks;
            doc["bells"] = bells;
            doc["groups"] = groupTree;
            doc["removes"] = removes;
            if (retired.Count > 0) doc["retired"] = retired;

            var unruled = locations.Where(l => ((string)l["key"]).StartsWith("challenge:") && !Second(l)
                                               && (l["rule"] == null || l["rule"].Type == JTokenType.Null))
                .Select(l => (string)l["key"]).ToList();
            var fillerOnly = locations.Where(l => ((string)l["key"]).StartsWith("challenge:") && !Second(l)
                                                  && (bool?)l["excluded"] == true)
                .Select(l => (string)l["key"]).ToList();
            summary = $"{cards.Count} cards, {items.Count} items ({items.Count(i => (string)i["kind"] == "Pack")} packs), " +
                      $"{locations.Count} locations, {bells.Count} storm bells" +
                      (removes.Count > 0 ? ", removes " + string.Join(", ", removes.Properties().Select(p => $"{((JArray)p.Value).Count} {p.Name}")) : "") +
                      // The mod's ID range, for reading only: /generate gives every ID (the user's call, 2026-11-25).
                      $"; IDs {low}-{high - 1}";
            int checks = locations.Count(l => !Second(l));
            if (items.Count > checks)
                // Spare "#2" checks and fuller packs make room in a seed, but they're a fallback: challenges for the
                // mod's content are better (the user, 2026-11-15).
                notes.Add($"{items.Count} items but {checks} checks: consider adding challenges for this mod's content; " +
                          "until then seeds make room with spare '#2' checks and, past those, fuller packs");
            if (fillerOnly.Count > 0)
                notes.Add("challenges that only hold filler until you write their rule and remove \"excluded\": " +
                          string.Join(", ", fillerOnly));
            var ruleless = unruled.Except(fillerOnly).ToList();
            if (ruleless.Count > 0)
                notes.Add("challenges with no rule (in logic from the start): " + string.Join(", ", ruleless));
            return Format(doc);
        }

        private class Tribe
        {
            public string Key, Name;
            public List<string> Shares = new List<string>();   // vanilla clans and shared pool clans it also draws
            public bool General;
            public GameContent.Clan Clan;
            public List<GameContent.Pool> Pools = new List<GameContent.Pool>();
        }

        private static string ClanOf(string pool)
        {
            var m = Regex.Match(pool, "^(General|Snow|Basic|Magic|Clunk)");
            return m.Success ? ClanOfPool[m.Groups[1].Value] : null;
        }

        private static JArray Sorted(IEnumerable<string> values) => new JArray(values.OrderBy(v => v, StringComparer.Ordinal));

        /// <summary>
        /// A location section's rows: nested by kind, and "twins" and "spares" ({original key: id}) come back as "#2"
        /// rows with just their key and ID.
        /// </summary>
        private static List<JObject> RowsOf(JToken section)
        {
            var rows = new List<JObject>();
            if (section is JObject tree)
            {
                foreach (var p in tree.Properties())
                {
                    if ((p.Name == "twins" || p.Name == "spares") && p.Value is JObject refs)
                        rows.AddRange(refs.Properties().Select(r => new JObject { ["key"] = r.Name + "#2", ["id"] = r.Value }));
                    else rows.AddRange(RowsOf(p.Value));
                }
            }
            else if (section is JArray list) rows.AddRange(list.Children<JObject>());
            return rows;
        }

        // ---- The file's layout: one entry per line in each list, so it reads (and diffs) a row at a time.

        public static string Format(JObject doc) => Value(doc, "") + "\n";

        private static bool Scalar(JToken t) => t.Type != JTokenType.Object && t.Type != JTokenType.Array;

        private static string Value(JToken v, string indent)
        {
            if (v is JObject o)
            {
                var props = o.Properties().ToList();
                if (props.Count > 3 && props.All(p => p.Value.Type == JTokenType.Integer || p.Value.Type == JTokenType.Boolean
                                                      || p.Value.Type == JTokenType.String))
                    return "{\n" + string.Join(",\n", props.Select(p => $"{indent}  {Json(p.Name, true)}: {Json(p.Value, true)}"))
                           + "\n" + indent + "}";
                if (props.Count > 1 && props.All(p => p.Value is JArray a && a.All(Scalar)))
                    return "{\n" + string.Join(",\n", props.Select(p => $"{indent}  {Json(p.Name, true)}: {Json(p.Value, false)}"))
                           + "\n" + indent + "}";
                if (props.Any(p => !Scalar(p.Value))
                    && props.Any(p => p.Value is JArray a && a.Count > 0 && a[0] is JObject || p.Value is JObject))
                    return "{\n" + string.Join(",\n", props.Select(p => $"{indent}  {Json(p.Name, true)}: {Value(p.Value, indent + "  ")}"))
                           + "\n" + indent + "}";
            }
            if (v is JArray list && list.Count > 0 && list[0] is JObject)
                return "[\n" + string.Join(",\n", list.Select(r => indent + "  " + Json(r, false))) + "\n" + indent + "]";
            return Json(v, false);
        }

        /// <summary>JSON as Python's json.dumps writes it (", " and ": "; ascii: non-ASCII escaped).</summary>
        private static string Json(JToken t, bool ascii)
        {
            switch (t.Type)
            {
                case JTokenType.Object:
                    return "{" + string.Join(", ", ((JObject)t).Properties().Select(p => Json(p.Name, ascii) + ": " + Json(p.Value, ascii))) + "}";
                case JTokenType.Array:
                    return "[" + string.Join(", ", t.Select(x => Json(x, ascii))) + "]";
                case JTokenType.String:
                    return (string)t == null ? "null" : Json((string)t, ascii);
                case JTokenType.Integer:
                    return ((long)t).ToString(CultureInfo.InvariantCulture);
                case JTokenType.Boolean:
                    return (bool)t ? "true" : "false";
                case JTokenType.Null:
                    return "null";
                case JTokenType.Float:
                    return ((double)t).ToString("R", CultureInfo.InvariantCulture);
                default:
                    return Json(t.ToString(), ascii);
            }
        }

        private static string Json(string s, bool ascii)
        {
            var sb = new StringBuilder("\"");
            foreach (char c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    case '\b': sb.Append("\\b"); break;
                    case '\f': sb.Append("\\f"); break;
                    default:
                        if (c < 0x20 || ascii && c > 0x7f) sb.Append("\\u").Append(((int)c).ToString("x4"));
                        else sb.Append(c);
                        break;
                }
            }
            return sb.Append('"').ToString();
        }
    }
}
