from collections.abc import Mapping
from typing import Any

from worlds.AutoWorld import World

from . import items, locations, regions, rules, web_world
from . import options as wildfrost_options  # renamed: World.options is taken


class WildfrostWorld(World):
    """
    Wildfrost is a tactical roguelike deckbuilder set in a frozen world.
    Battles and challenges send checks; every card and companion (in packs), charm (one by one), pet and tribe comes from the multiworld.
    """

    game = "Wildfrost"
    web = web_world.WildfrostWebWorld()
    options_dataclass = wildfrost_options.WildfrostOptions
    options: wildfrost_options.WildfrostOptions

    location_name_to_id = locations.LOCATION_NAME_TO_ID
    item_name_to_id = items.ITEM_NAME_TO_ID
    origin_region_name = regions.ORIGIN_REGION

    pack_contents: dict[str, list[str]]
    location_rules: dict[str, list]
    # The pet in the starting inventory: always one of the seven at random (the user's call, 2026-11-02).
    starting_pet: str

    # Universal Tracker rebuilds the world from slot_data alone (no yaml): generate_early takes the
    # options and packs that logic needs from re_gen_passthrough instead of rolling them.
    ut_can_gen_without_yaml = True

    def generate_early(self) -> None:
        slot_data = getattr(self.multiworld, "re_gen_passthrough", {}).get(self.game)
        if slot_data:
            self.options.goal.value = slot_data["goal"]
            self.options.clans_required.value = slot_data.get("clans_required", 3)
            self.options.starting_tribe.value = items.STARTING_TRIBES.index(slot_data["starting_tribe"])
            self.options.extra_storm_bells.value = slot_data.get("extra_storm_bells", 0)
            self.options.force_storm_bells.value = int(slot_data["force_storm_bells"])
            self.options.force_overcrank.value = int(slot_data["force_overcrank"])
            self.pack_contents = slot_data["packs"]
            self.starting_pet = slot_data["starting_pet"]
        else:
            self.pack_contents = items.fill_packs(self)
            self.starting_pet = self.random.choice(items.PET_NAMES)
        self.multiworld.push_precollected(self.create_item(items.starting_tribe(self)))
        self.multiworld.push_precollected(self.create_item(self.starting_pet))

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
            "clans_required": self.options.clans_required.value,
            "starting_tribe": items.starting_tribe(self),
            "extra_storm_bells": self.options.extra_storm_bells.value,
            "force_storm_bells": bool(self.options.force_storm_bells),
            "force_overcrank": bool(self.options.force_overcrank),
            "death_link": bool(self.options.death_link),
            "game_speed_up": bool(self.options.game_speed_up),
            "starting_pet": self.starting_pet,
            # Unlimited leader rerolls on the leader select screen (the client's LeaderReroll).
            "leader_reroll": bool(self.options.leader_reroll),
            # Which bells Force Storm Bells and Force Overcrank force, by the run clan's packs.
            "bell_kits": rules.bell_kits(rules.forced_extra(self)),
            # For the client's tracker: what each location needs, in item keys (rules.rule_json).
            "location_rules": self.location_rules,
        }
