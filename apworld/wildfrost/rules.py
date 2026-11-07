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


# Storm bell levels (items.STORM_BELL_LEVELS): each one adds 2 storm points, so the 5th reaches the
# True Final Boss's 10; the 11th unlocks Overcrank.
TRUE_FINAL_BELLS = 5


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


# Force Storm Bells Up To makes every run harder, so logic adds one pack of any kind to the win kits,
# and one more at 22 (Overcrank), as Force Storm Bells and Force Overcrank each did (decided by the
# user 2026-11-02; the two became one option 2026-11-06, and logic stays at that, the user's call).
OVERCRANK_POINTS = 22


def forced_extra(world: WildfrostWorld) -> int:
    points = world.options.force_storm_bells_up_to.value
    return int(points > 0) + int(points >= OVERCRANK_POINTS)


# The client's forcing ramp (bell_kits) asks more of the higher levels, so forcing never holds a run to
# bells its packs can't carry: none at 2 storm points, one pack at 4-12, two from 14 on, Overcrank
# included (decided by the user 2026-11-06). Logic doesn't follow it (forced_extra).
def forced_pack_extra(points: int) -> int:
    return 0 if points <= 2 else 1 if points <= 12 else 2


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


def bell_kits() -> list:
    """
    For slot_data: the most bell levels each kit carries, and its packs. Force Storm Bells Up To only
    forces the bells a run's clan has the packs for (decided by the user 2026-11-02): levels 1-4 (up
    to 8 storm points) take the Final Boss kit, level 5 (10, the True Final Boss) its kit, and levels
    6-11 (12 to 20 storm points, then Overcrank) the Overcranked one, each plus its level's forced
    extra (forced_pack_extra). Logic can't follow forced bells itself, since a requirement can't grow
    as items arrive.
    """
    def alternatives(kit, extra):
        # The forced extra as in packs(): each one more companion or item pack, or that many charms.
        return [{"Companion": c, "Item": i, "Charm": ch, "extra": extra, "charms_per_pack": CHARMS_PER_PACK} for c, i, ch in kit]

    kits = []
    for level in range(1, STORM_BELL_LEVELS + 1):
        kit = FINAL_BOSS_PACKS if level < TRUE_FINAL_BELLS else TRUE_FINAL_PACKS if level == TRUE_FINAL_BELLS else OVERCRANK_PACKS
        entry = alternatives(kit, forced_pack_extra(2 * level))
        if kits and kits[-1][1] == entry:
            kits[-1][0] = level  # same packs as the level below: one kit carries both
        else:
            kits.append([level, entry])
    return kits


GOAL_KIT = {0: final_boss_kit, 1: true_final_kit, 2: overcrank_kit}


# Reverse Storm Bells (designed with the user 2026-11-05): runs start Overcranked and each
# Progressive Storm Bell lowers the floor a step. Packs a run needs to get through each stretch,
# by bells received (0 = Overcranked, then 20, 18, ... 2 storm points, and 11 = no bells). A pack
# is a companion or item pack, or CHARMS_PER_PACK charms. Placeholder numbers, to tune from
# playtests (the client's "Run summary" log line); later split into companions, items and charms.
# Moved to the 11 even steps on 2026-11-06 by storm points: 12-20 take the old Overcranked column
# (the first playtests found 10 easy and Overcranked not much harder), 10 down to 0 the old ones.
REVERSE_PACKS = {
    #                 OC  20  18  16  14  12  10   8   6   4   2   0
    "Area 1 fights": (0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0),
    "Area 1 boss":   (2,  2,  2,  2,  2,  2,  2,  1,  1,  0,  0,  0),
    "Area 2":        (4,  4,  4,  4,  4,  4,  4,  3,  2,  1,  1,  1),
    "Area 3":        (6,  6,  6,  6,  5,  5,  5,  4,  3,  3,  2,  2),
}
assert all(len(row) == STORM_BELL_LEVELS + 1 for row in REVERSE_PACKS.values())


def reverse(world: WildfrostWorld) -> bool:
    return world.options.progression_direction == world.options.progression_direction.option_reverse


def reverse_kit(clan: str, stretch: str):
    """
    Any bell level reached with that level's packs: lower bells never make a run harder, so the
    cheapest level the bells allow is enough.
    """
    ways = []
    for bells, need in enumerate(REVERSE_PACKS[stretch]):
        rule = both(Has(STORM_BELL, bells) if bells else None, packs(clan, 0, 0, 0, need) if need else None)
        if rule is None:
            return None  # this stretch needs nothing at the level runs start at
        ways.append(rule)
    return Or(*ways)


