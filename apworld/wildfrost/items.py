from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification

from .data import CARDS, ITEMS, PACK_SIZE

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
# Pets are useful, except where logic counts one: Spike's Teeth for "Kill 10 enemies with Teeth".
SPIKE_PET = "Spike Pet"
PROGRESSION_PETS = {SPIKE_PET}
# Unlock the bells (5 storm points), raise the cap to 6, 7, 8, 9 and 10, Overcrank.
STORM_BELL_LEVELS = 7

CLASSIFICATION_BY_KIND = {
    # Tribes gate tribe-locked battles and the "win with tribe" challenges.
    "Tribe": ItemClassification.progression,
    "Event": ItemClassification.useful,
    "Pet": ItemClassification.useful,
    # Bell levels gate the True Final Boss and the harder goals.
    "StormBell": ItemClassification.progression,
    # Packs are deck strength: the second boss onwards needs some (rules.py).
    "Pack": ItemClassification.progression,
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


def create_all_items(world: WildfrostWorld) -> None:
    # No card is unlocked from the start: every card arrives in a pack. The starting tribe is in the
    # starting inventory (world.generate_early), so it's left out here.
    start = starting_tribe(world)
    itempool: list[Item] = [
        world.create_item(name) for name, kind in KIND_BY_NAME.items()
        if kind in ("Tribe", "Event", "Pet", "Pack") and name != start
    ]
    itempool += [world.create_item(STORM_BELL) for _ in range(STORM_BELL_LEVELS + world.options.extra_storm_bells.value)]
    free = len(world.multiworld.get_unfilled_locations(world.player)) - len(itempool)
    itempool += [world.create_filler() for _ in range(free)]
    world.multiworld.itempool += itempool
