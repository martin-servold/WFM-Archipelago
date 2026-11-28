"""
Everything the world knows: data.py (generated from the game's content dump) plus the extension files
that loaded (extensions.py). The rest of the apworld imports its tables from here, never from data.py.

Rows from an extension carry info["ext"], the mod's name: a slot only has them when its Mod Content
option picks that mod (WildfrostWorld.uses). An extension's rules may name our items, cards and groups
and its own, but not another extension's, since a slot can pick one without the other.
"""

import logging

from . import data, extensions
from .extensions import ExtensionError
from .groups import GROUPS

# The base game's groups, before any extension adds to them: an extension's rules may name these and its own
# (found in review, 2026-11-24: checking against GROUPS let a rule name an earlier file's new group).
BASE_GROUPS = {group: list(members) for group, members in GROUPS.items()}


def _check_references(ext: extensions.Extension) -> None:
    item_keys = {r[0] for r in data.ITEMS} | {r[0] for r in ext.items}
    cards = {r[0].removeprefix("card:") for r in data.CARDS} | {r[0].removeprefix("card:") for r in ext.cards}
    cards |= {info["card"].removeprefix("card:") for rows in (data.ITEMS, ext.items) for _, _, _, info in rows
              if info["kind"] == "Charm"}
    groups = set(BASE_GROUPS) | set(ext.groups)
    bells = {name for name, _, _ in data.BELLS} | set(ext.bells)
    battles = {key.split(":")[2] for rows in (data.LOCATIONS, ext.locations) for key, _, _, _ in rows if key.startswith("battle:")}
    applied = {e for rows in (data.CARDS, ext.cards) for _, _, info in rows for e in info.get("applies", [])}
    leaders = [leader for source in (data.LEADERS, ext.leaders) for rows in source.values() for leader in rows]
    applied |= {e for leader in leaders for e in leader.get("applies", [])}
    traits = {t for rows in (data.CARDS, ext.cards) for _, _, info in rows for t in info.get("traits", [])}
    traits |= {t for leader in leaders for t in leader.get("traits", [])}
    deck_cards = {c for source in (data.START_DECKS, ext.start_decks) for deck in source.values() for c in deck}

    def starts_with(card: str, what: str) -> None:
        if card not in deck_cards and card not in groups:
            raise ExtensionError(f"{what}: no tribe starts with {card!r}")

    def group_or_cards(value, what: str) -> int:
        """Checks a group name or card list; returns how many members it has."""
        if isinstance(value, str):
            if value not in groups:
                raise ExtensionError(f"{what} names an unknown group {value!r}")
            return len(set(BASE_GROUPS.get(value, [])) | set(ext.groups.get(value, [])))
        unknown = [c for c in value if c not in cards and not c.startswith("tribe:")]
        if unknown:
            raise ExtensionError(f"{what} names unknown cards {', '.join(unknown)}")
        return len(set(value))

    def check(rule, what: str) -> None:
        form = rule[0]
        if form in ("and", "or"):
            for child in rule[1]:
                check(child, what)
        elif form == "has" and rule[1] not in item_keys:
            raise ExtensionError(f"{what} names an unknown item {rule[1]!r}")
        elif form in ("all", "any"):
            unknown = [k for k in rule[1] if k not in item_keys]
            if unknown:
                raise ExtensionError(f"{what} names unknown items {', '.join(unknown)}")
        elif form == "bell" and rule[1] not in bells:
            raise ExtensionError(f"{what} names an unknown storm bell {rule[1]!r}")
        elif form == "card" and rule[1] not in cards:
            raise ExtensionError(f"{what} names an unknown card {rule[1]!r}")
        elif form == "cards":
            group_or_cards(rule[1], what)
        elif form == "with":
            if rule[1] not in cards:
                raise ExtensionError(f"{what} names an unknown card {rule[1]!r}")
            group_or_cards(rule[2], what)
        elif form == "trait" and rule[1] not in traits:
            raise ExtensionError(f"{what}: nothing has the trait {rule[1]!r}")
        elif form == "applies" and rule[1] not in applied:
            raise ExtensionError(f"{what}: nothing applies {rule[1]!r} (effects are the game's names, e.g. Weakness for Bom)")
        elif form == "starts_with":
            starts_with(rule[1], what)
        elif form == "clan_kit" and rule[1].get("starts_with"):
            starts_with(rule[1]["starts_with"], what)
        elif form == "battle" and rule[1] not in battles:
            raise ExtensionError(f"{what} names an unknown battle {rule[1]!r}")
        elif form in ("any_card", "two_of"):
            if isinstance(rule[1], str):
                if rule[1] not in groups:
                    raise ExtensionError(f"{what} names an unknown group {rule[1]!r}")
                size = len(set(BASE_GROUPS.get(rule[1], [])) | set(ext.groups.get(rule[1], [])))
            else:
                unknown = [c for c in rule[1] if c not in cards]
                if unknown:
                    raise ExtensionError(f"{what} names unknown cards {', '.join(unknown)}")
                size = len(set(rule[1]))
            if size < (2 if form == "two_of" else 1):
                raise ExtensionError(f"{what}: {form} needs {'two cards' if form == 'two_of' else 'a card'} or more")

    for key, _, _, info in ext.locations:
        if info.get("rule") is not None:
            check(info["rule"], f"{key}'s rule")


