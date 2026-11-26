"""
Extension files: content from other Wildfrost mods (PLAN.md §10, built from 2026-11-15).

A mod's creator ships one `<Mod>.wildfrost.json` file; the player who generates puts it loose in
Archipelago's custom_worlds folder, beside wildfrost.apworld (Archipelago only picks up .apworld files
and folders there, so the file is left alone). Approved mods' files can instead ship inside the apworld, in
OFFICIAL_DIR; a loose file of the same mod with a higher version overrides a built-in one (load). It's read here when the apworld is imported, before the
world class is built, so its items and locations join the data package. Each slot then picks which
installed extensions it uses with the Mod Content option; content of an extension a slot didn't pick is
never in that slot's seed.

The file holds rows in data.py's shape, written in game by the client's /generate command, with IDs
frozen from version to version. IDs come from the mod's block: block n is ID_BASE + n * BLOCK_SIZE up
to the next block, for items and locations alike (they're separate ID spaces). The block is a hash of
the mod's GUID (block_for; the user's call, 2026-11-24), so no registry is needed and no file can take
another mod's block; on the rare clash of two mods, one raises its "id_salt" for a new block. Rules are data in the
Checks tab's form, never code (rules.extension_rule turns them into rule objects).

A file that fails its checks is left out with an error in the log, and a yaml that asks for it fails
with that error, so a broken file never takes the rest of the world down with it.

Format 1:
{
  "format": 1,
  "mod": "MyMod",                       # its name in the Mod Content option and in display names
  "guid": "author.wildfrost.mymod",     # the game's mod GUID, which the client checks is loaded
  "version": "1.0.0",                   # the extension's version (Universal Tracker checks it matches)
  "id_salt": 0,                         # optional (default 0): raised only when two mods' blocks clash
  "cards": {                            # the reward cards it adds: by kind, then clan (the game's reward pools)
    "companions": {"Basic": [{"key": "card:Troll", "name": "Troll", "applies": ["Shroom"]}]},
    "items": {"General": [{"key": "card:TrollHammer", "name": "Troll Hammer", "applies": ["MyMod.Bog"]}]},
    "charms": {"General": [{"key": "card:CardUpgradeBog", "name": "Bog Charm"}]}
  },                                    # "applies": what the card applies (game names), for ["applies", ...]
  "ap_items": {                         # Archipelago items, by kind: packs, charm items and pets
    "Pack": [                           # clan and card_kind from the key; named "MyMod General Item Pack 1"
      {"key": "pack:General:Item:MyMod-1", "id": 106000},
      {"key": "pack:Basic:Companion:MyMod-1", "id": 106003, "name": "MyMod Troll Pack", "cards": ["card:Troll"]}
    ],
    "Charm": [{"key": "charm:General:CardUpgradeBog", "id": 106001}],   # its card's charm, named as the card
    "Pet": [{"key": "pet:MyMod.Toadie", "name": "Toadie Pet", "id": 106002}],
    "Tribe": [{"key": "tribe:MyMod.Bogfolk", "name": "Bogfolk", "id": 106004, "shares": "Basic"}]
  },
  "leaders": {"MyMod.Bogfolk": [{"key": "MyMod.BogKing", "applies": ["Shroom"], "traits": []}]},
  "start_decks": {"MyMod.Bogfolk": ["Sword", "SnowStick", "Woodhead"]},
  "ap_locations": {                     # Archipelago checks
    "battles": [                        # one per run tribe, and a spare "#2" each
      {"key": "battle:1:BogTrolls:Basic", "id": 106000, "title": "The Bog Trolls", "tier": 4},
      {"key": "battle:0:Snowbos:MyMod.Bogfolk", "id": 106007}
    ],                                  # see "Battle rows" below
    "challenges": [
      {"key": "challenge:MyMod Challenge 1", "name": "Challenge - Kill 5 Trolls", "id": 106003,
       "text": "Kill 5 Trolls", "region": "Area 2", "rule": ["applies", "MyMod.Bog"], "excluded": false}
    ],
    "twins": {"battle:0:Frenzy Boss:MyMod.Bogfolk": 106005},   # "#2" checks always in the seed (bosses)
    "spares": {"challenge:MyMod Challenge 1": 106006}           # "#2" checks only when a seed needs room
  },
  "groups": {"shroom": ["TrollShroom"], "applies:Bog": ["TrollHammer", "CardUpgradeBog"]},
  "bells": [{"name": "MyMod.TrollBell", "points": 2}],
  "removes": {"cards": ["Egg"], "charms": ["CardUpgradeInk"], "battles": ["Mimiks"], "challenges": ["Challenge Charm 23"],
              "bells": ["9.MoreEnemiesInBossBattles"]},
  "retired": {"items": {"pack:Basic:Item:MyMod-4": 106009}, "locations": {}}
}

Pack and charm rows (the user's call, 2026-11-25) need only "key" and "id" too. A pack's clan and kind are in its
key (pack:<clan>:<Companion/Item>:<mod>-<n>), and it's named "<mod> <clan label> <kind> Pack <n>" (a tribe's by its
item name); a themed pack may have its own name, and needs one if its key doesn't end in a number. A charm's key is
charm:<clan>:<its CardUpgradeData>, and it's named as that card. Listed fields win, if they match the key.

Battle rows (the user's calls, 2026-11-25) need only "key" and "id". The area and run tribe are in the key
(battle:<area 0-2>:<BattleData>:<run tribe>); a base game battle's tier, boss and True Final Boss flag come
from ours. The name is made like ours, "Area 2 Battle - The Bog Trolls (Snowdwellers)", from the area, the
title (ours for a base game battle) and the run tribe's item name, so renaming a tribe renames its battles.
A battle of the mod's own needs its "tier" and a "title" (or a "name"); "boss" and "true_final" default to
false. Any field a row lists wins ("area" and "run_tribe" must match the key). There are no tribe locks:
every battle can come up in every run, so an older file's "tribe" is ignored.

"retired" (written by /generate; found in review, 2026-11-24) keeps the IDs of keys the mod no longer has, by
key, so they're never given to new content (seeds already played may hold them); a key that comes back gets
its ID back. No live item or location may use a retired ID.

Tribes (the user's calls, 2026-11-16): a "Tribe" item adds a playable tribe, by its ClassData name. Its
runs draw from General, Snow, its "shares" clan (Basic, Magic or Clunk: the vanilla pools it also has) and
its own cards, filed under its ClassData name like a clan's. It gets battle checks like a vanilla clan (the
file lists them, run_tribe its ClassData; /generate writes one per base battle, the bosses' "#2" as
twins), and a Victory; a win with it counts toward Goal Clans Required. The client keeps it locked at tribe
select until its item arrives. "leaders" lists its leaders' effects, for ["applies", ...], and "start_decks" the
cards its runs start with, for ["starts_with", card].

A mod's cards are dealt only into its own packs (the user's call, 2026-11-15), so it needs at least one
pack for each clan and kind it has cards of, and no more packs than cards. A pack may list its cards
("cards": a themed pack, the same every seed; the user's call, 2026-11-15); the others are dealt at
random among its packs without a list.

"removes" names the base game's content the mod takes out (by CardData, CardUpgradeData, BattleData and
ChallengeData and storm bell names). A slot using the extension leaves those out (WildfrostWorld.removed),
and so any challenge whose needs are then impossible (rules.CardRules raises Impossible), such as a New
Challenge whose storm bell is gone. If the bells left can't reach the True Final Boss's 10 storm points,
the Lumin Vase appears at the most they reach instead (the user's call, 2026-11-15; world.true_final_points). The tribes, the bosses
and the Final Boss can't be removed: runs, wins and the goal are built on them.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from . import data

FORMAT = 1
SUFFIX = ".wildfrost.json"
# Built-in ("official") extension files: shipped inside the apworld in this folder (the user's call, 2026-11-24).
OFFICIAL_DIR = "official"
# Overrides where extensions are looked for (os.pathsep-separated folders); the tests use it.
FOLDER_ENV = "WILDFROST_EXTENSIONS_DIR"
ID_BASE = 100_000
BLOCK_SIZE = 2_000  # the user's call, 2026-11-15


def block_for(guid: str, salt: int = 0) -> int:
    """
    A mod's ID block: the first 4 bytes of the SHA-256 of its GUID (with "#<salt>" when the salt isn't 0).
    Up to 2^32 blocks keeps IDs under 9 * 10^12, well inside Archipelago's 2^53. Mirrored in the client's
    ExtensionGenerator.BlockFor.
    """
    text = guid if salt == 0 else f"{guid}#{salt}"
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:4], "big")

# Size caps (the user's call, 2026-11-24). The ID block already caps the entries at 2,000; these stop a broken or
# hostile file from eating memory or crashing the import. Terraria, the biggest so far, is 200 KB with rules 3 deep.
MAX_FILE_BYTES = 5 * 1024 * 1024
# The map tier of the True Final Boss fight (the game's "Final Final Boss"): a battle of an extension's own there
# is a True Final Boss fight too.
TRUE_FINAL_TIER = 8
MAX_RULE_DEPTH = 32

CLAN_NAMES = ("General", "Basic", "Magic", "Clunk")
CARD_KINDS = ("Companion", "Item")
# Area 4: the True Final Boss kit's packs (Sunbringer, the fight itself, its bells too; the user's call, 2026-11-16).
REGIONS = ("Area 1", "Area 2", "Area 3", "Area 4")
# Rule forms an extension may use (rules.extension_rule); the first word of each list.
RULE_FORMS = ("has", "all", "any", "packs", "and", "or", "card", "cards", "with", "any_card", "two_of", "tribe", "bell",
              "battle", "applies", "trait", "clan_kit", "starts_with")
CLAN_KIT_KEYS = {"clan": str, "companions": int, "items": int, "charms": int, "cards": int, "forced_extra": bool,
                 "area_kit": bool, "starts_with": str}
REMOVE_KINDS = ("cards", "charms", "battles", "challenges", "bells")
CARD_SECTIONS = {"companions": "Companion", "items": "Item", "charms": "Charm"}


class ExtensionError(ValueError):
    pass


def _battle_name(key: str) -> str:
    return key.split(":")[2]


# What "removes" may name: the base game's content (data.py), by game name.
BASE_NAMES = {
    "cards": {key.removeprefix("card:") for key, _, info in data.CARDS if info["kind"] != "Charm"},
    "charms": {key.removeprefix("card:") for key, _, info in data.CARDS if info["kind"] == "Charm"},
    "battles": {_battle_name(key) for key, _, _, _ in data.LOCATIONS if key.startswith("battle:")},
    "challenges": {info["internal"] for key, _, _, info in data.LOCATIONS
                   if key.startswith("challenge:") and not info["internal"].startswith("ap:")},
    "bells": {name for name, _, _ in data.BELLS},
}
# Bosses, the Final Boss and the True Final Boss: every run's path and the goal go through them.
# The map's boss tiers (each area's bosses, the Final Boss, the True Final Boss) and the base game's bosses in each.
# Every run's map deals a boss from each tier, so a tier must keep one: a mod may remove bosses as long as each tier
# still has a base boss or one of its own (the user's call, 2026-11-26; before, no boss could be removed).
BOSS_TIERS: dict[int, set[str]] = {}
for _key, _, _, _info in data.LOCATIONS:
    if _key.startswith("battle:") and not _key.endswith("#2") and (_info["boss"] or _info["true_final"]):
        BOSS_TIERS.setdefault(_info["tier"], set()).add(_battle_name(_key))


def own_boss_tiers(ext: "Extension") -> set[int]:
    """The boss tiers an extension has battles of its own in."""
    return {info["tier"] for key, _, _, info in ext.locations
            if key.startswith("battle:") and not key.endswith("#2") and _battle_name(key) not in BASE_BATTLES
            and (info["boss"] or info["true_final"])}


def empty_boss_tiers(removed_battles: set[str], own_tiers: set[int]) -> list[int]:
    """Boss tiers left with no boss: every base one removed and none of the mods' own there."""
    return sorted(tier for tier, bosses in BOSS_TIERS.items() if bosses <= removed_battles and tier not in own_tiers)


