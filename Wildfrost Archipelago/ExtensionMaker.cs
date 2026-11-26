using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Deadpan.Enums.Engine.Components.Modding;
using HarmonyLib;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace WildfrostArchipelago
{
    /// <summary>
    /// The "/generate" command in the client log (the user's call, 2026-11-24): writes a loaded mod's
    /// extension file from what the game has loaded, with no content dump, Python or base-game run
    /// needed. ExtensionGenerator holds the logic; this reads the live game into a GameContent and
    /// writes the file to the save folder's Extensions folder, updating the mod's file there if it has one.
    /// </summary>
    internal static class ExtensionMaker
    {
        /// <summary>Where files go unless folder=... says otherwise.</summary>
        public static string DefaultFolder => Path.Combine(ConnectionConfig.SaveFolder, "Extensions");
        private const string Suffix = ".wildfrost.json";

        // The user's wording (2026-11-25): short, with the details in EXTENSIONS.md.
        public const string Usage = "/generate <mod GUID> [version] [name=...] [folder=...] [salt=N]\n" +
                                    "Used to write an external mod's extension file. Instructions available on GitHub: " +
                                    "github.com/martin-servold/WFM-Archipelago (EXTENSIONS.md).\n" +
                                    "Install the file next to your wildfrost.apworld to use it for generation and Universal Tracker.";

        /// <summary>
        /// The mod's title as an extension name: only the letters, digits, spaces, '_', '.' and '-' the apworld
        /// takes ("VFX/SFX Tools" is "VFXSFX Tools"); the GUID's last part, the same way, when nothing's left (a title
        /// in another script, say); and when that's empty too, the creator is asked for name=.
        /// </summary>
        private static string NameFromTitle(WildfrostMod mod)
        {
            string Clean(string text) => System.Text.RegularExpressions.Regex.Replace(
                System.Text.RegularExpressions.Regex.Replace(text ?? "", @"[^A-Za-z0-9 _.\-]", ""), @"\s+", " ").Trim(' ', '.');
            string name = Clean(mod.Title);
            if (name.Length == 0) name = Clean(mod.GUID.Substring(mod.GUID.LastIndexOf('.') + 1));
            if (name.Length == 0)
                throw new ExtensionGenerator.Failure($"the mod's title ({mod.Title}) has no letters or digits a name can use: " +
                                                     "add name=... (A-Z, 0-9, spaces, _ . -)");
            return name;
        }

        public static void Run(ArchipelagoClient client, string args)
        {
            try
            {
                Generate(client, Split(args));
            }
            catch (ExtensionGenerator.Failure e)
            {
                client.Log("Generate failed: " + e.Message);
            }
            catch (Exception e)
            {
                client.Log("Generate failed: " + e.Message);
                Debug.LogError(ArchipelagoMod.LogPrefix + "generate: " + e);
            }
        }

        private static void Generate(ArchipelagoClient client, List<string> words)
        {
            var mods = Bootstrap.Mods.Where(m => m != null && m.HasLoaded && m != ArchipelagoMod.Instance).ToList();
            if (words.Count == 0)
            {
                client.Log(Usage);
                client.Log(mods.Count == 0 ? "No other mods are loaded."
                    : "Loaded mods: " + string.Join(", ", mods.Select(m => $"{m.GUID} ({m.Title})")));
                return;
            }
            var mod = mods.FirstOrDefault(m => m.GUID == words[0])
                      ?? throw new ExtensionGenerator.Failure($"no loaded mod has the GUID {words[0]} (/generate alone lists them)");

            // After the GUID: the version, and name=..., folder=... and salt=... (the user's layout, 2026-11-24).
            string version = null, name = null, saltText = null, folder = null;
            foreach (var word in words.Skip(1))
            {
                int eq = word.IndexOf('=');
                string key = eq < 0 ? null : word.Substring(0, eq).ToLowerInvariant(), value = eq < 0 ? word : word.Substring(eq + 1);
                if (key == null && version == null || key == "version") version = value;
                else if (key == "name") name = value;
                else if (key == "folder") folder = value;
                else if (key == "salt") saltText = value;
                else throw new ExtensionGenerator.Failure($"didn't understand {word}: " + Usage);
            }
            // Where to write, and where a rerun looks for the mod's file (the user's call, 2026-11-24).
            folder = Path.GetFullPath(string.IsNullOrWhiteSpace(folder) ? DefaultFolder : HostPath(folder));
            Directory.CreateDirectory(folder);
            string existing = null;
            JObject old = null;
            var owners = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);  // file -> its GUID (null: unreadable)
            foreach (var path in Directory.GetFiles(folder, "*" + Suffix))
            {
                JObject doc = null;
                try { doc = JObject.Parse(File.ReadAllText(path)); }
                catch (Exception) { }
                owners[path] = (string)doc?["guid"];
                if (existing == null && (string)doc?["guid"] == mod.GUID) { existing = path; old = doc; }
            }

            // The name: given, the existing file's, or the mod's title (the user's call, 2026-11-24).
            name = name ?? (string)old?["mod"] ?? NameFromTitle(mod);
            if (!System.Text.RegularExpressions.Regex.IsMatch(name, @"^[A-Za-z0-9 _.\-]+$"))
                throw new ExtensionGenerator.Failure("the name should be letters, digits, spaces, '_', '.' or '-'");
            version = version ?? (string)old?["version"] ?? "1.0.0";
            // The ID block comes from the GUID; the salt moves it, only when two mods' blocks clash.
            int salt = (int?)old?["id_salt"] ?? 0;
            if (saltText != null && (!int.TryParse(saltText, out salt) || salt < 0))
                throw new ExtensionGenerator.Failure($"the ID salt should be a whole number, 0 or more, not {saltText}");

            // Never overwrite another mod's file (or one that can't be read) with this one (found in review, 2026-11-24).
            string target = Path.Combine(folder, name + Suffix);
            if (owners.TryGetValue(target, out var owner) && owner != mod.GUID)
                throw new ExtensionGenerator.Failure($"{target} is {(owner == null ? "a file this can't read" : owner + "'s file")}: " +
                                                     "pick another name=");

            var notes = new List<string>();
            if (old != null && (string)old["mod"] != name)
                notes.Add($"renamed from {old["mod"]}: the pack keys and item names carry the name, so every pack has a new " +
                          "ID (the old ones are retired) and players need the new name in their options; raise the version");
            string text = ExtensionGenerator.Generate(Read(), BaseDoc(), old, mod.GUID, name, salt, version, notes, out var summary);
            // A rename: the old file goes. Paths compare without case (Windows, and Wine, ignore it): a rename that only
            // changes case deletes first, else the delete would take the file just written (found in review, 2026-11-24).
            if (existing != null && string.Equals(existing, target, StringComparison.OrdinalIgnoreCase))
            {
                if (existing != target) File.Delete(existing);
                File.WriteAllText(target, text);
            }
            else
            {
                File.WriteAllText(target, text);
                if (existing != null) File.Delete(existing);
            }
            client.Log($"Wrote {ShownPath(target)}: {summary}");
            foreach (var note in notes) client.Log("Note: " + note);
        }

        /// <summary>The base game's file, built into this DLL from apworld/wildfrost/base.wildfrost.json.</summary>
        private static JObject BaseDoc()
        {
            using (var stream = typeof(ExtensionMaker).Assembly.GetManifestResourceStream("WildfrostArchipelago.base.wildfrost.json"))
            using (var reader = new StreamReader(stream))
                return JObject.Parse(reader.ReadToEnd());
        }

        /// <summary>Words, with "double quotes" around one that has spaces.</summary>
        private static List<string> Split(string args)
        {
            var words = new List<string>();
            var current = new System.Text.StringBuilder();
            bool quoted = false, any = false;
            foreach (char c in args ?? "")
            {
                if (c == '"') { quoted = !quoted; any = true; }
                else if (c == ' ' && !quoted)
                {
                    if (any) words.Add(current.ToString());
                    current.Clear();
                    any = false;
                }
                else { current.Append(c); any = true; }
            }
            if (any) words.Add(current.ToString());
            return words;
        }

        /// <summary>What the game has loaded: every mod's content and the base game's.</summary>
        public static GameContent Read()
        {
            var game = new GameContent();
            game.LoadedMods.AddRange(Bootstrap.Mods.Where(m => m != null && m.HasLoaded).Select(m => m.GUID));

            foreach (var c in AddressableLoader.GetGroup<ClassData>("ClassData"))
            {
                if (c == null) continue;
                var clan = new GameContent.Clan { Name = c.name };
                foreach (var pool in c.rewardPools ?? new RewardPool[0])
                    if (pool != null)
                        clan.Pools.Add(new GameContent.Pool
                        {
                            Name = pool.name, Type = pool.type,
                            Cards = (pool.list ?? new List<DataFile>()).Select(SurveyLog.Name).ToList(),
                        });
                clan.Leaders.AddRange((c.leaders ?? new CardData[0]).Where(l => l != null).Select(l => l.name));
                clan.StartDeck.AddRange(StartDeck(c));
                game.Clans.Add(clan);
            }

            // Which battles can appear at each map tier (the normal game mode's populator). Tribe locks aren't read:
            // under AP every battle can come up in every run (the user's call, 2026-11-25).
            var mode = AddressableLoader.GetGroup<GameMode>("GameMode").FirstOrDefault(m => m.name == "GameModeNormal");
            var tiers = AccessTools.Field(typeof(CampaignPopulator), "tiers")?.GetValue(mode?.populator) as CampaignTier[];
            for (int i = 0; i < (tiers?.Length ?? 0); i++)
                foreach (var b in tiers[i]?.battlePool ?? new BattleData[0])
                {
                    if (b == null) continue;
                    string shown = SurveyLog.Loc(b.nameRef);
                    game.Battles.Add(new GameContent.Battle
                    {
                        Tier = i, Name = b.name, Shown = string.IsNullOrEmpty(shown) ? b.title ?? b.name : shown,
                    });
                }

            foreach (var c in ChallengeSystem.GetAllChallenges())
                if (c != null)
                    game.Challenges.Add(new GameContent.Challenge
                        { Name = c.name, Goal = c.goal, Title = SurveyLog.Loc(c.titleKey), Text = SurveyLog.Loc(c.textKey) });

            var bells = MonoBehaviourSingleton<References>.instance?.hardModeModifiers
                        ?? throw new ExtensionGenerator.Failure("the storm bells aren't loaded yet; try again from the main menu");
            foreach (var bell in bells)
                if (bell != null) game.Bells.Add(new KeyValuePair<string, int>(bell.name, bell.stormPoints));

            game.Pets.AddRange(MetaprogressionSystem.GetPetDict().Keys);

            var cards = AddressableLoader.GetGroup<CardData>("CardData").Where(c => c != null).ToList();
            var charms = AddressableLoader.GetGroup<CardUpgradeData>("CardUpgradeData").Where(u => u != null).ToList();
            // A card or charm without a localized title makes the game's own getter throw (seen 2026-11-24 with a
            // mod's upgrade): use its asset name instead, and log which.
            var untitled = new List<string>();
            foreach (var c in cards)
                if (!game.Titles.ContainsKey(c.name)) game.Titles[c.name] = Title(() => c.title, c.name, untitled);
            foreach (var u in charms)
                if (!game.Titles.ContainsKey(u.name)) game.Titles[u.name] = Title(() => u.title, u.name, untitled);
            if (untitled.Count > 0)
                Debug.LogWarning(ArchipelagoMod.LogPrefix + "generate: no title, so named by asset: " + string.Join(", ", untitled));

            // What each card and charm applies, and its traits (keywords): its attack effects, what its "apply X"
            // effects apply, and what its scripts add (how leaders get their abilities).
            var createScripts = AccessTools.Field(typeof(CardData), "createScripts");
            foreach (var c in cards)
                game.CardEffects[c.name] = Effects(SurveyLog.Name(c.cardType), c.attackEffects, c.startWithEffects, c.traits,
                                                   createScripts?.GetValue(c) as CardScript[]);
            foreach (var u in charms)
                game.CardEffects[u.name] = Effects(u.type.ToString(), u.attackEffects, u.effects, u.giveTraits, u.scripts);
            return game;
        }

        [System.Runtime.InteropServices.DllImport("ntdll.dll", EntryPoint = "wine_get_version")]
        static extern IntPtr WineGetVersion();

        static bool? wine;

        /// <summary>Running under Wine or Proton (ntdll has Wine's own export there, and not on Windows).</summary>
        static bool Wine
        {
            get
            {
                if (wine == null)
                {
                    try { wine = WineGetVersion() != IntPtr.Zero; }
                    catch (Exception) { wine = false; }
                }
                return wine.Value;
            }
        }

        /// <summary>A folder= as the player typed it, made a Windows path. Under Wine/Proton a Linux path ("/home/...")
        /// would otherwise land on the current drive (Proton's S:, the Steam folder; found 2026-11-24), so it goes
        /// through Z:, Wine's drive for "/"; "~" is the Linux home there. On Windows "~" is the user's profile.</summary>
        static string HostPath(string folder)
        {
            if (Wine)
            {
                if (folder.StartsWith("~"))
                {
                    // Proton doesn't pass HOME through (found 2026-11-24: "~" became C:\users\steamuser).
                    string home = LinuxHome() ?? throw new ExtensionGenerator.Failure(
                        "couldn't find your Linux home folder for \"~\"; give the full path, like folder=/home/you/...");
                    folder = home + folder.Substring(1);
                }
                if (folder.StartsWith("/") && !folder.StartsWith("//"))
                    return "Z:" + folder.Replace('/', '\\');
            }
            if (folder.StartsWith("~"))
                folder = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile) + folder.Substring(1);
            return folder;
        }

        /// <summary>
        /// The Linux home folder under Wine/Proton ("/home/you"): HOME when it's passed through, Wine's WINEHOMEDIR
        /// ("\\??\\Z:\\home\\you"), or the process's own Linux environment through Z:; null if none has it.
        /// </summary>
        static string LinuxHome()
        {
            string home = Environment.GetEnvironmentVariable("HOME");
            if (home != null && home.StartsWith("/")) return home.TrimEnd('/');
            string wine = Environment.GetEnvironmentVariable("WINEHOMEDIR");
            if (wine != null)
            {
                wine = wine.StartsWith(@"\??\") ? wine.Substring(4) : wine;
                if (wine.StartsWith(@"Z:\", StringComparison.OrdinalIgnoreCase)) return wine.Substring(2).Replace('\\', '/').TrimEnd('/');
            }
            try
            {
                foreach (string entry in File.ReadAllText(@"Z:\proc\self\environ").Split('\0'))
                    if (entry.StartsWith("HOME=/")) return entry.Substring(5).TrimEnd('/');
            }
            catch (Exception) { }
            return null;
        }

        /// <summary>A path as the player would type it: under Wine, a Z: path as the Linux path.</summary>
        static string ShownPath(string path) =>
            Wine && path.StartsWith("Z:\\", StringComparison.OrdinalIgnoreCase) ? path.Substring(2).Replace('\\', '/') : path;

        static string Title(Func<string> get, string name, List<string> untitled)
        {
            try
            {
                var title = get();
                if (!string.IsNullOrEmpty(title)) return title;
            }
            catch (Exception) { }
            untitled.Add(name);
            return name;
        }

        private static GameContent.Effects Effects(string kind, IEnumerable<CardData.StatusEffectStacks> attack,
                                                   IEnumerable<CardData.StatusEffectStacks> start,
                                                   IEnumerable<CardData.TraitStacks> traits, IEnumerable<CardScript> scripts)
        {
            var e = new GameContent.Effects { Kind = kind };
            foreach (var s in attack ?? Enumerable.Empty<CardData.StatusEffectStacks>())
                if (s?.data != null) e.Applies.Add(Applied(s.data) ?? s.data.name);
            foreach (var s in start ?? Enumerable.Empty<CardData.StatusEffectStacks>())
                if (s?.data != null && Applied(s.data) is string applied) e.Applies.Add(applied);
            if ((attack ?? Enumerable.Empty<CardData.StatusEffectStacks>()).Concat(start ?? Enumerable.Empty<CardData.StatusEffectStacks>())
                .Any(s => s?.data != null && IsSummon(s.data)))
                e.Traits.Add("Summon");
            foreach (var t in traits ?? Enumerable.Empty<CardData.TraitStacks>())
                if (t?.data != null) e.Traits.Add(t.data.name);
            foreach (var s in scripts ?? Enumerable.Empty<CardScript>())
            {
                object Get(string field) => s == null ? null : AccessTools.Field(s.GetType(), field)?.GetValue(s);
                switch (s)
                {
                    case CardScriptAddAttackEffect _:
                    case CardScriptAddPassiveEffect _:
                        if (Get("effect") is StatusEffectData effect)
                        {
                            e.Applies.Add(Applied(effect) ?? effect.name);
                            if (IsSummon(effect)) e.Traits.Add("Summon");
                        }
                        break;
                    case CardScriptAddTrait _:
                        if (Get("trait") is TraitData trait) e.Traits.Add(trait.name);
                        break;
                }
            }
            e.Applies.Remove("null");
            e.Traits.Remove("null");
            return e;
        }

        /// <summary>A clan's starting deck: its CardData names, each once, in deck order.</summary>
        internal static IEnumerable<string> StartDeck(ClassData c) =>
            (c?.startingInventory?.deck ?? Enumerable.Empty<CardData>()).Where(d => d != null).Select(d => d.name).Distinct();

        // The Summon keyword (the user's call, 2026-11-24): the effect, or the one it applies, summons an ally. Adding a
        // card to the hand ("... In Hand") isn't one. tools/gen_data.py finds the same in the dump by name.
        private static bool IsSummon(StatusEffectData e)
        {
            bool Summons(StatusEffectData d) => (d is StatusEffectSummon || d is StatusEffectInstantSummon)
                                                && !d.name.EndsWith(" In Hand");
            return Summons(e) || AccessTools.Field(e.GetType(), "effectToApply")?.GetValue(e) is StatusEffectData target && Summons(target);
        }

        // What an "apply X" effect applies (any effect with an effectToApply), or null.
        private static string Applied(StatusEffectData e) =>
            (AccessTools.Field(e.GetType(), "effectToApply")?.GetValue(e) as StatusEffectData)?.name;
    }
}
