from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import ItemClassification, Location, LocationProgressType

from . import items
from .data import LOCATIONS

if TYPE_CHECKING:
    from .world import WildfrostWorld

LOCATION_NAME_TO_ID = {name: loc_id for _, name, loc_id, _ in LOCATIONS}
LOCATION_ID_BY_KEY = {key: loc_id for key, _, loc_id, _ in LOCATIONS}

AREA_REGIONS = ["Area 1", "Area 2", "Area 3"]

# Challenges that need a whole run won, or a fight that only happens deeper in, live in the area
# where they can first be completed. Everything else can be done in Area 1.
CHALLENGE_REGION = {
    "Challenge Charm 8": "Area 3",   # Defeat the Frost Guardian with a Scrappy Sword
    "Challenge Charm 12": "Area 2",  # Survive King Moko (Spice Mokos, an Area 2 battle)
    "Challenge Charm 15": "Area 3",  # 3 win streak
    "Challenge Charm 16": "Area 3",  # Sunbringer: beat the True Final Boss
    "Challenge Charm 17": "Area 3",  # Win with the Naked Gnome
    "Challenge Charm 19": "Area 3",  # Win without charms
    "Challenge Charm 21": "Area 3",  # Win with only the pet
    "Challenge Charm 25": "Area 3",  # Win with Snowdwellers
    "Challenge Charm 26": "Area 3",  # Win with Shademancers
    "Challenge Charm 27": "Area 3",  # Win with Clunkmasters
}

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
    return CHALLENGE_REGION.get(info["internal"], "Area 1")


def included(world: WildfrostWorld, info: dict) -> bool:
    """The True Final Boss checks only exist when the goal sends the player there."""
    return not info.get("true_final") or world.options.goal != world.options.goal.option_final_boss


# Filler only (decided by the user 2026-11-02): Gnomebringer (win a run with the Naked Gnome) is too
# much luck to hold anything needed.
EXCLUDED_CHALLENGES = {"Challenge Charm 17"}
SUNBRINGER = "Challenge Charm 16"


def sunbringer_excluded(world: WildfrostWorld) -> bool:
    """
    Sunbringer (beat the True Final Boss, both its checks) is filler only when the goal is a plain win
    (any number of clans), which it lies past, or a single True Final Boss win, Overcranked or not,
    which it is.
    """
    goal = world.options.goal
    return goal == goal.option_final_boss or world.options.clans_required == 1


def create_all_locations(world: WildfrostWorld) -> None:
    for key, name, loc_id, info in LOCATIONS:
        if not included(world, info):
            continue
        region = world.get_region(region_for(key, info))
        location = WildfrostLocation(world.player, name, loc_id, region)
        internal = info.get("internal")
        if internal in EXCLUDED_CHALLENGES or (internal == SUNBRINGER and sunbringer_excluded(world)):
            location.progress_type = LocationProgressType.EXCLUDED
        region.locations.append(location)

    final_area = world.get_region("Area 3")
    for clan in CLANS:
        victory = WildfrostLocation(world.player, victory_location(clan), None, final_area)
        victory.place_locked_item(items.WildfrostItem(VICTORY_ITEM, ItemClassification.progression, None, world.player))
        final_area.locations.append(victory)
