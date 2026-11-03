using HarmonyLib;
using UnityEngine;

namespace WildfrostArchipelago
{
    /// <summary>
    /// Pressing Play opens this popup instead: server, slot and password (saved to config.cfg),
    /// Connect, or Play without Archipelago. Connecting switches to the seed's profile on the main
    /// menu as usual (ApMode), then carries on with the same Play. It opens on every Play, even when
    /// connected, with Continue as the default (decided by the user 2026-11-02): in a playtest the
    /// lobby re-seeded twice, and the game kept connecting to the old room by itself with no way back
    /// to these settings.
    /// </summary>
    internal class ConnectPopup : MonoBehaviour
    {
        public static bool IsOpen => instance != null && instance.open;

        private static ConnectPopup instance;
        // Set while the popup re-runs Play, so the gate lets it through.
        private static bool passThrough;

        private bool open, connecting;
        private int loginsAtConnect;
        private MainMenu menu;
        private string server = "", slot = "", password = "";
        private GUIStyle label, field, button;

        private void Awake() => instance = this;

        private void OnDestroy()
        {
            if (open) GameInput.Unblock();
            if (instance == this) instance = null;
        }

        private void Show(MainMenu playButton)
        {
            menu = playButton;
            var config = ArchipelagoMod.Client.Config;
            server = config.Server ?? "";
            slot = config.Slot ?? "";
            password = config.Password ?? "";
            connecting = false;
            open = true;
            GameInput.Block();
        }

        private void Close()
        {
            open = connecting = false;
            GameInput.Unblock();
        }

        private void Update()
        {
            if (!open) return;
            // Logged in and moved to the seed's profile: carry on into the game.
            if (connecting && ApMode.Active && ApMode.Logins > loginsAtConnect)
            {
                Close();
                Play();
            }
        }

        private void Play()
        {
            if (menu == null) return;
            passThrough = true;
            try
            {
                menu.Play();
            }
            finally
            {
                passThrough = false;
            }
        }

        private void Connect()
        {
            var client = ArchipelagoMod.Client;
            var config = client.Config;
            config.Server = server.Trim();
            config.Slot = slot.Trim();
            config.Password = password;
            config.Save(ArchipelagoMod.Instance);
            client.Configure(config);
            loginsAtConnect = ApMode.Logins;
            client.Connect();
            connecting = true;
        }

        private void PlayWithout()
        {
            ArchipelagoMod.Client.Disconnect();
            // On the AP profile: back to the player's own, which the popup never had to do while it
            // only opened with no slot loaded.
            if (ApMode.Active) ApMode.Exit();
            ApMode.StayOffline();
            ArchipelagoOverlay.HideUntilMainMenu();
            Close();
            Play();
        }

        private void Continue()
        {
            Close();
            Play();
        }

        // Whether the fields still say what the current connection uses.
        private bool Unchanged(ArchipelagoClient client)
        {
            var config = client.Config;
            return server.Trim() == (config.Server ?? "") && slot.Trim() == (config.Slot ?? "") && password == (config.Password ?? "");
        }

        private void OnGUI()
        {
            if (!open || ArchipelagoMod.Client == null) return;
            var client = ArchipelagoMod.Client;
            // Continue (on the slot that's loaded, with the same settings) is the default: Enter. While
            // disconnected, Connect is the default and Continue offline sits beside it, so a run isn't
            // played offline by accident (the user's call, 2026-11-02).
            bool canContinue = ApMode.Active && Unchanged(client) && !connecting && ApMode.BlockedProfile == null;
            bool offline = canContinue && !client.Connected;
            var e = Event.current;
            if (e.type == EventType.KeyDown && (e.keyCode == KeyCode.Return || e.keyCode == KeyCode.KeypadEnter))
            {
                e.Use();
                if (canContinue && !offline) Continue();
                else if (!connecting || !client.Connected) Connect();
                return;
            }
            if (label == null)
            {
                label = new GUIStyle(GUI.skin.label) { fontSize = 18, wordWrap = true };
                field = new GUIStyle(GUI.skin.textField) { fontSize = 18 };
                button = new GUIStyle(GUI.skin.button) { fontSize = 18 };
            }

            const float width = 640, height = 400;
            GUILayout.BeginArea(new Rect((Screen.width - width) / 2, (Screen.height - height) / 2, width, height), GUI.skin.box);
            GUILayout.Label("Connect to Archipelago", label);
            GUILayout.Space(8);
            GUILayout.Label("Server (host:port)", label);
            server = GUILayout.TextField(server, field);
            GUILayout.Label("Slot name", label);
            slot = GUILayout.TextField(slot, field);
            GUILayout.Label("Password (if the room has one)", label);
            password = GUILayout.PasswordField(password, '*', field);
            GUILayout.Space(8);

            string status = ApMode.BlockedProfile != null
                ? "That room is another seed. Connect again from the main menu to play it."
                : connecting && client.Connected && !ApMode.Active
                ? "Connected, loading this seed's profile..."
                : offline
                ? "Offline. Playing on keeps your progress on this computer: checks are sent and items arrive when you reconnect."
                : ApMode.Active && Unchanged(client)
                ? $"{client.Status}. Enter or Continue to play; change the settings and Connect for another room."
                : client.Status;
            GUILayout.Label(status, label);

            GUILayout.FlexibleSpace();
            GUILayout.BeginHorizontal();
            if (offline)
            {
                if (GUILayout.Button("Connect", button)) Connect();
                if (GUILayout.Button("Continue offline", button))
                {
                    ArchipelagoOverlay.ShowOfflineNotice();
                    Continue();
                }
            }
            else if (canContinue)
            {
                if (GUILayout.Button("Continue", button)) Continue();
            }
            else
            {
                GUI.enabled = !connecting || !client.Connected;
                if (GUILayout.Button("Connect", button)) Connect();
                GUI.enabled = true;
            }
            if (GUILayout.Button("Play without Archipelago", button)) PlayWithout();
            if (GUILayout.Button("Cancel", button)) Close();
            GUILayout.EndHorizontal();
            GUILayout.EndArea();
        }

        [HarmonyPatch(typeof(MainMenu), nameof(MainMenu.Play))]
        private static class PlayGate
        {
            private static bool Prefix(MainMenu __instance)
            {
                if (passThrough || instance == null || ArchipelagoMod.Client == null)
                {
                    // Mods can be switched on and off on the Mods screen, so content is checked as a run starts.
                    if (ApMode.Active) CompatCheck.Run(ArchipelagoMod.Client);
                    return true;
                }
                if (!instance.open) instance.Show(__instance);
                return false;
            }
        }
    }

    /// <summary>
    /// Keeps the game from reacting to keys typed into our text fields. The game's InputSystem is a
    /// single on/off flag, so it is only turned back on if it was on before.
    /// </summary>
    internal static class GameInput
    {
        private static int blocks;
        private static bool wasEnabled;

        public static void Block()
        {
            if (blocks++ > 0) return;
            wasEnabled = Traverse.Create(typeof(InputSystem)).Field("enabled").GetValue<bool>();
            InputSystem.Disable();
        }

        public static void Unblock()
        {
            if (blocks == 0 || --blocks > 0) return;
            if (wasEnabled) InputSystem.Enable();
        }
    }
}
