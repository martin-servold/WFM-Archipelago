using System.Linq;
using HarmonyLib;
using UnityEngine;

namespace WildfrostArchipelago
{
    /// <summary>
    /// Which map battles still hold a check for this run's tribe (asked for by the user 2026-10-31):
    /// a dot in the check colour at the top right of the node while its check isn't sent, and a line
    /// in its hover label (ApPatches.MapLabel). Nothing shows while the client can't tell (offline
    /// before the first connect) or the battle isn't a location.
    /// </summary>
    internal class CheckMarker : MonoBehaviour
    {
        private const float RefreshSeconds = 0.5f;
        // Of the node sprite's width.
        private const float Size = 0.2f, RimScale = 1.3f;
        private static readonly Color RimColor = new Color32(0xFF, 0xF8, 0xEA, 0xFF);

        private static Sprite dot;

        private MapNode mapNode;
        // The node's own sprites: battle nodes draw a base and an icon rather than the main one.
        private SpriteRenderer[] node;
        private SpriteRenderer marker;
        private SpriteRenderer rim;
        private string key;
        private float nextRefresh;
        private bool show;

        [HarmonyPatch(typeof(MapNew), "CreateNode")]
        private static class AddToNode
        {
            private static void Postfix(MapNode __result)
            {
                if (!ApMode.Active || __result == null) return;
                string key = LocationHooks.BattleKey(__result.campaignNode);
                if (key == null) return;
                var holder = new GameObject("AP check marker");
                holder.transform.SetParent(__result.transform, false);
                var marker = holder.AddComponent<CheckMarker>();
                marker.mapNode = __result;
                marker.key = key;
            }
        }

        /// <summary>The hover label's line for a battle node, or null when there is nothing to say.</summary>
        public static string LabelLine(CampaignNode node)
        {
            string key = ApMode.Active ? LocationHooks.BattleKey(node) : null;
            bool? sent = key == null ? null : ArchipelagoMod.Client?.CheckSent(key);
            if (sent == null) return null;
            return sent.Value ? "Check sent" : "Check not sent yet";
        }

        private void Start()
        {
            // Not the label, highlight or glow, which appear on hover and would move the dot.
            var t = Traverse.Create(mapNode);
            var skip = new[] { t.Field("label").GetValue<MapNodeLabel>()?.transform, t.Field("highlight").GetValue<GameObject>()?.transform, t.Field("glow").GetValue<GameObject>()?.transform }
                .Where(x => x != null).ToList();
            node = mapNode.GetComponentsInChildren<SpriteRenderer>(true)
                .Where(r => !skip.Any(x => r.transform.IsChildOf(x)))
                .ToArray();
            if (dot == null) dot = MakeDot();
            // A light rim behind the dot, so it reads on the map's paper colours.
            var rimObject = new GameObject("rim");
            rimObject.transform.SetParent(transform, false);
            rimObject.transform.localScale = new Vector3(RimScale, RimScale, 1);
            rim = rimObject.AddComponent<SpriteRenderer>();
            marker = gameObject.AddComponent<SpriteRenderer>();
            rim.sprite = marker.sprite = dot;
            var top = node.OrderByDescending(r => r.sortingOrder).FirstOrDefault();
            if (top != null)
            {
                rim.sortingLayerID = marker.sortingLayerID = top.sortingLayerID;
                rim.sortingOrder = top.sortingOrder + 1;
                marker.sortingOrder = top.sortingOrder + 2;
            }
            rim.enabled = marker.enabled = false;
        }

        private void LateUpdate()
        {
            if (Time.unscaledTime >= nextRefresh)
            {
                nextRefresh = Time.unscaledTime + RefreshSeconds;
                show = ArchipelagoMod.Client?.CheckSent(key) == false;
            }
            var shown = show ? node.Where(r => r != null && r.enabled && r.sprite != null && r.gameObject.activeInHierarchy).ToList() : null;
            bool visible = shown?.Count > 0;
            rim.enabled = marker.enabled = visible;
            if (!visible) return;

            // Follows the node's sprites as they are revealed, hovered and faded.
            var bounds = shown[0].bounds;
            foreach (var r in shown) bounds.Encapsulate(r.bounds);
            float alpha = shown.Max(r => r.color.a);
            float size = bounds.size.x * Size;
            transform.position = new Vector3(bounds.max.x - size * 0.5f, bounds.max.y - size * 0.5f, transform.parent.position.z);
            float spriteWorld = marker.sprite.bounds.size.x;
            var parentScale = transform.parent.lossyScale;
            transform.localScale = new Vector3(size / spriteWorld / Mathf.Max(parentScale.x, 1e-4f), size / spriteWorld / Mathf.Max(parentScale.y, 1e-4f), 1);
            var color = ApUi.SentColor;
            color.a = alpha;
            marker.color = color;
            var rimColor = RimColor;
            rimColor.a = alpha;
            rim.color = rimColor;
        }

        // A white filled circle, tinted by each renderer.
        private static Sprite MakeDot()
        {
            const int size = 64;
            const float radius = size / 2f - 1;
            var texture = new Texture2D(size, size, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp };
            var pixels = new Color32[size * size];
            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float distance = Mathf.Sqrt((x + 0.5f - size / 2f) * (x + 0.5f - size / 2f) + (y + 0.5f - size / 2f) * (y + 0.5f - size / 2f));
                    float alpha = Mathf.Clamp01(radius - distance + 0.5f);
                    pixels[y * size + x] = new Color32(255, 255, 255, (byte)(alpha * 255));
                }
            }
            texture.SetPixels32(pixels);
            texture.Apply();
            return Sprite.Create(texture, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100);
        }
    }
}
