from __future__ import annotations

from itertools import combinations
from typing import TYPE_CHECKING

from rule_builder.rules import And, Has, HasAll, HasFromList, Or

from .data import CARDS, ITEMS, LOCATIONS
from .items import LOKI_PET, SNEEZLE_PET, SPIKE_PET, STORM_BELL, STORM_BELL_LEVELS
from .locations import CHALLENGE_REGION, CLANS, SUNBRINGER, VICTORY_ITEM, included, victory_location

if TYPE_CHECKING:
    from .world import WildfrostWorld

# "Win a run with tribe X" needs that tribe.
CHALLENGE_TRIBE = {
    "Challenge Charm 25": "Basic",
    "Challenge Charm 26": "Magic",
    "Challenge Charm 27": "Clunk",
}
# Challenges done with a tribe's own cards (decided by the user 2026-10-31): Ritual's sacrifice
# cards and Summon 50 allies are Shademancer play, Add 10 Scrap a Clunkmaster run, and Block 10
# hits with Clunkers uses Woodhead from the Snowdweller starting deck. Kill 15 with Shroom and Apply
# 60 Shell use the Snowdweller leaders, who come with Shroom or Shell (decided by the user 2026-11-04).
CHALLENGE_NEEDS_TRIBE = {
    "Challenge Event 2": "Basic",
    "Challenge Item 5": "Basic",
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
    return {t for t in (info["run_tribe"], info["tribe"]) if t in CLANS}


# Storm bell levels: the first unlocks the bells at 5 storm points, each next one adds a point, so
# the 6th reaches the True Final Boss's 10; the 7th unlocks Overcrank.
TRUE_FINAL_BELLS = 6


# Deck strength (decided by the user 2026-10-30). Fights 1-5 of a run (map tiers 0-4: two battles,
# the first boss, two battles) need no cards. From the second boss (tier 5) on, a run needs some of
# its clan's cards; the True Final Boss and Overcrank need more, plus the bell levels. Counted in
# packs a run of that clan can draw from: General ones and the clan's own.
NO_CARDS_UP_TO_TIER = 4


PACK_KINDS = ("Companion", "Item", "Charm")
# Charms are items one by one (2026-11-02); where logic used to count a charm pack it counts this many.
CHARMS_PER_PACK = 3


def clan_packs(clan: str, kind: str) -> list[str]:
    """What a run of this clan draws from (General and its own): packs of a kind, or (Charm) charms."""
    return [name for _, name, _, info in ITEMS if info.get("clan") in ("General", clan) and
            (info["kind"] == "Charm" if kind == "Charm" else info["kind"] == "Pack" and info["card_kind"] == kind)]


def packs(clan: str, companions: int, items: int, charms: int, extra: int = 0):
    """
    Companion and item packs and charms, plus `extra` more: each one more companion or item pack, or
    CHARMS_PER_PACK more charms (so one charm doesn't stand in for a pack).
    """
    rules = [HasFromList(*clan_packs(clan, kind), count=n) for kind, n in zip(PACK_KINDS, (companions, items, charms)) if n]
    if extra:
        card_packs = clan_packs(clan, "Companion") + clan_packs(clan, "Item")
        ways = []
        for in_packs in range(extra + 1):
            way = [HasFromList(*card_packs, count=companions + items + in_packs)]
            in_charms = charms + CHARMS_PER_PACK * (extra - in_packs)
            if in_charms:
                way.append(HasFromList(*clan_packs(clan, "Charm"), count=in_charms))
            ways.append(And(*way) if len(way) > 1 else way[0])
        rules.append(Or(*ways))
    return And(*rules) if len(rules) > 1 else rules[0]


# Force Storm Bells and Force Overcrank make every run harder, so each adds one pack of any kind to
# the win kits (decided by the user 2026-11-02).
def forced_extra(world: WildfrostWorld) -> int:
    return int(bool(world.options.force_storm_bells)) + int(bool(world.options.force_overcrank))


# Each win kit as (companion packs, item packs, charms) alternatives; the charm counts were packs
# times CHARMS_PER_PACK (decided by the user 2026-11-02). The client gets them too (bell_kits), to
# force only the bells a run's packs can carry.
FINAL_BOSS_PACKS = ((1, 1, 0), (1, 0, 6))  # a companion pack, and an item pack or six charms
TRUE_FINAL_PACKS = ((2, 2, 3),)
OVERCRANK_PACKS = ((2, 3, 6),)


def kit_packs(clan: str, alternatives, extra: int):
    rules = [packs(clan, *counts, extra) for counts in alternatives]
    return Or(*rules) if len(rules) > 1 else rules[0]


def final_boss_kit(clan: str, extra: int = 0):
    return kit_packs(clan, FINAL_BOSS_PACKS, extra)


def true_final_kit(clan: str, extra: int = 0):
    return And(kit_packs(clan, TRUE_FINAL_PACKS, extra), Has(STORM_BELL, TRUE_FINAL_BELLS))


def overcrank_kit(clan: str, extra: int = 0):
    return And(kit_packs(clan, OVERCRANK_PACKS, extra), Has(STORM_BELL, STORM_BELL_LEVELS))


def bell_kits(extra: int) -> list:
    """
    For slot_data: the most bell levels each kit carries, and its packs. Force Storm Bells and Force
    Overcrank only force the bells a run's clan has the packs for (decided by the user 2026-11-02):
    levels 1-5 (up to 9 storm points) take the Final Boss kit, level 6 (10, the True Final Boss) its
    kit, and level 7 (Overcrank) the Overcranked one. Logic can't follow forced bells itself, since a
    requirement can't grow as items arrive.
    """
    def alternatives(kit):
        # The forced extra as in packs(): each one more companion or item pack, or that many charms.
        return [{"Companion": c, "Item": i, "Charm": ch, "extra": extra, "charms_per_pack": CHARMS_PER_PACK} for c, i, ch in kit]
    return [[TRUE_FINAL_BELLS - 1, alternatives(FINAL_BOSS_PACKS)],
            [TRUE_FINAL_BELLS, alternatives(TRUE_FINAL_PACKS)],
            [STORM_BELL_LEVELS, alternatives(OVERCRANK_PACKS)]]


GOAL_KIT = {0: final_boss_kit, 1: true_final_kit, 2: overcrank_kit}


def tribe_rule(tribes: set[str]):
    # Every tribe is an item (locations.CLANS names them); starting_tribe puts one in the starting inventory.
    tribes = sorted(t for t in tribes if t in CLANS)
    return HasAll(*(CLANS[t] for t in tribes)) if tribes else None


def both(*rules):
    rules = [r for r in rules if r is not None]
    return None if not rules else rules[0] if len(rules) == 1 else And(*rules)


def battle_kit(info: dict, extra: int):
    if info.get("true_final"):
        return true_final_kit(info["run_tribe"], extra)
    return final_boss_kit(info["run_tribe"], extra) if info["tier"] > NO_CARDS_UP_TO_TIER else None


def any_clan(kit):
    """A challenge any clan can do, with that clan's tribe item."""
    return Or(*(both(tribe_rule({clan}), kit(clan)) for clan in CLANS))


def battle_rule(key: str, info: dict, extra: int):
    return both(tribe_rule(required_tribes(key, info)), battle_kit(info, extra))


def companion_and_item_pack(clan: str):
    return packs(clan, 1, 1, 0)


# Challenges that need a companion pack and an item pack in the run's clan (decided by the user 2026-11-02).
NEEDS_COMPANION_AND_ITEM = ("Challenge Charm 22", "Challenge Charm 12")  # Beastmaster, Long Live the King


def two_companions_and_one_more(clan: str):
    """Two companion packs, and an item pack or CHARMS_PER_PACK charms."""
    return Or(packs(clan, 2, 1, 0), packs(clan, 2, 0, CHARMS_PER_PACK))


def challenge_kit(info: dict, extra: int):
    if info["internal"] == SUNBRINGER:  # the True Final Boss, with any clan
        return any_clan(lambda clan: true_final_kit(clan, extra))
    if info["internal"] in NEEDS_COMPANION_AND_ITEM:
        return any_clan(companion_and_item_pack)
    if info["internal"] == "Challenge Pet 5":  # 6x Kill Combo (decided by the user 2026-11-02)
        return any_clan(two_companions_and_one_more)
    if info["internal"] == "Challenge Pet 3":  # Buy 5 discounted items (decided by the user 2026-11-02)
        return any_clan(lambda clan: packs(clan, 0, 2 + extra, 0))
    if info["internal"] == "Challenge Companion 1":  # Equip 10 Charms: a single charm (decided by the user 2026-11-02)
        return any_clan(lambda clan: packs(clan, 0, 0, 1))
    # The Area 3 challenges need a won run (or the Final Boss); the "win with tribe X" ones with that tribe.
    if CHALLENGE_REGION.get(info["internal"]) != "Area 3":
        return None
    clan = WIN_WITH_CLAN.get(info["internal"])
    return final_boss_kit(clan, extra) if clan else any_clan(lambda clan: final_boss_kit(clan, extra))


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
DEMONIZE_CARDS = ("CardUpgradeDemonize", "Demonheart", "Dimona", "TotemOfTheGoat")  # Goat Charm, Demonheart, Dimona, Totem of the Goat
SHROOM_CARDS = ("Shroominator", "Fulbert", "Fungoose", "Wort", "HongosHammer", "SporePack", "ShroomLauncher")


class CardRules:
    def __init__(self, world: WildfrostWorld):
        pack_names = {key: name for key, name, _, _ in ITEMS}
        self.extra = forced_extra(world)
        self.pack_of = {card.removeprefix("card:"): pack_names[pack]
                        for pack, cards in world.pack_contents.items() for card in cards}
        # A charm is its own item.
        self.pack_of.update({info["card"].removeprefix("card:"): name for _, name, _, info in ITEMS if info["kind"] == "Charm"})

    def card(self, card: str):
        return both(tribe_rule({CLAN_OF_CARD[card]}), Has(self.pack_of[card]))

    def any_of(self, cards, clans=None):
        cards = [c for c in cards if clans is None or CLAN_OF_CARD[c] in clans]
        return Or(*(self.card(c) for c in cards)) if len(cards) > 1 else self.card(cards[0])

    def all_of(self, *cards):
        """Every one of these cards: their packs (one pack can hold several) and their clans."""
        tribes = tribe_rule({CLAN_OF_CARD[c] for c in cards})
        packs = sorted({self.pack_of[c] for c in cards})
        return both(tribes, HasAll(*packs) if len(packs) > 1 else Has(packs[0]))

    def two_of(self, cards):
        """Two different cards: their packs (one pack can hold both) and their clans."""
        return Or(*(self.all_of(a, b) for a, b in combinations(cards, 2)))

    def with_any(self, card: str, partners):
        """A card together with any one of the partners."""
        return Or(*(self.all_of(card, p) for p in partners))

    def big_hitter(self):
        # 50 damage in one hit (decided by the user 2026-11-02): Pepper Flag with a spice source,
        # Chikichi with Monch or Devicro, or Chompom with a shell source.
        return Or(self.with_any("PepperFlag", ("Pyra", "SpiceStones", "Peppereaper")),
                  self.with_any("TailsFive", ("Monch", "Reaper")),
                  self.with_any("Chompom", SHELL_CARDS))

    def hoarder(self):
        # 12 cards in hand (decided by the user 2026-11-02). Hand size is 6 and draw is capped by the
        # deck, so this rests on trash (temporary cards): a Clunkmaster run, whose leaders can trash,
        # with one of these. A looser bar than the true minimum, on purpose; Sneezle with Lupa outside
        # Clunkmasters is left out, and so is the Lumin Vase (a 10-bell event, not a card). Lumin Ring
        # with Sneezle or the Moko Charm is already covered by those alone.
        return both(tribe_rule({"Clunk"}), Or(
            self.card("LuminCat"),                                                    # Lupa
            self.any_of(("CardUpgradeDraw", "CardUpgradeTrash")),                     # Pinch, Gear Charm
            Has(SNEEZLE_PET),
            self.all_of("CardUpgradeBoost", "Gearhead"),                              # Lumin Ring + Folby
            self.any_of(("Bumblebee", "CardUpgradeFrenzyReduceAttack", "BlazeTea")),  # Frenzy for the leader: Blaze Bom, Moko Charm, Blaze Tea
            self.card("CardUpgradePunchfist"),                                        # Punchfist Charm
            self.with_any("Badoo", ("CardUpgradeCake", "CardUpgradeFrenzyConsume")),  # Bom Barrel + Cake or Frenzy Charm
        ))

    def for_challenge(self, internal: str):
        clunker = self.any_of(CLUNKERS)
        rules = {
            "Challenge Charm 5": self.any_of(SHELL_CARDS),                             # Tough Nut
            "Challenge Charm 20": self.any_of(FRENZY_CARDS),                           # Rampage
            "Challenge Charm 9": self.any_of(BLOCK_CARDS),                             # Icemaster
            "Challenge Charm 6": self.two_of(SACRIFICE_CARDS),                         # Ritual
            "Challenge Pet 4": Or(Has(SPIKE_PET), self.any_of(TEETH_CARDS)),           # Kill 10 with Teeth
            # Kill 3 Demonized enemies (decided by the user 2026-11-02). Demonize leaders don't count:
            # leaders aren't items, so a run can't be sure of one.
            "Challenge Pet 2": Or(Has(LOKI_PET), self.any_of(DEMONIZE_CARDS)),
            "Challenge Charm 7": self.two_of(SHROOM_CARDS),                            # Toxic
            "Challenge Item 2": clunker,                                               # Add 3 Clunkers
            # Block 10 hits with Clunkers needs only Snowdwellers (CHALLENGE_NEEDS_TRIBE): Woodhead starts in their deck.
            # Add 10 Scrap to Clunkers: a Clunkmaster run (CHALLENGE_NEEDS_TRIBE) with a clunker it can draw.
            "Challenge Companion 6": self.any_of(CLUNKERS, ("General", "Clunk")),
            # Decided by the user 2026-11-02:
            "Challenge Charm 24": self.card("PinkberryJuice"),                         # Berry Good
            "Challenge Charm 2": self.card("Snowcake"),                                # Snowball Fight
            "Challenge Charm 3": self.big_hitter(),                                    # Big Hitter
            "Challenge Charm 4": self.card("SpiceStones"),                             # Bigger Hitter
            "Challenge Charm 18": self.hoarder(),                                      # Hoarder
            # Minimalist: Toaster empties the deck, or the Gunk Bugs fight does it for you.
            "Challenge Charm 23": Or(self.card("Havok"), *(battle_rule(key, info, self.extra) for key, _, _, info in LOCATIONS
                                                           if key.startswith("battle:2:Mimiks:"))),
        }
        return rules.get(internal)


# Rules for the client's tracker (slot_data "location_rules"), with item names turned into the item
# keys the client tracks: ["and", [...]], ["or", [...]], ["has", key, count], ["all", [keys]],
# ["any", [keys], count], and ["packs", clan, kind, count] for what a clan's runs draw from (General
# and its own): its Companion or Item packs, its Charm items, or ("") its companion and item packs
# together, which would otherwise list every key each time. A location without an
# entry needs nothing.
ITEM_KEY_BY_NAME = {name: key for key, name, _, _ in ITEMS}
PACK_GROUPS = {
    **{frozenset(clan_packs(clan, kind)): [clan, kind] for clan in CLANS for kind in PACK_KINDS},
    # "": companion and item packs together (the forced extra's count).
    **{frozenset(clan_packs(clan, "Companion") + clan_packs(clan, "Item")): [clan, ""] for clan in CLANS},
}


def rule_json(rule) -> list:
    if isinstance(rule, (And, Or)):
        return ["and" if isinstance(rule, And) else "or", [rule_json(child) for child in rule.children]]
    if isinstance(rule, Has):
        return ["has", ITEM_KEY_BY_NAME[rule.item_name], rule.count]
    if isinstance(rule, HasAll):
        return ["all", [ITEM_KEY_BY_NAME[name] for name in rule.item_names]]
    if isinstance(rule, HasFromList) and frozenset(rule.item_names) in PACK_GROUPS:
        return ["packs", *PACK_GROUPS[frozenset(rule.item_names)], rule.count]
    if isinstance(rule, HasFromList):
        return ["any", [ITEM_KEY_BY_NAME[name] for name in rule.item_names], rule.count]
    raise TypeError(f"No client form for {type(rule).__name__}")


def set_all_rules(world: WildfrostWorld) -> None:
    cards = CardRules(world)
    extra = forced_extra(world)
    world.location_rules = {}
    for key, name, _, info in LOCATIONS:
        if not included(world, info):
            continue
        if key.startswith("battle:"):
            rule = battle_rule(key, info, extra)
        else:
            rule = both(tribe_rule(required_tribes(key, info)), challenge_kit(info, extra), cards.for_challenge(info["internal"]))
        if rule is not None:
            world.set_rule(world.get_location(name), rule)
            world.location_rules[key] = rule_json(rule)

    kit = GOAL_KIT[world.options.goal.value]
    for clan in CLANS:
        world.set_rule(world.get_location(victory_location(clan)), both(tribe_rule({clan}), kit(clan, extra)))

    world.set_completion_rule(Has(VICTORY_ITEM, world.options.clans_required.value))
