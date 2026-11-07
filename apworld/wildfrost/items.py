from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification

from .data import CARDS, ITEMS

if TYPE_CHECKING:
    from .world import WildfrostWorld

ITEM_NAME_TO_ID = {name: item_id for _, name, item_id, _ in ITEMS}
ITEM_KEY_BY_ID = {item_id: key for key, _, item_id, _ in ITEMS}
KIND_BY_NAME = {name: info["kind"] for _, name, _, info in ITEMS}
PACK_KEYS = [key for key, _, _, info in ITEMS if info["kind"] == "Pack"]
CARD_KIND_BY_KEY = {key: info["kind"] for key, _, info in CARDS}

# Filler is Bling and the boons; trap_percentage of it is traps instead.
FILLER_NAMES = [name for _, name, _, info in ITEMS if info["kind"] == "Filler"]
TRAP_NAMES = [name for _, name, _, info in ITEMS if info["kind"] == "Trap"]


def filler_name(world: WildfrostWorld) -> str:
    if world.random.randint(1, 100) <= world.options.trap_percentage.value:
        return world.random.choice(TRAP_NAMES)
    return world.random.choice(FILLER_NAMES)


STORM_BELL = "Progressive Storm Bell"
# Pets are useful, except where logic counts one: Spike's Teeth for "Kill 10 enemies with Teeth",
# Loki's Demonize for "Kill 3 Demonized enemies", and Sneezle's draw for "Hoarder". Every seed starts with a random pet (world.generate_early),
# so "Best Friends" needs no rule for one.
SPIKE_PET = "Spike Pet"
LOKI_PET = "Loki Pet"
SNEEZLE_PET = "Sneezle Pet"
PROGRESSION_PETS = {SPIKE_PET, LOKI_PET, SNEEZLE_PET}
# Steps of two storm points (decided by the user 2026-11-06): caps 2, 4, ... 20, then Overcrank (22).
# Reverse runs the other way: Overcranked, 20, 18, ... 2, then no bells. The client lifts vanilla's
# 10-point cap for these seeds; seeds from before (slot_data without storm_bell_levels) had 7 levels:
# 5 storm points, up to 10, Overcrank.
STORM_BELL_LEVELS = 11

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


def create_item(world: WildfrostWorld, name: str) -> WildfrostItem:
    classification = ItemClassification.progression if name in PROGRESSION_PETS else CLASSIFICATION_BY_KIND[KIND_BY_NAME[name]]
    return WildfrostItem(name, classification, ITEM_NAME_TO_ID[name], world.player)


def fill_packs(world: WildfrostWorld) -> dict[str, list[str]]:
    """
    Deal each clan's cards of one kind into that group's packs, shuffled per seed. The cards are
    spread evenly (13 into 5 packs is 3, 3, 3, 2, 2 rather than 3, 3, 3, 3, 1), and which packs are
    the smaller ones is shuffled too.
    """
    packs: dict[str, list[str]] = {}
    groups = dict.fromkeys(tuple(key.split(":")[1:3]) for key in PACK_KEYS)
    for clan, kind in groups:
        cards = [key for key, _, info in CARDS if info["clan"] == clan and info["kind"] == kind]
        world.random.shuffle(cards)
        group_packs = [key for key in PACK_KEYS if key.startswith(f"pack:{clan}:{kind}:")]
        base, extra = divmod(len(cards), len(group_packs))
        sizes = [base + 1] * extra + [base] * (len(group_packs) - extra)
        world.random.shuffle(sizes)
        start = 0
        for key, size in zip(group_packs, sizes):
            packs[key] = cards[start:start + size]
            start += size
    return packs


# starting_tribe values, in option order.
STARTING_TRIBES = ["Snowdwellers", "Shademancers", "Clunkmasters"]


def starting_tribe(world: WildfrostWorld) -> str:
    return STARTING_TRIBES[world.options.starting_tribe.value]


PET_NAMES = [name for name, kind in KIND_BY_NAME.items() if kind == "Pet"]


def create_all_items(world: WildfrostWorld) -> None:
    # No card is unlocked from the start: every card arrives in a pack. The starting tribe and pet are
    # in the starting inventory (world.generate_early), so they're left out here.
    start = {starting_tribe(world), world.starting_pet}
    itempool: list[Item] = [
        world.create_item(name) for name, kind in KIND_BY_NAME.items()
        if kind in ("Tribe", "Event", "Pet", "Pack", "Charm") and name not in start
    ]
    itempool += [world.create_item(STORM_BELL) for _ in range(STORM_BELL_LEVELS + world.options.extra_storm_bells.value)]
    free = len(world.multiworld.get_unfilled_locations(world.player)) - len(itempool)
    itempool += [world.create_filler() for _ in range(free)]
    world.multiworld.itempool += itempool
