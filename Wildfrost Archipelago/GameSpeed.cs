using HarmonyLib;
using UnityEngine;

namespace WildfrostArchipelago
{
    /// <summary>
    /// A local speed-up for the game's animations (playtest feedback 2026-11-01; a client setting in
    /// config.cfg). F6 steps through the speeds. Only on the AP profile, like every other patch, and only
    /// when the seed's game_speed_up option allows it (off by default; the user's call, 2026-11-02).
    /// The game changes Time.timeScale itself: everything that goes through Events.InvokeTimeScaleChange
    /// (the miniboss death slow motion, the gamespeed console command) lands in TimeScaleSystem, which
    /// is scaled here, and the pause menu sets 0 on open and a flat 1 on close, which is put back.
    /// </summary>
    internal static class GameSpeed
    {
        // Percent, so config.cfg never holds a decimal (whose separator depends on the locale).
        // Capped at 2x: 3x played fine but wasn't needed (the user's call, 2026-11-02).
        private static readonly int[] Steps = { 100, 150, 200 };
        private static readonly int MaxPercent = Steps[Steps.Length - 1];

        private static float applied = 1f;

        /// <summary>The speed in effect. A config.cfg from before the setting reads as 0, which counts as normal.</summary>
        public static float Factor
        {
            get
            {
                var mod = ArchipelagoMod.Instance;
                if (mod == null || !ApMode.Active || !ApMode.SpeedUpAllowed || mod.speed <= 100) return 1f;
                return Mathf.Min(mod.speed, MaxPercent) / 100f;
            }
        }

        /// <summary>Main thread, every frame: follows setting and profile changes.</summary>
        public static void Tick()
        {
            float factor = Factor;
            if (Mathf.Approximately(factor, applied)) return;
            // Only from the plain running speed: leave a pause (0) or a slow motion running, and
            // they come back through the patches below.
            if (Mathf.Approximately(Time.timeScale, applied)) Time.timeScale = factor;
            applied = factor;
        }

        /// <summary>Back to normal speed, when the mod unloads.</summary>
        public static void Reset()
        {
            if (Mathf.Approximately(Time.timeScale, applied)) Time.timeScale = 1f;
            applied = 1f;
        }

        /// <summary>F6: the next speed step, saved to config.cfg.</summary>
        public static void Cycle(ArchipelagoClient client)
        {
            var mod = ArchipelagoMod.Instance;
            if (mod == null) return;
            if (!ApMode.Active)
            {
                client.Log("Game speed only applies on the Archipelago profile.");
                return;
            }
            if (!ApMode.SpeedUpAllowed)
            {
                client.Log("Game speed is off for this seed (the Game Speed Up option).");
                return;
            }
            int next = Steps[0];
            foreach (int step in Steps)
            {
                if (step > mod.speed)
                {
                    next = step;
                    break;
                }
            }
            mod.speed = next;
            ConnectionConfig.WriteConfigFile(mod);
            ApUi.ShowToast("Game speed", $"{next / 100f:0.#}x", "F6 to change", ApUi.ReceivedColor);
        }

        [HarmonyPatch(typeof(TimeScaleSystem), "TimeScaleSet")]
        private static class ScaleChanges
        {
            private static void Prefix(ref float value) => value *= Factor;
        }

        [HarmonyPatch(typeof(PauseMenu), "OnDisable")]
        private static class AfterPause
        {
            private static void Postfix()
            {
                if (Mathf.Approximately(Time.timeScale, 1f)) Time.timeScale = Factor;
            }
        }
    }
}