def boss_tier_names(tiers: list[int]) -> str:
    return ", ".join(f"map tier {t} ({', '.join(sorted(BOSS_TIERS[t]))})" for t in tiers)


# What a battle row may leave out (the user's call, 2026-11-25: short rows, renaming a tribe once renames its
# battles). Its area and run tribe are in its key; for the base game's battles, the rest is here, with the
# title read from our names ("Area 1 Battle - The Snowbo Squad (Snowdwellers)"). A field the row lists wins.
_BATTLE_NAME = re.compile(r"^Area \d (?:Battle|Boss) - (.+) \([^()]+\)$")
BASE_BATTLES: dict[str, dict] = {}
for _key, _name, _, _info in data.LOCATIONS:
    if _key.startswith("battle:") and not _key.endswith("#2"):
        _title = _BATTLE_NAME.match(_name)
        BASE_BATTLES.setdefault(_battle_name(_key), {
            "title": _title.group(1) if _title else _battle_name(_key),
            **{field_: _info[field_] for field_ in ("tier", "boss", "true_final")}})
BASE_TRIBE_NAMES = {key.removeprefix("tribe:"): name for key, name, _, _ in data.ITEMS if key.startswith("tribe:")}


# How /generate labels a clan in its pack names (a tribe's packs use the tribe's item name).
PACK_LABELS = {"General": "General", "Basic": "Snowdweller", "Magic": "Shademancer", "Clunk": "Clunkmaster"}