def _merge() -> tuple[list, list, list]:
    locations, items, cards = list(data.LOCATIONS), list(data.ITEMS), list(data.CARDS)
    new_groups: dict[str, str] = {}  # a group an extension made -> that extension
    for mod, ext in list(extensions.LOADED.items()):
        try:
            _check_references(ext)
            for group in ext.groups:
                if group not in BASE_GROUPS and group in new_groups:
                    raise ExtensionError(f"group {group!r} is already {new_groups[group]}'s")
        except ExtensionError as e:
            extensions.FAILED[mod] = f"{ext.path}: {e}"
            del extensions.LOADED[mod]
            logging.error(f"Wildfrost: extension {mod} left out: {e}")
            continue
        for group, names in ext.groups.items():
            if group not in BASE_GROUPS:
                new_groups[group] = mod
            if group not in GROUPS:
                GROUPS[group] = []
            GROUPS[group].extend(n for n in names if n not in GROUPS[group])
        locations += ext.locations
        items += ext.items
        cards += ext.cards
    return locations, items, cards


LOCATIONS, ITEMS, CARDS = _merge()
# Storm points by bell: the base game's and every loaded extension's (a slot has only its own; see
# WildfrostWorld.bell_points).
BASE_BELLS = {name for name, _, _ in data.BELLS}
BELL_POINTS = {name: points for name, points, _ in data.BELLS}
for _ext in extensions.LOADED.values():
    BELL_POINTS.update(_ext.bells)
EXT_OF_ITEM_NAME = {name: info["ext"] for _, name, _, info in ITEMS if "ext" in info}
# Every tribe (the user's calls, 2026-11-16): ClassData name -> its tribe item's row info, ours (Basic, Magic,
# Clunk) and the loaded extensions' (their info has "ext" and "shares"). A slot has ours and its extensions'
# (WildfrostWorld.tribes).
TRIBES = {key.removeprefix("tribe:"): {**info, "name": name} for key, name, _, info in ITEMS if info["kind"] == "Tribe"}
# The clans whose pools each extension tribe also draws from (rules.clan_packs): vanilla clans, or its extension's
# shared pool clans (the user's call, 2026-11-27: Another Snowfall's tribes all draw one "Enemy" pool).
SHARES = {tribe: tuple(info["shares"]) for tribe, info in TRIBES.items() if info.get("shares")}


def _draws(tribe: str, info: dict) -> tuple[str, ...]:
    """General (unless the tribe's reward pools leave it out), its own and the ones it shares."""
    return (("General",) if info.get("general", True) else ()) + (tribe,) + SHARES.get(tribe, ())


# Every clan whose packs and charms a run of each tribe can be offered (rules.clan_packs, items.drawn_clans).
DRAWS = {tribe: _draws(tribe, info) for tribe, info in TRIBES.items()}
# Cards of other clans that a tribe's runs can also be offered, from the pools of its own and shared clans
# (an extension's "reuses"; Another Snowfall's Enemy pools hold vanilla cards). Logic counts a pack by the share of
# its cards the tribe can draw, and a charm whole (rules.DrawnCount; the user's calls, 2026-11-27).
REUSES: dict[str, frozenset[str]] = {}  # an extension clan -> card keys
for _ext in extensions.LOADED.values():
    REUSES.update({clan: frozenset(cards) for clan, cards in _ext.reuses.items()})
TRIBE_REUSES = {tribe: frozenset().union(*(REUSES.get(clan, ()) for clan in draws))
                for tribe, draws in DRAWS.items() if any(clan in REUSES for clan in draws)}
_CLAN_OF_CARD = {key: info["clan"] for key, _, info in CARDS}
# Those cards' clans: their packs and charms stay in a seed with the tribe even when no tribe there draws the clan
# (items.drawn_clans), so the cards can arrive (a Modded Only seed of Another Snowfall has no vanilla tribe).
BONUS = {tribe: tuple(sorted({_CLAN_OF_CARD[k] for k in cards if k in _CLAN_OF_CARD} - set(DRAWS[tribe])))
         for tribe, cards in TRIBE_REUSES.items()}
# Each tribe's leaders and what they apply: ours (data.LEADERS) and the loaded extensions' tribes'.
LEADERS = {clan: list(rows) for clan, rows in data.LEADERS.items()}
for _ext in extensions.LOADED.values():
    LEADERS.update(_ext.leaders)
# Each tribe's starting deck: ours and the loaded extensions' tribes' (["starts_with", card]).
START_DECKS = {clan: list(cards) for clan, cards in data.START_DECKS.items()}
for _ext in extensions.LOADED.values():
    START_DECKS.update(_ext.start_decks)
