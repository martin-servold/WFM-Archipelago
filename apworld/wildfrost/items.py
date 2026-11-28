from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification

from .content import BONUS, CARDS, DRAWS, ITEMS
from .data import LOGIC

if TYPE_CHECKING:
    from .world import WildfrostWorld

ITEM_NAME_TO_ID = {name: item_id for _, name, item_id, _ in ITEMS}
ITEM_KEY_BY_ID = {item_id: key for key, _, item_id, _ in ITEMS}
KIND_BY_NAME = {name: info["kind"] for _, name, _, info in ITEMS}
PACK_KEYS = [key for key, _, _, info in ITEMS if info["kind"] == "Pack"]
INFO_BY_KEY = {key: info for key, _, _, info in ITEMS}
INFO_BY_NAME = {name: info for _, name, _, info in ITEMS}
ITEM_KEY_BY_NAME = {name: key for key, name, _, _ in ITEMS}
ITEM_NAME_BY_KEY = {key: name for key, name, _, _ in ITEMS}
CARD_KIND_BY_KEY = {key: info["kind"] for key, _, info in CARDS}

# Filler is Bling and the boons; trap_percentage of it is traps instead.
FILLER_NAMES = [name for _, name, _, info in ITEMS if info["kind"] == "Filler"]
TRAP_NAMES = [name for _, name, _, info in ITEMS if info["kind"] == "Trap"]


def filler_name(world: WildfrostWorld) -> str:
    if world.random.randint(1, 100) <= world.options.trap_percentage.value:
        return world.random.choice(TRAP_NAMES)
    return world.random.choice(FILLER_NAMES)


