using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using HarmonyLib;

namespace WildfrostArchipelago
{
    /// <summary>
    /// Milestone 2: writes content_dump.txt to the mod folder, listing everything that could become
    /// an Archipelago item or location: clans and their reward pools, unlocks, challenges, pets, and
    /// every card and charm. This is the raw material for the apworld's item and location tables.
    /// </summary>
    internal static class ContentDump
    {
        public static void Write(string modDirectory)
        {
            var lines = new List<string>();
            void Section(string title, Action body)
            {
                lines.Add("");
                lines.Add("## " + title);
                try { body(); }
                catch (Exception e) { lines.Add("  <failed: " + e + ">"); }
            }

            Section("Game mode classes (GameModeNormal)", () =>
            {
                var mode = AddressableLoader.GetGroup<GameMode>("GameMode").FirstOrDefault(m => m.name == "GameModeNormal");
                foreach (var c in mode?.classes ?? new ClassData[0]) lines.Add("  " + SurveyLog.Name(c));
            });

            // Which battles can appear at each map tier. node.tier from the survey indexes this array,
            // so it's what the per-area "find each battle" locations are built from.
            Section("Campaign tiers (GameModeNormal populator)", () =>
            {
                var mode = AddressableLoader.GetGroup<GameMode>("GameMode").FirstOrDefault(m => m.name == "GameModeNormal");
                var tiers = AccessTools.Field(typeof(CampaignPopulator), "tiers")?.GetValue(mode?.populator) as CampaignTier[];
                for (int i = 0; i < (tiers?.Length ?? 0); i++)
                {
                    var tier = tiers[i];
                    string battles = string.Join(", ", (tier?.battlePool ?? new BattleData[0])
                        .Select(b => b == null ? "null" : $"{b.name} \"{b.title}\""));
                    string rewards = string.Join(", ", (tier?.rewardPool ?? new CampaignNodeType[0]).Select(SurveyLog.Name));
                    lines.Add($"  tier {i} {SurveyLog.Name(tier)} points={tier?.pointRange} battles=[{battles}] rewardNodes=[{rewards}]");
                }

                var lockers = AccessTools.Field(typeof(CampaignPopulator), "battleLockers")?.GetValue(mode?.populator) as BattleLockData[];
                foreach (var l in lockers ?? new BattleLockData[0])
                    lines.Add($"  battle lock {SurveyLog.Name(l)} battle={l?.battleName} challenge={SurveyLog.Name(l?.linkToChallenge)}");
            });

            Section("BattleData", () =>
            {
                foreach (var b in AddressableLoader.GetGroup<BattleData>("BattleData").OrderBy(b => b.name))
                    lines.Add($"  {b.name} \"{b.title}\" name=\"{SurveyLog.Loc(b.nameRef)}\" waveCounter={b.waveCounter}");
            });

            Section("ClassData (clans) and reward pools", () =>
            {
                foreach (var c in AddressableLoader.GetGroup<ClassData>("ClassData"))
                {
                    lines.Add($"  {c.name} id={c.id} requiresUnlock={SurveyLog.Name(c.requiresUnlock)} leaders={c.leaders?.Length ?? 0}");
                    foreach (var pool in c.rewardPools ?? new RewardPool[0])
                    {
                        if (pool == null) continue;
                        lines.Add($"    pool {pool.name} type={pool.type} general={pool.isGeneralPool} copies={pool.copies} ({pool.list?.Count ?? 0}): " +
                                  string.Join(", ", (pool.list ?? new List<DataFile>()).Select(SurveyLog.Name)));
                    }
                }
            });

            Section("UnlockData", () =>
            {
                foreach (var u in AddressableLoader.GetGroup<UnlockData>("UnlockData").OrderBy(u => u.type).ThenBy(u => u.name))
                {
                    string requires = string.Join(", ", (u.requires ?? new UnlockData[0]).Select(SurveyLog.Name));
                    lines.Add($"  {u.name} type={u.type} building={SurveyLog.Name(u.relatedBuilding)} requires=[{requires}] title=\"{SurveyLog.Loc(u.unlockTitle)}\"");
                }
            });

            Section("ChallengeData", () =>
            {
                foreach (var c in ChallengeSystem.GetAllChallenges().OrderBy(c => c.name))
                {
                    string requires = string.Join(", ", (c.requires ?? new ChallengeData[0]).Select(SurveyLog.Name));
                    lines.Add($"  {c.name} goal={c.goal} hidden={c.hidden} reward={SurveyLog.Name(c.reward)} listener={SurveyLog.Name(c.listener)} " +
                              $"requires=[{requires}] title=\"{SurveyLog.Loc(c.titleKey)}\" text=\"{SurveyLog.Loc(c.textKey)}\"");
                }
            });

            Section("MetaprogressionSystem.data (unlock-ordered lists)", () =>
            {
                if (AccessTools.Field(typeof(MetaprogressionSystem), "data")?.GetValue(null) is Dictionary<string, object> data)
                    foreach (var kv in data.OrderBy(k => k.Key)) lines.Add($"  {kv.Key} = {SurveyLog.Describe(kv.Value)}");
            });

            Section("Pets (GetPetDict)", () =>
            {
                foreach (var kv in MetaprogressionSystem.GetPetDict()) lines.Add($"  {kv.Key} -> {kv.Value}");
            });

            Section("CampaignNodeType", () =>
            {
                foreach (var t in AddressableLoader.GetGroup<CampaignNodeType>("CampaignNodeType").OrderBy(t => t.name))
                    lines.Add($"  {t.name} ({t.GetType().Name})");
            });

            Section("CardData by CardType", () =>
            {
                foreach (var group in AddressableLoader.GetGroup<CardData>("CardData")
                             .GroupBy(c => SurveyLog.Name(c.cardType)).OrderBy(g => g.Key))
                {
                    lines.Add($"  [{group.Key}] ({group.Count()})");
                    foreach (var c in group.OrderBy(c => c.name)) lines.Add($"    {c.name} \"{c.title}\"");
                }
            });

            Section("CardUpgradeData by type", () =>
            {
                foreach (var group in AddressableLoader.GetGroup<CardUpgradeData>("CardUpgradeData")
                             .GroupBy(u => u.type).OrderBy(g => g.Key))
                {
                    lines.Add($"  [{group.Key}] ({group.Count()})");
                    foreach (var u in group.OrderBy(u => u.name)) lines.Add($"    {u.name} \"{u.title}\" tier={u.tier}");
                }
            });

            string path = Path.Combine(modDirectory, "content_dump.txt");
            lines.Insert(0, $"# Wildfrost content dump {DateTime.Now:yyyy-MM-dd HH:mm:ss}");
            File.WriteAllLines(path, lines);
            SurveyLog.Write($"content dump written: {lines.Count} lines -> {path}");
        }
    }
}
