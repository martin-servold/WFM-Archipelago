# Adding your mod to Wildfrost Archipelago

This guide is for Wildfrost mod creators or enthusiasts who want a mod's content in
[Archipelago](https://archipelago.gg) seeds. If you're an enthusiast, please check the links at the bottom
([Extensions already built](#extensions-already-built)) for mod extensions already built and shared by the creators
of those mods.

You don't change your mod's code. You ship one extra file, `<YourMod>.wildfrost.json` (an **extension file**), that
tells the Archipelago world about your content. The Archipelago mod writes most of it for you, in game, from what your
mod has loaded. You then fill in a few things by hand, like what your challenges need.

With an extension file, players who pick your mod get:

| From your mod | In the seed |
|---|---|
| Companions, items and charms in the reward pools | Items: your cards come in packs of about 3, and each charm is an item of its own |
| Pets | Items, locked until found |
| Tribes | Items. Each tribe gets a check for every battle and boss, and a win with it counts toward the goal |
| Battles in the map's battle pools | Checks, one for each tribe a run can win them with |
| Challenges (ChallengeData) | Checks |
| Storm bells | Count toward the storm points a seed can reach; your challenges can require them |
| Removed base-game content (cards, battles, challenges, bells) | Left out of the seed |

## What you need

- Wildfrost with the Archipelago mod and your mod
- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.7 or newer and `wildfrost.apworld`, to test

## Step by step

### 1. Generate the file in game

1. Enable both the Archipelago mod and your mod (with any mods yours depends on), then **close the game and start it
   again**. A mod enabled from the Mods screen in a running game doesn't always finish loading all its content (pets,
   for example), and the file would then miss it.
2. On the main menu, press **Enter** to open the Archipelago log's text line, and type:

   ```
   /generate <your mod's GUID> <optional: version number>
   ```

   For example, `/generate yourname.wildfrost.mymod 1.0.0`. The version defaults to `1.0.0`. `/generate` on its own
   lists the loaded mods' GUIDs.

   The extension is named after your mod's title. Players type the name into their options yaml, and it prefixes your
   item names, so you may want a shorter one: add `name=MyMod` (in "double quotes" if it has spaces: `"name=My Mod"`).
   A rerun keeps the name the file already has.

   Names can't contain special characters, since the name is also the file's name: only A-Z, a-z, 0-9, spaces, `_`,
   `.` and `-`. Anything else is dropped from the default name ("VFX/SFX Tools" becomes "VFXSFX Tools"). If nothing is
   left (a title in another script, for example), the last part of your GUID is used, and if that's empty too,
   `/generate` asks you for a `name=`.

   Your mod's IDs come from a hash of its GUID ([ID blocks](#id-blocks)), so there's nothing to claim or register
   first.

The file is written to the game's save folder (the folder with `Player.log` in it), in `Archipelago/Extensions/`:

- Windows: `%USERPROFILE%\AppData\LocalLow\Deadpan Games\Wildfrost\Archipelago\Extensions`
- Linux (Proton): `~/.local/share/Steam/steamapps/compatdata/1811990/pfx/drive_c/users/steamuser/AppData/LocalLow/Deadpan Games/Wildfrost/Archipelago/Extensions`

That's neither Archipelago's own folder nor the Archipelago mod's folder (a Workshop update replaces the mod's folder,
which would delete your file). Nothing reads the file there: copy it next to `wildfrost.apworld` to use it
([step 3](#3-test-it)).

To write it somewhere else, add `folder=` with a full path, in "double quotes" if it has spaces:
`"folder=C:\Users\me\Documents\My Mod"`. A rerun looks for your existing file in that same folder, so give the same
`folder=` each time.

The log shows a summary and notes. Read the notes: they say what was skipped and what needs your attention.

Your content is told apart by its name: the modding API names everything after your mod's GUID
(`<GUID>.<name>`), so other mods can stay enabled. The one exception is `removes` (base-game content your mod takes
out), which can't be traced to a specific mod if multiple are enabled: generate with only your mod enabled if it removes
anything, or check that list.

### 2. Fill in what the game can't know

Open the file and go through these.

**Challenges.** Each challenge your mod adds starts with `"region": "Area 1"` and no `rule`, which means it's in logic
from the very start. Give each one what it really needs (see [Rules](#rules)):

```json
{"key": "challenge:MyMod Kill Trolls", "name": "Challenge - Kill 5 Trolls", "id": 106003,
 "text": "Kill 5 Trolls", "region": "Area 2", "rule": ["any_card", "trolls"]}
```

Add `"excluded": true` to a challenge that's too luck-based to hold anything but filler.

**Adding a challenge.** A check needs a real challenge in your mod: a `ChallengeData`, made with the modding API's
`ChallengeDataBuilder`. The game reports when it's completed, and that sends the check. Its listener decides what
counts:

- **Across runs:** a game stat adds up over every run until it reaches the goal ("apply 100 Spice", "kill 50
  enemies"). Most base-game challenges work this way.
- **At the end of a run:** one run's stats are checked when it ends.
- **Custom:** your mod's own code decides (the base game's "win without charms" and "beat a boss without Snow" are
  this kind).

Under Archipelago its `requires` chain is ignored and its in-game reward isn't given: the check is the reward.

Then run `/generate` again. It finds the new challenge, adds its row with an ID, and keeps everything already in the
file. Write its `rule` and `region` as above. Don't write challenge rows or IDs yourself: a row with no
`ChallengeData` behind it can never be completed, and IDs come only from `/generate` (see [ID blocks](#id-blocks)).

**Tribe names.** A tribe is named from its ClassData ("TerrariaAliens" becomes "Terraria Aliens"). Rename it in its
`ap_items.Tribe` row if you like. Its battle checks are named after it, so they follow the new name.

**Themed packs (optional).** Packs are dealt at random each seed. To make one pack always hold the same cards, list them
in it:

```json
{"key": "pack:Basic:Companion:MyMod-1", "id": 106000, "name": "MyMod Troll Pack",
 "cards": ["card:Troll", "card:TrollKing", "card:TrollShaman"]}
```

**Groups (optional).** `/generate` adds your cards to some of the base game's card groups (see
[The base game's groups](#the-base-games-groups)). You can add cards to groups, or make groups of your own for your
challenges' rules.

### 3. Test it

1. Put your file in Archipelago's `custom_worlds` folder, next to `wildfrost.apworld`. (When Archipelago is installed
   somewhere it can't write to, like a Linux package in `/opt`, its apworlds and these files go in the `worlds`
   folder of its user folder instead, such as `~/.local/share/Archipelago/worlds`.) Archipelago reads these files
   when it starts: after changing one, restart the Launcher and anything opened from it, Universal Tracker included.
2. Make an options file with the Launcher's **Options Creator**: pick Wildfrost, add `MyMod` under **Mod Content**,
   then **Export Options** into Archipelago's `Players` folder.
3. Generate. If your file has a problem, the error names the field.
4. Host the seed, connect from the game with your mod enabled, and play a little. The Archipelago mod checks your mod
   is loaded and that everything the seed names exists in the game. If something's missing, it shows a toast and logs
   the details.

### 4. Ship it

Include the file with your mod (in its folder, or on its page) and tell players to:

1. Copy `MyMod.wildfrost.json` into Archipelago's `custom_worlds` folder on the computer that generates.
2. Add `MyMod` under **Mod Content** in their Wildfrost options (the Launcher's **Options Creator**).
3. Enable your mod in the game.

The file is needed on the computer that generates the seed, and by anyone tracking the seed with Universal Tracker,
who needs the exact same file. Players who only play don't need it.

#### Built into the apworld

A file can also ship inside `wildfrost.apworld` itself (its `official` folder), so players get it with the apworld
and don't copy anything. Ask the apworld's maintainer. A built-in file is updated with each apworld release.

Players can still override a built-in file: a loose `MyMod.wildfrost.json` in `custom_worlds` with the same GUID is
used instead when its version is higher, so a fixed file can go out before the next apworld release. With the same
or a lower version, the built-in one is used. Either way, the log says which file was left out. Versions compare
number by number (`1.10.0` is newer than `1.9.0`).

## Updating your mod

Restart the game with the new version of your mod and run `/generate <your mod's GUID>` again. It finds your
existing file in the Extensions folder (or the `folder=` you give) by its GUID and updates it, keeping its name and IDs.

- Everything that already has an ID keeps it, and new content gets the next free ID in your mod's block. Never edit IDs by
  hand, and never reuse one: seeds already played depend on them.
- What you wrote by hand stays: challenge rules, regions, names, `excluded` and `true_final`, tribe names, battle
  names you changed, themed packs (their cards and names) and groups. A themed pack's cards don't count toward the plain packs, and a themed
  pack with none of its cards left becomes a plain one again.
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

A card, pack or charm belongs to a clan: `General` (every tribe can be offered it; the game's Snow pools count as
General), `Basic` (Snowdwellers), `Magic` (Shademancers), `Clunk` (Clunkmasters), or one of your tribes by its
ClassData name.

### Cards

```json
"cards": {
  "companions": {"Basic": [{"key": "card:Troll", "name": "Troll", "applies": ["Shroom"], "traits": ["Smackback"]}]}
}
```

`key` is `card:` plus the CardData name (charms: the CardUpgradeData name). `applies` and `traits` come from the game
and feed the `applies` and `trait` rules.

### Items

- **Pack:** the key is `pack:<clan>:<Companion or Item>:<your extension's name>-<number>`, and a row needs only its
  `key` and `id`. The apworld reads the clan and kind from the key, and names the pack "MyMod Snowdweller Companion
  Pack 2" (a tribe's packs by the tribe's item name, so renaming the tribe renames them). A themed pack can have its
  own `name`. A clan and kind's cards are dealt evenly across its packs, so the number of packs sets their size.
  `/generate` makes one pack for every 3 cards. Each of your clan-and-kind groups needs at least one pack, and no more
  packs than cards.
- **Charm:** one item per charm. The key is `charm:<clan>:<the charm's CardUpgradeData name>`, and a row needs only its
  `key` and `id`: it unlocks that charm card, and is named as the card.
- **Pet:** `pet:` plus the pet's internal name.
- **Tribe:** `tribe:` plus the ClassData name, and `shares`: the vanilla clan (`Basic`, `Magic` or `Clunk`) whose
  pools your tribe also draws from. Logic counts that clan's packs for your tribe's runs.

### Locations

- **Battles:** keys are `battle:<area 0-2>:<BattleData>:<run tribe>`, one row for each tribe the battle can be won
  with. For each of your tribes, `/generate` writes a row for every base-game battle and every battle of yours.
  A row only needs its `key` and `id`; the apworld works out the rest:
  - The area and run tribe come from the key.
  - A base-game battle's map tier, boss flag and title come from the base game's.
  - The name is built like the base game's, from the area, the title and the run tribe's item name:
    `Area 1 Battle - The Snowbo Squad (Bogfolk)`. Renaming a tribe item renames all its battles.

  A battle of your own also needs its `tier` (the map tier it's in, 0-8) and a `title`. `boss` and `true_final` are
  false unless the row says otherwise. A `name` written on a row replaces the built one, and any other field you write
  replaces the worked-out value; `area` and `run_tribe` must match the key.

  `true_final` marks a True Final Boss fight: a tribe's own row of the base game's (worked out), and any battle of
  yours in the True Final Boss's map tier (`"tier": 8`), which must have it. A True Final Boss fight needs the storm
  bells to reach it, and is only in seeds whose goal goes there. `/generate` sets it.

  There are no tribe locks: in the base game some battles only appear once a tribe is unlocked, but under Archipelago
  every battle can come up in every run. Older files' `"tribe"` field is ignored.
- **Challenges:** keys are `challenge:<ChallengeData name>`. The game reports a challenge done when its ChallengeData
  completes, so nothing else is needed in game.
- **twins:** `{"<key>": id}`: "#2" checks for a tribe's bosses, like the base game's. They're in the seed unless it
  has far more checks than items (see [Good to know](#good-to-know)).
- **spares:** `{"<key>": id}`: "#2" checks that only appear when a seed is short of checks for all its items.

Only battles in the map's battle pools come up in a run. A battle your mod starts some other way never becomes a check.

### Removes

```json
"removes": {"cards": ["Egg"], "charms": ["CardUpgradeInk"], "battles": ["Mimiks"],
            "challenges": ["Challenge Charm 23"], "bells": ["9.MoreEnemiesInBossBattles"]}
```

Names are the game's. Challenges that become impossible drop out of the seed. The base tribes, the bosses and the
Final Bosses can't be removed: a file that removes one won't load, and `/generate` warns you when it writes one. To
change a boss fight, keep its BattleData and change what's in it. If the storm bells left can't reach the True Final Boss's 10 storm points, it appears
at the most they reach.

## Rules

A challenge's `rule` is a list whose first word is its form. Card names are CardData names without `card:`. A rule
may name the base game's cards, items and groups and your own, but not another extension's.

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

`clan_kit` takes:

- `clan`: the tribe (otherwise any tribe will do)
- `starts_with`: instead of `clan`, any tribe whose starting deck has this card
- `companions`, `items`: that many companion or item packs
- `charms`: that many charms
- `cards`: that many companion and item packs together
- `forced_extra`: one more pack when the player forces storm bells
- `area_kit`: the region's kit (below), for that same clan

### Regions

`region` says how far into a run the challenge can be done. It adds a kit of packs on top of the rule:

| Region | Adds |
|---|---|
| `Area 1` | Nothing |
| `Area 2` | Nothing, unless the rule uses `area_kit` |
| `Area 3` | A won run: the Final Boss kit |
| `Area 4` | The True Final Boss kit's packs |

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

## Good to know

- **More items than checks:** an extension that adds many items and few checks fills the seed with spare "#2" checks,
  then with fuller packs. That works, but challenges for your content are better, so `/generate` suggests adding some
  when your items outnumber your checks.
- **More checks than items:** a tribe brings a check for every battle, so a seed with your tribes can have far more
  checks than items. Then it drops every boss's "#2" check (the base game's and yours), and after those the charm
  challenges' "#2"s, a whole group at a time, as long as at least 15% of its checks are still left for filler.
- **Several mods together:** players can pick any mods whose extensions they have. Each mod's cards go only into its
  own packs. One mod's battles get no checks for another mod's tribes.
- **Tribes option:** players can run only your tribes (Modded Only) or only the vanilla ones (Vanilla Only). Without
  a tribe, its battle checks go, and so do the packs and charms of any clan no remaining tribe draws from (a tribe
  draws from General, its own pools and the clan it shares). Challenges that need what's gone are left out.
- **Mods that aren't picked:** if a player has your mod enabled but their seed doesn't use your extension, your cards
  are offered from the start, your tribes send no checks, and the Archipelago mod warns about both.

## ID blocks

Every item and check in your file has an Archipelago ID. **You never pick one:** `/generate` gives each new card,
pack, battle and challenge the next free ID, and keeps the IDs already in the file. Don't edit or reuse IDs by hand.
Seeds already played depend on them.

Each mod's IDs come from its own block of 2,000, so two mods' IDs never mix. The block comes from the mod's GUID: the
first 4 bytes of its SHA-256 hash, and the IDs run from 100,000 + block × 2,000. The file doesn't list the block. The
apworld works it out from the GUID and refuses any ID outside it, so no file can take another mod's IDs, and there's
no registry to keep. `/generate`'s summary shows your range ("IDs 3810960040000-3810960041999"). Files written before
2026-11-25 list it as `id_block`, which is still checked.

Two GUIDs can hash to the same block, though rarely: about 1 in 400,000 with 100 mods. Archipelago then loads only one
of the two files, with an error that names the clash. To fix it, one of the two mods moves to a new block with a salt:

```
/generate <your mod's GUID> <new version> salt=1
```

The salt is `id_salt` in the file (0 when it's not there). Every ID in the file moves to the new
block, so give it a new version: seeds made with the old file still need the old file.

## Extensions already built

Extension files shared by the creators of these mods. Some are built into `wildfrost.apworld`, so there's nothing to
copy: just add the mod under **Mod Content**. For the others, copy the file into Archipelago's `custom_worlds` folder.

| Mod | Extension file | Built in |
|---|---|---|
| *None listed yet* | | |
