using System.Collections.Generic;
using System.Linq;
using System.Text;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace WildfrostArchipelago
{
    /// <summary>
    /// The player-facing UI (decided with the user 2026-10-31): toasts at the top right for items
    /// received and checks sent, a status pill at the top left (connection and unread log lines;
    /// clicking it opens the full log, ArchipelagoOverlay), and a panel on H with tabs for hints,
    /// checks and packs (ApTracker; 2026-11-02). Built in uGUI with the game's own TextMeshPro font.
    /// Main thread only.
    /// </summary>
    internal class ApUi : MonoBehaviour
    {
        public static readonly Color ReceivedColor = new Color32(0x2F, 0x8F, 0x83, 0xFF);
        public static readonly Color SentColor = new Color32(0xD9, 0x82, 0x2B, 0xFF);
        private static readonly Color PanelColor = new Color32(0xF4, 0xE3, 0xC1, 0xF2);
        private static readonly Color TextColor = new Color32(0x5A, 0x3A, 0x22, 0xFF);
        private static readonly Color PillColor = new Color32(0x2B, 0x34, 0x42, 0xE0);

        private const float ToastSeconds = 7f, FadeIn = 0.25f, FadeOut = 0.6f;
        // The game's own buttons (pause, deck, the eye) run down the right edge; ours stay left of
        // them. In the canvas's 1920x1080 reference units.
        private const float RightClear = 110f, TopMargin = 24f;
        private const int MaxToasts = 4;
        private const string SeenKey = "apToastSeen";
        private const string HintsSeenKey = "apHintsSeen";
        private const float PanelRefreshSeconds = 1f;
        private static readonly string[] Tabs = { "Hints", "Checks", "Packs" };
        private static readonly Color HintColor = new Color32(0x8A, 0x5C, 0xC2, 0xFF);

        private static ApUi instance;
        // Received items wait for the AP profile, whose save says which were already shown (the
        // server resends every item on each connect).
        private static readonly List<KeyValuePair<int, KeyValuePair<string, string>>> pendingReceived =
            new List<KeyValuePair<int, KeyValuePair<string, string>>>();

        private Canvas canvas;
        private RectTransform toastColumn;
        private readonly List<KeyValuePair<CanvasGroup, float>> toasts = new List<KeyValuePair<CanvasGroup, float>>();
        private GameObject pill, hintPanel, rerollButton;
        private Image pillDot;
        private TextMeshProUGUI pillText, hintText, rerollText;
        private TMP_FontAsset font;
        private Sprite rounded;
        private int linesSeen;
        private int tab, packGroup, checkPage;
        private float panelRefreshAt;
        private IReadOnlyList<ArchipelagoClient.HintRow> hintsChecked;

        /// <summary>
        /// Whether an item was already shown in an earlier session. The server resends every item on
        /// connect, and those log lines shouldn't count as new on the pill.
        /// </summary>
        public static bool AlreadyShown(int index) => ApMode.Active && index <= SaveSystem.LoadProgressData(SeenKey, 0);

        public static void QueueReceived(int index, string item, string body) =>
            pendingReceived.Add(new KeyValuePair<int, KeyValuePair<string, string>>(index, new KeyValuePair<string, string>(item, body)));

        /// <summary>Leaving one seed for another: its received toasts not shown yet are dropped.</summary>
        public static void ForgetSeed() => pendingReceived.Clear();

        public static void ShowToast(string title, string item, string body, Color accent)
        {
            if (instance != null) instance.AddToast(title, item, body, accent);
        }

        private void Awake() => instance = this;

        private void OnDestroy()
        {
            if (instance == this) instance = null;
            if (canvas != null) Destroy(canvas.gameObject);
        }

        private void Update()
        {
            var client = ArchipelagoMod.Client;
            if (client == null) return;
            if (canvas == null && !Build()) return;

            bool hidden = ArchipelagoOverlay.HiddenUntilMenu;
            canvas.enabled = !hidden;
            ShowReceived();
            AlertNewHints(client);
            // Below the hint panel while it's open, so they don't cover it.
            float below = hintPanel.activeSelf ? ((RectTransform)hintPanel.transform).rect.height + 12f : 0f;
            toastColumn.anchoredPosition = new Vector2(-RightClear, -TopMargin - below);
            UpdateToasts();
            UpdatePill(client);
            UpdateReroll(hidden);

            if (!ArchipelagoOverlay.Typing && !ConnectPopup.IsOpen && !hidden)
            {
                if (Input.GetKeyDown(KeyCode.H)) OpenPanel(!hintPanel.activeSelf, tab);
                // Not Escape: that's the game's pause menu, and the panel should stay up through it (the user's call, 2026-11-02).
                else if (hintPanel.activeSelf && Input.GetKeyDown(KeyCode.Tab)) OpenPanel(true, (tab + 1) % Tabs.Length);
                else if (hintPanel.activeSelf && tab > 0 && Input.GetKeyDown(KeyCode.PageDown)) ChangePage(1);
                else if (hintPanel.activeSelf && tab > 0 && Input.GetKeyDown(KeyCode.PageUp)) ChangePage(-1);
            }
            // The Checks tab evaluates every location's rule, so the text is rebuilt once a second
            // (and right away on a key), not every frame.
            if (hintPanel.activeSelf && Time.unscaledTime >= panelRefreshAt) UpdatePanel(client);
        }

        private void OpenPanel(bool open, int newTab)
        {
            hintPanel.SetActive(open);
            tab = newTab;
            panelRefreshAt = 0;
        }

        // PgUp/PgDn: the Checks tab's pages (wrapped by ApTracker, which knows how many), or the Packs tab's groups.
        private void ChangePage(int step)
        {
            if (tab == 1) checkPage += step;
            else packGroup = (packGroup + step + ApTracker.PackGroupCount) % ApTracker.PackGroupCount;
            panelRefreshAt = 0;
        }

        // A new hint for an item this slot holds for someone else opens the panel on the hints: they
        // may be stuck waiting for it (a missed hint kept a player BK'd in a playtest, 2026-11-01).
        // New hints for our own items get a toast. Hints are saved as seen in the AP profile, since
        // the server sends them all again on every connect.
        private void AlertNewHints(ArchipelagoClient client)
        {
            var rows = client.Hints;
            if (ReferenceEquals(rows, hintsChecked) || !ApMode.Active) return;
            hintsChecked = rows;
            var seen = SaveSystem.LoadProgressData(HintsSeenKey, new List<string>());
            var fresh = rows.Where(r => !r.Found && r.Key != null && !seen.Contains(r.Key)).ToList();
            if (fresh.Count == 0) return;
            foreach (var row in fresh)
            {
                seen.Add(row.Key);
                if (row.Mine) AddToast("Hint", row.Item, $"at {(row.Player == null ? "" : row.Player + "'s ")}{row.Location}", HintColor);
                else AddToast("Someone needs this", $"{row.Item} for {row.Player}", $"at {row.Location}", HintColor);
            }
            SaveSystem.SaveProgressData(HintsSeenKey, seen);
            if (fresh.Any(r => !r.Mine)) OpenPanel(true, 0);
        }

        private void ShowReceived()
        {
            if (pendingReceived.Count == 0 || !ApMode.Active) return;
            int seen = SaveSystem.LoadProgressData(SeenKey, 0);
            foreach (var item in pendingReceived.OrderBy(p => p.Key).Where(p => p.Key > seen))
            {
                AddToast("Received", item.Value.Key, item.Value.Value, ReceivedColor);
                seen = item.Key;
            }
            pendingReceived.Clear();
            SaveSystem.SaveProgressData(SeenKey, seen);
        }

        // --- Building ---

        // The game's font is the one most of its texts on screen use (some use special fonts, like
        // the numbers on cards), so this waits until there are texts.
        private bool Build()
        {
            font = FindObjectsOfType<TMP_Text>().Select(t => t.font).Where(f => f != null)
                .GroupBy(f => f).OrderByDescending(g => g.Count()).Select(g => g.Key).FirstOrDefault();
            if (font == null) return false;
            rounded = MakeRoundedSprite();

            var root = new GameObject("ArchipelagoUI");
            DontDestroyOnLoad(root);
            canvas = root.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 5000;
            var scaler = root.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920, 1080);
            scaler.matchWidthOrHeight = 0.5f;
            root.AddComponent<GraphicRaycaster>();

            toastColumn = NewRect("Toasts", root.transform);
            Anchor(toastColumn, new Vector2(1, 1), new Vector2(-RightClear, -TopMargin));
            toastColumn.sizeDelta = new Vector2(460, 0);
            var column = toastColumn.gameObject.AddComponent<VerticalLayoutGroup>();
            column.spacing = 10;
            column.childControlHeight = column.childControlWidth = true;
            column.childForceExpandHeight = false;
            toastColumn.gameObject.AddComponent<ContentSizeFitter>().verticalFit = ContentSizeFitter.FitMode.PreferredSize;

            BuildPill(root.transform);
            BuildHintPanel(root.transform);
            BuildRerollButton(root.transform);
            return true;
        }

        private void BuildPill(Transform parent)
        {
            var rect = NewRect("StatusPill", parent);
            Anchor(rect, new Vector2(0, 1), new Vector2(16, -12));
            pill = rect.gameObject;
            Panel(pill, PillColor);
            var layout = pill.AddComponent<HorizontalLayoutGroup>();
            layout.padding = new RectOffset(14, 16, 6, 6);
            layout.spacing = 10;
            layout.childAlignment = TextAnchor.MiddleLeft;
            layout.childControlWidth = layout.childControlHeight = true;
            layout.childForceExpandWidth = layout.childForceExpandHeight = false;
            var fitter = pill.AddComponent<ContentSizeFitter>();
            fitter.horizontalFit = fitter.verticalFit = ContentSizeFitter.FitMode.PreferredSize;

            var dot = NewRect("Dot", rect);
            pillDot = dot.gameObject.AddComponent<Image>();
            pillDot.sprite = rounded;
            var dotSize = dot.gameObject.AddComponent<LayoutElement>();
            dotSize.preferredWidth = dotSize.preferredHeight = 14;
            pillText = Text(rect, "Archipelago", 22, Color.white);

            pill.AddComponent<Button>().onClick.AddListener(() =>
            {
                ArchipelagoOverlay.ToggleLog();
                linesSeen = ArchipelagoMod.Client?.LinesAdded ?? 0;
            });
        }

        private void BuildHintPanel(Transform parent)
        {
            var rect = NewRect("Hints", parent);
            Anchor(rect, new Vector2(1, 1), new Vector2(-RightClear, -TopMargin));
            hintPanel = rect.gameObject;
            Panel(hintPanel, PanelColor);
            // Fixed width (it isn't inside a layout, so a LayoutElement width wouldn't apply); the
            // height follows the text.
            rect.sizeDelta = new Vector2(640, 0);
            var layout = hintPanel.AddComponent<VerticalLayoutGroup>();
            layout.padding = new RectOffset(22, 22, 16, 18);
            layout.childControlWidth = layout.childControlHeight = true;
            layout.childForceExpandWidth = true;
            hintPanel.AddComponent<ContentSizeFitter>().verticalFit = ContentSizeFitter.FitMode.PreferredSize;
            hintText = Text(rect, "", 22, TextColor);
            hintPanel.SetActive(false);
        }

        // The leader reroll (LeaderReroll): bottom centre, below the leader cards, styled like the pill.
        private void BuildRerollButton(Transform parent)
        {
            var rect = NewRect("LeaderReroll", parent);
            Anchor(rect, new Vector2(0.5f, 0), new Vector2(0, 36));
            rerollButton = rect.gameObject;
            Panel(rerollButton, PillColor);
            var layout = rerollButton.AddComponent<HorizontalLayoutGroup>();
            layout.padding = new RectOffset(22, 22, 10, 10);
            layout.childControlWidth = layout.childControlHeight = true;
            var fitter = rerollButton.AddComponent<ContentSizeFitter>();
            fitter.horizontalFit = fitter.verticalFit = ContentSizeFitter.FitMode.PreferredSize;
            rerollText = Text(rect, "", 24, Color.white);
            rerollButton.AddComponent<Button>().onClick.AddListener(LeaderReroll.Try);
            rerollButton.SetActive(false);
        }

        private void UpdateReroll(bool hidden)
        {
            bool show = !hidden && LeaderReroll.Showing;
            if (rerollButton.activeSelf != show) rerollButton.SetActive(show);
            if (!show) return;
            rerollText.text = "Reroll leaders  <size=80%>(R)</size>";
            if (!ArchipelagoOverlay.Typing && !ConnectPopup.IsOpen && Input.GetKeyDown(KeyCode.R)) LeaderReroll.Try();
        }

        // --- Toasts ---

        private void AddToast(string title, string item, string body, Color accent)
        {
            if (toastColumn == null) return;
            while (toasts.Count >= MaxToasts)
            {
                Destroy(toasts[0].Key.gameObject);
                toasts.RemoveAt(0);
            }
            var rect = NewRect("Toast", toastColumn);
            Panel(rect.gameObject, PanelColor);
            var layout = rect.gameObject.AddComponent<VerticalLayoutGroup>();
            layout.padding = new RectOffset(18, 18, 10, 12);
            layout.spacing = 2;
            layout.childControlWidth = layout.childControlHeight = true;
            layout.childForceExpandHeight = false;
            Text(rect, $"<b>{title}</b>", 20, accent);
            Text(rect, item, 26, TextColor);
            if (!string.IsNullOrEmpty(body)) Text(rect, body, 19, TextColor);
            var group = rect.gameObject.AddComponent<CanvasGroup>();
            group.alpha = 0;
            group.blocksRaycasts = false;
            toasts.Add(new KeyValuePair<CanvasGroup, float>(group, Time.unscaledTime));
        }

        private void UpdateToasts()
        {
            for (int i = toasts.Count - 1; i >= 0; i--)
            {
                float age = Time.unscaledTime - toasts[i].Value;
                if (age >= ToastSeconds || toasts[i].Key == null)
                {
                    if (toasts[i].Key != null) Destroy(toasts[i].Key.gameObject);
                    toasts.RemoveAt(i);
                    continue;
                }
                toasts[i].Key.alpha = Mathf.Min(age / FadeIn, (ToastSeconds - age) / FadeOut, 1f);
            }
        }

        // --- Pill and hints ---

        private void UpdatePill(ArchipelagoClient client)
        {
            bool connected = client.Connected;
            bool trying = !connected && client.Status.StartsWith("Connecting");
            pillDot.color = connected ? new Color32(0x5C, 0xD6, 0x6B, 0xFF) : trying ? new Color32(0xF2, 0xC1, 0x4E, 0xFF) : new Color32(0xE0, 0x5A, 0x4F, 0xFF);
            if (ArchipelagoOverlay.LogOpen) linesSeen = client.LinesAdded;
            int unread = client.LinesAdded - linesSeen;
            string state = connected ? "Connected" : trying ? "Connecting" : "Offline";
            pillText.text = unread > 0 ? $"Archipelago  {state}  |  {unread} new" : $"Archipelago  {state}";
        }

        private void UpdatePanel(ArchipelagoClient client)
        {
            panelRefreshAt = Time.unscaledTime + PanelRefreshSeconds;
            // The tab row: the open one bold, the others dimmed.
            var text = new StringBuilder(string.Join("   ", Tabs.Select((t, i) => i == tab ? $"<b>{t}</b>" : $"<alpha=#80>{t}<alpha=#FF>")));
            text.Append("   <size=70%>(Tab to switch, H to close)</size>\n");
            if (tab == 1) ApTracker.Checks(text, client, checkPage);
            else if (tab == 2) ApTracker.Packs(text, client, packGroup);
            else
            {
                var rows = client.Hints;
                Section(text, "Your items", rows.Where(r => r.Mine), r => $"{r.Item}  <size=80%>at {(r.Player == null ? "" : r.Player + "'s ")}{r.Location}</size>");
                Section(text, "Items you hold for others", rows.Where(r => !r.Mine), r => $"{r.Item} for {r.Player}  <size=80%>at {r.Location}</size>");
            }
            if (!client.Connected) text.Append("\n<size=80%>Not connected; this may be out of date.</size>");
            hintText.text = text.ToString();
        }

        private static void Section(StringBuilder text, string title, IEnumerable<ArchipelagoClient.HintRow> rows, System.Func<ArchipelagoClient.HintRow, string> line)
        {
            var list = rows.OrderBy(r => r.Found).ToList();
            text.Append($"\n<b>{title}</b>\n");
            if (list.Count == 0) text.Append("<size=80%>None yet. Ask the server with !hint in chat (Enter).</size>\n");
            const int shown = 10;
            foreach (var row in list.Take(shown))
            {
                text.Append(row.Found ? "<alpha=#80><s>" + line(row) + "</s><alpha=#FF>" : line(row)).Append('\n');
            }
            if (list.Count > shown) text.Append($"<size=80%>and {list.Count - shown} more</size>\n");
        }

        // --- Helpers ---

        private static RectTransform NewRect(string name, Transform parent)
        {
            var go = new GameObject(name, typeof(RectTransform));
            go.transform.SetParent(parent, false);
            return (RectTransform)go.transform;
        }

        private static void Anchor(RectTransform rect, Vector2 corner, Vector2 offset)
        {
            rect.anchorMin = rect.anchorMax = rect.pivot = corner;
            rect.anchoredPosition = offset;
        }

        private void Panel(GameObject go, Color color)
        {
            var image = go.AddComponent<Image>();
            image.sprite = rounded;
            image.type = Image.Type.Sliced;
            image.color = color;
        }

        private TextMeshProUGUI Text(Transform parent, string text, float size, Color color)
        {
            var label = NewRect("Text", parent).gameObject.AddComponent<TextMeshProUGUI>();
            label.font = font;
            label.fontSize = size;
            label.color = color;
            label.richText = true;
            label.enableWordWrapping = true;
            label.raycastTarget = false;
            label.text = text;
            return label;
        }

        // A white rounded rectangle, 9-sliced so panels of any size keep round corners.
        private static Sprite MakeRoundedSprite()
        {
            const int size = 64, radius = 20;
            var texture = new Texture2D(size, size, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp };
            var pixels = new Color32[size * size];
            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float dx = Mathf.Max(radius - x - 0.5f, x + 0.5f - (size - radius), 0);
                    float dy = Mathf.Max(radius - y - 0.5f, y + 0.5f - (size - radius), 0);
                    float alpha = Mathf.Clamp01(radius - Mathf.Sqrt(dx * dx + dy * dy) + 0.5f);
                    pixels[y * size + x] = new Color32(255, 255, 255, (byte)(alpha * 255));
                }
            }
            texture.SetPixels32(pixels);
            texture.Apply();
            return Sprite.Create(texture, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100, 0,
                SpriteMeshType.FullRect, new Vector4(radius, radius, radius, radius));
        }
    }
}