def reverse_true_final_kit(clan: str):
    """A no-bell run (every bell step), with the True Final Boss kit."""
    return And(kit_packs(clan, TRUE_FINAL_PACKS, 0), Has(STORM_BELL, STORM_BELL_LEVELS))


def reverse_stretch(area: int, tier: int) -> str:
    if area == 0:
        return "Area 1 boss" if tier > 1 else "Area 1 fights"
    return "Area 2" if area == 1 else "Area 3"


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


def battle_rule(key: str, info: dict, extra: int, reversed_bells: bool = False):
    if reversed_bells:
        clan = info["run_tribe"]
        kit = reverse_true_final_kit(clan) if info.get("true_final") else reverse_kit(clan, reverse_stretch(info["area"], info["tier"]))
        return both(tribe_rule(required_tribes(key, info)), kit)
    return both(tribe_rule(required_tribes(key, info)), battle_kit(info, extra))


def companion_and_item_pack(clan: str):
    return packs(clan, 1, 1, 0)


# Challenges that need a companion pack and an item pack in the run's clan (decided by the user 2026-11-02).
NEEDS_COMPANION_AND_ITEM = ("Challenge Charm 22", "Challenge Charm 12")  # Beastmaster, Long Live the King


def two_companions_and_one_more(clan: str):
    """Two companion packs, and an item pack or CHARMS_PER_PACK charms."""
    return Or(packs(clan, 2, 1, 0), packs(clan, 2, 0, CHARMS_PER_PACK))


def challenge_kit(info: dict, extra: int, reversed_bells: bool = False):
    if reversed_bells:
        return reverse_challenge_kit(info)
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


def reverse_challenge_kit(info: dict):
    """
    Reverse Storm Bells: the normal pack needs (without the forced extra), plus getting as far as
    the challenge's area at the run's bells. The win challenges take the Area 3 stretch.
    """
    internal = info["internal"]
    if internal == SUNBRINGER:
        return any_clan(reverse_true_final_kit)
    base = challenge_kit(info, 0)
    region = CHALLENGE_REGION.get(internal, "Area 1")
    if region == "Area 1":
        return base
    stretch = "Area 3" if region == "Area 3" else "Area 2"
    clan = WIN_WITH_CLAN.get(internal) or CHALLENGE_NEEDS_TRIBE.get(internal)
    reach = reverse_kit(clan, stretch) if clan else any_clan(lambda c: reverse_kit(c, stretch))
    return both(base, reach)


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
        self.reversed = reverse(world)
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
            # Use Smackback to kill 20 enemies (decided by the user 2026-11-06): Snowdweller and
            # Shademancer runs have Smackback leaders and Clunkmasters have none, so a Clunkmaster
            # start needs one of those clans, Gojiber or the Punchfist Charm.
            "Challenge Companion 4": Or(Has(CLANS["Basic"]), Has(CLANS["Magic"]),
                                        self.any_of(("Noggin", "CardUpgradePunchfist"))),
            # Minimalist: Toaster empties the deck, or the Gunk Bugs fight does it for you.
            "Challenge Charm 23": Or(self.card("Havok"), *(battle_rule(key, info, self.extra, self.reversed) for key, _, _, info in LOCATIONS
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
    reversed_bells = reverse(world)
    world.location_rules = {}
    for key, name, _, info in LOCATIONS:
        if not included(world, info):
            continue
        if key.startswith("battle:"):
            rule = battle_rule(key, info, extra, reversed_bells)
        else:
            rule = both(tribe_rule(required_tribes(key, info)), challenge_kit(info, extra, reversed_bells),
                        cards.for_challenge(info["internal"]))
        if rule is not None:
            world.set_rule(world.get_location(name), rule)
            world.location_rules[key] = rule_json(rule)

    kit = (lambda clan, _: reverse_true_final_kit(clan)) if reversed_bells else GOAL_KIT[world.options.goal.value]
    for clan in CLANS:
        world.set_rule(world.get_location(victory_location(clan)), both(tribe_rule({clan}), kit(clan, extra)))

    world.set_completion_rule(Has(VICTORY_ITEM, world.options.clans_required.value))
