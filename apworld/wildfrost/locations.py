from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import ItemClassification, Location, LocationProgressType
from Options import OptionError

from . import items
from .content import LOCATIONS, TRIBES

if TYPE_CHECKING:
    from .world import WildfrostWorld

LOCATION_NAME_TO_ID = {name: loc_id for _, name, loc_id, _ in LOCATIONS}
LOCATION_ID_BY_KEY = {key: loc_id for key, _, loc_id, _ in LOCATIONS}

AREA_REGIONS = ["Area 1", "Area 2", "Area 3"]

# A challenge's region (where it can first be completed: Area 3 for a whole run won, or a fight that
# only happens deeper in) is its row's "region" in base.wildfrost.json, as in an extension's file.

# The goal is a winning run per clan (what counts as winning depends on the goal option). Each is
# an event location holding a "Victory"; the seed is done with as many as Goal Clans Required asks for.
# Every tribe by ClassData name -> its item's name: ours, then the loaded extensions' (the user's calls,
# 2026-11-16: a win with any tribe in the seed counts). A slot has its own (WildfrostWorld.tribes).
CLANS = {tribe: info["name"] for tribe, info in TRIBES.items()}
BASE_CLANS = ("Basic", "Magic", "Clunk")
VICTORY_ITEM = "Victory"


def victory_location(clan: str) -> str:
    return f"Victory ({CLANS[clan]})"


class WildfrostLocation(Location):
    game = "Wildfrost"


def region_for(key: str, info: dict) -> str:
    if key.startswith("battle:"):
        return AREA_REGIONS[info["area"]]
    # An extension's challenge names its own region.
    # "Area 4" is a kit, the True Final Boss's (rules.area_kit); its challenges are done in Area 3.
    region = info.get("region", "Area 1")
    return "Area 3" if region == "Area 4" else region


def included(world: WildfrostWorld, info: dict, key: str = "") -> bool:
    """
    With New Challenges, the challenges made for Archipelago replace the charm challenges' second checks.
    The True Final Boss checks only exist when the goal sends the player there. Sunbringer (beat it)
    went with them on 2026-11-08 (the user's call), when the Final Boss goal's bells became filler that
    logic can't count; seeds from before (goal_sized_bells false) keep it, filler only.
    """
    if not world.uses(info):  # an extension's content this slot didn't pick (Mod Content)
        return False
    # Base game content a chosen extension removes, and challenges impossible after that (PLAN.md §10).
    removed = getattr(world, "removed", None)
    if removed:
        if key.startswith("battle:") and key.split(":")[2] in removed["battles"]:
            return False
        internal = info.get("internal")
        if internal in removed["challenges"] or internal in getattr(world, "impossible", ()):
            return False
    # A battle won with a tribe this slot doesn't have (the Tribes option). A challenge that needs one is
    # impossible (rules.impossible_challenges).
    if key.startswith("battle:") and info["run_tribe"] in CLANS and info["run_tribe"] not in world.tribes:
        return False
    new_challenges = bool(world.options.new_challenges)
    # "#2" checks dropped from a seed with room to spare (dropped_seconds).
    if key in (getattr(world, "dropped_seconds", None) or ()):
        return False
    # Spare "#2" checks are only in a seed whose items need the room (spare_checks).
    if is_spare(world, info) and key not in (getattr(world, "spare_checks", None) or ()):
        return False
    if info.get("ap"):
        return new_challenges
    if world.options.goal != world.options.goal.option_final_boss:
        return True
    if true_final_challenge(info):
        return not world.goal_sized_bells
    return not info.get("true_final")


def filler_only(world: WildfrostWorld, info: dict) -> bool:
    """An excluded check: it only ever holds filler."""
    return (true_final_challenge(info) and sunbringer_excluded(world)) or bool(info.get("excluded"))


def is_spare(world: WildfrostWorld, info: dict) -> bool:
    """
    A spare "#2" check: one a challenge only gets when the seed needs room (spare_checks). The charm
    challenges' own "#2"s are spares too with New Challenges, which take their place.
    """
    return bool(info.get("spare")) or bool(world.options.new_challenges) and bool(info.get("second")) \
        and info.get("internal", "").startswith("Challenge Charm ")


