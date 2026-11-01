namespace WildfrostArchipelago
{
    /// <summary>
    /// Turns game events into Archipelago location keys. The keys match the apworld's data.py
    /// ("battle:&lt;areaIndex&gt;:&lt;BattleData name&gt;:&lt;ClassData name&gt;", "challenge:&lt;ChallengeData name&gt;").
    /// </summary>
    internal static class LocationHooks
    {
        // PreBattleSetUp is the last point that hands us the battle's node: neither PostBattle nor
        // OnBattleWin fires for a run's last battle, because the win ends the campaign first.
        private static CampaignNode currentBattle;

        public static void Enable()
        {
            Events.PreBattleSetUp += OnPreBattleSetUp;
            Events.OnBattleWin += OnBattleWin;
            Events.OnChallengeCompletedSaved += OnChallengeCompleted;
            Events.OnCampaignEnd += OnCampaignEnd;
        }

        public static void Disable()
        {
            Events.PreBattleSetUp -= OnPreBattleSetUp;
            Events.OnBattleWin -= OnBattleWin;
            Events.OnChallengeCompletedSaved -= OnChallengeCompleted;
            Events.OnCampaignEnd -= OnCampaignEnd;
            currentBattle = null;
        }

        private static void OnPreBattleSetUp(CampaignNode node) => currentBattle = node;

        // A battle continued from a save skips PreBattleSetUp; the player then still stands on it.
        private static CampaignNode BattleNode()
        {
            if (currentBattle != null) return currentBattle;
            var node = References.Player != null ? Campaign.FindCharacterNode(References.Player) : null;
            return node?.type != null && node.type.isBattle ? node : null;
        }

        // Only the AP profile sends checks: battles on the player's own profile are not part of the seed.
        private static void OnBattleWin()
        {
            var node = BattleNode();
            currentBattle = null;
            if (!ApMode.Active || DailyRun()) return;
            // node.data["battle"] holds the BattleData's name (set by CampaignPopulator).
            if (node?.data == null || !node.data.ContainsKey("battle"))
            {
                ArchipelagoMod.Client?.Log("Battle won, but its map node wasn't found, so no check was sent");
                return;
            }
            ArchipelagoMod.Client?.SendLocation(BattleKey(node));
        }

        // Daily Voyages are blocked under AP (ApPatches.NoDailyVoyage); a run that got through anyway
        // (one already saved, say) doesn't count: its deck isn't the multiworld's.
        private static bool DailyRun() => Campaign.Data?.GameMode?.name == "GameModeDaily";

        /// <summary>The location key of a battle node for this run's tribe, or null if it isn't one.</summary>
        public static string BattleKey(CampaignNode node) =>
            node?.data != null && node.data.TryGetValue("battle", out object battle)
                ? $"battle:{node.areaIndex}:{battle}:{RunTribe()}"
                : null;

        // The ClassData name of the run: Basic, Magic or Clunk. The forced first run uses a
        // "Tutorial" class with the Snowdweller deck, so it counts as Basic.
        private static string RunTribe()
        {
            string tribe = References.PlayerData?.classData?.name;
            return tribe == null || tribe == "Tutorial" ? "Basic" : tribe;
        }

        private static void OnChallengeCompleted(ChallengeData challenge)
        {
            if (challenge != null && ApMode.Active) ArchipelagoMod.Client?.SendLocation("challenge:" + challenge.name);
        }

        private static void OnCampaignEnd(Campaign.Result result, CampaignStats stats, PlayerData playerData)
        {
            if (ApMode.Active) DeathLinkHandler.RunEnded(result);
            if (result != Campaign.Result.Win || !ApMode.Active || DailyRun())
            {
                currentBattle = null;
                return;
            }
            // The last battle's win ends the campaign before OnBattleWin fires (seen on a Final
            // Boss win), so it still holds the node: that battle is sent here.
            // (Sending it twice, after an OnBattleWin that did fire, is harmless: sent checks are skipped.)
            if (BattleNode() != null) OnBattleWin();
            // Set before OnCampaignEnd (the game's own bell system reads it there too).
            var mode = Campaign.Data?.GameMode;
            bool trueWin = mode != null && SaveSystem.LoadCampaignData(mode, "trueWin", false);
            ApMode.RunWon(RunTribe(), trueWin, SaveSystem.LoadProgressData("stormPointOvercrank", false));
        }
    }
}
