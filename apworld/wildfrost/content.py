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


def _check_references(ext: extensions.Extension) -> None:
    item_keys = {r[0] for r in data.ITEMS} | {r[0] for r in ext.items}
    cards = {r[0].removeprefix("card:") for r in data.CARDS} | {r[0].removeprefix("card:") for r in ext.cards}
    cards |= {info["card"].removeprefix("card:") for rows in (data.ITEMS, ext.items) for _, _, _, info in rows
              if info["kind"] == "Charm"}
    groups = set(GROUPS) | set(ext.groups)
    bells = {name for name, _, _ in data.BELLS} | set(ext.bells)
    battles = {key.split(":")[2] for rows in (data.LOCATIONS, ext.locations) for key, _, _, _ in rows if key.startswith("battle:")}
    applied = {e for rows in (data.CARDS, ext.cards) for _, _, info in rows for e in info.get("applies", [])}
    leaders = [leader for source in (data.LEADERS, ext.leaders) for rows in source.values() for leader in rows]
    applied |= {e for leader in leaders for e in leader.get("applies", [])}
    traits = {t for rows in (data.CARDS, ext.cards) for _, _, info in rows for t in info.get("traits", [])}
    traits |= {t for leader in leaders for t in leader.get("traits", [])}

    def group_or_cards(value, what: str) -> int:
        """Checks a group name or card list; returns how many members it has."""
        if isinstance(value, str):
            if value not in groups:
                raise ExtensionError(f"{what} names an unknown group {value!r}")
            return len(set(GROUPS.get(value, [])) | set(ext.groups.get(value, [])))
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
        elif form == "battle" and rule[1] not in battles:
            raise ExtensionError(f"{what} names an unknown battle {rule[1]!r}")
        elif form in ("any_card", "two_of"):
            if isinstance(rule[1], str):
                if rule[1] not in groups:
                    raise ExtensionError(f"{what} names an unknown group {rule[1]!r}")
                size = len(set(GROUPS.get(rule[1], [])) | set(ext.groups.get(rule[1], [])))
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
                if group not in GROUPS and group in new_groups:
                    raise ExtensionError(f"group {group!r} is already {new_groups[group]}'s")
        except ExtensionError as e:
            extensions.FAILED[mod] = f"{ext.path}: {e}"
            del extensions.LOADED[mod]
            logging.error(f"Wildfrost: extension {mod} left out: {e}")
            continue
        for group, names in ext.groups.items():
            if group not in GROUPS:
                new_groups[group] = mod
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
# The vanilla clan whose pools each extension tribe also draws from (rules.clan_packs).
SHARES = {tribe: info["shares"] for tribe, info in TRIBES.items() if "shares" in info}
# Each tribe's leaders and what they apply: ours (data.LEADERS) and the loaded extensions' tribes'.
LEADERS = {clan: list(rows) for clan, rows in data.LEADERS.items()}
for _ext in extensions.LOADED.values():
    LEADERS.update(_ext.leaders)
