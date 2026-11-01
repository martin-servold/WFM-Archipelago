using System.Text.RegularExpressions;
using Archipelago.MultiClient.Net.Enums;

namespace WildfrostArchipelago
{
    /// <summary>
    /// The overlay log's rich text (asked for by the user 2026-10-31, to make it scannable): items
    /// bold and coloured by importance, the rest dimmed. Player.log gets the same lines without tags.
    /// </summary>
    internal static class LogText
    {
        public const string Dim = "#8F9AA6";
        public const string Detail = "#C3CAD3";
        public const string Check = "#E8A35A";
        // Archipelago's usual colours: progression plum, useful blue, trap red, filler plain.
        private const string Progression = "#C9A6FF";
        private const string Useful = "#7FB2FF";
        private const string Trap = "#FF8A80";
        private const string Filler = "#F2C96B";

        public static string Color(string hex, string text) => $"<color={hex}>{text}</color>";

        public static string Item(string name, ItemFlags flags) => $"<b>{Color(ColorOf(flags), name)}</b>";

        private static string ColorOf(ItemFlags flags) =>
            (flags & ItemFlags.Advancement) != 0 ? Progression
            : (flags & ItemFlags.Trap) != 0 ? Trap
            : (flags & ItemFlags.NeverExclude) != 0 ? Useful
            : Filler;

        public static string Strip(string text) => text == null ? null : Regex.Replace(text, "</?(color|b|i|size)[^>]*>", "");
    }
}