def battle_name(area: int, boss: bool, title: str, tribe_name: str) -> str:
    """A battle check's name, as the base game's are made."""
    return f"Area {area + 1} {'Boss' if boss else 'Battle'} - {title} ({tribe_name})"


@dataclass
class Extension:
    mod: str
    guid: str
    version: str
    id_block: int
    path: str
    hash: str  # of the file's bytes: Universal Tracker refuses a rebuild with a different file
    cards: list = field(default_factory=list)       # rows (key, name, info), as data.CARDS
    items: list = field(default_factory=list)       # rows (key, name, id, info), as data.ITEMS
    locations: list = field(default_factory=list)   # rows (key, name, id, info), as data.LOCATIONS
    groups: dict = field(default_factory=dict)      # group name -> card names
    removes: dict = field(default_factory=dict)     # REMOVE_KINDS -> base game names taken out
    bells: dict = field(default_factory=dict)       # its own storm bells: game name -> storm points
    tribes: dict = field(default_factory=dict)      # its tribes: ClassData name -> the vanilla clan it shares pools with
    leaders: dict = field(default_factory=dict)     # its tribes' leaders, as data.LEADERS
    start_decks: dict = field(default_factory=dict)  # its tribes' starting decks, as data.START_DECKS

    def meta(self) -> dict:
        """What slot_data records of it."""
        return {"mod": self.mod, "guid": self.guid, "version": self.version, "hash": self.hash}


def folders() -> list[str]:
    override = os.environ.get(FOLDER_ENV)
    if override:
        return [f for f in override.split(os.pathsep) if f]
    try:
        import worlds  # the package is mid-import here, but user_folder is set before any world loads
        folder = getattr(worlds, "user_folder", None)
    except ImportError:
        folder = None
    return [folder] if folder else []


def _require(value, kind, what: str):
    if not isinstance(value, kind) or isinstance(value, bool) and kind is not bool:
        raise ExtensionError(f"{what} should be {kind.__name__ if isinstance(kind, type) else kind}")
    return value


def _rows(value, what: str) -> list:
    """A list of objects (a section's rows)."""
    _require(value, list, what)
    for i, row in enumerate(value):
        if not isinstance(row, dict):
            raise ExtensionError(f"{what}[{i}] should be an object ({{...}})")
    return value


