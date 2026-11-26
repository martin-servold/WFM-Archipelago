from __future__ import annotations

import json
from itertools import combinations
from typing import TYPE_CHECKING

from rule_builder.rules import And, Has, HasAll, HasFromList, Or, Rule

from .content import CARDS, ITEMS, LEADERS, LOCATIONS, SHARES, START_DECKS
from .data import LOGIC
from .groups import GROUPS
from .items import INK_PET, LOKI_PET, SNEEZLE_PET, SPIKE_PET, STORM_BELL, STORM_BELL_LEVELS, TRUE_FINAL_BELLS, drawn_clans
from .locations import BASE_CLANS, CLANS, VICTORY_ITEM, included, victory_location

if TYPE_CHECKING:
    from .world import WildfrostWorld

# "Win a run with tribe X" needs that tribe.
def rule_tribes(rule) -> set[str]:
    """
    The tribes a challenge's rule needs outright: a top-level ["tribe", X], or ["clan_kit", {"clan": X}],
    alone or within an "and". For Reverse's stretch and for tests; the rule itself checks them.
    """
    if not rule:
        return set()
    if rule[0] == "tribe":
        return {rule[1]}
    if rule[0] == "clan_kit" and rule[1].get("clan"):
        return {rule[1]["clan"]}
    if rule[0] == "and":
        return set().union(*(rule_tribes(child) for child in rule[1]))
    return set()


def challenge_region(info: dict) -> str:
    """Where a challenge can first be completed: an extension's names its own."""
    return info.get("region", "Area 1")


def required_tribes(key: str, info: dict) -> set[str]:
    """Tribe items a location needs."""
    if not key.startswith("battle:"):
        return rule_tribes(info.get("rule"))
    # A battle check is won while playing run_tribe. Vanilla's tribe locks on battles (BattleLockData) are
    # gone under AP (the user's call, 2026-11-25): the client lets every battle come up in every run.
    return {info["run_tribe"]} & set(CLANS)


# Kits, storm bell steps, goals, forcing and Reverse are the base file's "logic" section (PLAN.md §10,
# phase 3); the numbers were decided with the user between 2026-10-30 and 2026-11-16 (PLAN.md §5-§7).
# A kit is (companion packs, item packs, charms) alternatives, counted in what a run of its clan draws
# from: General packs and charms and the clan's own.
STORM = LOGIC["storm_bells"]
POINTS_PER_LEVEL = STORM["points_per_level"]
TRUE_FINAL_POINTS = STORM["true_final_points"]  # vanilla's StormBellManager.TrueFinalBossPointThreshold
OVERCRANK_POINTS = STORM["overcrank_points"]
KITS = {name: tuple((a.get("companions", 0), a.get("items", 0), a.get("charms", 0)) for a in alternatives)
        for name, alternatives in LOGIC["kits"].items()}
# Fights before this map tier (the first boss and the battles around it) need no cards.
CARDS_FROM_TIER = LOGIC["battles"]["cards_from_tier"]
# Charms are items one by one (2026-11-02); where logic counts a pack, it may count this many charms.
CHARMS_PER_PACK = LOGIC["charms_per_pack"]
PACK_KINDS = ("Companion", "Item", "Charm")


