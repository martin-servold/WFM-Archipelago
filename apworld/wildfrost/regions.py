from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Region

from .locations import AREA_REGIONS

if TYPE_CHECKING:
    from .world import WildfrostWorld

ORIGIN_REGION = "Snowdwell"


def create_and_connect_regions(world: WildfrostWorld) -> None:
    names = [ORIGIN_REGION, *AREA_REGIONS]
    regions = [Region(name, world.player, world.multiworld) for name in names]
    world.multiworld.regions += regions

    # A run goes Snowdwell -> Area 1 -> Area 2 -> Area 3. The entrances carry the (future) area
    # power requirements; for now every area is open.
    for parent, child in zip(regions, regions[1:]):
        parent.connect(child, f"{parent.name} to {child.name}")
