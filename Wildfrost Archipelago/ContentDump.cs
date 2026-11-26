using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Deadpan.Enums.Engine.Components.Modding;
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
        private static string directory;

        /// <summary>
        /// Writes the dump now, and again whenever another mod loads or unloads: a mod that loads after this
        /// one adds its content after our first dump (found 2026-11-15, a mod's dump that came out vanilla).
        /// </summary>
        public static void Enable(string modDirectory)
        {
            directory = modDirectory;
            Events.OnModLoaded += Rewrite;
            Events.OnModUnloaded += Rewrite;
            Rewrite(null);
        }

        public static void Disable()
        {
            Events.OnModLoaded -= Rewrite;
            Events.OnModUnloaded -= Rewrite;
        }

        private static void Rewrite(Deadpan.Enums.Engine.Components.Modding.WildfrostMod mod)
        {
            if (directory == null) return;
            try
            {
                Write(directory);
            }
            catch (Exception e)
            {
                SurveyLog.Write("content dump failed: " + e);
            }
        }

        // An effect, and what it applies when it's an "apply X" kind (any effect with an effectToApply).
        private static string Effect(StatusEffectData e)
        {
            if (e == null) return "null";
            var applies = AccessTools.Field(e.GetType(), "effectToApply")?.GetValue(e) as StatusEffectData;
            return applies != null ? $"{e.name} -> {applies.name}" : e.name;
        }

        private static string Stacks(IEnumerable<CardData.StatusEffectStacks> stacks) =>
            string.Join(", ", (stacks ?? Enumerable.Empty<CardData.StatusEffectStacks>()).Where(s => s?.data != null)
                .Select(s => $"{Effect(s.data)} x{s.count}"));

        private static string Traits(IEnumerable<CardData.TraitStacks> traits) =>
            string.Join(", ", (traits ?? Enumerable.Empty<CardData.TraitStacks>()).Where(t => t?.data != null)
                .Select(t => $"{t.data.name} x{t.count}"));

        // What a card's scripts add: leaders get their random abilities this way.
        private static string Scripts(IEnumerable<CardScript> scripts) =>
            string.Join(", ", (scripts ?? Enumerable.Empty<CardScript>()).Where(s => s != null).Select(s =>
            {
                object Get(string field) => AccessTools.Field(s.GetType(), field)?.GetValue(s);
                switch (s)
                {
                    case CardScriptAddAttackEffect _: return "attack:" + Effect(Get("effect") as StatusEffectData);
                    case CardScriptAddPassiveEffect _: return "start:" + Effect(Get("effect") as StatusEffectData);
                    case CardScriptAddTrait _: return "trait:" + ((Get("trait") as TraitData)?.name ?? "null");
                    case CardScriptGiveUpgrade _: return "charm:" + ((Get("upgradeData") as CardUpgradeData)?.name ?? "null");
                    default: return s.GetType().Name;
                }
            }));

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

            // Which mods were loaded: modded content is named after its mod's GUID ("<GUID>.<name>"), which is
            // how a mod's content is told apart for its extension file (PLAN.md §10).
            Section("Loaded mods", () =>
            {
                foreach (var m in Bootstrap.Mods.Where(m => m != null && m.HasLoaded))
                    lines.Add($"  {m.GUID} title=\"{m.Title}\"");
            });

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
                    // The starting deck, for ["starts_with", card] (tools/gen_data.py; the user's call, 2026-11-24).
                    lines.Add("    start deck: " + string.Join(", ", ExtensionMaker.StartDeck(c)));
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

            // The storm bells (References.hardModeModifiers), for the New Challenges that need one and for
            // extensions that add or remove bells (PLAN.md §10, 2026-11-15). Each line: the bell, its storm
            // points, the modifier behind it, its title, and what the modifier runs.
            Section("Storm bells (References.hardModeModifiers)", () =>
            {
                var bells = MonoBehaviourSingleton<References>.instance?.hardModeModifiers;
                if (bells == null) { lines.Add("  <References not loaded yet>"); return; }
                foreach (var bell in bells)
                {
                    var m = bell?.modifierData;
                    string scripts = string.Join(", ", (m?.setupScripts ?? new Script[0]).Concat(m?.startScripts ?? new Script[0])
                        .Where(s => s != null).Select(s => s.GetType().Name));
                    lines.Add($"  {SurveyLog.Name(bell)} points={bell?.stormPoints} modifier={SurveyLog.Name(m)} " +
                              $"title=\"{(m == null ? "" : SurveyLog.Loc(m.titleKey))}\" visible={m?.visible} " +
                              $"systems=[{string.Join(", ", m?.systemsToAdd ?? new string[0])}] scripts=[{scripts}]");
                }
            });

            // Each clan's leaders, and every card's and charm's effects (PLAN.md §10, the user's call 2026-11-15):
            // tools/gen_data.py lists what the base game's cards apply, leaders included, so "apply X"
            // challenges know which cards and clans can do it. "-> Y" is what an "apply" effect applies.
            Section("Clan leaders", () =>
            {
                foreach (var c in AddressableLoader.GetGroup<ClassData>("ClassData"))
                    lines.Add($"  {c.name}: {string.Join(", ", (c.leaders ?? new CardData[0]).Where(l => l != null).Select(l => l.name))}");
            });

            Section("Card effects", () =>
            {
                foreach (var c in AddressableLoader.GetGroup<CardData>("CardData").OrderBy(c => c.name))
                {
                    var scripts = AccessTools.Field(typeof(CardData), "createScripts")?.GetValue(c) as CardScript[];
                    string line = $"  {c.name} type={SurveyLog.Name(c.cardType)} attack=[{Stacks(c.attackEffects)}] " +
                                  $"start=[{Stacks(c.startWithEffects)}] traits=[{Traits(c.traits)}] scripts=[{Scripts(scripts)}]";
                    lines.Add(line);
                }
            });

            Section("Charm effects", () =>
            {
                foreach (var u in AddressableLoader.GetGroup<CardUpgradeData>("CardUpgradeData").OrderBy(u => u.name))
                    lines.Add($"  {u.name} type={u.type} attack=[{Stacks(u.attackEffects)}] effects=[{Stacks(u.effects)}] " +
                              $"traits=[{Traits(u.giveTraits)}] scripts=[{Scripts(u.scripts)}]");
            });

            Section("GameModifierData (every modifier, bells and others)", () =>
            {
                foreach (var m in AddressableLoader.GetGroup<GameModifierData>("GameModifierData").OrderBy(m => m.name))
                    lines.Add($"  {m.name} title=\"{SurveyLog.Loc(m.titleKey)}\" value={m.value} visible={m.visible}");
            });

            string path = Path.Combine(modDirectory, "content_dump.txt");
            lines.Insert(0, $"# Wildfrost content dump {DateTime.Now:yyyy-MM-dd HH:mm:ss}");
            File.WriteAllLines(path, lines);
            SurveyLog.Write($"content dump written: {lines.Count} lines -> {path}");
        }
    }
}
