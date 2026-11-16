using System.Collections.Generic;
using System.Linq;
using Deadpan.Enums.Engine.Components.Modding;
using HarmonyLib;

namespace WildfrostArchipelago
{
    /// <summary>
    /// Other mods that add content or patch what this mod patches (decided with the user 2026-10-31:
    /// warn, never lock). Runs on Play with the AP profile loaded: mods can be switched on and off on
    /// the Mods screen until then (the user's call: not on connect). Everything goes to the log; a
    /// toast only says to look there, and only when something was found. Repeats are skipped while
    /// nothing has changed since the last check.
    /// It also checks the seed against the game (PLAN.md §10): the mods its extension files came from, and
    /// the battles, challenges, cards, charms and pets it names. Anything missing gets its own toast, since
    /// those checks can't be done (wrong or missing mod, or a mod version that changed its content).
    /// </summary>
    internal static class CompatCheck
    {
        private static string lastResult;

        // Vanilla tribes. Their ClassData names; Tutorial is the forced first run's Snowdweller deck.
        private static readonly HashSet<string> KnownTribes = new HashSet<string> { "Basic", "Magic", "Clunk", "Tutorial" };
        private static readonly HashSet<string> CardPoolTypes = new HashSet<string> { "Items", "Units", "Charms" };

        /// <summary>Main thread, at the main menu (content is loaded by then).</summary>
        public static void Run(ArchipelagoClient client)
        {
            var findings = new List<string>();
            var missing = SeedContentMissing(client);

            var others = Bootstrap.Mods
                .Where(m => m != null && m.HasLoaded && m.GUID != ArchipelagoMod.Instance?.GUID)
                .Select(m => $"{m.Title} ({m.GUID})")
                .ToList();

            var knownCards = new HashSet<string>((client.CardKinds ?? new Dictionary<string, string>()).Keys.Select(k => k.Substring("card:".Length)));
            var tribes = AddressableLoader.GetGroup<ClassData>("ClassData").Where(c => c != null).ToList();
            var unknownCards = tribes
                .SelectMany(c => c.rewardPools ?? new RewardPool[0])
                .Where(p => p != null && CardPoolTypes.Contains(p.type))
                .SelectMany(p => p.list ?? new List<DataFile>())
                .Where(f => f != null && !knownCards.Contains(f.name))
                .Select(f => f.name)
                .Distinct()
                .OrderBy(n => n)
                .ToList();
            if (unknownCards.Count > 0)
                findings.Add($"{unknownCards.Count} cards in the reward pools aren't in this seed, so runs offer them from the start: {string.Join(", ", unknownCards)}");

            var unknownTribes = tribes.Select(c => c.name).Where(n => !KnownTribes.Contains(n)).Distinct().ToList();
            if (unknownTribes.Count > 0)
                findings.Add($"Tribes this seed doesn't know (playable, but their runs send no checks and don't count toward the goal): {string.Join(", ", unknownTribes)}");

            // Pets with an unlock that isn't one of the seed's pet items never unlock under AP.
            var knownPets = new HashSet<string>(client.ItemKeyValues.Where(k => k.StartsWith("pet:")).Select(k => k.Substring("pet:".Length)));
            var lockedPets = MetaprogressionSystem.GetPetDict()
                .Where(p => p.Value != null && !knownPets.Contains(p.Key))
                .Select(p => p.Key)
                .ToList();
            if (lockedPets.Count > 0)
                findings.Add($"Pets this seed doesn't know, which stay locked: {string.Join(", ", lockedPets)}");

            string ours = ArchipelagoMod.Instance?.HarmonyId;
            if (ours != null)
            {
                var shared = Harmony.GetAllPatchedMethods()
                    .Select(m => new { Method = m, Owners = Harmony.GetPatchInfo(m)?.Owners ?? new List<string>().AsReadOnly() })
                    .Where(p => p.Owners.Contains(ours) && p.Owners.Any(o => o != ours))
                    .Select(p => $"{p.Method.DeclaringType?.Name}.{p.Method.Name} (also {string.Join(", ", p.Owners.Where(o => o != ours))})")
                    .ToList();
                if (shared.Count > 0)
                    findings.Add($"Game methods another mod patches too (may conflict): {string.Join("; ", shared)}");
            }

            string modLine = others.Count == 0 ? "No other mods loaded" : "Other mods loaded: " + string.Join(", ", others);
            string result = modLine + "\n" + string.Join("\n", missing) + "\n" + string.Join("\n", findings);
            if (result == lastResult) return;
            lastResult = result;
            if (others.Count == 0) client.LogDebug(modLine);
            else client.Log(modLine);
            foreach (string problem in missing) client.Log("Seed content missing: " + problem);
            foreach (string finding in findings) client.Log("Compatibility: " + finding);
            if (missing.Count > 0)
                ApUi.ShowToast("Mods", "This seed needs content the game doesn't have", "Details in the Archipelago log", ApUi.SentColor);
            else if (findings.Count > 0)
                ApUi.ShowToast("Other mods", "Content this seed doesn't know about", "Details in the Archipelago log", ApUi.SentColor);
        }