def _text(value, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExtensionError(f"{what} should be a non-empty string")
    return value


def _count(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def check_rule(rule, what: str, clans: tuple = CLAN_NAMES, depth: int = 1) -> None:
    """
    Checks a rule's shape; which items and cards it names is checked once every file is read. clans: the
    clans it may name (General and the vanilla three, and the extension's own tribes).
    """
    if depth > MAX_RULE_DEPTH:
        raise ExtensionError(f"{what}: rules nest more than {MAX_RULE_DEPTH} deep")
    if not isinstance(rule, list) or not rule or rule[0] not in RULE_FORMS:
        raise ExtensionError(f"{what}: a rule is a list starting with one of {', '.join(RULE_FORMS)}")
    form = rule[0]
    if form in ("and", "or"):
        if len(rule) != 2 or not isinstance(rule[1], list) or not rule[1]:
            raise ExtensionError(f"{what}: [\"{form}\", [rule, ...]]")
        for child in rule[1]:
            check_rule(child, what, clans, depth + 1)
    elif form == "has" and not (len(rule) == 3 and isinstance(rule[1], str) and _count(rule[2])):
        raise ExtensionError(f"{what}: [\"has\", item key, count] (count 1 or more)")
    elif form == "all" and not (len(rule) == 2 and isinstance(rule[1], list) and all(isinstance(k, str) for k in rule[1])):
        raise ExtensionError(f"{what}: [\"all\", [item key, ...]]")
    elif form == "any" and not (len(rule) == 3 and isinstance(rule[1], list) and all(isinstance(k, str) for k in rule[1])
                                and _count(rule[2]) and rule[2] <= len(rule[1])):
        raise ExtensionError(f"{what}: [\"any\", [item key, ...], count] (count from 1 to the list's length)")
    elif form == "packs" and not (len(rule) == 4 and rule[1] in clans and rule[2] in ("Companion", "Item", "Charm", "")
                                  and isinstance(rule[3], int)):
        raise ExtensionError(f"{what}: [\"packs\", clan, Companion/Item/Charm/\"\", count]")
    elif form == "card" and not (len(rule) == 2 and isinstance(rule[1], str)):
        raise ExtensionError(f"{what}: [\"card\", card name]")
    elif form == "two_of" and not (len(rule) == 2 and isinstance(rule[1], (str, list))):
        raise ExtensionError(f"{what}: [\"two_of\", group name or [card name, ...]]")
    elif form == "any_card" and not (len(rule) in (2, 3) and isinstance(rule[1], (str, list))
                                     and (len(rule) == 2 or isinstance(rule[2], list) and set(rule[2]) <= set(clans))):
        raise ExtensionError(f"{what}: [\"any_card\", group name or [card name, ...]] (and optionally [clan, ...])")
    elif form == "cards" and not (len(rule) == 2 and isinstance(rule[1], list) and rule[1]):
        raise ExtensionError(f"{what}: [\"cards\", [card name, ...]], cards together")
    elif form == "with" and not (len(rule) == 3 and isinstance(rule[1], str) and isinstance(rule[2], (str, list))):
        raise ExtensionError(f"{what}: [\"with\", card name, group name or [card name, ...]]")
    elif form == "trait" and not (len(rule) == 2 and isinstance(rule[1], str) and rule[1]):
        raise ExtensionError(f"{what}: [\"trait\", trait name] (a card with it, or a clan whose leaders have it)")
    elif form == "clan_kit" and not (len(rule) == 2 and isinstance(rule[1], dict) and all(
            k in CLAN_KIT_KEYS and isinstance(v, CLAN_KIT_KEYS[k]) and not (CLAN_KIT_KEYS[k] is int and isinstance(v, bool))
            for k, v in rule[1].items()) and rule[1].get("clan", "Basic") in clans[1:]):
        raise ExtensionError(f"{what}: [\"clan_kit\", {{...}}] takes {', '.join(CLAN_KIT_KEYS)} (clan: Basic/Magic/Clunk or its tribe)")
    elif form == "starts_with" and not (len(rule) == 2 and isinstance(rule[1], str) and rule[1]):
        raise ExtensionError(f"{what}: [\"starts_with\", card or group] (a tribe whose starting deck has it)")
    elif form == "applies" and not (len(rule) == 2 and isinstance(rule[1], str) and rule[1]):
        raise ExtensionError(f"{what}: [\"applies\", effect name] (a card that applies it, or a clan whose leaders do)")
    elif form == "battle" and not (len(rule) == 2 and isinstance(rule[1], str)):
        raise ExtensionError(f"{what}: [\"battle\", BattleData name]")
    elif form == "tribe" and not (len(rule) == 2 and rule[1] in clans[1:]):
        raise ExtensionError(f"{what}: [\"tribe\", Basic/Magic/Clunk or one of its tribes]")
    elif form == "bell" and not (len(rule) == 2 and isinstance(rule[1], str)):
        raise ExtensionError(f"{what}: [\"bell\", storm bell name]")


def parse(path: str, raw: bytes) -> Extension:
    if len(raw) > MAX_FILE_BYTES:
        raise ExtensionError(f"the file is over {MAX_FILE_BYTES // (1024 * 1024)} MB")
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ExtensionError(f"not valid JSON: {e}") from e
    except RecursionError as e:
        raise ExtensionError("not valid JSON: nested too deep") from e
    _require(doc, dict, "the file")
    if doc.get("format") != FORMAT:
        raise ExtensionError(f"format should be {FORMAT} (this apworld reads format {FORMAT})")
    guid = _text(doc.get("guid"), "guid")
    salt = doc.get("id_salt", 0)
    if not isinstance(salt, int) or isinstance(salt, bool) or salt < 0:
        raise ExtensionError("id_salt should be a whole number, 0 or more")
    # The ID block comes from the GUID and salt; files don't list it (the user's call, 2026-11-25: it could only
    # ever hold the one right number). An older file's "id_block" is still checked.
    block = block_for(guid, salt)
    if "id_block" in doc and doc["id_block"] != block:
        raise ExtensionError(f"id_block should be {block}, the block of guid {guid}"
                             + (f" with id_salt {salt}" if salt else "") + " (or leave it out): write the file with /generate")
    ext = Extension(mod=_text(doc.get("mod"), "mod"), guid=guid, version=_text(doc.get("version"), "version"),
                    id_block=block, path=path, hash=hashlib.sha256(raw).hexdigest()[:16])
    if not re.fullmatch(r"[A-Za-z0-9 _.\-]+", ext.mod):
        raise ExtensionError("mod should be letters, digits, spaces, '_', '.' or '-'")
    low = ID_BASE + ext.id_block * BLOCK_SIZE
    high = low + BLOCK_SIZE

    def in_block(value, what: str) -> int:
        value = _require(value, int, what)
        if not low <= value < high:
            raise ExtensionError(f"{what} {value} is outside block {ext.id_block} ({low}-{high - 1})")
        return value

    # Its tribes (the user's calls, 2026-11-16), read first: they're clans in the rest of the file.
    ap_items = _require(doc.get("ap_items", {}), dict, "ap_items")
    tribes: dict[str, str] = {}  # ClassData name -> the vanilla clan whose pools it shares
    tribe_names = dict(BASE_TRIBE_NAMES)  # ClassData name -> its item's name, for battles' names
    for i, item in enumerate(_rows(ap_items.get("Tribe", []), "ap_items.Tribe")):
        what = f"ap_items.Tribe[{i}]"
        key = _text(item.get("key"), f"{what}.key")
        tribe = key.removeprefix("tribe:")
        if not key.startswith("tribe:") or not tribe or ":" in tribe or tribe in CLAN_NAMES or tribe in tribes:
            raise ExtensionError(f"{what}: a tribe's key is 'tribe:<ClassData>', one per tribe, not a vanilla clan")
        shares = item.get("shares")
        if shares not in CLAN_NAMES[1:]:
            raise ExtensionError(f"{what}.shares should be Basic, Magic or Clunk (the vanilla clan whose pools it draws from)")
        tribes[tribe] = shares
        tribe_names[tribe] = _text(item.get("name"), f"{what}.name")
    ext.tribes = tribes
    clans = (*CLAN_NAMES, *tribes)
    run_tribes = (*CLAN_NAMES[1:], *tribes)

    # Its reward cards by kind (the user's layout, 2026-11-15). Charms are cards too (data.CARDS has them):
    # the client locks each card in its kind's reward pool.
    cards_by_kind = _require(doc.get("cards", {}), dict, "cards")
    for section in cards_by_kind:
        if section not in CARD_SECTIONS:
            raise ExtensionError(f"cards.{section}: cards has {', '.join(CARD_SECTIONS)}")
    # ...then by clan (the user's layout, 2026-11-15): cards.companions.Basic, ...
    for section, kind in CARD_SECTIONS.items():
        by_clan = _require(cards_by_kind.get(section, {}), dict, f"cards.{section}")
        for clan, entries in by_clan.items():
            if clan not in clans:
                raise ExtensionError(f"cards.{section}.{clan}: clans are {', '.join(clans)}")
            for i, card in enumerate(_rows(entries, f"cards.{section}.{clan}")):
                what = f"cards.{section}.{clan}[{i}]"
                key = _text(card.get("key"), f"{what}.key")
                if not key.startswith("card:"):
                    raise ExtensionError(f"{what}.key should start with 'card:'")
                info = {"kind": kind, "clan": clan, "ext": ext.mod}
                # What it applies and its traits (from the dump), for the "applies" and "trait" rule forms.
                for field in ("applies", "traits"):
                    names = _require(card.get(field, []), list, f"{what}.{field}")
                    if not all(isinstance(a, str) and a for a in names):
                        raise ExtensionError(f"{what}.{field} lists names")
                    if names:
                        info[field] = list(names)
                ext.cards.append((key, _text(card.get("name"), f"{what}.name"), info))

    fixed_cards: set[str] = set()
    for kind in ap_items:
        if kind not in ("Pack", "Charm", "Pet", "Tribe"):
            raise ExtensionError(f"ap_items.{kind}: an extension's items are Pack, Charm, Pet or Tribe")
    for kind, entries in ap_items.items():
        for i, item in enumerate(_rows(entries, f"ap_items.{kind}")):
            what = f"ap_items.{kind}[{i}]"
            key = _text(item.get("key"), f"{what}.key")
            # Packs and charms may leave out their name, clan, kind and card (the user's call, 2026-11-25): the key
            # holds them, and the name is made as /generate makes it. A field the row lists wins, if it matches.
            parts = key.split(":", 3)
            derived = kind in ("Pack", "Charm") and len(parts) >= 3
            name = None if derived and "name" not in item else _text(item.get("name"), f"{what}.name")
            item_id = in_block(item.get("id"), f"{what}.id")
            clan = item.get("clan", parts[1] if derived else None)
            if kind not in ("Pet", "Tribe") and (clan not in clans or derived and clan != parts[1]):
                raise ExtensionError(f"{what}.clan should be one of {', '.join(clans)}, and the one in its key")
            if kind == "Tribe":
                info = {"kind": "Tribe", "shares": item["shares"]}
            elif kind == "Pet":
                # A pet the mod adds: an item like ours, so the client keeps it locked until it arrives.
                if not key.startswith("pet:"):
                    raise ExtensionError(f"{what}: a pet's key is 'pet:<CardData>'")
                info = {"kind": "Pet"}
            elif kind == "Pack":
                card_kind = item.get("card_kind", parts[2] if len(parts) == 4 else None)
                # The clan and kind lead the key: fill_packs and the client group packs by them.
                if card_kind not in CARD_KINDS or not key.startswith(f"pack:{clan}:{card_kind}:"):
                    raise ExtensionError(f"{what}: a pack has card_kind Companion or Item and a key 'pack:<clan>:<card_kind>:...'")
                info = {"kind": "Pack", "clan": clan, "card_kind": card_kind}
                if name is None:
                    # "pack:Basic:Companion:MyMod-2": "MyMod Snowdweller Companion Pack 2"; a tribe's by its item's
                    # name, not prefixed twice when it starts with the mod's ("Terraria Aliens").
                    number = parts[3].rsplit("-", 1)[-1]
                    if not number.isdigit():
                        raise ExtensionError(f"{what}: a pack whose key doesn't end in -<number> needs a name")
                    label = PACK_LABELS.get(clan) or tribe_names[clan]
                    shown = label if label.startswith(ext.mod) else f"{ext.mod} {label}"
                    name = f"{shown} {card_kind} Pack {int(number)}"
                if "cards" in item:
                    # A themed pack: these cards, every seed.
                    listed = _require(item["cards"], list, f"{what}.cards")
                    own = {c[0] for c in ext.cards if c[2]["clan"] == clan and c[2]["kind"] == card_kind}
                    wrong = [c for c in listed if c not in own]
                    if not listed or wrong:
                        raise ExtensionError(f"{what}.cards lists this extension's {clan} {card_kind} cards"
                                             + (f"; not one: {', '.join(map(str, wrong))}" if wrong else ""))
                    twice = [c for c in listed if c in fixed_cards]
                    if twice or len(set(listed)) != len(listed):
                        raise ExtensionError(f"{what}.cards: a card can only be in one pack ({', '.join(twice) or 'repeated'})")
                    fixed_cards.update(listed)
                    info["cards"] = list(listed)
            elif kind == "Charm":
                # "charm:<clan>:<CardUpgradeData>": its card is that charm card, and it's named as the card is.
                card = _text(item.get("card", "card:" + parts[2] if derived else None), f"{what}.card")
                found = [c for c in ext.cards if c[0] == card and c[2]["kind"] == "Charm"]
                if not key.startswith(f"charm:{clan}:") or not found or derived and card != "card:" + parts[2]:
                    raise ExtensionError(f"{what}: a charm has a key 'charm:<clan>:<card>' naming one of this "
                                         "extension's cards of kind Charm")
                if name is None:
                    name = found[0][1]
                info = {"kind": "Charm", "clan": clan, "card": card}
            else:
                raise ExtensionError(f"{what}.kind should be Pack, Charm, Pet or Tribe")
            info["ext"] = ext.mod
            ext.items.append((key, name, item_id, info))

    ap_locations = _require(doc.get("ap_locations", {}), dict, "ap_locations")
    for section in ap_locations:
        if section not in ("battles", "challenges", "twins", "spares"):
            raise ExtensionError(f"ap_locations.{section}: ap_locations has battles, challenges, twins and spares")
    entries = [(f"ap_locations.{section}[{i}]", section, loc) for section in ("battles", "challenges")
               for i, loc in enumerate(_rows(ap_locations.get(section, []), f"ap_locations.{section}"))]
    for what, section, loc in entries:
        key = _text(loc.get("key"), f"{what}.key")
        # A battle's name may be left out: it's made from its area, title and run tribe (see BASE_BATTLES).
        name = None if key.startswith("battle:") and "name" not in loc else _text(loc.get("name"), f"{what}.name")
        loc_id = in_block(loc.get("id"), f"{what}.id")
        if not key.startswith("battle:" if section == "battles" else "challenge:"):
            raise ExtensionError(f"{what}.key: {section} keys start with '{'battle:' if section == 'battles' else 'challenge:'}'")
        if key.startswith("battle:"):
            # Only the key and ID are needed (the user's call, 2026-11-25): the area and run tribe are in the
            # key, and a base game battle's tier, boss and title come from ours. A field the row lists wins,
            # except that the area and run tribe must match the key.
            parts = key.split(":")
            if len(parts) != 4 or parts[1] not in ("0", "1", "2") or parts[3] not in run_tribes:
                raise ExtensionError(f"{what}: a battle's key is 'battle:<area 0-2>:<BattleData>:<run tribe>' "
                                     "(Basic, Magic, Clunk or one of its tribes)")
            area, run_tribe = int(parts[1]), parts[3]
            if loc.get("area", area) != area or loc.get("run_tribe", run_tribe) != run_tribe:
                raise ExtensionError(f"{what}: area and run_tribe, when listed, should match the key ({area}, {run_tribe})")
            base = BASE_BATTLES.get(parts[2])
            own = base is None
            # No "tribe" lock (the user's call, 2026-11-25): every battle can come up in every run, so a lock in
            # an older file is ignored.
            if own and "tier" not in loc:
                raise ExtensionError(f"{what}.tier: needed for a battle of the mod's own (the map tier it's in)")
            tier = _require(loc.get("tier", base and base["tier"]), int, f"{what}.tier")
            boss = _require(loc.get("boss", base["boss"] if base else False), bool, f"{what}.boss")
            # "true_final": the True Final Boss fight (its kit and bells, and only in seeds whose goal goes there):
            # a tribe's own row of the base game's, or a battle of the extension's own in the True Final Boss's
            # map tier, which must say so (the user's call, 2026-11-24: else it'd be a check in every seed, with
            # no bells in its logic).
            true_final = _require(loc.get("true_final", bool(base and base["true_final"])), bool, f"{what}.true_final")
            if own and tier == TRUE_FINAL_TIER and not true_final:
                raise ExtensionError(f"{what}: a battle in tier {TRUE_FINAL_TIER} is a True Final Boss fight: "
                                     "\"true_final\": true")
            # On a base game battle it's only the True Final Boss fight's own (found in review, 2026-11-25: any base
            # battle row of a mod's tribe could say true_final).
            if true_final and not (own and tier == TRUE_FINAL_TIER or not own and run_tribe in tribes and base["true_final"]) \
                    or not own and not true_final and base["true_final"]:
                raise ExtensionError(f"{what}.true_final: only a battle of its own in tier {TRUE_FINAL_TIER}, or a tribe's "
                                     "own row of the base game's True Final Boss (which always has it)")
            if name is None:
                if own and "title" not in loc:
                    raise ExtensionError(f"{what}: a battle of the mod's own needs a name or a title")
                title = _text(loc["title"], f"{what}.title") if "title" in loc else base["title"]
                name = battle_name(area, boss, title, tribe_names[run_tribe])
            info = {"area": area, "boss": boss, "run_tribe": run_tribe, "true_final": true_final, "tier": tier}
        elif key.startswith("challenge:"):
            internal = key.removeprefix("challenge:")
            if internal.startswith("ap:"):
                raise ExtensionError(f"{what}: 'challenge:ap:' keys are this apworld's own New Challenges")
            region = loc.get("region", "Area 1")
            if region not in REGIONS:
                raise ExtensionError(f"{what}.region should be one of {', '.join(REGIONS)}")
            rule = loc.get("rule")
            if rule is not None:
                check_rule(rule, f"{what}.rule", clans)
            info = {"internal": internal, "text": loc.get("text", name), "region": region, "rule": rule,
                    "excluded": _require(loc.get("excluded", False), bool, f"{what}.excluded")}
            # The True Final Boss fight itself, like our Sunbringer: its bells too, and filler only (or left
            # out) where the goal doesn't go there (locations.true_final_challenge).
            if _require(loc.get("true_final", False), bool, f"{what}.true_final"):
                info["true_final"] = True
        else:
            raise ExtensionError(f"{what}.key should start with 'battle:' or 'challenge:'")
        info["ext"] = ext.mod
        ext.locations.append((key, name, loc_id, info))
    # "#2" checks, {original key: id}, each its original with another ID (the user's call, 2026-11-16):
    # twins are always in the seed (a tribe's bosses, like ours), spares only in a seed short of room
    # (locations.spare_checks).
    firsts = {key: (name, info) for key, name, _, info in ext.locations}
    for section, spare in (("twins", False), ("spares", True)):
        for key, loc_id in _require(ap_locations.get(section, {}), dict, f"ap_locations.{section}").items():
            if key not in firsts:
                raise ExtensionError(f"ap_locations.{section}: {key!r} isn't one of this extension's battles or challenges")
            name, info = firsts[key]
            ext.locations.append((key + "#2", name + " #2", in_block(loc_id, f"ap_locations.{section}.{key}"),
                                  {**info, "second": True, **({"spare": True} if spare else {})}))

    # Its tribes' leaders and what they apply, for ["applies", ...] and ["trait", ...] (as the base file's).
    for tribe, leaders in _require(doc.get("leaders", {}), dict, "leaders").items():
        if tribe not in tribes:
            raise ExtensionError(f"leaders.{tribe}: leaders are listed for this extension's own tribes")
        rows = []
        for i, leader in enumerate(_rows(leaders, f"leaders.{tribe}")):
            what = f"leaders.{tribe}[{i}]"
            row = {"key": _text(leader.get("key"), f"{what}.key")}
            for field in ("applies", "traits"):
                names = _require(leader.get(field, []), list, f"{what}.{field}")
                if not all(isinstance(a, str) and a for a in names):
                    raise ExtensionError(f"{what}.{field} lists names")
                if names:
                    row[field] = list(names)
            rows.append(row)
        ext.leaders[tribe] = rows

    # Its tribes' starting decks (CardData names), for ["starts_with", card] (the user's call, 2026-11-24).
    for tribe, deck in _require(doc.get("start_decks", {}), dict, "start_decks").items():
        if tribe not in tribes:
            raise ExtensionError(f"start_decks.{tribe}: starting decks are listed for this extension's own tribes")
        if not all(isinstance(c, str) and c for c in _require(deck, list, f"start_decks.{tribe}")):
            raise ExtensionError(f"start_decks.{tribe} lists card names")
        ext.start_decks[tribe] = list(deck)

    # Its cards go only into its own packs: each clan and kind it has cards of needs a pack, and no more
    # packs than cards (an empty pack would be an item that gives nothing).
    # Themed packs hold their own cards; the rest are dealt among the packs without a list.
    for clan in clans:
        for kind in CARD_KINDS:
            cards = sum(1 for key, _, info in ext.cards if info["clan"] == clan and info["kind"] == kind
                        and key not in fixed_cards)
            packs = sum(1 for _, _, _, info in ext.items if info["kind"] == "Pack" and info["clan"] == clan
                        and info["card_kind"] == kind and "cards" not in info)
            if cards and not packs:
                raise ExtensionError(f"{cards} {clan} {kind} cards but no {clan} {kind} pack to deal them into")
            if packs > cards:
                raise ExtensionError(f"{packs} {clan} {kind} packs for {cards} cards")

    # Its own storm bells (HardModeModifierData names), so its challenges can need one (["bell", name]);
    # they also count toward the storm points a seed can reach.
    for i, bell in enumerate(_rows(doc.get("bells", []), "bells")):
        what = f"bells[{i}]"
        name = _text(bell.get("name"), f"{what}.name")
        points = _require(bell.get("points"), int, f"{what}.points")
        if name in BASE_NAMES["bells"] or name in ext.bells:
            raise ExtensionError(f"{what}: storm bell {name!r} is already loaded")
        if points < 0:
            raise ExtensionError(f"{what}.points should be 0 or more")
        ext.bells[name] = points

    removes = _require(doc.get("removes", {}), dict, "removes")
    for kind, names in removes.items():
        if kind not in REMOVE_KINDS:
            raise ExtensionError(f"removes.{kind}: removes takes {', '.join(REMOVE_KINDS)}")
        if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
            raise ExtensionError(f"removes.{kind} should be a list of names")
        unknown = [n for n in names if n not in BASE_NAMES[kind]]
        if unknown:
            raise ExtensionError(f"removes.{kind} names what the base game doesn't have: {', '.join(unknown)}")
        if kind == "battles":
            empty = empty_boss_tiers(set(names), own_boss_tiers(ext))
            if empty:
                raise ExtensionError(f"removes.battles takes every boss of {boss_tier_names(empty)}: every run's map needs "
                                     "one there, so keep one or add a boss of your own in that tier")
        ext.removes[kind] = set(names)

    groups = _require(doc.get("groups", {}), dict, "groups")
    for group, cards in groups.items():
        if not isinstance(cards, list) or not all(isinstance(c, str) for c in cards):
            raise ExtensionError(f"groups.{group} should be a list of card names")
        ext.groups[group] = list(cards)

    retired = _require(doc.get("retired", {}), dict, "retired")
    for space, rows in (("items", ext.items), ("locations", ext.locations)):
        ids = {}
        for key, value in _require(retired.get(space, {}), dict, f"retired.{space}").items():
            ids[in_block(value, f"retired.{space}.{key}")] = key
        if len(ids) != len(retired.get(space, {})):
            raise ExtensionError(f"retired.{space} gives one ID to two keys")
        live = sorted(f"{key} ({row_id})" for key, _, row_id, _ in rows if row_id in ids)
        if live:
            raise ExtensionError(f"retired IDs are in use again: {', '.join(live)} (never reuse an ID)")
    for space in retired:
        if space not in ("items", "locations"):
            raise ExtensionError(f"retired.{space}: retired has items and locations")
    return ext


def _check_against(ext: Extension, keys: set, names: set, item_ids: set, loc_ids: set, card_keys: set) -> None:
    """No clash with what's already loaded (ours, then earlier extensions), nor within the file itself."""
    keys, names, item_ids, loc_ids, card_keys = set(keys), set(names), set(item_ids), set(loc_ids), set(card_keys)
    for key, name, item_id, _ in ext.items:
        if key in keys or name in names or item_id in item_ids:
            raise ExtensionError(f"item {key!r} ({name!r}, {item_id}) clashes with one already loaded or in this file")
        keys.add(key), names.add(name), item_ids.add(item_id)
    for key, name, loc_id, _ in ext.locations:
        if key in keys or name in names or loc_id in loc_ids:
            raise ExtensionError(f"location {key!r} ({name!r}, {loc_id}) clashes with one already loaded or in this file")
        keys.add(key), names.add(name), loc_ids.add(loc_id)
    for key, _, _ in ext.cards:
        if key in card_keys:
            raise ExtensionError(f"card {key!r} is already loaded, or listed twice in this file")
        card_keys.add(key)
    own_cards = {key.removeprefix("card:") for key, _, _ in ext.cards}
    own_cards |= {info["card"].removeprefix("card:") for _, _, _, info in ext.items if info["kind"] == "Charm"}
    # A group lists its cards, and "tribe:<clan>" for clans whose leaders do it (the user's call, 2026-11-15).
    tribes = {f"tribe:{clan}" for clan in (*CLAN_NAMES[1:], *ext.tribes)}
    for group, cards in ext.groups.items():
        unknown = [c for c in cards if c not in own_cards and c not in tribes]
        if unknown:
            raise ExtensionError(f"groups.{group} names cards this extension doesn't add: {', '.join(unknown)}")


def official_files() -> list[tuple[str, bytes]]:
    """The extension files built into the apworld (OFFICIAL_DIR): (where it is, its bytes). Read through the
    package, so they're found inside the .apworld zip too."""
    try:
        folder = resources.files(__package__ or __name__).joinpath(OFFICIAL_DIR)
        if not folder.is_dir():
            return []
        entries = sorted((e for e in folder.iterdir() if e.name.endswith(SUFFIX)), key=lambda e: e.name)
        return [(f"{OFFICIAL_DIR}/{e.name}", e.read_bytes()) for e in entries]
    except (OSError, ModuleNotFoundError, TypeError) as e:
        logging.error(f"Wildfrost: the built-in extension files couldn't be read: {e}")
        return []


def version_key(version: str) -> tuple[int, ...]:
    """Versions compare by their numbers in order (1.10 is newer than 1.9); one without numbers is oldest."""
    return tuple(int(n) for n in re.findall(r"\d+", version))


def load(paths: list[str] | None = None,
         official: list[tuple[str, bytes]] | None = None) -> tuple[dict[str, Extension], dict[str, str]]:
    """Reads every extension file; returns the loaded ones by mod name and the failed ones' errors.

    Built-in files come first, then the loose ones. When a loose file is the same mod (same GUID) as a built-in
    one, the higher version is used and the other is left out with a warning; on a tie the built-in one wins (the user's call,
    2026-11-24: a player can fix a broken built-in file with a newer loose one). If the chosen file then
    clashes with something already loaded, the next one is tried."""
    if paths is None:
        paths = sorted(str(p) for folder in folders() if os.path.isdir(folder)
                       for p in Path(folder).iterdir() if p.name.endswith(SUFFIX))
        official = official_files() if official is None else official
    entries = [(where, raw, True) for where, raw in (official or [])] + [(path, None, False) for path in paths]

    loaded: dict[str, Extension] = {}
    failed: dict[str, str] = {}
    keys = {r[0] for r in data.LOCATIONS} | {r[0] for r in data.ITEMS}
    names = {r[1] for r in data.LOCATIONS} | {r[1] for r in data.ITEMS}
    item_ids, loc_ids = {r[2] for r in data.ITEMS}, {r[2] for r in data.LOCATIONS}
    card_keys = {r[0] for r in data.CARDS}
    blocks: dict[int, str] = {}
    bells: set[str] = set()

    def fail(label: str, where: str, error: str) -> None:
        failed[label] = f"{Path(where).name}: {error}"
        logging.error(f"Wildfrost: extension {Path(where).name} left out: {error}")

    # Read and check each file on its own. A loose file joins the group of the built-in file with its GUID;
    # any other loose file is a group of its own (two loose copies of a mod still clash, so the player sees it).
    groups: list[list[tuple[Extension, bool]]] = []
    built_in_group: dict[str, list[tuple[Extension, bool]]] = {}
    for where, raw, built_in in entries:
        label = Path(where).name.removesuffix(SUFFIX)
        try:
            if raw is None:
                with open(where, "rb") as f:
                    raw = f.read(MAX_FILE_BYTES + 1)
            ext = parse(where, raw)
        except (TypeError, AttributeError, KeyError, ValueError, IndexError, RecursionError) as e:
            if isinstance(e, ExtensionError):
                fail(label, where, str(e))
            else:  # a shape parse's checks don't cover: still only this file fails, never the apworld's import
                fail(label, where, f"malformed ({type(e).__name__}: {e})")
            continue
        except OSError as e:
            fail(label, where, str(e))
            continue
        group = built_in_group.get(ext.guid)
        if group is None:
            group = []
            groups.append(group)
            if built_in:
                built_in_group[ext.guid] = group
        group.append((ext, built_in))

    for candidates in groups:
        # Highest version first; a built-in file before a loose one of the same version.
        candidates.sort(key=lambda c: (version_key(c[0].version), c[1]), reverse=True)
        errors = []
        for ext, built_in in candidates:
            try:
                if ext.mod in loaded:
                    raise ExtensionError(f"another file already loaded mod {ext.mod!r}")
                if ext.id_block in blocks:
                    raise ExtensionError(f"id_block {ext.id_block} is already {blocks[ext.id_block]}'s (a hash clash: "
                                         "one of the two raises its id_salt and runs /generate again)")
                _check_against(ext, keys, names, item_ids, loc_ids, card_keys)
                clashing = sorted(set(ext.bells) & bells)
                if clashing:
                    raise ExtensionError(f"storm bells {', '.join(clashing)} are already another extension's")
            except ExtensionError as e:
                errors.append((ext, str(e)))
                logging.error(f"Wildfrost: extension {Path(ext.path).name} left out: {e}")
                continue
            loaded[ext.mod] = ext
            blocks[ext.id_block] = ext.mod
            keys |= {r[0] for r in ext.items} | {r[0] for r in ext.locations}
            names |= {r[1] for r in ext.items} | {r[1] for r in ext.locations}
            item_ids |= {r[2] for r in ext.items}
            loc_ids |= {r[2] for r in ext.locations}
            card_keys |= {r[0] for r in ext.cards}
            bells |= set(ext.bells)
            logging.info(f"Wildfrost: loaded extension {ext.mod} {ext.version}{' (built in)' if built_in else ''} "
                         f"({len(ext.items)} items, {len(ext.locations)} locations)")
            tried = {id(e) for e, _ in errors}
            for other, other_built_in in candidates:
                if other is not ext and id(other) not in tried:
                    logging.warning(f"Wildfrost: {Path(other.path).name} ({'built in, ' if other_built_in else ''}"
                                    f"version {other.version}) left out: {Path(ext.path).name} has version "
                                    f"{ext.version} of {ext.guid}")
            break
        else:
            ext, error = errors[0]
            failed[ext.mod] = f"{Path(ext.path).name}: {error}"

    # A file left out while its mod loaded from another file isn't a failure of that mod (a yaml asking for the
    # mod would fail): it's filed under the file's own name instead.
    for label in [label for label in failed if label in loaded]:
        error = failed.pop(label)
        failed[error.split(": ", 1)[0]] = error
    return loaded, failed


LOADED, FAILED = load()