def spare_checks(world: WildfrostWorld) -> set[str]:
    """
    Room for every item (PLAN.md §10): when a slot's mod extensions bring more items than it has checks,
    challenges get spare "#2" checks, picked at random, as many as needed, then regular battles do (the
    user's calls, 2026-11-15).
    If those run out, the extensions' packs get fuller (items.shrink_extension_packs), one pack fewer
    at a time. Vanilla seeds always have room, so they get none.
    """
    # Real items need checks that aren't filler only: those take the filler (Bling, boons, traps).
    world.spare_checks = set()
    checks = sum(1 for key, _, _, info in LOCATIONS if included(world, info, key) and not filler_only(world, info))
    need = items.real_item_count(world) - checks
    if need <= 0:
        return set()
    world.spare_checks = {key for key, _, _, info in LOCATIONS if is_spare(world, info)}
    candidates = sorted(key for key, _, _, info in LOCATIONS
                        if is_spare(world, info) and included(world, info, key) and not filler_only(world, info))
    # The challenges' spares first, then the regular battles' (the user's call, 2026-11-15).
    chosen = set()
    for spares in ([k for k in candidates if k.startswith("challenge:")], [k for k in candidates if k.startswith("battle:")]):
        picked = world.random.sample(spares, min(need, len(spares)))
        chosen.update(picked)
        need -= len(picked)
    while need > 0:
        if not items.shrink_extension_packs(world):
            raise OptionError(f"Wildfrost: {world.player_name}'s mod content ({', '.join(sorted(world.extensions))}) "
                              f"brings {need} more items than the seed has checks, even with every spare check and "
                              "the mods' packs as full as they go")
        need -= 1
    return chosen


# Filler only: a row's "excluded" in base.wildfrost.json (Gnomebringer, decided by the user 2026-11-02:
# too much luck; Reach a boss holding 200+ Bling, 2026-11-08: players may sink a run for it; Bigger Hitter,
# 2026-11-24: 100 damage in one hit is too hard to put a rule on, and a seed shouldn't wait on it).


def true_final_challenge(info: dict) -> bool:
    """A challenge that is the True Final Boss fight itself: its row's "true_final" (Sunbringer, ours)."""
    return bool(info.get("true_final")) and "internal" in info


def sunbringer_excluded(world: WildfrostWorld) -> bool:
    """
    Sunbringer, or any challenge that is the True Final Boss fight (true_final_challenge), is filler only
    when the goal is a plain win (any number of clans), which it lies past, or a single True Final Boss
    win, Overcranked or not, which it is.
    """
    goal = world.options.goal
    return goal == goal.option_final_boss or world.options.clans_required == 1


# A seed keeps at least this share of its checks for filler (Bling, boons, traps) when it drops "#2" checks.
FILLER_FLOOR = 0.15


def dropped_seconds(world: WildfrostWorld) -> set[str]:
    """
    The other way round from spare_checks (the user's calls, 2026-11-25): a seed with far more checks than items
    drops "#2" checks, a whole group at a time so seeds stay consistent: the bosses' first, then the charm
    challenges' (only there with New Challenges off). A group goes only if the filler left is still at least
    FILLER_FLOOR of the checks; if the bosses' can't go, neither do the charm challenges'. Vanilla seeds keep
    theirs (about 20% filler, 12% without the bosses' "#2"); mods with tribes (Companion Start) drop them.
    """
    world.dropped_seconds = set()
    if world.spare_checks:  # short of room already
        return set()
    checks = [(key, info) for key, _, _, info in LOCATIONS if included(world, info, key)]
    seconds = [(key, info) for key, info in checks if key.endswith("#2") and not is_spare(world, info)]
    groups = ([(key, info) for key, info in seconds if key.startswith("battle:")],
              [(key, info) for key, info in seconds if info.get("internal", "").startswith("Challenge Charm ")])
    real = items.real_item_count(world)
    remaining = len(checks)
    # Real items also need checks that aren't filler only, as spare_checks counts them (found in review, 2026-11-25:
    # a mod with many filler-only challenges could pass the 15% test with too few checks for its items).
    usable = sum(1 for _, info in checks if not filler_only(world, info))
    dropped: set[str] = set()
    for group in groups:
        left = remaining - len(group)
        usable_left = usable - sum(1 for _, info in group if not filler_only(world, info))
        if not group or left - real < FILLER_FLOOR * left or usable_left < real:
            break
        dropped.update(key for key, _ in group)
        remaining, usable = left, usable_left
    return dropped


def create_all_locations(world: WildfrostWorld) -> None:
    if getattr(world, "spare_checks", None) is None:  # Universal Tracker's rebuild has them from slot_data
        world.spare_checks = spare_checks(world)
    if getattr(world, "dropped_seconds", None) is None:
        world.dropped_seconds = dropped_seconds(world)
    for key, name, loc_id, info in LOCATIONS:
        if not included(world, info, key):
            continue
        region = world.get_region(region_for(key, info))
        location = WildfrostLocation(world.player, name, loc_id, region)
        if filler_only(world, info):  # ours, or an extension's challenge it marks as filler only
            location.progress_type = LocationProgressType.EXCLUDED
        region.locations.append(location)

    final_area = world.get_region("Area 3")
    for clan in world.tribes:
        victory = WildfrostLocation(world.player, victory_location(clan), None, final_area)
        victory.place_locked_item(items.WildfrostItem(VICTORY_ITEM, ItemClassification.progression, None, world.player))
        final_area.locations.append(victory)
