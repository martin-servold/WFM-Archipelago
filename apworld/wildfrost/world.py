from collections.abc import Mapping
from typing import Any

from worlds.AutoWorld import World

from . import items, locations, regions, rules, web_world
from . import options as wildfrost_options  # renamed: World.options is taken


class WildfrostWorld(World):
    """
    Wildfrost is a tactical roguelike deckbuilder set in a frozen world.
    Battles and challenges send checks; every card, companion and charm (in packs of 3), pet and tribe comes from the multiworld.
    """

    game = "Wildfrost"
    web = web_world.WildfrostWebWorld()
    options_dataclass = wildfrost_options.WildfrostOptions
    options: wildfrost_options.WildfrostOptions

    location_name_to_id = locations.LOCATION_NAME_TO_ID
    item_name_to_id = items.ITEM_NAME_TO_ID
    origin_region_name = regions.ORIGIN_REGION

    pack_contents: dict[str, list[str]]

    def generate_early(self) -> None:
        self.pack_contents = items.fill_packs(self)
        self.multiworld.push_precollected(self.create_item(items.starting_tribe(self)))

    def create_regions(self) -> None:
        regions.create_and_connect_regions(self)
        locations.create_all_locations(self)

    def set_rules(self) -> None:
        rules.set_all_rules(self)

    def create_items(self) -> None:
        items.create_all_items(self)

    def create_item(self, name: str) -> items.WildfrostItem:
        return items.create_item(self, name)

    def get_filler_item_name(self) -> str:
        return items.filler_name(self)

    def fill_slot_data(self) -> Mapping[str, Any]:
        # The client matches game events to these keys ("battle:<area>:<BattleData>:<ClassData>",
        # "challenge:<ChallengeData>") instead of rebuilding display names, so renaming a location
        # never breaks the client. card_kinds tells it which reward pool (Item, Companion, Charm) to
        # lock each card in, and packs which cards each pack item unlocks this seed.
        return {
            "location_ids": locations.LOCATION_ID_BY_KEY,
            "item_keys": {str(item_id): key for item_id, key in items.ITEM_KEY_BY_ID.items()},
            "card_kinds": items.CARD_KIND_BY_KEY,
            "packs": self.pack_contents,
            # 0 win each clan, 1 True Final Boss each clan, 2 Overcranked True Final Boss each clan.
            "goal": self.options.goal.value,
            "starting_tribe": items.starting_tribe(self),
            "force_storm_bells": bool(self.options.force_storm_bells),
            "force_overcrank": bool(self.options.force_overcrank),
            "death_link": bool(self.options.death_link),
        }