STORM_BELL = "Progressive Storm Bell"
# Steps of two storm points (decided by the user 2026-11-06): caps 2, 4, ... 20, then Overcrank (22).
# Reverse runs the other way: Overcranked, 20, 18, ... 2, then no bells. The client lifts vanilla's
# 10-point cap for these seeds; seeds from before (slot_data without storm_bell_levels) had 7 levels:
# 5 storm points, up to 10, Overcrank.
# The numbers are the base file's logic "storm_bells" (PLAN.md §10, phase 3).
STORM_BELL_LEVELS = LOGIC["storm_bells"]["levels"]
# The 5th bell reaches the True Final Boss's 10 storm points.
TRUE_FINAL_BELLS = -(-LOGIC["storm_bells"]["true_final_points"] // LOGIC["storm_bells"]["points_per_level"])

CLASSIFICATION_BY_KIND = {
    # Tribes gate tribe-locked battles and the "win with tribe" challenges.
    "Tribe": ItemClassification.progression,
    "Event": ItemClassification.useful,
    "Pet": ItemClassification.useful,
    # Bell levels gate the True Final Boss and the harder goals.
    "StormBell": ItemClassification.progression,
    # Packs and charms are deck strength: the second boss onwards needs some (rules.py).
    "Pack": ItemClassification.progression,
    "Charm": ItemClassification.progression,
    "Filler": ItemClassification.filler,
    "Trap": ItemClassification.trap,
}


class WildfrostItem(Item):
    game = "Wildfrost"


def forward(world: WildfrostWorld) -> bool:
    return world.options.progression_direction != world.options.progression_direction.option_reverse


def bells_are_filler(world: WildfrostWorld) -> bool:
    """A forward Final Boss goal: bells gate nothing there, they only raise (and force) the difficulty."""
    return world.goal_sized_bells and forward(world) and world.options.goal == world.options.goal.option_final_boss


def storm_bells_in_pool(world: WildfrostWorld) -> int:
    """
    Bell levels in the pool, before Extra Storm Bells (decided by the user 2026-11-08: with all 11 in a
    forward True Final Boss seed, the 5 it needs came early). Forward True Final Boss seeds, any number of
    clans, get the 5 they need, so their storm point limit tops out at 10 plus the extras. The others get
    all 11: Overcranked and Reverse need every one, and the Final Boss goal's are filler.
    Seeds from before (goal_sized_bells false, for Universal Tracker) always had all 11.
    """
    if world.goal_sized_bells and forward(world) and world.options.goal == world.options.goal.option_true_final_boss:
        return world.true_final_bells
    return STORM_BELL_LEVELS


def named_items(world: WildfrostWorld) -> set[str]:
    """
    Items a rule names by key (["has", ...], ["all", ...], ["any", ...]) in a challenge this slot can have: its
    extensions' and, with New Challenges, ours. Pets and map events are only useful unless one is named, then
    progression, so logic can count it (found in review, 2026-11-25: an extension's ["has", "pet:..."] could
    never be reached). For the base game that's what the hand-kept list was: Spike (Teeth), Loki (Demonize),
    Sneezle (Hoarder), and with New Challenges Binku (Ink) and the three map events. Worked out once, before
    the checks exist (the starting pet is made in generate_early), so a check left out later still counts.
    """
    cached = getattr(world, "_named_items", None)
    if cached is not None:
        return cached
    from .content import LOCATIONS  # noqa: PLC0415  (content imports this module)

    def walk(rule, found):
        if isinstance(rule, list) and rule:
            if rule[0] == "has":
                found.add(rule[1])
            elif rule[0] in ("all", "any"):
                found.update(rule[1])
            elif rule[0] in ("and", "or"):
                for child in rule[1]:
                    walk(child, found)
    keys: set[str] = set()
    for key, _, _, info in LOCATIONS:
        if key.startswith("challenge:") and world.uses(info) and (not info.get("ap") or world.options.new_challenges):
            walk(info.get("rule"), keys)
    world._named_items = {ITEM_NAME_BY_KEY[k] for k in keys if k in ITEM_NAME_BY_KEY}
    return world._named_items


def create_item(world: WildfrostWorld, name: str) -> WildfrostItem:
    progression = KIND_BY_NAME[name] in ("Pet", "Event") and name in named_items(world)
    classification = ItemClassification.progression if progression else CLASSIFICATION_BY_KIND[KIND_BY_NAME[name]]
    if name == STORM_BELL and bells_are_filler(world):
        classification = ItemClassification.filler
    return WildfrostItem(name, classification, ITEM_NAME_TO_ID[name], world.player)


def drawn_clans(world: WildfrostWorld) -> set[str]:
    """
    The reward pools this slot's tribes draw from (content.DRAWS): General, each tribe's own, and the clans an
    extension's tribe shares, plus the clans of the cards its own pools reuse (content.BONUS, not counted in logic).
    A clan none of them draws from (the Tribes option left its tribe out, or every tribe's pools leave out General)
    has no packs or charms in the seed (the user's call, 2026-11-24).
    """
    tribes = getattr(world, "tribes", ())
    if not tribes:
        return {"General"}
    return {clan for tribe in tribes for clan in (*DRAWS.get(tribe, ("General", tribe)), *BONUS.get(tribe, ()))}


def fill_packs(world: WildfrostWorld) -> dict[str, list[str]]:
    """
    Deal each clan's cards of one kind into that group's packs, shuffled per seed. The cards are
    spread evenly (13 into 5 packs is 3, 3, 3, 2, 2 rather than 3, 3, 3, 3, 1), and which packs are
    the smaller ones is shuffled too.
    """
    packs: dict[str, list[str]] = {}
    removed = {"card:" + name for name in world.removed["cards"]}
    # An extension's cards go only into its own packs (the user's call, 2026-11-15), so each mod
    # (None: the base game) deals its own clan and kind groups. Cards an extension removes aren't dealt.
    drawn = drawn_clans(world)
    groups = dict.fromkeys((*key.split(":")[1:3], INFO_BY_KEY[key].get("ext")) for key in PACK_KEYS
                           if world.uses(INFO_BY_KEY[key]) and INFO_BY_KEY[key]["clan"] in drawn)
    for clan, kind, mod in groups:
        cards = [key for key, _, info in CARDS if info["clan"] == clan and info["kind"] == kind
                 and info.get("ext") == mod and key not in removed]
        world.random.shuffle(cards)
        group_packs = [key for key in PACK_KEYS if key.startswith(f"pack:{clan}:{kind}:") and INFO_BY_KEY[key].get("ext") == mod]
        # An extension's themed packs hold the cards they list, every seed; the rest are dealt below.
        for key in [k for k in group_packs if "cards" in INFO_BY_KEY[k]]:
            packs[key] = list(INFO_BY_KEY[key]["cards"])
            cards = [c for c in cards if c not in packs[key]]
            group_packs.remove(key)
        if not group_packs:
            continue
        # Fewer, fuller packs when the seed is short of checks (shrink_extension_packs).
        group_packs = group_packs[:getattr(world, "pack_limits", {}).get((clan, kind, mod), len(group_packs))]
        base, extra = divmod(len(cards), len(group_packs))
        sizes = [base + 1] * extra + [base] * (len(group_packs) - extra)
        world.random.shuffle(sizes)
        start = 0
        for key, size in zip(group_packs, sizes):
            packs[key] = cards[start:start + size]
            start += size
    return packs


# starting_tribe values, in option order (then Any Tribe: WildfrostWorld.choose_starting_tribe).
STARTING_TRIBES = ["Snowdwellers", "Shademancers", "Clunkmasters"]


def starting_tribe(world: WildfrostWorld) -> str:
    """The starting tribe's item name."""
    return getattr(world, "starting_tribe_name", None) or STARTING_TRIBES[world.options.starting_tribe.value]


PET_NAMES = [name for name, kind in KIND_BY_NAME.items() if kind == "Pet"]


def pet_names(world: WildfrostWorld) -> list[str]:
    """The pets this slot can have: ours, and those of the extensions it uses (PLAN.md §10)."""
    return [name for name in PET_NAMES if world.uses(INFO_BY_NAME[name]) and in_seed(world, name)]


def in_seed(world: WildfrostWorld, name: str) -> bool:
    """
    Whether an item is in this slot's pool: not from an extension it didn't pick, not a charm an extension
    removes, and not a pack left empty by removed cards (PLAN.md §10).
    """
    info = INFO_BY_NAME[name]
    if not world.uses(info):
        return False
    if info["kind"] == "Tribe":  # the Tribes option can leave some out
        return ITEM_KEY_BY_NAME[name].removeprefix("tribe:") in world.tribes
    if info["kind"] == "Charm":
        return info["card"].removeprefix("card:") not in world.removed["charms"] and info["clan"] in drawn_clans(world)
    if info["kind"] == "Pack":
        return bool(world.pack_contents.get(ITEM_KEY_BY_NAME[name]))
    if info["kind"] == "Pet":  # a pet an extension removes (Another Snowfall replaces the base game's)
        return ITEM_KEY_BY_NAME[name].removeprefix("pet:") not in getattr(world, "removed", {}).get("pets", ())
    return True


def real_item_count(world: WildfrostWorld) -> int:
    """The items create_all_items puts in the pool before filler."""
    start = {starting_tribe(world), world.starting_pet}
    count = sum(1 for name, kind in KIND_BY_NAME.items()
                if kind in ("Tribe", "Event", "Pet", "Pack", "Charm") and name not in start and in_seed(world, name))
    return count + storm_bells_in_pool(world) + world.options.extra_storm_bells.value


def shrink_extension_packs(world: WildfrostWorld) -> bool:
    """
    One pack fewer for the extension group (clan, kind, mod) with the most packs, its cards dealt again
    into the rest (fuller packs; the user's fallback, 2026-11-15). False when each group is down to one.
    """
    counts = {}
    for key, cards in world.pack_contents.items():
        info = INFO_BY_KEY[key]
        if "ext" in info and cards and "cards" not in info:  # themed packs keep their cards
            group = (info["clan"], info["card_kind"], info["ext"])
            counts[group] = counts.get(group, 0) + 1
    shrinkable = sorted((-n, group) for group, n in counts.items() if n > 1)
    if not shrinkable:
        return False
    n, group = shrinkable[0]
    world.pack_limits[group] = -n - 1
    world.pack_contents = fill_packs(world)
    return True


def create_all_items(world: WildfrostWorld) -> None:
    # No card is unlocked from the start: every card arrives in a pack. The starting tribe and pet are
    # in the starting inventory (world.generate_early), so they're left out here.
    start = {starting_tribe(world), world.starting_pet}
    itempool: list[Item] = [
        world.create_item(name) for name, kind in KIND_BY_NAME.items()
        if kind in ("Tribe", "Event", "Pet", "Pack", "Charm") and name not in start and in_seed(world, name)
    ]
    bells = [world.create_item(STORM_BELL) for _ in range(storm_bells_in_pool(world) + world.options.extra_storm_bells.value)]
    if bells and bells_are_filler(world) and world.options.new_challenges:
        # Some New Challenges ring a storm bell, so one bell stays progression (the user's call, 2026-11-08).
        bells[0].classification = ItemClassification.progression
    itempool += bells
    free = len(world.multiworld.get_unfilled_locations(world.player)) - len(itempool)
    itempool += [world.create_filler() for _ in range(free)]
    world.multiworld.itempool += itempool
