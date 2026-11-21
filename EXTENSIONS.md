# Adding your mod to Wildfrost Archipelago

This guide is for Wildfrost mod creators who want their mod's content in [Archipelago](https://archipelago.gg) seeds.

You don't change your mod's code. You ship one extra file, `<YourMod>.wildfrost.json` (an **extension file**), that
tells the Archipelago world about your content. A tool in this repository writes most of it from a content dump of the
game. You then fill in a few things by hand, like what your challenges need.

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
- [Python](https://www.python.org/downloads/) 3.10 or newer
- A copy of this repository (the tool reads the base game's data from it)
- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.7 or newer and `wildfrost.apworld`, to test

## Step by step

### 1. Claim an ID block

Every mod gets its own block of 2,000 Archipelago IDs, so two mods never clash. Open an issue on
[this repository](https://github.com/martin-servold/WFM-Archipelago/issues) with your mod's name and GUID, and a block
number is added to the [registry](#id-block-registry) below. Use only your block, and keep it for every version.

### 2. Take two content dumps

The Archipelago mod writes `content_dump.txt` into its own folder when its `debug` setting is on. That's the Workshop
folder, for example:

- Windows: `C:\Program Files (x86)\Steam\steamapps\workshop\content\1811990\3831295900`
- Linux: `~/.steam/steam/steamapps/workshop/content/1811990/3831295900`

1. With the game closed, open `config.cfg` in that folder and set `System.Boolean : debug = True`.
2. **The base game's dump:** start the game with only the Archipelago mod enabled. Copy `content_dump.txt` somewhere
   safe, for example as `vanilla_dump.txt`.
3. **Your mod's dump:** enable your mod (and any mods it depends on), then **close the game and start it again**. Copy
   the new `content_dump.txt`, for example as `mymod_dump.txt`.

Restarting matters. A mod enabled from the Mods screen in a running game doesn't always finish loading all its content
(pets, for example), and the dump then misses it. Take your mod's dump with nothing else enabled that adds content.

### 3. Run the tool

From your copy of this repository:

```
python3 -I tools/make_extension.py --dump mymod_dump.txt --vanilla vanilla_dump.txt --mod MyMod --block 7
```

On Windows, use `py -3` in place of `python3`.

- `--mod` is your extension's name. Players type it into their options, and it starts your item names, so keep it
  short and readable.
- `--block` is your block number from the registry.
- `--guid` is your mod's GUID. Only needed when the dump lists more than one other mod (dependencies, for example).
- `--version` is the extension file's own version (default `1.0.0`). Raise it whenever you ship a new file.
- `--out` is where to write the file (default `MyMod.wildfrost.json` in the current folder).

The tool prints a summary and notes. Read the notes: they say what was skipped and what needs your attention.

### 4. Fill in what the tool can't know

Open the file and go through these.

**Challenges.** Each challenge your mod adds starts with `"region": "Area 1"` and no `rule`, which means it's in logic
from the very start. Give each one what it really needs (see [Rules](#rules)):

```json
{"key": "challenge:MyMod Kill Trolls", "name": "Challenge - Kill 5 Trolls", "id": 106003,
 "text": "Kill 5 Trolls", "region": "Area 2", "rule": ["any_card", "trolls"]}
```

Add `"excluded": true` to a challenge that's too luck-based to hold anything but filler.

**Tribe names.** A tribe is named from its ClassData ("TerrariaAliens" becomes "Terraria Aliens"). Rename it in its
`ap_items.Tribe` row if you like. The new name also appears in its battle checks the next time you run the tool.

**Themed packs (optional).** Packs are dealt at random each seed. To make one pack always hold the same cards, list them
in it:

```json
{"key": "pack:Basic:Companion:MyMod-1", "name": "MyMod Troll Pack", "id": 106000, "clan": "Basic",
 "card_kind": "Companion", "cards": ["card:Troll", "card:TrollKing", "card:TrollShaman"]}
```

**Groups (optional).** The tool adds your cards to the base game's card groups by the effect they apply. You can add
cards to groups, or make groups of your own for your challenges' rules.

### 5. Test it

1. Put your file in Archipelago's `custom_worlds` folder, next to `wildfrost.apworld`.
2. Make an options file with the Launcher's **Options Creator**: pick Wildfrost, add `MyMod` under **Mod Content**,
   then **Export Options** into Archipelago's `Players` folder.
3. Generate. If your file has a problem, the error names the field.
4. Host the seed, connect from the game with your mod enabled, and play a little. The Archipelago mod checks your mod
   is loaded and that everything the seed names exists in the game. If something's missing, it shows a toast and logs
   the details.

### 6. Ship it

Include the file with your mod (in its folder, or on its page) and tell players to:

1. Copy `MyMod.wildfrost.json` into Archipelago's `custom_worlds` folder on the computer that generates.
2. Add `MyMod` under **Mod Content** in their Wildfrost options (the Launcher's **Options Creator**).
3. Enable your mod in the game.

Only the person generating needs the file. Players who track with Universal Tracker need the same file too: it refuses
a different version of it.

## Updating your mod

Take a new dump of your mod and run the tool again with `--out` pointing at your existing file.

- Everything that already has an ID keeps it, and new content gets the next free ID in your block. Never edit IDs by
  hand, and never reuse one: seeds already played depend on them.
- What you wrote by hand stays: challenge rules, regions, names and `excluded`, tribe names, themed packs and groups.
- Content your mod no longer has is listed in a note, and its IDs stay retired.
- Raise `--version`. Universal Tracker uses the version and the file itself to match seeds.

## File reference

The tool writes all of this. The reference is for reading the file and making hand edits.

| Key | What it holds |
|---|---|
| `format` | Always `1` |
| `mod`, `guid`, `version`, `id_block` | Your extension's name, your mod's GUID, the file's version, your block |
| `cards` | Your reward cards, by kind (`companions`, `items`, `charms`), then by clan |
| `ap_items` | Archipelago items, by kind: `Pack`, `Charm`, `Pet`, `Tribe` |
| `ap_locations` | Checks: `battles`, `challenges`, and `twins` and `spares` ("#2" checks) |
| `leaders` | Your tribes' leaders and what they apply |
| `groups` | Card groups for rules |
| `bells` | Your storm bells and their storm points |
| `removes` | Base-game content your mod takes out |

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

`key` is `card:` plus the CardData name (charms: the CardUpgradeData name). `applies` and `traits` come from the dump
and feed the `applies` and `trait` rules.

### Items

- **Pack:** `card_kind` is `Companion` or `Item`, and the key starts with `pack:<clan>:<card_kind>:`. A clan and kind's
  cards are dealt evenly across its packs, so the number of packs sets their size. The tool makes one pack for every 3
  cards. Each of your clan-and-kind groups needs at least one pack, and no more packs than cards.
- **Charm:** one item per charm. `card` names the charm's card.
- **Pet:** `pet:` plus the pet's name, as the dump lists it.
- **Tribe:** `tribe:` plus the ClassData name, and `shares`: the vanilla clan (`Basic`, `Magic` or `Clunk`) whose
  pools your tribe also draws from. Logic counts that clan's packs for your tribe's runs.

### Locations

- **Battles:** keys are `battle:<area 0-2>:<BattleData>:<run tribe>`, one row for each tribe the battle can be won
  with. For each of your tribes, the tool writes a row for every base-game battle and every battle of yours.
  `true_final` marks a tribe's own row of the True Final Boss.
- **Challenges:** keys are `challenge:<ChallengeData name>`. The game reports a challenge done when its ChallengeData
  completes, so nothing else is needed in game.
- **twins:** `{"<key>": id}`: "#2" checks that are always in the seed (a tribe's bosses, like the base game's).
- **spares:** `{"<key>": id}`: "#2" checks that only appear when a seed is short of checks for all its items.

Only battles in the map's battle pools come up in a run. A battle your mod starts some other way never becomes a check.

### Removes

```json
"removes": {"cards": ["Egg"], "charms": ["CardUpgradeInk"], "battles": ["Mimiks"],
            "challenges": ["Challenge Charm 23"], "bells": ["9.MoreEnemiesInBossBattles"]}
```

Names are the game's. Challenges that become impossible drop out of the seed. The base tribes, the bosses and the
Final Bosses can't be removed. If the storm bells left can't reach the True Final Boss's 10 storm points, it appears
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
| `["clan_kit", {...}]` | A run of one clan with packs: see below |
| `["packs", "Basic", "Companion", 2]` | That many packs a run of the clan can draw from (`""` for companion and item packs together, `Charm` for charms) |
| `["bell", "MyMod.TrollBell"]` | Enough storm bells to ring that bell |
| `["battle", "Mimiks"]` | Whatever winning that battle needs |
| `["has", "pet:MyMod.Toadie", 1]` | An item, by key |
| `["all", [keys]]`, `["any", [keys], 2]` | All of the items, or that many of them |
| `["and", [rules]]`, `["or", [rules]]` | All of the rules, or any one |

`clan_kit` takes:

- `clan`: the tribe (otherwise any tribe will do)
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

Rules use the game's internal names, as the dump's "Card effects" section lists them. Most match what players see, but
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

| Group | Cards that |
|---|---|
| `shell` | apply Shell |
| `block` | apply Block |
| `frenzy` | give Frenzy |
| `shroom` | apply Shroom |
| `spice` | apply Spice |
| `haze` | apply Haze |
| `demonize` | apply Demonize |
| `teeth` | give Teeth |
| `clunkers` | are Clunkers |
| `sacrifice` | sacrifice allies or cards |

The tool adds your cards to these by the effect they apply (`sacrifice` excepted). A group can also list
`"tribe:<clan>"`, for a clan whose leaders do what the group stands for.

## Good to know

- **More items than checks:** an extension that adds many items and few checks fills the seed with spare "#2" checks,
  then with fuller packs. That works, but challenges for your content are better, so the tool suggests adding some
  when your items outnumber your checks.
- **Several mods together:** players can pick any mods whose extensions they have. Each mod's cards go only into its
  own packs. One mod's battles get no checks for another mod's tribes.
- **Mods that aren't picked:** if a player has your mod enabled but their seed doesn't use your extension, your cards
  are offered from the start, your tribes send no checks, and the Archipelago mod warns about both.

## ID block registry

Each block runs from 100,000 + block × 2,000, for 2,000 IDs.

| Block | Extension | Mod GUID |
|---|---|---|
| 0 | CompanionStart | `fuko.wildfrost.companionstart` |