def clan_packs(clan: str, kind: str) -> list[str]:
    """
    What a run of this clan draws from (General and its own, and for an extension's tribe the vanilla clan
    whose pools it shares): packs of a kind, or (Charm) charms.
    """
    pools = ("General", clan, SHARES[clan]) if clan in SHARES else ("General", clan)
    return [name for _, name, _, info in ITEMS if info.get("clan") in pools and
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


def step_value(steps: list, points: int) -> int:
    """A ramp's value at these storm points: the last step whose "from_points" they reach (0 before the first)."""
    return max((step["extra"] for step in steps if points >= step["from_points"]), default=0)


def forced_extra(world: WildfrostWorld) -> int:
    """
    Force Storm Bells Up To makes every run harder, so logic adds packs of any kind to the win kits
    (logic "forced_extra": one when forcing, two at Overcrank; the user's calls 2026-11-02 and 11-06).
    """
    return step_value(LOGIC["forced_extra"], world.options.force_storm_bells_up_to.value)


def forced_pack_extra(points: int) -> int:
    """The client's forcing ramp (logic "forcing"): the extra packs a run needs before bells up to these points are forced."""
    return step_value(LOGIC["forcing"]["extra"], points)


def kit(name: str, clan: str, extra: int = 0):
    """A kit's packs for a run of that clan, plus the forced extra."""
    rules = [packs(clan, *counts, extra) for counts in KITS[name]]
    return Or(*rules) if len(rules) > 1 else rules[0]


def bells_for(points: int, world: WildfrostWorld | None = None) -> int:
    """
    The Progressive Storm Bells that reach these storm points. Overcrank takes every level; anything up to
    the True Final Boss's threshold is held to it (world.true_final_points: lower when an extension removes
    so many storm bells that 10 can't be reached, the user's call 2026-11-15).
    """
    if points >= OVERCRANK_POINTS:
        return STORM_BELL_LEVELS
    if world is not None and points >= TRUE_FINAL_POINTS:
        return world.true_final_bells + -(-(points - TRUE_FINAL_POINTS) // POINTS_PER_LEVEL)
    return -(-points // POINTS_PER_LEVEL)


def kit_with_bells(name: str, clan: str, extra: int, bells: int):
    return both(kit(name, clan, extra), Has(STORM_BELL, bells) if bells else None)


def final_boss_kit(clan: str, extra: int = 0):
    return kit(LOGIC["battles"]["kit"], clan, extra)


def true_final_kit(clan: str, extra: int = 0, bells: int = TRUE_FINAL_BELLS):
    """The True Final Boss fight: its kit and the bells that reach it (world.true_final_bells)."""
    return kit_with_bells(LOGIC["battles"]["true_final_kit"], clan, extra, bells)


def goal_kit(world: WildfrostWorld, clan: str, extra: int):
    """A win for the goal: its kit, and the bells for its storm points (logic "goals")."""
    goal = LOGIC["goals"][world.options.goal.current_key]
    return kit_with_bells(goal["kit"], clan, extra, bells_for(goal["storm_points"], world))


def bell_kits(true_final_bells: int = TRUE_FINAL_BELLS) -> list:
    """
    For slot_data: the most bell levels each kit carries, and its packs. Force Storm Bells Up To only
    forces the bells a run's clan has the packs for (decided by the user 2026-11-02): each level takes the
    kit for its storm points (logic "forcing"), plus its forced extra (forced_pack_extra). Logic can't
    follow forced bells itself, since a requirement can't grow as items arrive.
    true_final_bells (world.true_final_bells): when an extension's removals lower the True Final Boss
    threshold, the level that reaches it takes its kit, and the kits above move down with it; the
    forced extra stays on the level's own storm points.
    """
    shift = POINTS_PER_LEVEL * (TRUE_FINAL_BELLS - true_final_bells)
    def alternatives(counts, extra):
        # The forced extra as in packs(): each one more companion or item pack, or that many charms.
        return [{"Companion": c, "Item": i, "Charm": ch, "extra": extra, "charms_per_pack": CHARMS_PER_PACK} for c, i, ch in counts]

    kits = []
    for level in range(1, STORM_BELL_LEVELS + 1):
        points = POINTS_PER_LEVEL * level
        name = next(step["kit"] for step in LOGIC["forcing"]["kits"] if min(points + shift, OVERCRANK_POINTS) <= step["up_to_points"])
        entry = alternatives(KITS[name], forced_pack_extra(points))
        if kits and kits[-1][1] == entry:
            kits[-1][0] = level  # same packs as the level below: one kit carries both
        else:
            kits.append([level, entry])
    return kits


# Reverse Storm Bells (designed with the user 2026-11-05): runs start Overcranked and each
# Progressive Storm Bell lowers the floor a step. Logic "reverse.stretches": the packs a run needs to get
# through each stretch, by bells received (0 = Overcranked, then 20, 18, ... 2 storm points, and every
# bell = none). A pack is a companion or item pack, or CHARMS_PER_PACK charms. Placeholder numbers, to
# tune from playtests (the client's "Run summary" log line).
REVERSE_PACKS = LOGIC["reverse"]["stretches"]


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
    return kit_with_bells(LOGIC["reverse"]["true_final_kit"], clan, 0, STORM_BELL_LEVELS)


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


def battle_kit(info: dict, extra: int, tf_bells: int = TRUE_FINAL_BELLS):
    if info.get("true_final"):
        return true_final_kit(info["run_tribe"], extra, tf_bells)
    return final_boss_kit(info["run_tribe"], extra) if info["tier"] >= CARDS_FROM_TIER else None


def any_clan(kit, clans=BASE_CLANS):
    """A challenge any clan (of the slot's tribes, WildfrostWorld.tribes) can do, with that clan's tribe item."""
    return Or(*(both(tribe_rule({clan}), kit(clan)) for clan in clans))


def battle_rule(key: str, info: dict, extra: int, reversed_bells: bool = False, tf_bells: int = TRUE_FINAL_BELLS):
    if reversed_bells:
        clan = info["run_tribe"]
        kit = reverse_true_final_kit(clan) if info.get("true_final") else reverse_kit(clan, reverse_stretch(info["area"], info["tier"]))
        return both(tribe_rule(required_tribes(key, info)), kit)
    return both(tribe_rule(required_tribes(key, info)), battle_kit(info, extra, tf_bells))


def card_packs(clan: str, count: int):
    """Companion and item packs together."""
    return HasFromList(*(clan_packs(clan, "Companion") + clan_packs(clan, "Item")), count=count)


def uses_area_kit(info: dict) -> bool:
    """Whether the rule takes its area's kit itself, for a set clan ("clan_kit" with "area_kit")."""
    return '"area_kit": true' in json.dumps(info.get("rule"))


def area_kit(region: str, clan: str, extra: int, tf_bells: int = TRUE_FINAL_BELLS, true_final: bool = False):
    """
    What a run of a clan needs to do a challenge in that region (logic "regions"; the user's calls,
    2026-11-16): Area 1 nothing; Area 2 the Final Boss kit, which Area 2's battles need (only when a rule
    asks, "area_kit"); Area 3 a won run, the Final Boss kit; Area 4 the True Final Boss kit's packs. A
    challenge that is the True Final Boss fight itself ("true_final": Sunbringer) needs its bells too.
    """
    name = LOGIC["regions"].get(region)
    if name is None:
        return None
    return kit_with_bells(name, clan, extra, tf_bells if true_final else 0)


def challenge_kit(info: dict, extra: int, reversed_bells: bool = False, tf_bells: int = TRUE_FINAL_BELLS,
                  clans=BASE_CLANS):
    """
    A challenge's area kit, any clan: Area 3 and 4 always (area_kit), unless its rule takes it for a set
    clan. Its own needs (cards, packs, tribes) are its rule (CardRules.extension_rule).
    """
    if reversed_bells:
        return reverse_challenge_kit(info, clans)
    region = challenge_region(info)
    if region not in ("Area 3", "Area 4") or uses_area_kit(info):
        return None
    return any_clan(lambda clan: area_kit(region, clan, extra, tf_bells, bool(info.get("true_final"))), clans)


def reverse_challenge_kit(info: dict, clans=BASE_CLANS):
    """
    Reverse Storm Bells: the normal pack needs (without the forced extra), plus getting as far as
    the challenge's area at the run's bells. The win challenges take the Area 3 stretch.
    """
    if info.get("true_final"):
        return any_clan(reverse_true_final_kit, clans)
    base = challenge_kit(info, 0, clans=clans)
    region = challenge_region(info)
    if region == "Area 1":
        return base
    stretch = "Area 3" if region in ("Area 3", "Area 4") else "Area 2"
    tribes = sorted(rule_tribes(info.get("rule")))
    clan = tribes[0] if len(tribes) == 1 else None
    reach = reverse_kit(clan, stretch) if clan else any_clan(lambda c: reverse_kit(c, stretch), clans)
    return both(base, reach)


# Challenges that need particular cards (decided by the user 2026-10-31), by CardData name. A card
# is in logic with the pack holding it this seed, and a run of its clan (the tribe item for
# Shademancer and Clunkmaster cards). Clunkers are the pool cards of the game's Clunker type.
CLAN_OF_CARD = {key.removeprefix("card:"): info["clan"] for key, _, info in CARDS}
# The groups live in groups.py, where extensions can add to them (PLAN.md §10).
CLUNKERS = GROUPS["clunkers"]
SHELL_CARDS = GROUPS["shell"]
FRENZY_CARDS = GROUPS["frenzy"]
BLOCK_CARDS = GROUPS["block"]
SACRIFICE_CARDS = GROUPS["sacrifice"]
TEETH_CARDS = GROUPS["teeth"]
SHROOM_CARDS = GROUPS["shroom"]
SPICE_CARDS = GROUPS["spice"]
# Each challenge's needs are its row's "rule" in base.wildfrost.json (PLAN.md §10, phase 2).


class Impossible(Exception):
    """A rule needs a card this seed doesn't have (an extension removed it, PLAN.md §10)."""


class CardRules:
    """
    Card needs. A card is in logic with the pack holding it this seed; one that isn't in this seed (an
    extension removed it, or it's from an extension the slot didn't pick) raises Impossible, and the
    "any of" helpers drop such alternatives (either), raising only when none is left.
    """

    def __init__(self, world: WildfrostWorld):
        pack_names = {key: name for key, name, _, _ in ITEMS}
        self.world = world
        self.clans = tuple(getattr(world, "tribes", BASE_CLANS))
        self.extra = forced_extra(world)
        self.reversed = reverse(world)
        self.pack_of = {card.removeprefix("card:"): pack_names[pack]
                        for pack, cards in world.pack_contents.items() for card in cards}
        # A charm is its own item: those of this slot's game that no extension removes.
        removed = getattr(world, "removed", {}).get("charms", set())
        drawn = drawn_clans(world)  # a clan no tribe here draws from has no charms in the seed
        self.pack_of.update({info["card"].removeprefix("card:"): name for _, name, _, info in ITEMS
                             if info["kind"] == "Charm" and world.uses(info) and info["clan"] in drawn
                             and info["card"].removeprefix("card:") not in removed})

    @staticmethod
    def either(*alternatives):
        """Any of these (rules, or callables making one); impossible ones are dropped."""
        rules = []
        for alternative in alternatives:
            try:
                rules.append(alternative() if callable(alternative) and not isinstance(alternative, Rule) else alternative)
            except Impossible:
                pass
        if not rules:
            raise Impossible("no alternative left")
        if any(rule is None for rule in rules):  # one alternative needs nothing
            return None
        return rules[0] if len(rules) == 1 else Or(*rules)

    def bell(self, bell: str):
        """
        A run that can ring this storm bell: enough Progressive Storm Bells for its points (each raises
        the limit by POINTS_PER_LEVEL; Reverse runs start with every bell). Impossible if this seed lacks the bell.
        """
        points = self.world.bell_points.get(bell)
        if points is None:
            raise Impossible(bell)
        return None if self.reversed else Has(STORM_BELL, max(1, -(-points // POINTS_PER_LEVEL)))

    def drawn_by(self, clans) -> Rule | None:
        """
        A run that can be offered cards of these clans: for each, its tribe or one of the slot's extension
        tribes that shares its pools (the user's call, 2026-11-16: Terraria Aliens draws Clunkmaster cards).
        General cards need no tribe.
        """
        parts = []
        for clan in sorted(c for c in clans if c in CLANS):
            runners = [t for t in self.clans if t == clan or SHARES.get(t) == clan]
            if not runners:
                raise Impossible(f"tribe {clan}")
            parts.append(Or(*(tribe_rule({t}) for t in runners)) if len(runners) > 1 else tribe_rule({runners[0]}))
        return both(*parts)

    def card(self, card: str):
        if card not in self.pack_of:
            raise Impossible(card)
        return both(self.drawn_by({CLAN_OF_CARD[card]}), Has(self.pack_of[card]))

    def members(self, cards, clans=None) -> list:
        """
        A group's members this seed: its cards with a pack (removed ones and those from an extension this
        slot didn't pick are skipped) and its tribes ("tribe:<clan>": a clan whose leaders do it).
        """
        return [c for c in cards if c.startswith("tribe:") and c[6:] in self.clans
                or c in self.pack_of and (clans is None or CLAN_OF_CARD[c] in clans)]

    def member(self, member: str):
        return Has(CLANS[member[6:]]) if member.startswith("tribe:") else self.card(member)

    def any_of(self, cards, clans=None):
        members = self.members(cards, clans)
        if not members:
            raise Impossible("none of the cards")
        return Or(*(self.member(c) for c in members)) if len(members) > 1 else self.member(members[0])

    def all_of(self, *cards):
        """Every one of these cards: their packs (one pack can hold several) and their clans."""
        missing = [c for c in cards if c not in self.pack_of]
        if missing:
            raise Impossible(", ".join(missing))
        tribes = self.drawn_by({CLAN_OF_CARD[c] for c in cards})
        packs = sorted({self.pack_of[c] for c in cards})
        return both(tribes, HasAll(*packs) if len(packs) > 1 else Has(packs[0]))

    def two_of(self, cards):
        """Two different cards: their packs (one pack can hold both) and their clans."""
        members = self.members(cards)
        if len(members) < 2:
            raise Impossible("fewer than two of the cards")

        def pair(a: str, b: str):
            tribes = [m for m in (a, b) if m.startswith("tribe:")]
            rest = [m for m in (a, b) if not m.startswith("tribe:")]
            return both(*(self.member(t) for t in tribes), self.all_of(*rest) if rest else None)
        return Or(*(pair(a, b) for a, b in combinations(members, 2)))

    def with_any(self, card: str, partners):
        """A card together with any one of the partners."""
        return self.either(*(lambda p=p: self.all_of(card, p) for p in partners))

    def extension_rule(self, rule, region: str = "Area 1"):
        """A challenge's rule from its row (extensions.RULE_FORMS; ours or an extension's) as rule objects."""
        form = rule[0]
        if form == "or":  # alternatives this seed can't have are dropped; a battle's are each one of them
            alternatives = []
            for child in rule[1]:
                if child[0] == "battle":
                    alternatives += self.battle_alternatives(child[1])
                else:
                    alternatives.append(lambda child=child: self.extension_rule(child, region))
            return self.either(*alternatives)
        if form == "battle":
            return self.either(*self.battle_alternatives(rule[1]))
        if form == "and":
            return both(*(self.extension_rule(child, region) for child in rule[1]))
        if form == "has":
            return Has(ITEM_NAME_BY_KEY[rule[1]], rule[2])
        if form == "all":
            return HasAll(*(ITEM_NAME_BY_KEY[k] for k in rule[1]))
        if form == "any":
            return HasFromList(*(ITEM_NAME_BY_KEY[k] for k in rule[1]), count=rule[2])
        if form == "packs":
            clan, kind, count = rule[1:]
            pool = clan_packs(clan, "Companion") + clan_packs(clan, "Item") if kind == "" else clan_packs(clan, kind)
            return HasFromList(*pool, count=count)
        if form == "tribe":
            if rule[1] not in self.clans:
                raise Impossible(f"tribe {rule[1]}")
            return tribe_rule({rule[1]})
        if form == "cards":  # these cards together
            return self.all_of(*rule[1])
        if form == "with":  # a card together with any one of a group's (or a list's) cards
            partners = GROUPS[rule[2]] if isinstance(rule[2], str) else rule[2]
            return self.with_any(rule[1], [p for p in partners if not p.startswith("tribe:")])
        if form == "bell":
            return self.bell(rule[1])
        if form == "applies":
            return self.applies(rule[1])
        if form == "trait":
            return self.applies(rule[1], "traits")
        if form == "clan_kit":
            return self.clan_kit(rule[1], region)
        if form == "starts_with":  # a run of a tribe whose starting deck has the card
            return self.either(*(lambda clan=clan: tribe_rule({clan}) for clan in self.starters(rule[1])))
        if form == "card":
            return self.card(rule[1])
        cards = GROUPS[rule[1]] if isinstance(rule[1], str) else rule[1]
        if form == "any_card":  # an optional third entry keeps the cards of those clans
            return self.any_of(cards, tuple(rule[2]) if len(rule) > 2 else None)
        return self.two_of(cards)

    def applies(self, effect: str, field: str = "applies"):
        """
        A card this seed has that applies the effect (its "applies", from the content dump), or a clan whose
        leaders apply it (the user's call, 2026-11-15: leaders count, e.g. only Clunkmaster leaders apply Bom).
        With field "traits", a card or leader with that trait (keyword: Smackback, Consume, ...).
        """
        cards = [key[5:] for key, _, info in CARDS if effect in info.get(field, ())]
        tribes = [f"tribe:{clan}" for clan, leaders in LEADERS.items()
                  if clan in self.clans and any(effect in leader.get(field, ()) for leader in leaders)]
        return self.any_of(tribes + cards)

    def clan_kit(self, spec: dict, region: str):
        """
        ["clan_kit", {...}]: one clan's run with its tribe and: "companions", "items" (packs), "charms",
        "cards" (companion or item packs together); "forced_extra" adds the forced bells' extra pack to the
        items; "area_kit" adds the region's kit for that same clan (area_kit). "clan" sets the clan;
        otherwise any clan will do.
        """
        def kit(clan: str):
            items = spec.get("items", 0) + (self.extra if spec.get("forced_extra") else 0)
            counts = (spec.get("companions", 0), items, spec.get("charms", 0))
            parts = [packs(clan, *counts) if any(counts) else None,
                     card_packs(clan, spec["cards"]) if spec.get("cards") else None,
                     area_kit(region, clan, self.extra, self.world.true_final_bells) if spec.get("area_kit") else None]
            return both(*parts)
        clan = spec.get("clan")
        if clan and clan not in self.clans:
            raise Impossible(f"tribe {clan}")
        if clan:
            return both(tribe_rule({clan}), kit(clan))
        # "starts_with": only the slot's tribes whose starting deck has that card (the user's call, 2026-11-24).
        return any_clan(kit, self.starters(spec["starts_with"]) if spec.get("starts_with") else self.clans)

    def starters(self, card: str) -> list:
        """
        This slot's tribes whose starting deck has the card, or one of a group's cards (["starts_with", "clunkers"],
        the user's call 2026-11-24); Impossible when none do.
        """
        cards = set(GROUPS[card]) if card in GROUPS else {card}
        clans = [clan for clan in self.clans if cards & set(START_DECKS.get(clan, ()))]
        if not clans:
            raise Impossible(f"no tribe here starts with {card}")
        return clans

    def battle_alternatives(self, battle: str) -> list:
        """Winning that battle (BattleData name), with any run tribe it's a check for, unless it was removed."""
        if battle in getattr(self.world, "removed", {}).get("battles", ()):
            return []
        # Only this slot's rows: another extension's tribe can't win it here (found in review, 2026-11-24).
        return [battle_rule(key, info, self.extra, self.reversed, self.world.true_final_bells) for key, _, _, info in LOCATIONS
                if key.startswith("battle:") and key.split(":")[2] == battle and not info.get("second")
                and info["run_tribe"] in self.clans and self.world.uses(info)]


def impossible_challenges(world: WildfrostWorld) -> set[str]:
    """
    Challenges (by internal name) this slot can't do after its extensions' removals (PLAN.md §10), or without
    the tribes the Tribes option left out, found before the locations are made so they're left out
    (locations.included) and the pool fits.
    """
    if not any(getattr(world, "removed", {}).values()) and not getattr(world, "tribes_limited", False):
        return set()
    cards = CardRules(world)
    impossible = set()
    for key, _, _, info in LOCATIONS:
        if not key.startswith("challenge:") or not world.uses(info):
            continue
        try:
            if info.get("rule"):
                cards.extension_rule(info["rule"], challenge_region(info))
        except Impossible:
            impossible.add(info["internal"])
    return impossible


# Rules for the client's tracker (slot_data "location_rules"), with item names turned into the item
# keys the client tracks: ["and", [...]], ["or", [...]], ["has", key, count], ["all", [keys]],
# ["any", [keys], count], and ["packs", clan, kind, count] for what a clan's runs draw from (General
# and its own): its Companion or Item packs, its Charm items, or ("") its companion and item packs
# together, which would otherwise list every key each time. A location without an
# entry needs nothing.
ITEM_KEY_BY_NAME = {name: key for key, name, _, _ in ITEMS}
ITEM_NAME_BY_KEY = {key: name for key, name, _, _ in ITEMS}
# The first clan to have a set wins, the vanilla clans first: a tribe with no charms (or packs) of its own has
# exactly its shared clan's set, and the vanilla clan is the one every slot's client knows (found in review,
# 2026-11-24: the tribe had taken Basic's charm rules over, vanilla slots included). Equal sets are the same items,
# so either name counts the same.
PACK_GROUPS: dict[frozenset, list] = {}
for _clan in (*BASE_CLANS, *(c for c in CLANS if c not in BASE_CLANS)):
    for _kind in PACK_KINDS:
        PACK_GROUPS.setdefault(frozenset(clan_packs(_clan, _kind)), [_clan, _kind])
    # "": companion and item packs together (the forced extra's count).
    PACK_GROUPS.setdefault(frozenset(clan_packs(_clan, "Companion") + clan_packs(_clan, "Item")), [_clan, ""])


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
        if not included(world, info, key):
            continue
        if key.startswith("battle:"):
            rule = battle_rule(key, info, extra, reversed_bells, world.true_final_bells)
        else:
            # A challenge's own needs: its row's rule, ours and extensions' alike (PLAN.md §10).
            needs = cards.extension_rule(info["rule"], challenge_region(info)) if info.get("rule") else None
            rule = both(challenge_kit(info, extra, reversed_bells, world.true_final_bells, world.tribes), needs)
        if rule is not None:
            world.set_rule(world.get_location(name), rule)
            world.location_rules[key] = rule_json(rule)

    for clan in world.tribes:
        win = reverse_true_final_kit(clan) if reversed_bells else goal_kit(world, clan, extra)
        world.set_rule(world.get_location(victory_location(clan)), both(tribe_rule({clan}), win))

    world.set_completion_rule(Has(VICTORY_ITEM, world.options.clans_required.value))
