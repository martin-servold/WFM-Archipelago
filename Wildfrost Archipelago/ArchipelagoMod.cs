using System;
using System.Linq;
using System.Reflection;
using Deadpan.Enums.Engine.Components.Modding;
using UnityEngine;

namespace WildfrostArchipelago
{
    public class ArchipelagoMod : WildfrostMod
    {
        public ArchipelagoMod(string modDirectory) : base(modDirectory) { }

        public override string GUID => "fuko.wildfrost.archipelago";
        public override string[] Depends => new string[] { };
        public override string Title => "Archipelago";
        public override string Description => "Connects Wildfrost to an Archipelago multiworld randomizer server.";

        internal const string LogPrefix = "Archipelago: ";

        internal static ArchipelagoClient Client { get; private set; }
        internal static string Directory { get; private set; }
        internal static ArchipelagoMod Instance { get; private set; }

        // Settings, in the game's per-mod config.cfg (read before Load). The Play popup edits the
        // connection ones and saves them through ConnectionConfig.
        [ConfigItem(ConnectionConfig.DefaultServer, "Archipelago server as host:port (wss://host:port to require a secure connection)", "server")]
        public string server;

        [ConfigItem("Player1", "Your slot name", "slot")]
        public string slot;

        [ConfigItem("", "Room password, if it has one", "password")]
        public string password;

        [ConfigItem(false, "Development tools: F8 sends a check, F10 a blank survey profile, and the survey log and content dump", "debug")]
        public bool debug;

        internal static bool DebugMode => Instance != null && Instance.debug;

        /// <summary>This mod's Harmony ID, to tell its patches from other mods' (CompatCheck).</summary>
        internal string HarmonyId => HarmonyInstance?.Id;

        private GameObject overlayHost;

        protected override void Load()
        {
            base.Load();

            // Archipelago.MultiClient.Net is compiled against Newtonsoft.Json 11.0.0.0, but the game
            // ships 13.0.0.0 and we deliberately don't bundle a second copy (two Newtonsoft
            // assemblies in one AppDomain breaks JSON type identity). Mono normally binds the
            // newer version on its own; this handler only runs if it doesn't, and logs so we know.
            AppDomain.CurrentDomain.AssemblyResolve += ResolveNewtonsoft;

            Directory = ModDirectory;
            Instance = this;
            Client = new ArchipelagoClient(ConnectionConfig.Load(this));

            overlayHost = new GameObject("WildfrostArchipelagoOverlay");
            UnityEngine.Object.DontDestroyOnLoad(overlayHost);
            overlayHost.AddComponent<ArchipelagoOverlay>();
            overlayHost.AddComponent<ConnectPopup>();
            overlayHost.AddComponent<ApUi>();

            LocationHooks.Enable();

            if (debug)
            {
                SurveyLog.Open(ModDirectory);
                HookSurvey.Enable();
                try
                {
                    ContentDump.Write(ModDirectory);
                }
                catch (Exception e)
                {
                    SurveyLog.Write("content dump failed: " + e);
                }
                HookSurvey.CheckState("mod load");
            }

            Client.Connect();
        }

        protected override void Unload()
        {
            LocationHooks.Disable();
            ApMode.Exit();
            HookSurvey.Disable();
            SurveyLog.Close();

            Client?.Disconnect();
            Client = null;
            Instance = null;

            if (overlayHost != null)
            {
                UnityEngine.Object.Destroy(overlayHost);
                overlayHost = null;
            }

            AppDomain.CurrentDomain.AssemblyResolve -= ResolveNewtonsoft;

            base.Unload();
        }

        private static Assembly ResolveNewtonsoft(object sender, ResolveEventArgs args)
        {
            if (!args.Name.StartsWith("Newtonsoft.Json,", StringComparison.Ordinal))
            {
                return null;
            }

            Assembly loaded = AppDomain.CurrentDomain.GetAssemblies()
                .FirstOrDefault(a => a.GetName().Name == "Newtonsoft.Json");
            Debug.Log($"{LogPrefix}AssemblyResolve fallback for '{args.Name}' -> {loaded?.FullName ?? "none loaded"}");
            return loaded;
        }
    }
}
