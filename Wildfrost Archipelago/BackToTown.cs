using System;
using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using UnityEngine;
using UnityEngine.UI;

namespace WildfrostArchipelago
{
    /// <summary>
    /// A "Back To Town" line on the pause menu during an AP run (decided by the user 2026-11-05): the
    /// same as Back To Menu, run saved and all, but it lands in town. Vanilla's Back To Menu is
    /// Sequences.EndCampaign("MainMenu"), and the end screen already ends into "Town" the same way.
    /// The button is a copy of Back To Menu, shown under it, and hidden outside a run (the scenes
    /// where vanilla turns Quick Restart off) and off AP.
    /// </summary>
    internal static class BackToTown
    {
        private const string Name = "ApBackToTown";
        // PauseMenu.OnEnable's list: no run to leave in these.
        private static readonly HashSet<string> NotInRun = new HashSet<string> { "MainMenu", "CharacterSelect", "ContinueRun", "Town", "Cards" };

        private static readonly AccessTools.FieldRef<PauseMenu, ButtonAnimator> BackToMenuButton =
            AccessTools.FieldRefAccess<PauseMenu, ButtonAnimator>("backToMenuButton");
        private static readonly AccessTools.FieldRef<Menu, bool> MenuActive = AccessTools.FieldRefAccess<Menu, bool>("active");

        [HarmonyPatch(typeof(PauseMenu), "OnEnable")]
        private static class Show
        {
            private static void Postfix(PauseMenu __instance)
            {
                try
                {
                    var back = BackToMenuButton(__instance);
                    if (back == null) return;
                    var line = back.transform.parent;
                    var existing = line.parent.Find(Name);
                    bool shown = ApMode.Active && !NotInRun.Contains(SceneManager.GetActive().name);
                    if (existing == null && !shown) return;
                    (existing != null ? existing.gameObject : Create(__instance, line)).SetActive(shown);
                }
                catch (Exception e)
                {
                    ArchipelagoMod.Client?.LogDebug("Back To Town button: " + e);
                }
            }
        }

        // Each menu line is a wrapper ("SaveQuit", with the ButtonAnimator inside) in the pause menu's
        // VerticalLayoutGroup, so copying the wrapper lets the layout make room (copying the button
        // alone put both in one slot, 2026-11-05).
        private static GameObject Create(PauseMenu menu, Transform line)
        {
            var copy = UnityEngine.Object.Instantiate(line.gameObject, line.parent);
            copy.name = Name;
            copy.transform.SetSiblingIndex(line.GetSiblingIndex() + 1);
            // The label is localized; without this it would switch back to "Back To Menu".
            foreach (var c in copy.GetComponentsInChildren<Component>(true).Where(c => c != null && c.GetType().Name.Contains("Locali")).ToList())
                UnityEngine.Object.DestroyImmediate(c);
            var animator = copy.GetComponentInChildren<ButtonAnimator>(true);
            if (animator?.text != null) animator.text.text = "Back To Town";

            // Rebuild the click: Back To Menu's own handler becomes ours, anything else it calls stays.
            var click = copy.GetComponentInChildren<Button>(true);
            if (click != null)
            {
                var old = click.onClick;
                click.onClick = new Button.ButtonClickedEvent();
                var calls = new List<string>();
                for (int i = 0; i < old.GetPersistentEventCount(); i++)
                {
                    var target = old.GetPersistentTarget(i);
                    string method = old.GetPersistentMethodName(i);
                    calls.Add($"{target?.GetType().Name}.{method}");
                    if (method == nameof(PauseMenu.BackToMainMenu)) click.onClick.AddListener(() => Go(menu));
                    else if (target != null)
                    {
                        var info = AccessTools.Method(target.GetType(), method, Type.EmptyTypes);
                        if (info != null) click.onClick.AddListener(() => info.Invoke(target, null));
                    }
                }
                if (calls.Count == 0) click.onClick.AddListener(() => Go(menu));
                ArchipelagoMod.Client?.LogDebug("Back To Town button made from: " + (calls.Count > 0 ? string.Join(", ", calls) : "no persistent calls"));
            }

            return copy;
        }

        // PauseMenu.BackToMainMenu with "Town". AP runs always save (GameMode.doSave), so the run is kept.
        private static void Go(PauseMenu menu)
        {
            if (!MenuActive(menu)) return;
            new Routine(Sequences.EndCampaign("Town"));
            MenuActive(menu) = false;
            Events.InvokeBackToMainMenu();
        }
    }
}
