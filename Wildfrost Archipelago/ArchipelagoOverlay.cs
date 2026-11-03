using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace WildfrostArchipelago
{
    /// <summary>
    /// The full log: connection status and messages, and the main-thread pump for the client's queue.
    /// F7 (or ApUi's status pill) toggles it, F9 reconnects, F11 logs what the AP rules currently
    /// unlock, and Enter opens it with a line for chat, server "!" commands and local "/" commands. With the debug setting on, F8 sends
    /// a check by hand and F10 switches to a blank survey profile.
    /// </summary>
    internal class ArchipelagoOverlay : MonoBehaviour
    {
        // The full log starts closed: ApUi's toasts and status pill cover normal play, and the pill,
        // F7 or Enter (to chat) open it.
        private static bool logOpen;
        public static bool LogOpen => logOpen && !hiddenUntilMenu;
        public static bool HiddenUntilMenu => hiddenUntilMenu;
        public static bool Typing => typing;
        private static bool typing;

        public static void ToggleLog() => logOpen = !logOpen;

        // "Play without Archipelago" hides the overlay until the player is back on the main menu.
        private static bool hiddenUntilMenu, leftMenu;

        // Playing offline is put in front of the player with the game's own prompt (as for boons and
        // traps), saying the progress is only local for now (asked for by the user 2026-11-02): after
        // "Continue offline" in the connect popup, once past the main menu (a moment after it unloads, so
        // not on the loading screen), and when the connection goes mid-game: at once for /disconnect,
        // and for a lost connection once the client's quick retries have failed (ArchipelagoClient).
        private const float ContinueOfflineDelay = 1.5f, OfflineDelay = 0.3f;
        private const string ContinueOfflineText =
            "You're playing offline. Your progress is saved on this computer, and your checks are sent when you reconnect (F9).";
        private const string LostText =
            "Connection to Archipelago lost. Your progress is saved on this computer, and your checks are sent once the mod reconnects (it tries every minute; F9 to try now).";
        private const string DisconnectedText =
            "Disconnected from Archipelago. Your progress is saved on this computer, and your checks are sent when you reconnect (F9).";
        private static string noticeText;
        private static float noticeDelay;

        public static void ShowOfflineNotice() => QueueNotice(ContinueOfflineText, ContinueOfflineDelay);

        /// <summary>The connection went while playing (lost: it reconnects by itself). Nothing on the main menu.</summary>
        public static void NotifyOffline(bool lost)
        {
            if (!AtMainMenu) QueueNotice(lost ? LostText : DisconnectedText, OfflineDelay);
        }

        private static void QueueNotice(string text, float delay)
        {
            noticeText = text;
            noticeDelay = delay;
        }

        private static bool AtMainMenu => ApMode.AtMainMenu();

        private IEnumerator OfflineNotice(ArchipelagoClient client, string text, float delay)
        {
            yield return new WaitForSecondsRealtime(delay);
            if (!client.Connected && ApMode.Active && !AtMainMenu) yield return ApPatches.ShowPrompt(text);
        }

        public static void HideUntilMainMenu()
        {
            hiddenUntilMenu = true;
            leftMenu = false;
        }
        private GUIStyle style;
        private Texture2D background, divider;
        private GUIStyle titleStyle, keysStyle;
        private Vector2 scroll;
        private bool followLatest = true;
        private string lastLine;
        private float contentHeight;

        private const string ChatControl = "ArchipelagoChat";
        private bool chatOpen, focusChat, submitChat, closeChat;
        private int chatOpenedFrame;
        private string chatText = "";

        private void Update()
        {
            var client = ArchipelagoMod.Client;
            if (client == null) return;

            client.Drain();
            if (hiddenUntilMenu)
            {
                if (!AtMainMenu) leftMenu = true;
                else if (leftMenu) hiddenUntilMenu = false;
            }
            if (noticeText != null && !AtMainMenu)
            {
                StartCoroutine(OfflineNotice(client, noticeText, noticeDelay));
                noticeText = null;
            }
            ApMode.Tick();
            DeathLinkHandler.Tick();
            ApEffects.Tick();
            GameSpeed.Tick();

            // Typing goes to the chat line, not the hotkeys. (OnGUI flags these; the line is drawn
            // until the next frame so IMGUI's layout and repaint passes agree.)
            if (chatOpen)
            {
                if (submitChat) SubmitChat(client);
                if (submitChat || closeChat) CloseChat();
                submitChat = closeChat = false;
                return;
            }

            if (Input.GetKeyDown(KeyCode.F6)) GameSpeed.Cycle(client);
            if (Input.GetKeyDown(KeyCode.F7)) logOpen = !logOpen;
            if (Input.GetKeyDown(KeyCode.F9)) client.Connect();
            if (Input.GetKeyDown(KeyCode.F11)) client.Log(ApMode.Describe());
            if (ArchipelagoMod.DebugMode)
            {
                if (Input.GetKeyDown(KeyCode.F8)) client.SendNextMissingCheck("F8");
                if (Input.GetKeyDown(KeyCode.F10)) SwitchToSurveyProfile(client);
            }
            if (!hiddenUntilMenu && !ConnectPopup.IsOpen && (Input.GetKeyDown(KeyCode.Return) || Input.GetKeyDown(KeyCode.KeypadEnter)))
            {
                logOpen = true;
                chatOpen = typing = focusChat = true;
                chatOpenedFrame = Time.frameCount;
                chatText = "";
                GameInput.Block();
            }
        }

        private void CloseChat()
        {
            chatOpen = typing = false;
            GameInput.Unblock();
        }

        // "/" is ours (like the standard Archipelago client); anything else goes to the room, where
        // the server runs "!" commands.
        private void SubmitChat(ArchipelagoClient client)
        {
            string text = chatText.Trim();
            if (text.Length == 0) return;
            if (!text.StartsWith("/"))
            {
                client.Say(text);
                return;
            }
            string[] words = text.Split(new[] { ' ' }, System.StringSplitOptions.RemoveEmptyEntries);
            switch (words[0].ToLowerInvariant())
            {
                case "/connect":
                    var config = client.Config;
                    if (words.Length > 1) config.Server = words[1];
                    if (words.Length > 2) config.Slot = words[2];
                    if (words.Length > 3) config.Password = words[3];
                    config.Save(ArchipelagoMod.Instance);
                    client.Configure(config);
                    client.Connect();
                    break;
                case "/disconnect":
                    client.Disconnect();
                    client.Log("Disconnected");
                    NotifyOffline(lost: false);
                    break;
                case "/help":
                    client.Log("Local commands: /connect [server] [slot] [password], /disconnect, /help. " +
                               "Server commands start with ! (try !help); other text is chat.");
                    break;
                default:
                    client.Log($"Unknown command {words[0]} (try /help)");
                    break;
            }
        }

        private const string SurveyProfile = "ArchipelagoSurvey";

        // Survey only: watch vanilla unlocks happen on a blank profile without touching the real
        // one. save=false means the choice isn't written to data.sav, so the next game start is back
        // on the player's normal profile. This mirrors the dev console's "save profile <name>",
        // which also refuses to switch mid-campaign.
        private static void SwitchToSurveyProfile(ArchipelagoClient client)
        {
            if (!AtMainMenu)
            {
                client.Log("F10: profile can only be switched from the main menu");
                return;
            }
            if (ApMode.Profile != null)
            {
                client.Log("F10: an AP slot is logged in, so its profile is in use");
                return;
            }
            if (SaveSystem.Profile == SurveyProfile)
            {
                client.Log("F10: already on " + SurveyProfile + " (restart the game to return to your profile)");
                return;
            }

            string from = SaveSystem.Profile;
            string reloaded = ProfileSwitch.SetProfile(SurveyProfile, false, null);
            client.Log($"F10: switched profile {from} -> {SaveSystem.Profile}. Restart the game to return.");
            SurveyLog.Write($"profile switched {from} -> {SaveSystem.Profile}; reloaded {reloaded}");
            HookSurvey.ResetBaseline("profile switch");
        }

        // Key prompts: the key in bold white, its action in the caption colour.
        private static string Keys(params (string key, string action)[] keys) =>
            string.Join("    ", keys.Select(k => $"<b><color=#FFFFFF>{k.key}</color></b> {k.action}"));

        private void DrawChat()
        {
            var e = Event.current;
            if (e.type == EventType.KeyDown && Time.frameCount != chatOpenedFrame)
            {
                if (e.keyCode == KeyCode.Return || e.keyCode == KeyCode.KeypadEnter) submitChat = true;
                else if (e.keyCode == KeyCode.Escape) closeChat = true;
            }
            GUI.SetNextControlName(ChatControl);
            chatText = GUILayout.TextField(chatText ?? "", 200);
            if (focusChat)
            {
                GUI.FocusControl(ChatControl);
                focusChat = false;
            }
        }

        private void OnGUI()
        {
            var client = ArchipelagoMod.Client;
            if (!LogOpen || client == null) return;

            int fontSize = Mathf.Max(13, Mathf.RoundToInt(Screen.height / 80f));
            if (style == null || style.fontSize != fontSize)
            {
                // Rich text for the log's colours (LogText); a gap between entries.
                style = new GUIStyle(GUI.skin.label) { fontSize = fontSize, wordWrap = true, richText = true };
                style.margin = new RectOffset(0, 0, 0, Mathf.RoundToInt(fontSize * 0.6f));
                style.normal.textColor = Color.white;
                titleStyle = new GUIStyle(style) { fontStyle = FontStyle.Bold };
                keysStyle = new GUIStyle(style) { fontSize = Mathf.RoundToInt(fontSize * 0.85f), richText = true };
                keysStyle.normal.textColor = new Color(0.72f, 0.76f, 0.82f);
            }
            if (divider == null)
            {
                divider = new Texture2D(1, 1);
                divider.SetPixel(0, 0, new Color(1f, 1f, 1f, 0.35f));
                divider.Apply();
            }
            if (background == null)
            {
                background = new Texture2D(1, 1);
                background.SetPixel(0, 0, new Color32(0x1E, 0x25, 0x30, 0xCC));
                background.Apply();
            }

            // Below ApUi's status pill, down to the game's bottom bar, and wide enough to reach a third
            // of the way into the back row's first card (sized by the user against a battle screen,
            // 2026-10-31). Mostly opaque, for reading.
            var area = new Rect(10, Screen.height * 0.06f, Screen.width * 0.18f, Screen.height * (0.70f - 0.06f));
            GUI.DrawTexture(area, background);
            GUILayout.BeginArea(new Rect(area.x + 6, area.y + 4, area.width - 12, area.height - 8));
            // Header: status, then the keys as a muted caption, then a line above the messages.
            GUILayout.Label($"Archipelago: {client.Status}" + (ArchipelagoMod.DebugMode ? $"   profile: {SaveSystem.Profile}" : ""), titleStyle);
            var keys = new List<(string, string)> { ("F7", "close log"), ("F9", "reconnect"), ("H", "hints"), ("Enter", "chat") };
            // F6 only where it does something: the AP profile of a seed with game_speed_up.
            if (ApMode.Active && ApMode.SpeedUpAllowed) keys.Add(("F6", $"speed ({GameSpeed.Factor:0.#}x)"));
            GUILayout.Label(Keys(keys.ToArray()), keysStyle);
            // F11 (AP state) works but isn't advertised; the debug keys only show with debug on.
            if (ArchipelagoMod.DebugMode) GUILayout.Label("Debug   " + Keys(("F8", "send a check"), ("F10", "survey profile (main menu)")), keysStyle);
            GUILayout.Space(4);
            GUI.DrawTexture(GUILayoutUtility.GetRect(1, 1, GUILayout.ExpandWidth(true)), divider);
            GUILayout.Space(4);

            // The log scrolls (mouse wheel). It follows new lines unless scrolled up to read back.
            // (By reference: the line count stops changing once the log is full.)
            string newest = client.Lines.Count > 0 ? client.Lines[client.Lines.Count - 1] : null;
            if (!ReferenceEquals(newest, lastLine) && followLatest) scroll.y = float.MaxValue;
            lastLine = newest;
            scroll = GUILayout.BeginScrollView(scroll);
            foreach (string line in client.Lines)
            {
                GUILayout.Label(line, style);
            }
            bool repaint = Event.current.type == EventType.Repaint;
            if (repaint) contentHeight = GUILayoutUtility.GetLastRect().yMax;
            GUILayout.EndScrollView();
            if (repaint) followLatest = scroll.y + GUILayoutUtility.GetLastRect().height >= contentHeight - 20;
            if (chatOpen) DrawChat();
            GUILayout.EndArea();
        }
    }
}
