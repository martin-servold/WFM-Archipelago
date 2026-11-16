"""
Named card groups the rules use, by CardData name (a "tribe:<clan>" entry: a clan whose leaders do it).
The base game's are in base.wildfrost.json ("groups", hand-written: data.GROUPS); extension files add
their cards to these and define new ones (PLAN.md §10). content.py appends extensions' additions here
in place, so the rules see them; a card from an extension a slot didn't pick has no pack in that seed,
and rules.CardRules skips it.
"""

from . import data

GROUPS: dict[str, list[str]] = {group: list(cards) for group, cards in data.GROUPS.items()}
