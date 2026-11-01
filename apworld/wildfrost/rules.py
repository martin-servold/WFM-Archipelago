from __future__ import annotations

from itertools import combinations
from typing import TYPE_CHECKING

from rule_builder.rules import And, Has, HasAll, HasFromList, Or

from .data import CARDS, ITEMS, LOCATIONS
from .items import SPIKE_PET, STORM_BELL, STORM_BELL_LEVELS
from .locations import CHALLENGE_REGION, CLANS, VICTORY_ITEM, included, victory_location

if TYPE_CHECKING:
    from .world import WildfrostWorld

# Every tribe is an item; starting_tribe puts one in the starting inventory.
TRIBE_ITEM = {"Basic": "Snowdwellers", "Magic": "Shademancers", "Clunk": "Clunkmasters"}

# "Win a run with tribe X" needs that tribe.
CHALLENGE_TRIBE = {
    "Challenge Charm 25": "Basic",
    "Challenge Charm 26": "Magic",
    "Challenge Charm 27": "Clunk",
}
# Challenges done with a tribe's own cards (decided by the user 2026-10-31): Ritual's sacrifice
# cards and Summon 50 allies are Shademancer play, Add 10 Scrap a Clunkmaster run, and Block 10
# hits with Clunkers uses Woodhead from the Snowdweller starting deck.
CHALLENGE_NEEDS_TRIBE = {
    "Challenge Item 4": "Basic",
    "Challenge Charm 8": "Basic",  # One Punch: the Scrappy Sword is a Snowdweller starting card
    "Challenge Charm 6": "Magic",
    "Challenge Companion 5": "Magic",
    "Challenge Companion 6": "Clunk",
}
# ...and that clan's cards. One Punch is the Frost Guardian with a Scrappy Sword, a Snowdweller
# starting card, so it needs a Snowdweller win.
WIN_WITH_CLAN = {**CHALLENGE_TRIBE, "Challenge Charm 8": "Basic"}


def required_tribes(key: str, info: dict) -> set[str]:
    """Tribe items a location needs."""
    if not key.startswith("battle:"):
        tribe = CHALLENGE_TRIBE.get(info["internal"]) or CHALLENGE_NEEDS_TRIBE.get(info["internal"])
        return {tribe} if tribe else set()
    # A battle check is won while playing run_tribe. Some battles also only appear once a tribe is
    # unlocked: vanilla locks them behind the tribe challenges (BattleLockData), and the client
    # re-links each lock to the tribe item.
    return {t for t in (info["run_tribe"], info["tribe"]) if t in TRIBE_ITEM}


# Storm bell levels: the first unlocks the bells at 5 storm points, each next one adds a point, so
# the 6th reaches the True Final Boss's 10; the 7th unlocks Overcrank.
TRUE_FINAL_BELLS = 6


# Deck strength (decided by the user 2026-10-30). Fights 1-5 of a run (map tiers 0-4: two battles,
# the first boss, two battles) need no cards. From the second boss (tier 5) on, a run needs some of
# its clan's cards; the True Final Boss and Overcrank need more, plus the bell levels. Counted in
# packs a run of that clan can draw from: General ones and the clan's own.
NO_CARDS_UP_TO_TIER = 4


def clan_packs(clan: str, kind: str) -> list[str]:
    return [name for _, name, _, info in ITEMS
            if info["kind"] == "Pack" and info["card_kind"] == kind and info["clan"] in ("General", clan)]


def packs(clan: str, companions: int, items: int, charms: int):
    return And(*(HasFromList(*clan_packs(clan, kind), count=n)
                 for kind, n in (("Companion", companions), ("Item", items), ("Charm", charms)) if n))


def final_boss_kit(clan: str):
    """A companion pack, and an item pack or two charm packs."""
    return And(HasFromList(*clan_packs(clan, "Companion")),
               Or(HasFromList(*clan_packs(clan, "Item")), HasFromList(*clan_packs(clan, "Charm"), count=2)))


def true_final_kit(clan: str):
    return And(packs(clan, 2, 2, 1), Has(STORM_BELL, TRUE_FINAL_BELLS))


def overcrank_kit(clan: str):
    return And(packs(clan, 2, 3, 2), Has(STORM_BELL, STORM_BELL_LEVELS))


GOAL_KIT = {0: final_boss_kit, 1: true_final_kit, 2: overcrank_kit}


def tribe_rule(tribes: set[str]):
    tribes = sorted(t for t in tribes if t in TRIBE_ITEM)
    return HasAll(*(TRIBE_ITEM[t] for t in tribes)) if tribes else None


def both(*rules):
    rules = [r for r in rules if r is not None]
    return None if not rules else rules[0] if len(rules) == 1 else And(*rules)


def battle_kit(info: dict):
    if info.get("true_final"):
        return true_final_kit(info["run_tribe"])
    return final_boss_kit(info["run_tribe"]) if info["tier"] > NO_CARDS_UP_TO_TIER else None


def any_clan(kit):
    """A challenge any clan can do, with that clan's tribe item."""
    return Or(*(both(tribe_rule({clan}), kit(clan)) for clan in CLANS))


