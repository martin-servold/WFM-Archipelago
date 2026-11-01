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
            string result = modLine + "\n" + string.Join("\n", findings);
            if (result == lastResult) return;
            lastResult = result;
            if (others.Count == 0) client.LogDebug(modLine);
            else client.Log(modLine);
            if (findings.Count == 0) return;
            foreach (string finding in findings) client.Log("Compatibility: " + finding);
            ApUi.ShowToast("Other mods", "Content this seed doesn't know about", "Details in the Archipelago log", ApUi.SentColor);
        }
    }
}
