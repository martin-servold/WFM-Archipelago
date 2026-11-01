using System;
using System.Collections;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEngine;
using UnityEngine.Localization;

namespace WildfrostArchipelago
{
    /// <summary>
    /// Milestone 2 hook survey output. Lines go to Player.log (prefixed) and to survey.log in the
    /// mod folder, which is easier to pull out of the Proton prefix and survives game restarts.
    /// Main thread only: every caller is a game event or Harmony patch.
    /// </summary>
    internal static class SurveyLog
    {
        private static string path;

        public static void Open(string modDirectory)
        {
            path = Path.Combine(modDirectory, "survey.log");
            Write($"===== session {DateTime.Now:yyyy-MM-dd HH:mm:ss} =====");
        }

        public static void Close()
        {
            path = null;
        }

        // Off unless the debug setting is on: HookSurvey's patches stay applied and call this on
        // every unlock query.
        public static void Write(string message)
        {
            if (!ArchipelagoMod.DebugMode) return;
            Debug.Log(ArchipelagoMod.LogPrefix + "survey: " + message);
            if (path == null) return;
            try
            {
                File.AppendAllText(path, $"[{DateTime.Now:HH:mm:ss}] {message}\n");
            }
            catch (Exception e)
            {
                Debug.LogWarning(ArchipelagoMod.LogPrefix + "survey.log write failed: " + e.Message);
                path = null;
            }
        }

        public static string Name(object o)
        {
            switch (o)
            {
                case null: return "null";
                case UnityEngine.Object u: return u ? u.name : "destroyed";
                default: return o.ToString();
            }
        }

        public static string Loc(LocalizedString s)
        {
            if (s == null || s.IsEmpty) return "";
            try { return s.GetLocalizedString(); }
            catch { return "?"; }
        }

        public static string Card(Entity e)
        {
            if (e == null || e.data == null) return Name(e);
            return $"{e.data.name} [{Name(e.data.cardType)}]";
        }

        /// <summary>Short, reflection-based description, used to log and diff save values whose types we haven't mapped yet.</summary>
        public static string Describe(object o, int depth = 0)
        {
            if (o == null) return "null";
            if (o is string s) return s;
            if (o is UnityEngine.Object u) return Name(u);
            Type t = o.GetType();
            if (t.IsPrimitive || t.IsEnum) return o.ToString();
            if (o is IDictionary dict)
            {
                return "{" + string.Join(", ", dict.Keys.Cast<object>().OrderBy(k => k.ToString())
                    .Select(k => $"{k}={Describe(dict[k], depth + 1)}")) + "}";
            }
            if (o is IEnumerable list)
            {
                return "[" + string.Join(", ", list.Cast<object>().Select(x => Describe(x, depth + 1))) + "]";
            }
            if (depth >= 2) return t.Name;
            var fields = t.GetFields(BindingFlags.Public | BindingFlags.Instance);
            return t.Name + "(" + string.Join(", ", fields.Select(f => $"{f.Name}={Describe(f.GetValue(o), depth + 1)}")) + ")";
        }
    }
}