def challenge_kit(info: dict):
    # The Area 3 challenges need a won run (or the Final Boss); the "win with tribe X" ones with that tribe.
    if CHALLENGE_REGION.get(info["internal"]) != "Area 3":
        return None
    clan = WIN_WITH_CLAN.get(info["internal"])
    return final_boss_kit(clan) if clan else any_clan(final_boss_kit)


# Challenges that need particular cards (decided by the user 2026-10-31), by CardData name. A card
# is in logic with the pack holding it this seed, and a run of its clan (the tribe item for
# Shademancer and Clunkmaster cards). Clunkers are the pool cards of the game's Clunker type.
CLAN_OF_CARD = {key.removeprefix("card:"): info["clan"] for key, _, info in CARDS}
CLUNKERS = ("Bitebox", "Blingo", "Bonfire", "Heartforge", "HeartmistStation", "Joob", "Junkmuncher", "Krono",
            "Madness", "MegaMimik", "Mimik", "MobileCampfire", "OhNo", "PepperFlag", "Peppermaton", "Plinker",
            "PomDispenser", "Shroominator", "Shroomine", "ShroomLauncher", "Snowcracker", "SpiceSparklers",
            "TotemOfTheGoat", "Vimifier", "Vox", "ZoomlinNest")
SHELL_CARDS = ("Kernel", "Shelly", "ShellShield", "Shellbo")
FRENZY_CARDS = ("Bumblebee", "TinyTyko", "Timmy")  # Blaze Bom, Tiny Tyko, Mini Mika
BLOCK_CARDS = ("IceDice", "Blunky")
SACRIFICE_CARDS = ("SnufferMask", "SnowMaul", "ZapOrb", "TailsFive", "TheBaker", "Boggler")  # Snuffer Mask, Yeti Skull, Azul Skull, Chikichi, The Baker, Groff
TEETH_CARDS = ("SharkTooth", "TigrisMask", "Kokonut", "Tusk")  # Tiger Skull, Tigris Mask, Taiga, Tusk
SHROOM_CARDS = ("Shroominator", "Fulbert", "Fungoose", "Wort", "HongosHammer", "SporePack", "ShroomLauncher")


class CardRules:
    def __init__(self, world: WildfrostWorld):
        pack_names = {key: name for key, name, _, _ in ITEMS}
        self.pack_of = {card.removeprefix("card:"): pack_names[pack]
                        for pack, cards in world.pack_contents.items() for card in cards}

    def card(self, card: str):
        return both(tribe_rule({CLAN_OF_CARD[card]}), Has(self.pack_of[card]))

    def any_of(self, cards, clans=None):
        cards = [c for c in cards if clans is None or CLAN_OF_CARD[c] in clans]
        return Or(*(self.card(c) for c in cards)) if len(cards) > 1 else self.card(cards[0])

    def two_of(self, cards):
        """Two different cards: their packs (one pack can hold both) and their clans."""
        rules = []
        for a, b in combinations(cards, 2):
            tribes = tribe_rule({CLAN_OF_CARD[a], CLAN_OF_CARD[b]})
            rules.append(both(tribes, HasAll(*sorted({self.pack_of[a], self.pack_of[b]}))))
        return Or(*rules)

    def for_challenge(self, internal: str):
        clunker = self.any_of(CLUNKERS)
        rules = {
            "Challenge Charm 5": self.any_of(SHELL_CARDS),                             # Tough Nut
            "Challenge Charm 20": self.any_of(FRENZY_CARDS),                           # Rampage
            "Challenge Charm 9": self.any_of(BLOCK_CARDS),                             # Icemaster
            "Challenge Charm 6": self.two_of(SACRIFICE_CARDS),                         # Ritual
            "Challenge Pet 4": Or(Has(SPIKE_PET), self.any_of(TEETH_CARDS)),           # Kill 10 with Teeth
            "Challenge Charm 7": self.two_of(SHROOM_CARDS),                            # Toxic
            "Challenge Item 2": clunker,                                               # Add 3 Clunkers
            # Block 10 hits with Clunkers needs only Snowdwellers (CHALLENGE_NEEDS_TRIBE): Woodhead starts in their deck.
            # Add 10 Scrap to Clunkers: a Clunkmaster run (CHALLENGE_NEEDS_TRIBE) with a clunker it can draw.
            "Challenge Companion 6": self.any_of(CLUNKERS, ("General", "Clunk")),
        }
        return rules.get(internal)


def set_all_rules(world: WildfrostWorld) -> None:
    cards = CardRules(world)
    for key, name, _, info in LOCATIONS:
        if not included(world, info):
            continue
        if key.startswith("battle:"):
            rule = both(tribe_rule(required_tribes(key, info)), battle_kit(info))
        else:
            rule = both(tribe_rule(required_tribes(key, info)), challenge_kit(info), cards.for_challenge(info["internal"]))
        if rule is not None:
            world.set_rule(world.get_location(name), rule)

    kit = GOAL_KIT[world.options.goal.value]
    for clan in CLANS:
        world.set_rule(world.get_location(victory_location(clan)), both(tribe_rule({clan}), kit(clan)))

    world.set_completion_rule(Has(VICTORY_ITEM, len(CLANS)))
