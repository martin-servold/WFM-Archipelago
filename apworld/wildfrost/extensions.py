"""
Extension files: content from other Wildfrost mods (PLAN.md §10, built from 2026-11-15).

A mod's creator ships one `<Mod>.wildfrost.json` file; the player who generates puts it loose in
Archipelago's custom_worlds folder, beside wildfrost.apworld (Archipelago only picks up .apworld files
and folders there, so the file is left alone). It's read here when the apworld is imported, before the
world class is built, so its items and locations join the data package. Each slot then picks which
installed extensions it uses with the Mod Content option; content of an extension a slot didn't pick is
never in that slot's seed.

The file holds rows in data.py's shape, made from the mod's content dump by a creator tool, with IDs
frozen from version to version. IDs come from the mod's block: block n is ID_BASE + n * BLOCK_SIZE up
to the next block, for items and locations alike (they're separate ID spaces). Rules are data in the
Checks tab's form, never code (rules.extension_rule turns them into rule objects).

A file that fails its checks is left out with an error in the log, and a yaml that asks for it fails
with that error, so a broken file never takes the rest of the world down with it.

Format 1:
{
  "format": 1,
  "mod": "MyMod",                       # its name in the Mod Content option and in display names
  "guid": "author.wildfrost.mymod",     # the game's mod GUID, which the client checks is loaded
  "version": "1.0.0",                   # the extension's version (Universal Tracker checks it matches)
  "id_block": 3,
  "cards": {                            # the reward cards it adds: by kind, then clan (the game's reward pools)
    "companions": {"Basic": [{"key": "card:Troll", "name": "Troll", "applies": ["Shroom"]}]},
    "items": {"General": [{"key": "card:TrollHammer", "name": "Troll Hammer", "applies": ["MyMod.Bog"]}]},
    "charms": {"General": [{"key": "card:CardUpgradeBog", "name": "Bog Charm"}]}
  },                                    # "applies": what the card applies (game names), for ["applies", ...]
  "ap_items": {                         # Archipelago items, by kind: packs, charm items and pets
    "Pack": [
      {"key": "pack:General:Item:MyMod-1", "name": "MyMod General Item Pack 1", "id": 106000, "clan": "General",
       "card_kind": "Item"},
      {"key": "pack:Basic:Companion:MyMod-1", "name": "MyMod Snowdweller Companion Pack 1", "id": 106003,
       "clan": "Basic", "card_kind": "Companion", "cards": ["card:Troll"]}
    ],
    "Charm": [{"key": "charm:General:CardUpgradeBog", "name": "Bog Charm", "id": 106001, "clan": "General",
               "card": "card:CardUpgradeBog"}],
    "Pet": [{"key": "pet:MyMod.Toadie", "name": "Toadie Pet", "id": 106002}],
    "Tribe": [{"key": "tribe:MyMod.Bogfolk", "name": "Bogfolk", "id": 106004, "shares": "Basic"}]
  },
  "leaders": {"MyMod.Bogfolk": [{"key": "MyMod.BogKing", "applies": ["Shroom"], "traits": []}]},
  "ap_locations": {                     # Archipelago checks
    "battles": [                        # one per run tribe, and a spare "#2" each
      {"key": "battle:1:BogTrolls:Basic", "name": "Area 2 Battle - The Bog Trolls (Snowdwellers)", "id": 106000,
       "area": 1, "tier": 4, "boss": false, "tribe": null, "run_tribe": "Basic"}
    ],
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
              "bells": ["9.MoreEnemiesInBossBattles"]}
}

Tribes (the user's calls, 2026-11-16): a "Tribe" item adds a playable tribe, by its ClassData name. Its
runs draw from General, Snow, its "shares" clan (Basic, Magic or Clunk: the vanilla pools it also has) and
its own cards, filed under its ClassData name like a clan's. It gets battle checks like a vanilla clan (the
file lists them, run_tribe its ClassData; make_extension.py writes one per base battle, the bosses' "#2" as
twins), and a Victory; a win with it counts toward Goal Clans Required. The client keeps it locked at tribe
select until its item arrives. "leaders" lists its leaders' effects, for ["applies", ...].

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
from pathlib import Path

from . import data

FORMAT = 1
SUFFIX = ".wildfrost.json"
# Overrides where extensions are looked for (os.pathsep-separated folders); the tests use it.
FOLDER_ENV = "WILDFROST_EXTENSIONS_DIR"
ID_BASE = 100_000
BLOCK_SIZE = 2_000  # the user's call, 2026-11-15

CLAN_NAMES = ("General", "Basic", "Magic", "Clunk")
CARD_KINDS = ("Companion", "Item")
# Area 4: the True Final Boss kit's packs (Sunbringer, the fight itself, its bells too; the user's call, 2026-11-16).
REGIONS = ("Area 1", "Area 2", "Area 3", "Area 4")
# Rule forms an extension may use (rules.extension_rule); the first word of each list.
RULE_FORMS = ("has", "all", "any", "packs", "and", "or", "card", "cards", "with", "any_card", "two_of", "tribe", "bell",
              "battle", "applies", "trait", "clan_kit")
CLAN_KIT_KEYS = {"clan": str, "companions": int, "items": int, "charms": int, "cards": int, "forced_extra": bool,
                 "area_kit": bool}
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
REFUSED_REMOVALS = {
    "battles": {_battle_name(key) for key, _, _, info in data.LOCATIONS
                if key.startswith("battle:") and (info["boss"] or info["true_final"])},
}


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


def _text(value, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExtensionError(f"{what} should be a non-empty string")
    return value


def check_rule(rule, what: str, clans: tuple = CLAN_NAMES) -> None:
    """
    Checks a rule's shape; which items and cards it names is checked once every file is read. clans: the
    clans it may name (General and the vanilla three, and the extension's own tribes).
    """
    if not isinstance(rule, list) or not rule or rule[0] not in RULE_FORMS:
        raise ExtensionError(f"{what}: a rule is a list starting with one of {', '.join(RULE_FORMS)}")
    form = rule[0]
    if form in ("and", "or"):
        if len(rule) != 2 or not isinstance(rule[1], list) or not rule[1]:
            raise ExtensionError(f"{what}: [\"{form}\", [rule, ...]]")
        for child in rule[1]:
            check_rule(child, what, clans)
    elif form == "has" and not (len(rule) == 3 and isinstance(rule[1], str) and isinstance(rule[2], int)):
        raise ExtensionError(f"{what}: [\"has\", item key, count]")
    elif form == "all" and not (len(rule) == 2 and isinstance(rule[1], list) and all(isinstance(k, str) for k in rule[1])):
        raise ExtensionError(f"{what}: [\"all\", [item key, ...]]")
    elif form == "any" and not (len(rule) == 3 and isinstance(rule[1], list) and isinstance(rule[2], int)):
        raise ExtensionError(f"{what}: [\"any\", [item key, ...], count]")
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
    elif form == "applies" and not (len(rule) == 2 and isinstance(rule[1], str) and rule[1]):
        raise ExtensionError(f"{what}: [\"applies\", effect name] (a card that applies it, or a clan whose leaders do)")
    elif form == "battle" and not (len(rule) == 2 and isinstance(rule[1], str)):
        raise ExtensionError(f"{what}: [\"battle\", BattleData name]")
    elif form == "tribe" and not (len(rule) == 2 and rule[1] in clans[1:]):
        raise ExtensionError(f"{what}: [\"tribe\", Basic/Magic/Clunk or one of its tribes]")
    elif form == "bell" and not (len(rule) == 2 and isinstance(rule[1], str)):
        raise ExtensionError(f"{what}: [\"bell\", storm bell name]")


def parse(path: str, raw: bytes) -> Extension:
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ExtensionError(f"not valid JSON: {e}") from e
    _require(doc, dict, "the file")
    if doc.get("format") != FORMAT:
        raise ExtensionError(f"format should be {FORMAT} (this apworld reads format {FORMAT})")
    ext = Extension(mod=_text(doc.get("mod"), "mod"), guid=_text(doc.get("guid"), "guid"),
                    version=_text(doc.get("version"), "version"), id_block=_require(doc.get("id_block"), int, "id_block"),
                    path=path, hash=hashlib.sha256(raw).hexdigest()[:16])
    if not re.fullmatch(r"[A-Za-z0-9 _.\-]+", ext.mod):
        raise ExtensionError("mod should be letters, digits, spaces, '_', '.' or '-'")
    if ext.id_block < 0:
        raise ExtensionError("id_block should be 0 or more")
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
    for i, item in enumerate(_require(ap_items.get("Tribe", []), list, "ap_items.Tribe")):
        what = f"ap_items.Tribe[{i}]"
        key = _text(item.get("key"), f"{what}.key")
        tribe = key.removeprefix("tribe:")
        if not key.startswith("tribe:") or not tribe or ":" in tribe or tribe in CLAN_NAMES or tribe in tribes:
            raise ExtensionError(f"{what}: a tribe's key is 'tribe:<ClassData>', one per tribe, not a vanilla clan")
        shares = item.get("shares")
        if shares not in CLAN_NAMES[1:]:
            raise ExtensionError(f"{what}.shares should be Basic, Magic or Clunk (the vanilla clan whose pools it draws from)")
        tribes[tribe] = shares
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
            for i, card in enumerate(_require(entries, list, f"cards.{section}.{clan}")):
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
        for i, item in enumerate(_require(entries, list, f"ap_items.{kind}")):
            what = f"ap_items.{kind}[{i}]"
            key, name = _text(item.get("key"), f"{what}.key"), _text(item.get("name"), f"{what}.name")
            item_id = in_block(item.get("id"), f"{what}.id")
            clan = item.get("clan")
            if kind not in ("Pet", "Tribe") and clan not in clans:
                raise ExtensionError(f"{what}.clan should be one of {', '.join(clans)}")
            if kind == "Tribe":
                info = {"kind": "Tribe", "shares": item["shares"]}
            elif kind == "Pet":
                # A pet the mod adds: an item like ours, so the client keeps it locked until it arrives.
                if not key.startswith("pet:"):
                    raise ExtensionError(f"{what}: a pet's key is 'pet:<CardData>'")
                info = {"kind": "Pet"}
            elif kind == "Pack":
                card_kind = item.get("card_kind")
                # The clan and kind lead the key: fill_packs and the client group packs by them.
                if card_kind not in CARD_KINDS or not key.startswith(f"pack:{clan}:{card_kind}:"):
                    raise ExtensionError(f"{what}: a pack has card_kind Companion or Item and a key 'pack:<clan>:<card_kind>:...'")
                info = {"kind": "Pack", "clan": clan, "card_kind": card_kind}
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
                card = _text(item.get("card"), f"{what}.card")
                if not key.startswith(f"charm:{clan}:") or not any(c[0] == card and c[2]["kind"] == "Charm" for c in ext.cards):
                    raise ExtensionError(f"{what}: a charm has a key 'charm:<clan>:...' and a card naming one of this "
                                         "extension's cards of kind Charm")
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
               for i, loc in enumerate(_require(ap_locations.get(section, []), list, f"ap_locations.{section}"))]
    for what, section, loc in entries:
        key, name = _text(loc.get("key"), f"{what}.key"), _text(loc.get("name"), f"{what}.name")
        loc_id = in_block(loc.get("id"), f"{what}.id")
        if not key.startswith("battle:" if section == "battles" else "challenge:"):
            raise ExtensionError(f"{what}.key: {section} keys start with '{'battle:' if section == 'battles' else 'challenge:'}'")
        if key.startswith("battle:"):
            parts = key.split(":")
            area, run_tribe = loc.get("area"), loc.get("run_tribe")
            if len(parts) != 4 or area not in (0, 1, 2) or parts[1] != str(area) or run_tribe not in run_tribes \
                    or parts[3] != run_tribe:
                raise ExtensionError(f"{what}: a battle's key is 'battle:<area 0-2>:<BattleData>:<run tribe>', "
                                     "matching its area and run_tribe (Basic, Magic, Clunk or one of its tribes)")
            tribe = loc.get("tribe")
            if tribe not in (None, *CLAN_NAMES[1:]):
                raise ExtensionError(f"{what}.tribe should be null or Basic/Magic/Clunk")
            # "true_final": the True Final Boss fight, for a tribe's own row of it (its kit and bells, and only
            # in seeds whose goal goes there); an extension's own battles never are.
            true_final = _require(loc.get("true_final", False), bool, f"{what}.true_final")
            if true_final and (parts[2] not in BASE_NAMES["battles"] or run_tribe not in tribes):
                raise ExtensionError(f"{what}.true_final: only a tribe's own row of the base game's True Final Boss")
            info = {"area": area, "boss": _require(loc.get("boss", False), bool, f"{what}.boss"), "tribe": tribe,
                    "run_tribe": run_tribe, "true_final": true_final, "tier": _require(loc.get("tier"), int, f"{what}.tier")}
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
        for i, leader in enumerate(_require(leaders, list, f"leaders.{tribe}")):
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
    for i, bell in enumerate(_require(doc.get("bells", []), list, "bells")):
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
        refused = [n for n in names if n in REFUSED_REMOVALS.get(kind, ())]
        if refused:
            raise ExtensionError(f"removes.{kind}: {', '.join(refused)} can't be removed (runs, wins and the goal are built on them)")
        ext.removes[kind] = set(names)

    groups = _require(doc.get("groups", {}), dict, "groups")
    for group, cards in groups.items():
        if not isinstance(cards, list) or not all(isinstance(c, str) for c in cards):
            raise ExtensionError(f"groups.{group} should be a list of card names")
        ext.groups[group] = list(cards)
    return ext


def _check_against(ext: Extension, keys: set, names: set, item_ids: set, loc_ids: set, card_keys: set) -> None:
    """No clash with what's already loaded (ours, then earlier extensions)."""
    for key, name, item_id, _ in ext.items:
        if key in keys or name in names or item_id in item_ids:
            raise ExtensionError(f"item {key!r} ({name!r}, {item_id}) clashes with one already loaded")
    for key, name, loc_id, _ in ext.locations:
        if key in keys or name in names or loc_id in loc_ids:
            raise ExtensionError(f"location {key!r} ({name!r}, {loc_id}) clashes with one already loaded")
    for key, _, _ in ext.cards:
        if key in card_keys:
            raise ExtensionError(f"card {key!r} is already loaded")
    own_cards = {key.removeprefix("card:") for key, _, _ in ext.cards}
    own_cards |= {info["card"].removeprefix("card:") for _, _, _, info in ext.items if info["kind"] == "Charm"}
    # A group lists its cards, and "tribe:<clan>" for clans whose leaders do it (the user's call, 2026-11-15).
    tribes = {f"tribe:{clan}" for clan in (*CLAN_NAMES[1:], *ext.tribes)}
    for group, cards in ext.groups.items():
        unknown = [c for c in cards if c not in own_cards and c not in tribes]
        if unknown:
            raise ExtensionError(f"groups.{group} names cards this extension doesn't add: {', '.join(unknown)}")


def load(paths: list[str] | None = None) -> tuple[dict[str, Extension], dict[str, str]]:
    """Reads every extension file; returns the loaded ones by mod name and the failed ones' errors."""
    if paths is None:
        paths = sorted(str(p) for folder in folders() if os.path.isdir(folder)
                       for p in Path(folder).iterdir() if p.name.endswith(SUFFIX))
    loaded: dict[str, Extension] = {}
    failed: dict[str, str] = {}
    keys = {r[0] for r in data.LOCATIONS} | {r[0] for r in data.ITEMS}
    names = {r[1] for r in data.LOCATIONS} | {r[1] for r in data.ITEMS}
    item_ids, loc_ids = {r[2] for r in data.ITEMS}, {r[2] for r in data.LOCATIONS}
    card_keys = {r[0] for r in data.CARDS}
    blocks: dict[int, str] = {}
    bells: set[str] = set()
    for path in paths:
        label = Path(path).name.removesuffix(SUFFIX)
        try:
            with open(path, "rb") as f:
                ext = parse(path, f.read())
            label = ext.mod
            if ext.mod in loaded:
                raise ExtensionError(f"another file already loaded mod {ext.mod!r}")
            if ext.id_block in blocks:
                raise ExtensionError(f"id_block {ext.id_block} is already {blocks[ext.id_block]}'s")
            _check_against(ext, keys, names, item_ids, loc_ids, card_keys)
            clashing = sorted(set(ext.bells) & bells)
            if clashing:
                raise ExtensionError(f"storm bells {', '.join(clashing)} are already another extension's")
        except (OSError, ExtensionError) as e:
            failed[label] = f"{Path(path).name}: {e}"
            logging.error(f"Wildfrost: extension {Path(path).name} left out: {e}")
            continue
        loaded[ext.mod] = ext
        blocks[ext.id_block] = ext.mod
        keys |= {r[0] for r in ext.items} | {r[0] for r in ext.locations}
        names |= {r[1] for r in ext.items} | {r[1] for r in ext.locations}
        item_ids |= {r[2] for r in ext.items}
        loc_ids |= {r[2] for r in ext.locations}
        card_keys |= {r[0] for r in ext.cards}
        bells |= set(ext.bells)
        logging.info(f"Wildfrost: loaded extension {ext.mod} {ext.version} ({len(ext.items)} items, "
                     f"{len(ext.locations)} locations)")
    return loaded, failed


LOADED, FAILED = load()
