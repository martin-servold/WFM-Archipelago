# Wildfrost mods in Archipelago

Other Wildfrost mods' content can join [Archipelago](https://archipelago.gg) seeds through an **extension file**,
`<Mod>.wildfrost.json`. It tells the Archipelago world what a mod adds. The other mod needs no changes (most of the time):
the Archipelago mod writes the file in game, from what the mod has loaded.

This guide has two parts:

- **[Part 1: Using a mod's content](#part-1-using-a-mods-content)** is for players and enthusiasts: get an extension
  file (or make one in a minute) and play with it.
- **[Part 2: For mod authors](#part-2-for-mod-authors)** has the details: what to fill in by hand, the file format,
  the rule language and how IDs work.

With an extension file, a seed that picks the mod gets:

| From the mod | In the seed |
|---|---|
| Companions, items and charms in the reward pools | Items: its cards come in packs of about 3, and each charm is an item of its own |
| Pets | Items, locked until found |
| Tribes | Items. Each tribe gets a check for every battle and boss (only the bosses in a seed with 5 or more tribes), and a win with it counts toward the goal |
| Battles in the map's battle pools | Checks, one for (each tribe * each battle) |
| Challenges | Checks |
| Storm bells | Count toward the storm points a seed can reach; its challenges can require them |
| Removed vanilla content | Left out of the seed |

# Part 1: Using a mod's content

## Extensions already built

Check here first. These are extension files shared by the creators of their mods. Some are built into
`wildfrost.apworld`, so there's nothing to copy: just add the mod under **Mod Content** in your Archipelago YAML
(options) file ([Load it](#load-it)).

| Mod | Extension file | Built in |
|---|---|---|
| *None listed yet* | | |

## What you need

- Wildfrost with the Archipelago mod and the mod you want
- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.7 or newer, with `wildfrost.apworld`

## Make the file

Skip this if the mod's file is in the list above, or its author ships one.

1. Enable the Archipelago mod and the mod you want (with any mods it depends on), then **close the game and start it
   again**. A mod enabled from the Mods screen in a running game sometimes doesn't finish loading, so it's best to
   have both loaded when the game starts.
2. On the main menu, press **Enter** to open the Archipelago log's text line (top left overlay element), and type `/generate` on its own. It
   lists the loaded mods with their GUIDs.
3. Type `/generate <the mod's GUID>`, for example `/generate yourname.wildfrost.mymod`.

The log shows a summary and some notes. The file is written to the game's save folder (the folder with `Player.log`
in it), in `Archipelago/Extensions/`:

- Windows: `%USERPROFILE%\AppData\LocalLow\Deadpan Games\Wildfrost\Archipelago\Extensions`
- Linux (Proton): `~/.local/share/Steam/steamapps/compatdata/1811990/pfx/drive_c/users/steamuser/AppData/LocalLow/Deadpan Games/Wildfrost/Archipelago/Extensions`

That's neither Archipelago's own folder nor the Archipelago mod's folder (a Workshop update replaces the mod's folder,
which would delete the file). Nothing reads the file in this default export location: you'll have to copy it to
Archipelago as described below.

A file made this way works as it is. If the mod defines challenges, they're checks that only hold filler (Bling,
boons, traps) until the mod's author writes what each one needs ([Part 2](#2-fill-in-what-the-game-cant-know)), so
they can't make a seed unwinnable.

## Load it

1. Copy the file into Archipelago's folder, next to `wildfrost.apworld`.
2. Restart the Archipelago Launcher, and anything opened from it (Universal Tracker included). Archipelago reads these
   files when it starts.
3. In the Launcher's **Options Creator**, pick Wildfrost and add the mod's name under **Mod Content**, then
   **Export Options** into Archipelago's `Players` folder. The name is the extension (JSON) file's prefix (without
   `.wildfrost.json`). With a mod that adds tribes, the **Tribes** option can run only its tribes (Modded Only) or
   only the vanilla ones (Vanilla Only), and **Modded Clans** can keep half or a quarter of each mod's tribes, picked
   at random, for mods with many.
4. Make sure the mod is still enabled in the game, and play. You'll get a warning if it's disabled when you connect.

Who needs the extension file in their Archipelago folder: the computer that generates the seed, and anyone tracking it
with Universal Tracker (both should have the same file). If you're doing neither (you use the in-game tracker), you
don't need to install it. Other players in a seed do not need the apworld or the extension file. 

**Built-in files.** A file built into `wildfrost.apworld` needs no downloading or copying. A loose file of the same mod
is used instead only when its version is higher, so a mod author can distribute a fixed file before the next apworld
release.

## ⚠️ Test your seed before a public multiworld

**Before you bring modded content into a shared or public multiworld, test it yourself:** generate a seed locally
with your YAML, host it, and connect to it from the game with the mods enabled. Check that it generates, that the
game shows no warnings about missing content when you press Play, and play a little.

Mod authors can push updates through the Steam Workshop at any time, and an update can change or remove content an
existing seed depends on. If you know a mod has updated, test again. If a mod you're using pushes an update in the
middle of an async, you may have to release yourself (`!release`) or have the host send the affected items.

## If something's wrong

- **Generating fails:** the error names the file and what's wrong with it (a missing file, a field it doesn't
  understand, a mod picked under Mod Content whose file isn't installed).
- **In game:** when you press Play, the Archipelago mod checks that the seed's mods are loaded and that everything the
  seed names exists in the game. If something's missing, it shows a toast and lists the details in its log. A seed
  whose only tribes come from a mod that's turned off says so at the town gate.
- **Universal Tracker refuses the seed:** it needs the exact version of the file the seed was generated with. If a
  different version is installed, the error names both versions.

# Part 2: For mod authors

New to Archipelago? Its [setup guide](https://archipelago.gg/tutorial/Archipelago/setup/en) covers installing it,
making options files, generating and hosting.

You're not required to change your mod's code (though adding challenges for your content makes for better seeds,
see [Adding a challenge](#2-fill-in-what-the-game-cant-know)). You ship `<YourMod>.wildfrost.json`: `/generate`
writes most of it, and you fill in a few things by hand, like what your challenges need.

## 1. Generate the file

Generate it as in [Make the file](#make-the-file), with these options:

```
/generate <your mod's GUID> [version] [name=...] [folder=...] [salt=N]
```

- **Version:** defaults to `1.0.0`. Raise it whenever you ship a changed file ([Updating your mod](#updating-your-mod)).
- **`name=`:** the extension is named after your mod's title. Players type the name into their options, and it
  prefixes your item names, so you may want a shorter one: `name=MyMod` (in "double quotes" if it has spaces:
  `"name=My Mod"`). A rerun keeps the name the file already has.

  Names can't contain special characters, since the name is also the file's name: only A-Z, a-z, 0-9, spaces, `_`,
  `.` and `-`. Anything else is dropped from the default name ("VFX/SFX Tools" becomes "VFXSFX Tools"). If nothing is
  left (a title in another language or character set, for example), the last part of your GUID is used, and if that's empty too,
  `/generate` asks you for a `name=`.
- **`folder=`:** writes the file somewhere else, with a full path, in "double quotes" if it has spaces:
  `"folder=C:\Users\me\Documents\My Mod"`. A rerun looks for your existing file in that same folder, so give the same
  `folder=` each time.
- **`salt=`:** only for an ID clash ([ID blocks](#id-blocks)).

Your mod's IDs come from a hash of its GUID ([ID blocks](#id-blocks)), so there's nothing to claim or register first.

Read the notes in the in game overlay log: they say what was skipped and what needs your attention.

Your content is told apart by its name: the modding API names everything after your mod's GUID
(`<GUID>.<name>`). The one exception is `removes` (base-game content your mod takes
out), which can't be traced to a specific mod if multiple are enabled: generate with only your mod enabled if it removes
anything, or check that list.

## 2. Fill in what the game can't know

Open the file and go through these.

**Challenges.** Each challenge your mod adds starts with `"region": "Area 1"`, no `rule` and `"excluded": true`: it's
a check that only ever holds filler, so a plain export can't make a seed unwinnable. Give each one what it really
needs (see [Rules](#rules)) and **remove `"excluded"`**, so it can hold real items:

```json
{"key": "challenge:dev.wildfrost.MyMod.Trolls", "name": "Challenge - Kill 5 Trolls", "id": 106003,
 "text": "Kill 5 Trolls", "region": "Area 2", "rule": ["any_card", "trolls"]}
```

Keep `"excluded": true` on a challenge that's too luck-based to hold anything but filler. A challenge with no `rule`
and no `"excluded"` is in logic from the very start. `/generate`'s notes list the challenges still filler only.

**Adding a challenge.** A check needs a real challenge in your mod: a `ChallengeData`, made with the modding API's
`ChallengeDataBuilder`. The game reports when it's completed, and that sends the check. Its listener decides what
counts:

- **Across runs:** a game stat adds up over every run until it reaches the goal ("apply 100 Spice", "kill 50
  enemies"). Most base-game challenges work this way.
- **At the end of a run:** one run's stats are checked when it ends.
- **Custom:** your mod's own code decides (the base game's "win without charms" and "beat a boss without Snow" are
  this kind).

Under Archipelago, its `requires` list (the challenges that must be completed before it unlocks) is ignored, so every
challenge is open from the start, and its in-game reward isn't given: the check is the reward.

Then run `/generate` again. It finds the new challenge, adds its row with an ID (filler only, as above), and keeps
everything already in the file. Write its `rule` and `region`, and remove its `"excluded"`. Don't write challenge rows or IDs yourself: a row with no
`ChallengeData` behind it can never be completed, and IDs come only from `/generate` (see [ID blocks](#id-blocks)).

**Tribe names.** A tribe is named from its ClassData ("TerrariaAliens" becomes "Terraria Aliens"). Rename it in its
`ap_items.Tribe` row if you like. Its battle checks and packs are named after it, so they follow the new name.

**Themed packs (optional).** Packs are dealt at random each seed. To make one pack always hold the same cards, list them
in it:

```json
{"key": "pack:Basic:Companion:MyMod-1", "id": 106000, "name": "MyMod Troll Pack",
 "cards": ["card:Troll", "card:TrollKing", "card:TrollShaman"]}
```

**Groups (optional).** `/generate` adds your cards to some of the base game's card groups (see
[The base game's groups](#the-base-games-groups)). You can add cards to groups, or make groups of your own for your
challenges' rules.

## 3. Test it

[Load it](#load-it) as a player would, generate a seed, then host it and connect from the game with your mod enabled.
If your file has a problem, generating fails with an error that names the field. In game, the Archipelago mod checks
your mod is loaded and that everything the seed names exists.

## 4. Ship it

Include the file with your mod (in its folder, or on its page), and point players to
[Part 1](#part-1-using-a-mods-content) for loading it.

### Getting your file built in

A file can also ship inside `wildfrost.apworld` itself (its `official` folder), so players get it with the apworld
and don't need to download or copy anything besides the apworld. To get yours built in:

1. Finish the file: every challenge has its `rule` and `region` (or stays `"excluded"` on purpose), and the tribe and
   pack names read well.
2. Test it ([Test it](#3-test-it)): generate seeds with the Tribes option on All and on Modded Only if you add tribes,
   and playtest some seeds.
3. Open an issue on the [Wildfrost Archipelago GitHub](https://github.com/martin-servold/WFM-Archipelago/issues) with
   your mod's name, its GUID, a link to it (the Workshop page), the extension file attached, and what you tested.

Only a mod's own author can ask for its file to be built in: an enthusiast's file for someone else's mod needs that
author's permission, given in the issue.

The maintainer checks it loads and generates, then adds it to the next apworld release and to
[Extensions already built](#extensions-already-built).

To update a built-in file, open an issue the same way with the new file and a higher version. Until the next apworld
release, ship the new file with your mod as well: a loose file with a higher version overrides the built-in one
([Load it](#load-it)). Versions compare number by number (`1.10.0` is newer than `1.9.0`).

## Updating your mod

Restart the game with the new version of your mod and run `/generate <your mod's GUID>` again. It finds your
existing file in the Extensions folder (or the `folder=` you give) by its GUID and updates it, keeping its name and IDs.

- Everything that already has an ID keeps it, and new content gets the next free ID in your mod's block. Never edit IDs by
  hand, and never reuse one: seeds already played depend on them.
- What you wrote by hand stays: challenge rules, regions, names, `excluded` and `true_final`, tribe names, battle
  names you changed, themed packs (their cards and names) and groups. A themed pack's cards don't count toward the
  plain packs, and a themed pack with none of its cards left becomes a plain one again.
- Content your mod no longer has is listed in a note, and its IDs go into `retired` in the file, so they're never
  given to anything else. If that content comes back, it gets its old ID back.
- Changing the name (`name=`) changes every pack's key and every item name, so the packs get new IDs and players need
  the new name in their options. `/generate` says so; give the file a new version.
- Raise the version whenever you ship a changed file: `/generate <GUID> <version>`. A seed records which file it was
  generated with, and Universal Tracker refuses to track it with any other, so a player can't mix up two versions'
  content by accident. The error names the version the seed needs and the one the player has, so a new number for
  every new file tells players which file to get.

## File reference

`/generate` writes all of this. The reference is for reading the file and making hand edits.

| Key | What it holds |
|---|---|
| `format` | Always `1` |
| `mod`, `guid`, `version`, `id_salt` | Your extension's name, your mod's GUID, the file's version, and the salt (only there when a clash moved your [ID block](#id-blocks)) |
| `clans` | Your shared pool clans and their pack labels (only there when several of your tribes draw one pool of yours) |
| `reuses` | Cards of other clans that your clans' own pools also hold, by clan |
| `cards` | Your reward cards, by kind (`companions`, `items`, `charms`), then by clan |
| `ap_items` | Archipelago items, by kind: `Pack`, `Charm`, `Pet`, `Tribe` |
| `ap_locations` | Checks: `battles`, `challenges`, and `twins` and `spares` ("#2" checks) |
| `leaders` | Your tribes' leaders and what they apply |
| `start_decks` | Your tribes' starting decks, for `["starts_with", card]` |
| `groups` | Card groups for rules |
| `bells` | Your storm bells and their storm points |
| `removes` | Base-game content your mod takes out |
| `retired` | IDs of content your mod no longer has, by key (`items` and `locations`), so they're never reused |

### Clans

A card, pack or charm belongs to a clan: `General` (the game's Snow pools count as General), `Basic`
(Snowdwellers), `Magic` (Shademancers), `Clunk` (Clunkmasters), one of your tribes by its ClassData name, or one of
your shared pool clans.

A **shared pool clan** is a reward pool of your own that several of your tribes draw from, for example an
`EnemyItemPool` that all your tribes have. `/generate` makes it a clan named `<your GUID>.pool.<pool name>`
(`EnemyItemPool`, `EnemyUnitPool` and `EnemyCharmPool` make one clan, `...pool.Enemy`) and lists it under `clans`
with the label its packs show:

```json
"clans": {"dev.wildfrost.MyMod.pool.Enemy": "Enemy"}
```

Its packs are named "MyMod Enemy Item Pack 1". Change the label to rename them all. A pool only one of your tribes
draws stays that tribe's own clan.

Cards of other clans that your pools also hold (base-game cards, usually) stay in their own packs. `/generate` lists
them under `reuses`, by the clan whose pools hold them:

```json
"reuses": {"dev.wildfrost.MyMod.pool.Enemy": ["FrostBell", "CardUpgradeSpice"], "dev.wildfrost.MyMod.Frost": ["Peppering"]}
```

Logic then counts such a pack by the share of its cards your tribe can be offered (a Snowdweller pack holding one of
your three cards counts as a third of a pack), and such a charm whole. A seed with your tribe keeps those packs and
charms even when no tribe in it draws their clan (a Modded Only seed, say).

### Cards

```json
"cards": {
  "companions": {"Basic": [{"key": "card:dev.wildfrost.MyMod.Troll", "name": "Troll", "applies": ["Shroom"], "traits": ["Smackback"]}]}
}
```

`key` is `card:` plus the CardData name (charms: the CardUpgradeData name). `applies` and `traits` come from the game
and feed the `applies` and `trait` rules.

### Items

- **Pack:** the key is `pack:<clan>:<Companion or Item>:<your extension's name>-<number>`, and a row needs only its
  `key` and `id`. The apworld reads the clan and kind from the key, and names the pack "MyMod Snowdweller Companion
  Pack 2" (a tribe's packs by the tribe's item name, so renaming the tribe renames them). A themed pack can have its
  own `name`. Your cards of one clan and kind (your Snowdweller companions, say) are dealt evenly across the packs of
  that same clan and kind, so the number of packs sets their size. `/generate` makes one pack for every 3 cards. Each
  clan and kind you have cards of needs at least one pack, and no more packs than cards.
- **Charm:** one item per charm. The key is `charm:<clan>:<the charm's CardUpgradeData name>`, and a row needs only its
  `key` and `id`.
- **Pet:** `pet:` plus the pet's internal name.
- **Tribe:** `tribe:` plus the ClassData name. `shares` names the other clans whose pools your tribe draws from: a
  vanilla clan (`Basic`, `Magic` or `Clunk`), your shared pool clans, or a list of several. `"general": false` says
  your tribe's reward pools leave out General's. Logic counts the packs of exactly those clans (and General's,
  unless left out) for your tribe's runs, plus the cards its pools reuse (see [Clans](#clans)). `/generate` writes
  them from your tribes' reward pools. A tribe with no
  leaders can't be played, so `/generate` leaves it out.

### Locations

- **Battles:** keys are `battle:<area 0-2>:<BattleData>:<run tribe>`, one row for each tribe the battle can be won
  with. For each of your tribes, `/generate` writes a row for every base-game battle and every battle of yours.
  A row only needs its `key` and `id`; the apworld works out the rest:
  - The area and run tribe come from the key.
  - A base-game battle's map tier, boss flag and title come from the base game's.
  - The name is built like the base game's, from the area, the title and the run tribe's item name:
    `Area 1 Battle - The Snowbo Squad (Bogfolk)`. Renaming the tribe's item renames all its battles automatically.

  A battle of your own also needs its `tier` (the map tier it's in, 0-8) and a `title`. `boss` and `true_final` are
  false unless the row says otherwise. A `name` written on a row replaces the built one, and any other field you write
  replaces the worked-out value; `area` and `run_tribe` must match the key.

  `true_final` marks a True Final Boss fight: a tribe's own row of the base game's true final boss, and any battle of
  yours in the True Final Boss's map tier (`"tier": 8`). A True Final Boss fight needs the storm
  bells to reach it, and is only in seeds whose goal goes past there. `/generate` sets it automatically based on the battle pool it's in.

  There are no battle locks: in the base game some battles only appear once a tribe is unlocked, but under Archipelago
  every battle can come up in every run.

  Keep every battle row, even if your mod adds many tribes. A seed with 5 or more tribes drops the regular battles
  itself when it has room (see [Good to know](#good-to-know)), and needs them back when it doesn't. A row deleted by
  hand comes back the next time you run `/generate`, with a new ID.
- **Challenges:** keys are `challenge:<ChallengeData name>`. The game reports a challenge done when its ChallengeData
  completes, so nothing else is needed in game.
- **twins:** `{"<key>": id}`: A double ("My Challange #2") check for a tribe's bosses. They're in the seed unless it
  has far more checks than items (see [Good to know](#good-to-know)).
- **spares:** `{"<key>": id}`: "#2" checks that only appear when a seed is short of checks for all its items, or
  has less than 15% of its checks left for filler.
  `/generate` writes one for each of your challenges and battles; there's nothing to do.

Only battles in the map's battle pools come up in a run. A battle your mod starts some other way never becomes a check.

### Removes

```json
"removes": {"cards": ["Egg"], "charms": ["CardUpgradeInk"], "battles": ["Mimiks"],
            "challenges": ["Challenge Charm 23"], "bells": ["9.MoreEnemiesInBossBattles"], "pets": ["BerryPet"]}
```

Names are the vanilla game's internal names. Challenges that become impossible drop out of the seed. A removed pet
isn't an item in the seed, and is never the starting pet.

Bosses can be removed, as long as every boss tier keeps a boss: every run's map deals one from each. The tiers are
the Area 1 bosses (tier 2: `Split Boss`, `Frenzy Boss`), the Area 2 bosses (tier 5: `Toadstool Boss`,
`Clunker Boss`), the Final Boss (tier 7: `Final Boss`) and the True Final Boss (tier 8: `Final Final Boss`). A tier
keeps a boss if one of the base ones stays, or if your mod adds a boss of its own there. A file that empties a tier
won't load, and `/generate` warns you when it writes one; a seed whose mods empty a tier together won't generate.

To replace the True Final Boss, remove `Final Final Boss` and add your own fight in tier 8 (it gets `true_final`, see
[Locations](#locations)). Archipelago counts a True Final Boss win the way the game records one, so your fight has to
end the run as a True Final Boss win, as the base game's does.

The base tribes can't be removed: `removes` has no entry for them. Players who want only your tribes use the Tribes
option (Modded Only). If the storm bells left can't reach the True Final Boss's 10 storm points, it appears at the
maximum the player can reach.

## Rules

A challenge's `rule` is a list whose first word is its form. Card names are CardData names without `card:`. A rule
may name the base game's cards, items and groups and your own, but not another extension's.

For worked examples, see the base game's own file,
[`base.wildfrost.json`](apworld/wildfrost/base.wildfrost.json): it's in the same format as yours, and every base-game
challenge's `rule` and `region` is written there (under `ap_locations.challenges`), with the `groups` they use. A few
from it:

| Challenge | Its rule |
|---|---|
| Kill 3 Demonized enemies | `["or", [["has", "pet:DemonPet", 1], ["applies", "Demonize"]]]` |
| Recycle 20 Junk | `["or", [["trait", "Recycle"], ["starts_with", "SunShard"]]]` |
| Ritual (sacrifice allies) | `["two_of", "sacrifice"]` |
| Block 10 hits with Clunkers | `["or", [["starts_with", "clunkers"], ["any_card", "clunkers"]]]` |
| One Punch | `["clan_kit", {"starts_with": "Sword", "area_kit": true}]` |

| Rule | Needs |
|---|---|
| `["card", "Troll"]` | That card's pack, and a tribe that can be offered it |
| `["cards", ["Troll", "TrollHammer"]]` | All of those cards |
| `["any_card", "shell"]` | Any card of a group or list. Add `["Basic"]` as a third entry to keep one clan's |
| `["two_of", "shroom"]` | Two different cards of a group or list |
| `["with", "Troll", "spice"]` | A card together with any one of a group or list |
| `["applies", "Shroom"]` | Any card that applies the effect, or a tribe whose leaders do |
| `["trait", "Smackback"]` | Any card with the trait, or a tribe whose leaders have it |
| `["tribe", "Magic"]` | That tribe |
| `["starts_with", "Sword"]` | A tribe whose starting deck has the card, or any of a group's cards (`"clunkers"`); yours count, from `start_decks` |
| `["clan_kit", {...}]` | A run of one clan with packs: see below |
| `["packs", "Basic", "Companion", 2]` | That many packs a run of the clan can draw from (`""` for companion and item packs together, `Charm` for charms) |
| `["bell", "MyMod.TrollBell"]` | Enough storm bells to ring that bell |
| `["battle", "Mimiks"]` | Whatever winning that battle needs |
| `["has", "pet:MyMod.Toadie", 1]` | An item, by key |
| `["all", [keys]]`, `["any", [keys], 2]` | All of the items, or that many of them |
| `["and", [rules]]`, `["or", [rules]]` | All of the rules, or any one |

An item named by `has`, `all` or `any` counts for logic even when it's normally only useful (a pet or a map event).
A challenge whose rule needs an item the seed doesn't have (a tribe the player's Tribes option left out, for example)
is left out of that seed.

`kits`
What logic assumes a run needs to get to a certain area/boss.

`clan_kit` takes:

- `clan`: the tribe (otherwise any tribe will do)
- `starts_with`: instead of `clan`, any tribe whose starting deck has this card
- `companions`, `items`: that many companion or item packs
- `charms`: that many charms
- `cards`: that many companion and item packs together
- `forced_extra`: one more pack when the player forces storm bells
- `area_kit`: also the challenge region's kit (see [Regions](#regions)), for that same clan. Areas 3 and 4 add their
  kit to every challenge anyway, but for any tribe; use `area_kit` when the run must be the tribe this rule is about,
  for example "win a run with Snowdwellers using only X". In Area 2 a challenge only gets a kit this way.

### Regions

`region` says how far into a run the challenge can be done. It adds a **kit**, the packs logic expects a run to need
to get that far, on top of the rule. Packs count from what one tribe's runs can draw (General unless its pools leave
it out, the tribe's own and the clans it shares):

| Region | Adds |
|---|---|
| `Area 1` | Nothing |
| `Area 2` | Nothing, unless the rule's `clan_kit` uses `area_kit`: then the Final Boss kit |
| `Area 3` | The Final Boss kit (a run that can win): 1 companion pack, and 1 item pack or 6 charms |
| `Area 4` | The True Final Boss kit: 2 companion packs, 2 item packs and 3 charms |

Add `"true_final": true` to a challenge that *is* the True Final Boss fight ("beat the Heart of the Storm with X"). It
then also needs the storm bells for it, and it's left out of seeds whose goal doesn't go there.

### Effect and trait names

Rules use the game's internal names, as your file's `applies` and `traits` lists show them. Most match what players see, but
not all:

| Players see | The game's name |
|---|---|
| Bom | `Weakness` |
| Ink | `Null` |
| Frenzy | `MultiHit` |
| Overburn | `Overload` |

Others in the base game include `Shell`, `Block`, `Spice`, `Shroom`, `Snow`, `Frost`, `Teeth`, `Haze`, `Demonize` and
`Scrap`. Traits use their keyword names: `Smackback`, `Consume`, `Barrage`, `Aimless`, `Zoomlin` and so on. A rule
naming an effect or trait that nothing in the seed has is an error, which catches typos.

### The base game's groups

| Group | What it holds | `/generate` adds your cards that |
|---|---|---|
| `shell` | cards that give Shell | apply Shell, are items, and don't have Consume |
| `block` | cards that give Block | apply Block and don't have Consume |
| `spice` | cards that give Spice | apply Spice |
| `teeth` | cards that give Teeth | apply Teeth |
| `clunkers` | Clunkers | are Clunkers |
| `summon` | cards that summon allies (the Masks, and Shademancer leaders) | have the Summon keyword |
| `shroom` | cards that give Shroom | (add yours by hand) |
| `frenzy` | cards that give Frenzy | (add yours by hand) |
| `sacrifice` | cards that sacrifice allies or cards | (add yours by hand) |

What you add to a group by hand stays when you run `/generate` again. A group can also list `"tribe:<clan>"`, for a
clan whose leaders do what the group stands for. Rules that don't need a group use `["applies", ...]` or
`["trait", ...]` instead (Demonize and Haze, for example), which count your cards without any listing. "Summon" is a
trait `/generate` writes for any card that summons an ally (not one that adds a card to your hand).

## Known unsupported content

- New map tiers or areas
- Battles started outside the map's battle pools (from a mod's own events, for example)
- New map events and node types (they aren't items, so they're never locked)
- Cards handed out outside the tribes' reward pools (a mod's own events or shops)
- Changes to vanilla cards (logic uses the base game's data)
- Content created during a run rather than at load
- Changes to Wildfrost's own unlock and progression systems

## Good to know

- **More items than checks:** an extension that adds many items and few checks fills the seed with spare "#2" checks
  until at least 15% of the checks are left for filler, then, if the spares run out before every item has a check,
  with fuller packs. That works, but challenges for your content are better, so `/generate` suggests adding some
  when your items outnumber your checks.
- **More checks than items:** a tribe brings a check for every battle, so a seed with your tribes can have far more
  checks than items. With 5 or more tribes in a seed, every tribe's regular battles stop being checks, keeping only
  the bosses, if at least 15% of the checks are still left for filler, adding spare "#2" checks to challenges to get
  there if needed. Then the seed drops every boss's "#2" check (the base game's and yours), and after those the charm
  challenges' "#2"s, a whole group at a time, under the same 15% rule.
- **Several mods together:** players can pick any mods whose extensions they have. Each mod's cards go only into its
  own packs. One mod's battles get no checks for another mod's tribes.
- **Tribes option:** players can run only your tribes (Modded Only) or only the vanilla ones (Vanilla Only), and the
  Modded Clans option can keep half or a quarter of your tribes (rounded up), picked at random. Without a tribe, its battle checks go, and so do the packs and charms of any clan no remaining tribe draws from (a tribe
  draws from General unless its pools leave it out, its own pools and the clans it shares). Challenges that need what's gone are left out. In a
  Vanilla Only seed your tribes stay locked in game, but your cards and charms that are added to the vanilla pools are
  still available.
- **Leaders:** the Archipelago mod finds a run's leader by the game's own miniboss flag, so leaders with a card type
  of their own (like Companion Start's) work with traps, boons and DeathLink.
- **Mods that aren't picked:** if a player has your mod enabled but their seed doesn't use your extension, your cards
  are offered from the start, your tribes send no checks, and the Archipelago mod warns about both.

## ID blocks

Every item and check in your file has an Archipelago ID. **You never pick one:** `/generate` gives each new card,
pack, battle and challenge the next free ID, and keeps the IDs already in the file. Don't edit or reuse IDs by hand.
Seeds already played depend on them.

Each mod's IDs come from its own block of 2,000, so two mods' IDs never mix. The block comes from the mod's GUID: the
first 4 bytes of its SHA-256 hash, and the IDs run from 100,000 + block × 2,000. The file doesn't list the block. The
apworld works it out from the GUID and refuses any ID outside it, so no file can take another mod's IDs, and there's
no registry to keep. `/generate`'s summary shows your range ("IDs 3810960040000-3810960041999").

Two GUIDs can hash to the same block, though rarely: about 1 in 400,000 with 100 mods. Archipelago then loads only one
of the two files, with an error that names the clash. To fix it, one of the two mods moves to a new block with a salt:

```
/generate <your mod's GUID> <new version> salt=1
```

The salt is `id_salt` in the file (0 when it's not there). Every ID in the file moves to the new
block, so give it a new version: seeds made with the old file still need the old file.
