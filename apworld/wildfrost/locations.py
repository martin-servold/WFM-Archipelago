from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import ItemClassification, Location, LocationProgressType
from Options import OptionError

from . import items
from .content import LOCATIONS

if TYPE_CHECKING:
    from .world import WildfrostWorld

LOCATION_NAME_TO_ID = {name: loc_id for _, name, loc_id, _ in LOCATIONS}
LOCATION_ID_BY_KEY = {key: loc_id for key, _, loc_id, _ in LOCATIONS}

AREA_REGIONS = ["Area 1", "Area 2", "Area 3"]

# A challenge's region (where it can first be completed: Area 3 for a whole run won, or a fight that
# only happens deeper in) is its row's "region" in base.wildfrost.json, as in an extension's file.

# The goal is a winning run per clan (what counts as winning depends on the goal option). Each is
# an event location holding a "Victory"; the seed is done with as many as Goal Clans Required asks for.
CLANS = {"Basic": "Snowdwellers", "Magic": "Shademancers", "Clunk": "Clunkmasters"}
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
    new_challenges = bool(world.options.new_challenges)
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
# too much luck; Reach a boss holding 200+ Bling, 2026-11-08: players may sink a run for it).


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


def create_all_locations(world: WildfrostWorld) -> None:
    if getattr(world, "spare_checks", None) is None:  # Universal Tracker's rebuild has them from slot_data
        world.spare_checks = spare_checks(world)
    for key, name, loc_id, info in LOCATIONS:
        if not included(world, info, key):
            continue
        region = world.get_region(region_for(key, info))
        location = WildfrostLocation(world.player, name, loc_id, region)
        if filler_only(world, info):  # ours, or an extension's challenge it marks as filler only
            location.progress_type = LocationProgressType.EXCLUDED
        region.locations.append(location)

    final_area = world.get_region("Area 3")
    for clan in CLANS:
        victory = WildfrostLocation(world.player, victory_location(clan), None, final_area)
        victory.place_locked_item(items.WildfrostItem(VICTORY_ITEM, ItemClassification.progression, None, world.player))
        final_area.locations.append(victory)
