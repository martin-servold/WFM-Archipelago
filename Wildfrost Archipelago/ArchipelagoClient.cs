using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Threading;
using Archipelago.MultiClient.Net;
using Archipelago.MultiClient.Net.BounceFeatures.DeathLink;
using Archipelago.MultiClient.Net.Enums;
using Archipelago.MultiClient.Net.Helpers;
using Archipelago.MultiClient.Net.MessageLog.Messages;
using Archipelago.MultiClient.Net.Models;
using Deadpan.Enums.Engine.Components.Modding;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace WildfrostArchipelago
{
    /// <summary>
    /// The connection settings, held in the mod's [ConfigItem] fields (ArchipelagoMod) so they live in
    /// the game's own per-mod config.cfg. The game reads that file at mod load, but only ever writes
    /// it with the defaults (when it is missing), so Save writes it in the same format itself.
    /// A copy is kept in the game's save folder (SaveFolder), since a Workshop update can replace the
    /// mod folder and config.cfg with it (the user's call, 2026-10-31). A config.cfg holding only the
    /// defaults then takes the saved copy; any other config.cfg (edited by hand) wins.
    /// </summary>
    internal class ConnectionConfig
    {
        public const string Game = "Wildfrost";
        // archipelago.gg rooms get a new port each time, so the default leaves it for the player to fill
        // in (the user's choice, 2026-10-31); nothing connects until they do.
        public const string DefaultServer = "archipelago.gg:<port>";
        private const string FileName = "config.cfg";
        private const string OldFileName = "connection.txt";
        private const string SavedFileName = "connection.txt";

        /// <summary>This mod's files that must outlive the mod folder: the settings copy and the offline queue.</summary>
        public static string SaveFolder => Path.Combine(Application.persistentDataPath, "Archipelago");

        public string Server;
        public string Slot;
        public string Password;

        public ConnectionConfig Copy() => (ConnectionConfig)MemberwiseClone();

        public static ConnectionConfig Load(ArchipelagoMod mod)
        {
            FillDefaults(mod);
            MigrateConnectionTxt(mod);
            if (IsDefault(mod) && ReadKeyValues(Path.Combine(SaveFolder, SavedFileName), mod))
                WriteConfigFile(mod);
            else
                WriteSavedCopy(mod);
            return new ConnectionConfig { Server = mod.server, Slot = mod.slot, Password = mod.password ?? "" };
        }

        public void Save(ArchipelagoMod mod)
        {
            mod.server = Server;
            mod.slot = Slot;
            mod.password = Password;
            WriteConfigFile(mod);
            WriteSavedCopy(mod);
        }

        private static bool IsDefault(ArchipelagoMod mod)
        {
            foreach (var field in typeof(ArchipelagoMod).GetFields(BindingFlags.Instance | BindingFlags.Public))
            {
                var item = field.GetCustomAttribute<WildfrostMod.ConfigItemAttribute>();
                if (item != null && field.FieldType == typeof(string) && !Equals(field.GetValue(mod) ?? "", item.defaultValue ?? ""))
                    return false;
            }
            return true;
        }

        private static void WriteSavedCopy(ArchipelagoMod mod)
        {
            try
            {
                Directory.CreateDirectory(SaveFolder);
                File.WriteAllLines(Path.Combine(SaveFolder, SavedFileName),
                    new[] { "server=" + mod.server, "slot=" + mod.slot, "password=" + mod.password });
            }
            catch (Exception e)
            {
                Debug.LogWarning(ArchipelagoMod.LogPrefix + "Saving the settings copy failed: " + e.Message);
            }
        }

        // key=value lines (server, slot, password) into the fields. False when there is no file.
        private static bool ReadKeyValues(string path, ArchipelagoMod mod)
        {
            if (!File.Exists(path)) return false;
            foreach (string line in File.ReadAllLines(path))
            {
                int eq = line.IndexOf('=');
                if (eq < 0) continue;
                string value = line.Substring(eq + 1).Trim();
                switch (line.Substring(0, eq).Trim().ToLowerInvariant())
                {
                    case "server": mod.server = value; break;
                    case "slot": mod.slot = value; break;
                    case "password": mod.password = value; break;
                }
            }
            return true;
        }

        // Each [ConfigItem] as the game writes it: "//comment", then "<field type> : <title> = <value>".
        public static void WriteConfigFile(ArchipelagoMod mod)
        {
            var text = new StringBuilder();
            foreach (var field in typeof(ArchipelagoMod).GetFields(BindingFlags.Instance | BindingFlags.Public))
            {
                var item = field.GetCustomAttribute<WildfrostMod.ConfigItemAttribute>();
                if (item == null) continue;
                text.AppendLine("//" + item.comment);
                text.AppendLine($"{field.FieldType.FullName} : {item.forceTitle ?? field.Name} = {field.GetValue(mod)}");
            }
            File.WriteAllText(Path.Combine(mod.ModDirectory, FileName), text.ToString());
        }

        // The game fills the fields from config.cfg, or writes the defaults when the file is missing. A
        // file without some setting (an older or hand-edited one) leaves that field null.
        private static void FillDefaults(ArchipelagoMod mod)
        {
            bool missing = false;
            foreach (var field in typeof(ArchipelagoMod).GetFields(BindingFlags.Instance | BindingFlags.Public))
            {
                var item = field.GetCustomAttribute<WildfrostMod.ConfigItemAttribute>();
                if (item == null || field.GetValue(mod) != null) continue;
                field.SetValue(mod, item.defaultValue);
                missing = true;
            }
            if (missing) WriteConfigFile(mod);
        }

        // Before config.cfg, the settings were key=value lines in connection.txt. Moved over once;
        // the old file is kept as connection.txt.old.
        private static void MigrateConnectionTxt(ArchipelagoMod mod)
        {
            string path = Path.Combine(mod.ModDirectory, OldFileName);
            if (!ReadKeyValues(path, mod)) return;
            WriteConfigFile(mod);
            File.Copy(path, path + ".old", true);
            File.Delete(path);
            Debug.Log(ArchipelagoMod.LogPrefix + "Moved connection.txt settings into config.cfg");
        }
    }

    /// <summary>
    /// Owns the Archipelago session. MultiClient.Net raises its events on socket threads, and Unity
    /// APIs may only be touched from the main thread, so every callback here only enqueues; the
    /// overlay's Update drains the queue on the main thread.
    /// </summary>
    internal class ArchipelagoClient
    {
        private const int MaxLines = 300;

        // Replaced by Configure; a connect attempt works on its own copy.
        private ConnectionConfig config;
        private readonly ConcurrentQueue<string> pending = new ConcurrentQueue<string>();
        private readonly List<string> lines = new List<string>();
        private ArchipelagoSession session;

        // From slot_data. Game events are matched by key ("battle:<area>:<BattleData>:<ClassData>",
        // "challenge:<ChallengeData>"), so the client never rebuilds the apworld's display names.
        // Written once on the login thread before session is published, then only read.
        private volatile Dictionary<string, long> locationIds;
        private volatile Dictionary<long, string> itemKeys;
        private volatile Dictionary<string, string> cardKinds;
        private volatile Dictionary<string, List<string>> packs;
        private volatile string seed;
        private volatile int goal;
        private volatile bool forceStormBells;
        private volatile bool forceOvercrank;
        private volatile bool snowdwellersIsItem;
        private volatile bool deathLinkOn;
        private DeathLinkService deathLink;
        // DeathLinks arrive on the socket thread; handled in Drain.
        private readonly ConcurrentQueue<DeathLink> deaths = new ConcurrentQueue<DeathLink>();

        // Items arrive on the socket thread, often before login has returned and slot_data is read,
        // so they're queued raw and only mapped to keys on the main thread once loginHandled is set.
        private readonly ConcurrentQueue<ItemInfo> receivedItems = new ConcurrentQueue<ItemInfo>();
        private bool loginHandled;

        private class ItemInfo
        {
            public long Id;
            public int Index;
            public string Name, Sender, Location;
            public ItemFlags Flags;
            public bool FromServer;
        }

        // Main thread only. Checks made while disconnected; sent once logged in. Saved to
        // pendingPath (one file per AP profile) so they survive a game restart while offline.
        private readonly HashSet<string> queuedLocations = new HashSet<string>();
        private bool goalQueued;
        // Sent this game session. A send into a connection that has died without the library noticing
        // yet is lost, so every login sends these again; the server already has most of them, and
        // those are skipped.
        private readonly HashSet<string> sentLocations = new HashSet<string>();
        private bool goalSent;
        private string pendingPath;
        private const string GoalLine = "goal";

        public string Status { get; private set; } = "Disconnected";
        public IReadOnlyList<string> Lines => lines;
        /// <summary>Lines logged since the client was made (Lines keeps only the last MaxLines).</summary>
        public int LinesAdded { get; private set; }
        // Set while an item from an earlier session is handled again: its lines don't count as new.
        private bool replaying;

        /// <summary>A hint row for the hint panel, with names already looked up.</summary>
        public class HintRow
        {
            public bool Mine;      // an item of this slot; otherwise one this slot holds for someone
            public bool Found;
            public string Item, Player, Location;
        }

        // Replaced whole by the socket thread's TrackHints callback; read on the main thread.
        private volatile List<HintRow> hints = new List<HintRow>();

        // Reconnecting by itself after a lost connection (an Archipelago client requirement): only
        // once these settings have logged in, retried with a growing delay until it connects again or
        // the player disconnects or changes the settings. Checks made meanwhile wait in the offline
        // queue. Each session's socket callbacks carry its generation, so a closed old session (or
        // one closed on purpose) doesn't count as lost.
        private static readonly float[] RetryDelays = { 2f, 5f, 10f, 30f, 60f };
        private volatile int generation;
        private bool reconnect;
        private float retryAt = -1;
        private int retries;
        public IReadOnlyList<HintRow> Hints => hints;

        // Toasts from socket threads (sent checks), shown on the main thread.
        // Check toasts: one per check sent. The server's item message for a check (if it sends one)
        // arrives after the check, so a check waits briefly for it: another player's item is named in
        // the toast, our own item already gets a received toast, and otherwise the location is shown.
        private readonly ConcurrentQueue<string> checksSent = new ConcurrentQueue<string>();
        private readonly ConcurrentQueue<ItemSend> itemSends = new ConcurrentQueue<ItemSend>();
        private readonly List<KeyValuePair<string, float>> checksWaiting = new List<KeyValuePair<string, float>>();
        private readonly HashSet<string> checksToasted = new HashSet<string>();
        private const float CheckToastWait = 2f;

        private struct ItemSend
        {
            public string Location, Item, Receiver;
            public ItemFlags Flags;
            public bool ToUs;
        }
        public string Server => config.Server;
        public Dictionary<string, string> CardKinds => cardKinds;

        /// <summary>Every item key in the seed (slot_data "item_keys").</summary>
        public IEnumerable<string> ItemKeyValues => itemKeys?.Values ?? Enumerable.Empty<string>();
        public Dictionary<string, List<string>> Packs => packs;
        /// <summary>slot_data "goal": 0 win each clan, 1 True Final Boss each clan, 2 Overcranked True Final Boss each clan.</summary>
        public int Goal => goal;
        /// <summary>slot_data "force_storm_bells": runs must start at the full storm point limit.</summary>
        public bool ForceStormBells => forceStormBells;

        /// <summary>slot_data "force_overcrank": with every bell level, runs must start Overcranked.</summary>
        public bool ForceOvercrank => forceOvercrank;

        /// <summary>
        /// Whether Snowdwellers is a tribe item too (slot_data "starting_tribe"; seeds from before that
        /// option always have them).
        /// </summary>
        public bool SnowdwellersIsItem => snowdwellersIsItem;

        public ConnectionConfig Config => config.Copy();

        public ArchipelagoClient(ConnectionConfig config)
        {
            this.config = config.Copy();
        }

        public bool Connected => session != null && session.Socket.Connected;

        public void Connect()
        {
            retries = 0;
            Open();
        }

        private void Open()
        {
            CloseSession();
            retryAt = -1;
            loginHandled = false;
            var config = this.config.Copy();
            if (config.Server.Contains("<port>"))
            {
                Status = "Enter your room's port in the server address";
                return;
            }
            Status = $"Connecting to {config.Server} as {config.Slot}...";
            if (retries == 0) Log(Status);
            else Debug.Log(ArchipelagoMod.LogPrefix + Status);
            int current = generation;
            // A retry's failures only go to Player.log; the overlay already said the connection was lost.
            bool quiet = retries > 0;

            // TryConnectAndLogin blocks on the network, so keep it off the main thread.
            ThreadPool.QueueUserWorkItem(_ =>
            {
                try
                {
                    var newSession = ArchipelagoSessionFactory.CreateSession(config.Server);
                    newSession.Items.ItemReceived += OnItemReceived;
                    newSession.MessageLog.OnMessageReceived += OnMessage;
                    newSession.Socket.SocketClosed += reason =>
                    {
                        if (current != generation) return;
                        if (quiet) Debug.Log(ArchipelagoMod.LogPrefix + "Socket closed: " + reason);
                        else Post($"Socket closed: {reason}", "Disconnected");
                        pending.Enqueue(LostMarker);
                    };
                    newSession.Socket.ErrorReceived += (e, message) =>
                    {
                        if (current != generation) return;
                        if (quiet) Debug.LogWarning(ArchipelagoMod.LogPrefix + $"Can't reach {config.Server}: " + e);
                        else PostError($"Can't reach {config.Server}", e);
                        // A lost server only raises this, never SocketClosed (found testing 2026-10-31).
                        pending.Enqueue(LostMarker);
                    };

                    LoginResult result = newSession.TryConnectAndLogin(
                        ConnectionConfig.Game, config.Slot, ItemsHandlingFlags.AllItems,
                        password: string.IsNullOrEmpty(config.Password) ? null : config.Password);

                    if (result is LoginSuccessful success)
                    {
                        seed = newSession.RoomState.Seed;
                        if (!ReadSlotData(success.SlotData))
                        {
                            Post("Connected, but slot_data has no location map. Is this a Wildfrost slot?", "Wrong slot data");
                            newSession.Socket.DisconnectAsync();
                            return;
                        }
                        session = newSession;
                        newSession.Hints.TrackHints(found => OnHints(newSession, found));
                        if (deathLinkOn)
                        {
                            var service = newSession.CreateDeathLinkService();
                            service.OnDeathLinkReceived += OnDeathLink;
                            service.EnableDeathLink();
                            deathLink = service;
                            Post("DeathLink on");
                        }
                        int missing = newSession.Locations.AllMissingLocations.Count;
                        Post($"Connected as slot {success.Slot}. Missing locations: {missing}", $"Connected ({config.Slot})");
                        pending.Enqueue(FlushMarker);
                    }
                    else
                    {
                        var failure = (LoginFailure)result;
                        string why = "Login failed: " + string.Join("; ", failure.Errors.Concat(failure.ErrorCodes.Select(c => c.ToString())));
                        if (quiet) Debug.Log(ArchipelagoMod.LogPrefix + why);
                        else Post(why, "Login failed");
                        if (current == generation) pending.Enqueue(LostMarker);
                    }
                }
                catch (Exception e)
                {
                    // Surfaces assembly binding (Newtonsoft) and TLS failures, which are what the spike is testing.
                    if (quiet) Debug.LogWarning(ArchipelagoMod.LogPrefix + $"Can't connect to {config.Server}: " + e);
                    else PostError($"Can't connect to {config.Server}", e, "Connect error");
                    if (current == generation) pending.Enqueue(LostMarker);
                }
            });
        }

        /// <summary>Main thread only. New settings for the next Connect.</summary>
        public void Configure(ConnectionConfig newConfig)
        {
            config = newConfig.Copy();
            reconnect = false;
        }

        /// <summary>
        /// Main thread only. Chat to the room; the server runs "!" commands (!help, !hint ...) itself
        /// and answers with messages, which the overlay shows.
        /// </summary>
        public void Say(string text)
        {
            var current = session;
            if (current == null)
            {
                Log("Not connected");
                return;
            }
            ThreadPool.QueueUserWorkItem(_ =>
            {
                try
                {
                    current.Say(text);
                }
                catch (Exception e)
                {
                    PostError("Sending chat failed", e);
                }
            });
        }

        /// <summary>Main thread only. On purpose: no reconnecting until the next Connect logs in.</summary>
        public void Disconnect()
        {
            reconnect = false;
            retryAt = -1;
            CloseSession();
            Status = "Disconnected";
        }

        private void CloseSession()
        {
            generation++;
            var old = session;
            session = null;
            var oldDeathLink = deathLink;
            deathLink = null;
            if (old == null) return;
            try
            {
                old.Items.ItemReceived -= OnItemReceived;
                if (oldDeathLink != null) oldDeathLink.OnDeathLinkReceived -= OnDeathLink;
                old.MessageLog.OnMessageReceived -= OnMessage;
                old.Socket.DisconnectAsync();
            }
            catch (Exception e)
            {
                Debug.LogWarning(ArchipelagoMod.LogPrefix + "Disconnect threw: " + e);
            }
        }

        private bool ReadSlotData(Dictionary<string, object> slotData)
        {
            if (slotData == null
                || !slotData.TryGetValue("location_ids", out object locs) || !(locs is JObject locObject)
                || !slotData.TryGetValue("item_keys", out object items) || !(items is JObject itemObject)
                || !slotData.TryGetValue("card_kinds", out object kinds) || !(kinds is JObject kindObject)
                || !slotData.TryGetValue("packs", out object packData) || !(packData is JObject packObject))
            {
                return false;
            }
            itemKeys = itemObject.Properties().ToDictionary(p => long.Parse(p.Name), p => (string)p.Value);
            cardKinds = kindObject.ToObject<Dictionary<string, string>>();
            packs = packObject.ToObject<Dictionary<string, List<string>>>();
            locationIds = locObject.ToObject<Dictionary<string, long>>();
            // Seeds from before the goal option had one win as the goal; 0 is the closest.
            goal = slotData.TryGetValue("goal", out object goalValue) ? Convert.ToInt32(goalValue) : 0;
            forceStormBells = slotData.TryGetValue("force_storm_bells", out object force) && Convert.ToBoolean(force);
            forceOvercrank = slotData.TryGetValue("force_overcrank", out object overcrank) && Convert.ToBoolean(overcrank);
            snowdwellersIsItem = slotData.ContainsKey("starting_tribe");
            deathLinkOn = slotData.TryGetValue("death_link", out object death) && Convert.ToBoolean(death);
            return true;
        }

        /// <summary>Main thread only. Loads the offline queue saved for an AP profile and keeps saving to it.</summary>
        public void UsePendingFile(string path)
        {
            pendingPath = path;
            if (!File.Exists(path)) return;
            foreach (string line in File.ReadAllLines(path))
            {
                if (line == GoalLine) goalQueued = true;
                else if (line.Length > 0) queuedLocations.Add(line);
            }
            Log($"Loaded {queuedLocations.Count} offline checks{(goalQueued ? " and the goal" : "")}");
            if (session != null) FlushQueued();
        }

        private void SavePending()
        {
            if (pendingPath == null) return;
            try
            {
                if (queuedLocations.Count == 0 && !goalQueued)
                {
                    if (File.Exists(pendingPath)) File.Delete(pendingPath);
                    return;
                }
                Directory.CreateDirectory(Path.GetDirectoryName(pendingPath));
                var lines = queuedLocations.ToList();
                if (goalQueued) lines.Add(GoalLine);
                File.WriteAllLines(pendingPath, lines);
            }
            catch (Exception e)
            {
                Log("Saving offline checks failed: " + e.Message);
            }
        }

        /// <summary>
        /// Main thread only. Whether a game event's check was sent (or is queued to be): null while
        /// that isn't known (not connected yet) or the event isn't a location.
        /// </summary>
        /// <summary>Whether a game event is a location in this seed (false before slot data arrives).</summary>
        public bool IsLocation(string key) => locationIds?.ContainsKey(key) == true;

        public bool? CheckSent(string key)
        {
            if (queuedLocations.Contains(key)) return true;
            var current = session;
            var ids = locationIds;
            if (current == null || ids == null || !ids.TryGetValue(key, out long id)) return null;
            try
            {
                return current.Locations.AllLocationsChecked.Contains(id);
            }
            catch (InvalidOperationException)
            {
                return null; // the socket thread changed the list mid-read; asked again next time
            }
        }

        /// <summary>
        /// Main thread only. Sends the check for a game event, or queues it while offline. quiet skips
        /// the log line for keys that aren't locations (for catch-up over everything in the save).
        /// </summary>
        public void SendLocation(string key, bool quiet = false)
        {
            var current = session;
            var ids = locationIds;
            // A lost connection keeps its session until the loss is noticed, so check the socket too.
            if (current == null || ids == null || !current.Socket.Connected)
            {
                if (queuedLocations.Add(key))
                {
                    Log($"Offline; queued check {key}");
                    SavePending();
                }
                return;
            }
            if (!ids.TryGetValue(key, out long id))
            {
                // Not every game event is a location (tutorial battles, excluded challenges).
                if (!quiet) Log($"No location for {key}");
                return;
            }
            if (current.Locations.AllLocationsChecked.Contains(id)) return;
            sentLocations.Add(key);

            ThreadPool.QueueUserWorkItem(_ =>
            {
                try
                {
                    current.Locations.CompleteLocationChecks(id);
                    string name = current.Locations.GetLocationNameFromId(id) ?? key;
                    checksSent.Enqueue(name);
                    Debug.Log($"{ArchipelagoMod.LogPrefix}Sent check '{name}'");
                }
                catch (Exception e)
                {
                    // Queued again, so the next connection sends it.
                    PostError($"Sending check {key} failed", e);
                    pending.Enqueue(QueueMarker + key);
                }
            });
        }

        /// <summary>Main thread only.</summary>
        public void SendGoal(bool quiet = false)
        {
            var current = session;
            if (current == null || !current.Socket.Connected)
            {
                goalQueued = true;
                Log("Offline; goal queued");
                SavePending();
                return;
            }
            goalSent = true;
            ThreadPool.QueueUserWorkItem(_ =>
            {
                try
                {
                    current.SetGoalAchieved();
                    if (!quiet) Post("Goal complete!");
                }
                catch (Exception e)
                {
                    PostError("Sending the goal failed", e);
                    pending.Enqueue(GoalQueueMarker);
                }
            });
        }

        private void FlushQueued()
        {
            var keys = queuedLocations.Union(sentLocations).ToList();
            bool goal = goalQueued || goalSent;
            // Only a queued goal is news; one sent before is sent again quietly.
            bool announce = goalQueued;
            queuedLocations.Clear();
            goalQueued = false;
            SavePending();
            foreach (string key in keys) SendLocation(key);
            if (goal) SendGoal(quiet: !announce);
        }

        public void SendNextMissingCheck(string reason)
        {
            var current = session;
            if (current == null)
            {
                Log($"Not connected; dropped check from {reason}");
                return;
            }

            ThreadPool.QueueUserWorkItem(_ =>
            {
                try
                {
                    long id = current.Locations.AllMissingLocations.FirstOrDefault();
                    if (id == 0)
                    {
                        Post("No missing locations left");
                        return;
                    }
                    string name = current.Locations.GetLocationNameFromId(id) ?? id.ToString();
                    current.Locations.CompleteLocationChecks(id);
                    checksSent.Enqueue(name);
                    Debug.Log($"{ArchipelagoMod.LogPrefix}Sent check '{name}' ({reason})");
                }
                catch (Exception e)
                {
                    PostError("Sending the check failed", e);
                }
            });
        }

        /// <summary>Main thread only. Logs immediately and adds the line to the overlay.</summary>
        /// <param name="fileMessage">A fuller version for Player.log, when the overlay shows a short one.</param>
        public void Log(string message, string fileMessage = null)
        {
            Debug.Log(ArchipelagoMod.LogPrefix + (fileMessage ?? LogText.Strip(message)));
            lines.Add(message);
            if (!replaying) LinesAdded++;
            if (lines.Count > MaxLines) lines.RemoveAt(0);
        }

        /// <summary>Main thread only. Player.log always; the overlay only with debug=true.</summary>
        public void LogDebug(string message)
        {
            if (ArchipelagoMod.DebugMode) Log(message);
            else Debug.Log(ArchipelagoMod.LogPrefix + LogText.Strip(message));
        }

        /// <summary>
        /// Main thread only. A detail of the entry just logged (what an item unlocks), shown dimmed
        /// beneath it as part of the same entry.
        /// </summary>
        public void LogDetail(string text)
        {
            if (lines.Count == 0)
            {
                Log(text);
                return;
            }
            Debug.Log(ArchipelagoMod.LogPrefix + "  " + text);
            lines[lines.Count - 1] += "\n" + LogText.Color(LogText.Detail, "    " + text);
        }

        /// <summary>Main thread only. Called from the overlay's Update.</summary>
        public void Drain()
        {
            while (pending.TryDequeue(out string message))
            {
                if (message == FlushMarker)
                {
                    // Logged in: ApMode picks (or switches to) this seed's profile, which loads its
                    // saved offline queue, then everything queued this session is sent.
                    ApMode.OnConnected(this, seed, config.Slot);
                    loginHandled = true;
                    reconnect = true;
                    retries = 0;
                    FlushQueued();
                }
                else if (message.StartsWith(QueueMarker, StringComparison.Ordinal))
                {
                    if (queuedLocations.Add(message.Substring(QueueMarker.Length))) SavePending();
                }
                else if (message == GoalQueueMarker)
                {
                    goalQueued = true;
                    SavePending();
                }
                else if (message == LostMarker)
                {
                    if (!reconnect || retryAt >= 0) continue;
                    // Checks made from now on wait in the offline queue.
                    CloseSession();
                    float delay = RetryDelays[Math.Min(retries, RetryDelays.Length - 1)];
                    if (retries == 0) Log("Connection lost; reconnecting by itself (F9 to try now)");
                    retries++;
                    retryAt = Time.unscaledTime + delay;
                    Status = $"Connection lost; retrying in {delay:0}s";
                }
                else if (message.StartsWith(StatusMarker, StringComparison.Ordinal))
                {
                    Status = message.Substring(StatusMarker.Length);
                }
                else
                {
                    Log(message);
                }
            }
            if (retryAt >= 0 && Time.unscaledTime >= retryAt) Open();
            while (loginHandled && receivedItems.TryDequeue(out ItemInfo item)) HandleItem(item);
            AnnounceChecks();
            while (loginHandled && deaths.TryDequeue(out DeathLink death)) DeathLinkHandler.Received(death.Source, death.Cause);
        }

        // Main thread. A toast and a log entry per check. Either message can come first, so a location
        // announced once isn't announced again. A check that found our own item is the received entry.
        private void AnnounceChecks()
        {
            while (itemSends.TryDequeue(out ItemSend send))
            {
                checksWaiting.RemoveAll(c => c.Key == send.Location);
                if (send.Location == null || !checksToasted.Add(send.Location) || send.ToUs) continue;
                ApUi.ShowToast("Check sent", $"{send.Item} for {send.Receiver}", send.Location, ApUi.SentColor);
                Log(LogText.Color(LogText.Check, "<b>Sent</b> ") + LogText.Item(send.Item, send.Flags)
                    + LogText.Color(LogText.Dim, $" to {send.Receiver}") + "\n" + LogText.Color(LogText.Dim, "    " + send.Location));
            }
            while (checksSent.TryDequeue(out string name))
            {
                if (!checksToasted.Contains(name)) checksWaiting.Add(new KeyValuePair<string, float>(name, Time.unscaledTime + CheckToastWait));
            }
            for (int i = checksWaiting.Count - 1; i >= 0; i--)
            {
                if (Time.unscaledTime < checksWaiting[i].Value) continue;
                string name = checksWaiting[i].Key;
                checksWaiting.RemoveAt(i);
                if (!checksToasted.Add(name)) continue;
                ApUi.ShowToast("Check sent", name, null, ApUi.SentColor);
                Log(LogText.Color(LogText.Check, "<b>Checked</b>") + "\n" + LogText.Color(LogText.Dim, "    " + name));
            }
        }

        private const string StatusMarker = "\u0001status:";
        private const string FlushMarker = "\u0001flush";
        private const string LostMarker = "\u0001lost";
        private const string QueueMarker = "\u0001queue:";
        private const string GoalQueueMarker = "\u0001goal";

        // The overlay gets one line with the innermost cause ("Connection refused"); the full
        // exception goes to Player.log. Debug.Log is safe from socket threads.
        private void PostError(string what, Exception e, string status = null)
        {
            Debug.LogWarning(ArchipelagoMod.LogPrefix + what + ": " + e);
            var cause = e;
            while (cause.InnerException != null) cause = cause.InnerException;
            Post($"{what}: {cause.Message}", status);
        }

        private void Post(string message, string status = null)
        {
            pending.Enqueue(message);
            if (status != null) pending.Enqueue(StatusMarker + status);
        }

        private void OnItemReceived(ReceivedItemsHelper helper)
        {
            var item = helper.DequeueItem();
            receivedItems.Enqueue(new ItemInfo
            {
                Id = item.ItemId,
                Index = helper.Index,
                Name = item.ItemName,
                Sender = item.Player.Name,
                Location = item.LocationName,
                Flags = item.Flags,
                // Starting inventory: from the server (slot 0) at location -2, resent on every connect.
                // Items a host sends from the server console come from location -1 and are announced.
                FromServer = item.Player.Slot == 0 && item.LocationId == -2,
            });
        }

        private void HandleItem(ItemInfo item)
        {
            string key = null;
            itemKeys?.TryGetValue(item.Id, out key);
            // The item key is for debugging; the overlay shows it only with the debug setting on.
            string line = $"Received #{item.Index} {item.Name} [{key}] from {item.Sender} ({item.Location})";
            replaying = ApUi.AlreadyShown(item.Index);
            string detail;
            try
            {
                // The item first and bold, coloured by importance; where it came from dimmed on the next
                // line (it nearly always wrapped). What it unlocks is added beneath by ApMode (LogDetail).
                string source = item.Sender == config.Slot ? item.Location : $"from {item.Sender}  ·  {item.Location}";
                string entry = LogText.Item(item.Name, item.Flags) + "\n" + LogText.Color(LogText.Dim, "    " + source)
                               + (ArchipelagoMod.DebugMode ? LogText.Color(LogText.Dim, $"  [{key}]") : "");
                if (item.FromServer) Debug.Log(ArchipelagoMod.LogPrefix + line);
                else Log(entry, line);
                detail = key != null ? ApMode.OnItemReceived(key, !item.FromServer, item.Index) : null;
            }
            finally
            {
                replaying = false;
            }
            if (item.FromServer) return;
            string from = item.Sender == config.Slot ? $"Found at {item.Location}" : $"From {item.Sender} ({item.Location})";
            ApUi.QueueReceived(item.Index, item.Name, detail == null ? from : from + "\n" + detail);
        }

        private void OnDeathLink(DeathLink death)
        {
            // The server bounces a death to its sender too.
            if (death.Source != config.Slot) deaths.Enqueue(death);
        }

        /// <summary>Main thread only. Sends a DeathLink if this slot has it on. Lost while offline.</summary>
        public void SendDeath(string cause)
        {
            var service = deathLink;
            if (service == null) return;
            string text = $"{config.Slot}'s run ended." + (cause == null ? "" : " " + cause);
            Log("DeathLink sent: " + text);
            ThreadPool.QueueUserWorkItem(_ =>
            {
                try
                {
                    service.SendDeathLink(new DeathLink(config.Slot, text));
                }
                catch (Exception e)
                {
                    PostError("Sending the DeathLink failed", e);
                }
            });
        }

        private void OnMessage(LogMessage message)
        {
            // What a check of ours found: announced once, as the check (AnnounceChecks) or the item
            // received, so the server's own line only goes to Player.log.
            if (message is ItemSendLogMessage send && !(message is HintItemSendLogMessage) && send.IsSenderTheActivePlayer)
            {
                Debug.Log(ArchipelagoMod.LogPrefix + "[AP] " + message);
                itemSends.Enqueue(new ItemSend
                {
                    Location = send.Item.LocationName,
                    Item = send.Item.ItemName,
                    Receiver = send.Receiver.Alias ?? send.Receiver.Name,
                    Flags = send.Item.Flags,
                    ToUs = send.IsReceiverTheActivePlayer,
                });
                return;
            }
            // Connection housekeeping only goes to Player.log (the user's call, 2026-10-31).
            if (message is TagsChangedLogMessage || message is TutorialLogMessage
                || message.ToString().StartsWith("Warning: your client does not support compressed websocket", StringComparison.Ordinal))
            {
                Debug.Log(ArchipelagoMod.LogPrefix + "[AP] " + message);
                return;
            }
            // Chat reads as normal text; the server's notices and other players' finds are dimmed.
            Post(message is ChatLogMessage ? message.ToString() : LogText.Color(LogText.Dim, message.ToString()));
        }

        // Socket thread. Names are looked up here, so the panel only reads strings.
        private void OnHints(ArchipelagoSession current, Hint[] all)
        {
            int me = current.ConnectionInfo.Slot;
            var rows = new List<HintRow>();
            foreach (var hint in all ?? new Hint[0])
            {
                bool mine = hint.ReceivingPlayer == me;
                if (!mine && hint.FindingPlayer != me) continue;
                var receiver = current.Players.GetPlayerInfo(hint.ReceivingPlayer);
                var finder = current.Players.GetPlayerInfo(hint.FindingPlayer);
                rows.Add(new HintRow
                {
                    Mine = mine,
                    Found = hint.Found,
                    Item = current.Items.GetItemName(hint.ItemId, receiver?.Game) ?? hint.ItemId.ToString(),
                    // Null for an item of ours in our own world.
                    Player = mine && hint.FindingPlayer == me ? null : (mine ? finder : receiver)?.Alias ?? "?",
                    Location = current.Locations.GetLocationNameFromId(hint.LocationId, finder?.Game) ?? hint.LocationId.ToString(),
                });
            }
            hints = rows;
        }
    }
}
