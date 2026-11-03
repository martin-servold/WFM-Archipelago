using System.Collections.Generic;
using System.Linq;
using System.Text;
using Newtonsoft.Json.Linq;

namespace WildfrostArchipelago
{
    /// <summary>
    /// The hint panel's Checks and Packs tabs (decided with the user 2026-11-02): which checks are
    /// still open and which of those are in logic, and what each pack holds, so a player knows which
    /// pack to !hint. Players don't know Universal Tracker exists, so the basics are in the game.
    /// "In logic" reads slot_data location_rules (rules.rule_json in the apworld) against the items
    /// received, so the logic itself stays in the apworld. Main thread only.
    /// </summary>
    internal static class ApTracker
    {
        // A page of checks, short enough that the panel and the toasts below it fit a 1080p screen.
        private const int ChecksPerPage = 14;

        /// <summary>Whether a location rule is met by the items received.</summary>
        public static bool Evaluate(JToken rule)
        {
            switch ((string)rule[0])
            {
                case "and": return rule[1].All(Evaluate);
                case "or": return rule[1].Any(Evaluate);
                case "has": return ApMode.Has((string)rule[1], (int)rule[2]);
                case "all": return rule[1].All(k => ApMode.Has((string)k));
                case "any": return rule[1].Count(k => ApMode.Has((string)k)) >= (int)rule[2];
                case "packs": return ApMode.PackCount((string)rule[1], (string)rule[2]) >= (int)rule[3];
                default: return false; // a newer apworld's rule this client can't read
            }
        }

        public static void Checks(StringBuilder text, ArchipelagoClient client, int page)
        {
            var names = client.LocationNames;
            var rules = client.LocationRules;
            if (names == null || rules == null)
            {
                text.Append("\n<size=80%>Connect once to load this seed's checks.</size>\n");
                return;
            }
            var keys = client.LocationKeys.ToList();
            var open = keys.Where(k => client.CheckSent(k) != true).ToList();
            var inLogic = open.Where(k => !rules.TryGetValue(k, out JToken rule) || Evaluate(rule)).ToList();
            text.Append($"\n<b>{keys.Count - open.Count}/{keys.Count} checks sent</b>\n");
            int pages = System.Math.Max(1, (inLogic.Count + ChecksPerPage - 1) / ChecksPerPage);
            page = (page % pages + pages) % pages;
            text.Append($"\n<b>In logic now ({inLogic.Count})</b>");
            if (pages > 1) text.Append($"  <size=70%>(page {page + 1}/{pages}, PgUp/PgDn for others)</size>");
            text.Append('\n');
            if (inLogic.Count == 0) text.Append("<size=80%>Nothing until more items arrive.</size>\n");
            foreach (string key in inLogic.Skip(page * ChecksPerPage).Take(ChecksPerPage))
                text.Append(names.TryGetValue(key, out string name) ? name : key).Append('\n');
            text.Append($"\n<size=80%>Not in logic yet: {open.Count - inLogic.Count}.</size>\n");
        }

        // Pack groups, as the apworld names them: General, then the clans, by kind.
        private static readonly string[] Clans = { "General", "Basic", "Magic", "Clunk" };
        private static readonly string[] Kinds = { "Companion", "Item", "Charm" };
        public static int PackGroupCount => Clans.Length * Kinds.Length;

        public static void Packs(StringBuilder text, ArchipelagoClient client, int group)
        {
            var itemNames = client.ItemNames;
            if (itemNames == null || ApMode.Packs.Count == 0)
            {
                text.Append("\n<size=80%>Connect once to load this seed's packs.</size>\n");
                return;
            }
            string clan = Clans[group / Kinds.Length], kind = Kinds[group % Kinds.Length];
            // Newer seeds have charms as items one by one ("charm:<clan>:<card>"), so their group lists those.
            var charms = kind == "Charm" ? itemNames.Keys.Where(k => k.StartsWith($"charm:{clan}:")).OrderBy(k => itemNames[k]).ToList() : null;
            if (charms != null && charms.Count > 0)
            {
                string label = clan == "General" ? "General" : itemNames.Keys.Where(k => k.StartsWith($"pack:{clan}:"))
                    .Select(k => itemNames[k]).Select(n => n.Substring(0, n.IndexOf(' '))).FirstOrDefault() ?? clan;
                text.Append($"\n<b>{label} Charms</b>  <size=70%>({group + 1}/{PackGroupCount}, PgUp/PgDn for others)</size>\n");
                // Up to 42 in a group, so they run on as one wrapped list; received ones dimmed.
                text.Append(string.Join(", ", charms.Select(c => ApMode.Has(c) ? $"<alpha=#80>{itemNames[c]}<alpha=#FF>" : itemNames[c])));
                text.Append("\n<size=70%>Dimmed: received.</size>\n");
                return;
            }
            string prefix = $"pack:{clan}:{kind}:";
            var groupPacks = ApMode.Packs.Keys.Where(k => k.StartsWith(prefix))
                .OrderBy(k => int.TryParse(k.Substring(prefix.Length), out int n) ? n : 0).ToList();
            string title = groupPacks.Count > 0 && itemNames.TryGetValue(groupPacks[0], out string first)
                ? first.Substring(0, first.LastIndexOf(' ')) + "s" : prefix;
            text.Append($"\n<b>{title}</b>  <size=70%>({group + 1}/{PackGroupCount}, PgUp/PgDn for others)</size>\n");
            foreach (string pack in groupPacks)
            {
                string name = itemNames.TryGetValue(pack, out string n) ? n : pack;
                string cards = string.Join(", ", ApMode.Packs[pack].Select(ApMode.CardTitle));
                string line = $"{name.Substring(name.LastIndexOf(' ') + 1)}: {cards}";
                // Received packs are dimmed: what's left to find stands out.
                text.Append(ApMode.Has(pack) ? $"<alpha=#80>{line}  <size=70%>(received)</size><alpha=#FF>" : line).Append('\n');
            }
        }
    }
}