        /// <summary>
        /// What the seed names that the game lacks: mods its extensions came from that aren't loaded, then
        /// battles and challenges among its locations, cards and charms, and pet items. Mods have no version
        /// in the game, so a changed mod shows up here as the content it no longer has.
        /// </summary>
        private static List<string> SeedContentMissing(ArchipelagoClient client)
        {
            var problems = new List<string>();
            var loaded = new HashSet<string>(Bootstrap.Mods.Where(m => m != null && m.HasLoaded).Select(m => m.GUID));
            foreach (var ext in client.SeedExtensions.Where(e => !loaded.Contains(e.Guid)))
                problems.Add($"the seed uses the {ext.Mod} extension (version {ext.Version}), but its mod ({ext.Guid}) isn't loaded: turn it on in the Mods screen, or its checks can't be done and its cards never come up");

            var battles = Names<BattleData>("BattleData");
            var challenges = Names<ChallengeData>("ChallengeData");
            var missingLocations = new List<string>();
            foreach (string key in client.LocationKeys)
            {
                string[] parts = key.Replace("#2", "").Split(':');
                bool known = parts[0] == "battle" && parts.Length == 4 ? battles.Contains(parts[2])
                    : parts[0] == "challenge" && parts.Length == 2 ? challenges.Contains(parts[1])
                    : true; // "challenge:ap:<slug>" are this mod's own New Challenges
                if (!known) missingLocations.Add(key);
            }
            if (missingLocations.Count > 0)
                problems.Add($"{missingLocations.Count} checks name battles or challenges the game doesn't have, so they can't be done: {string.Join(", ", missingLocations)}");

            var cards = Names<CardData>("CardData");
            var charms = Names<CardUpgradeData>("CardUpgradeData");
            var missingCards = (client.CardKinds ?? new Dictionary<string, string>())
                .Where(c => !(c.Value == "Charm" ? charms : cards).Contains(c.Key.Substring("card:".Length)))
                .Select(c => c.Key.Substring("card:".Length))
                .OrderBy(n => n)
                .ToList();
            if (missingCards.Count > 0)
                problems.Add($"{missingCards.Count} cards and charms in the seed aren't in the game, so their items give nothing: {string.Join(", ", missingCards)}");

            var pets = new HashSet<string>(MetaprogressionSystem.GetPetDict().Keys);
            var missingPets = client.ItemKeyValues.Where(k => k.StartsWith("pet:") && !pets.Contains(k.Substring("pet:".Length)))
                .Select(k => k.Substring("pet:".Length)).Distinct().OrderBy(n => n).ToList();
            if (missingPets.Count > 0)
                problems.Add($"pets in the seed that aren't in the game, so their items give nothing: {string.Join(", ", missingPets)}");
            return problems;
        }

        private static HashSet<string> Names<T>(string group) where T : DataFile =>
            new HashSet<string>(AddressableLoader.GetGroup<T>(group).Where(d => d != null).Select(d => d.name));
    }
}
