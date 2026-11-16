import json
import logging
from collections.abc import Mapping
from typing import Any

from Options import OptionError
from worlds.AutoWorld import World

from . import content, extensions, items, locations, regions, rules, web_world
from . import options as wildfrost_options  # renamed: World.options is taken


def force_points(slot_data: Mapping[str, Any]) -> int:
    """
    Force Storm Bells Up To from slot_data. Seeds from before it had two toggles, Force Storm Bells (the
    full limit) and Force Overcrank, each adding a pack to the wins: both are 22 (two packs), either one
    20 (one pack, which is all logic follows; the client keeps the toggles apart itself).
    """
    if "force_storm_bells_up_to" in slot_data:
        return slot_data["force_storm_bells_up_to"]
    toggles = int(bool(slot_data.get("force_storm_bells"))) + int(bool(slot_data.get("force_overcrank")))
    return (0, 20, rules.OVERCRANK_POINTS)[toggles]


def chosen_extensions(names) -> set[str]:
    """The Mod Content option's extensions, each installed and loaded, or an error that says why not."""
    for name in sorted(names):
        if name in extensions.FAILED:
            raise OptionError(f"Wildfrost: Mod Content {name!r}: its extension file didn't load: {extensions.FAILED[name]}")
        if name not in extensions.LOADED:
            have = ", ".join(sorted(extensions.LOADED)) or "none"
            raise OptionError(f"Wildfrost: Mod Content {name!r} needs its extension file ({name}{extensions.SUFFIX}) in "
                              f"Archipelago's custom_worlds folder; installed: {have}")
    return set(names)


def rebuilt_extensions(slot_data: Mapping[str, Any]) -> set[str]:
    """
    Universal Tracker's rebuild: the seed's extensions must be installed here as the same files, or the
    rebuilt logic would quietly differ from the seed's (PLAN.md §10).
    """
    for meta in slot_data.get("extensions", []):
        ext = extensions.LOADED.get(meta["mod"])
        if ext is None or ext.hash != meta["hash"]:
            have = f"you have version {ext.version}" if ext else "it isn't installed"
            raise OptionError(f"Wildfrost: this seed used {meta['mod']} {meta['version']} ({meta['mod']}{extensions.SUFFIX}); "
                              f"{have}. Install the same file in custom_worlds to track it.")
    return {meta["mod"] for meta in slot_data.get("extensions", [])}


def progression_direction(slot_data: Mapping[str, Any]) -> int:
    """Progression Direction from slot_data (0 forward, 1 reverse); seeds before 0.3.0 sent it as "storm_bells"."""
    return slot_data.get("progression_direction", slot_data.get("storm_bells", 0))


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
    # Bells fit the goal (items.storm_bells_in_pool); False when Universal Tracker rebuilds an older seed.
    goal_sized_bells: bool = True
    # The extensions this slot uses (Mod Content); content from others is never in its seed.
    extensions: set[str] = frozenset()
    # Base game content those extensions take out, by extensions.REMOVE_KINDS.
    removed: dict[str, set[str]]
    # Challenges (by internal name) whose needs are impossible after those removals (rules.CardRules).
    impossible: set[str]
    # This slot's storm bells and their points: the base game's less removed ones, plus its extensions'.
    bell_points: dict[str, int]
    # The True Final Boss's storm point threshold (the Lumin Vase appears at it), and the Progressive Storm
    # Bells that reach it: 10 and 5, unless the bells left can't reach 10 (the user's call, 2026-11-15).
    true_final_points: int = rules.TRUE_FINAL_POINTS
    true_final_bells: int = items.TRUE_FINAL_BELLS
    # The spare "#2" checks this seed has (locations.spare_checks; None until worked out), and how many
    # packs each extension group is held to when packs are made fuller.
    spare_checks: set[str] | None = None
    pack_limits: dict

    def set_bells(self) -> None:
        """This slot's storm bells, and the True Final Boss threshold they can reach (PLAN.md §10)."""
        self.bell_points = {name: points for name, points in content.BELL_POINTS.items()
                            if name not in self.removed["bells"] and (name in content.BASE_BELLS or any(
                                name in extensions.LOADED[mod].bells for mod in self.extensions))}
        reachable = sum(self.bell_points.values())
        self.true_final_points = min(rules.TRUE_FINAL_POINTS, reachable)
        self.true_final_bells = max(1, -(-self.true_final_points // 2))
        if self.true_final_points < rules.TRUE_FINAL_POINTS:
            logging.warning(f"Wildfrost: {self.player_name}'s storm bells reach {reachable} storm points with "
                            f"{', '.join(sorted(self.extensions))}, so the Lumin Vase (True Final Boss) appears at "
                            f"{self.true_final_points}")

    def removals(self) -> dict[str, set[str]]:
        removed = {kind: set() for kind in extensions.REMOVE_KINDS}
        for mod in self.extensions:
            for kind, names in extensions.LOADED[mod].removes.items():
                removed[kind] |= names
        return removed

    def uses(self, info: Mapping[str, Any]) -> bool:
        """Whether a row (location, item or card info) is in this slot's game: ours, or a chosen extension's."""
        return "ext" not in info or info["ext"] in self.extensions

    def generate_early(self) -> None:
        slot_data = getattr(self.multiworld, "re_gen_passthrough", {}).get(self.game)
        if slot_data:
            self.options.goal.value = slot_data["goal"]
            self.options.clans_required.value = slot_data.get("clans_required", 3)
            self.options.starting_tribe.value = items.STARTING_TRIBES.index(slot_data["starting_tribe"])
            self.options.extra_storm_bells.value = slot_data.get("extra_storm_bells", 0)
            self.options.force_storm_bells_up_to.value = force_points(slot_data)
            self.options.progression_direction.value = progression_direction(slot_data)
            self.goal_sized_bells = slot_data.get("goal_sized_bells", False)
            # Seeds from before New Challenges have the charm challenges' second checks.
            self.options.new_challenges.value = int(slot_data.get("new_challenges", False))
            self.pack_contents = slot_data["packs"]
            self.starting_pet = slot_data["starting_pet"]
            self.extensions = rebuilt_extensions(slot_data)
            self.removed = self.removals()
            self.set_bells()
            self.spare_checks = set(slot_data.get("spare_checks", []))
        else:
            self.extensions = chosen_extensions(self.options.mod_content.value)
            self.removed = self.removals()
            self.set_bells()
            self.pack_limits = {}
            if self.options.progression_direction == self.options.progression_direction.option_reverse:
                # Reverse Storm Bells: the True Final Boss is the goal, and the bells force themselves.
                if self.options.goal != self.options.goal.option_true_final_boss:
                    logging.warning(f"Wildfrost: {self.player_name} plays Reverse Storm Bells, so the goal is the True Final Boss")
                    self.options.goal.value = self.options.goal.option_true_final_boss
                self.options.force_storm_bells_up_to.value = 0
            elif self.options.goal == self.options.goal.option_true_final_boss:
                # The pool only has the 5 bells it needs plus extras (items.storm_bells_in_pool), so
                # forcing past what they reach (and the extra pack logic adds at 22) would never apply.
                cap = 2 * (self.true_final_bells + self.options.extra_storm_bells.value)
                self.options.force_storm_bells_up_to.value = min(self.options.force_storm_bells_up_to.value, cap)
            # Forcing past what this slot's storm bells can reach would hold every run back (an extension
            # removed bells, PLAN.md §10). 22 (Overcrank) rings every bell there is, so it stays.
            reachable = sum(self.bell_points.values())
            if rules.OVERCRANK_POINTS > self.options.force_storm_bells_up_to.value > reachable:
                self.options.force_storm_bells_up_to.value = reachable
            # Storm points come in steps of 2: an odd number means the even one below.
            self.options.force_storm_bells_up_to.value -= self.options.force_storm_bells_up_to.value % 2
            self.pack_contents = items.fill_packs(self)
            self.starting_pet = self.random.choice(items.pet_names(self))
        self.impossible = rules.impossible_challenges(self)
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
            # Only this slot's game: ours and its extensions' (an unpicked extension's pet listed here would
            # stay locked for good, the client taking it for one of this seed's items).
            "location_ids": {key: loc_id for key, _, loc_id, info in content.LOCATIONS if self.uses(info)},
            "item_keys": {str(item_id): key for key, _, item_id, info in content.ITEMS if self.uses(info)},
            "card_kinds": {key: info["kind"] for key, _, info in content.CARDS if self.uses(info)},
            "packs": self.pack_contents,
            # 0 Final Boss, 1 True Final Boss, 2 Overcranked True Final Boss (each clans_required clan).
            "goal": self.options.goal.value,
            "clans_required": self.options.clans_required.value,
            "starting_tribe": items.starting_tribe(self),
            "extra_storm_bells": self.options.extra_storm_bells.value,
            # Storm points runs are forced up to (even, 0 off); 22 also forces Overcrank.
            "force_storm_bells_up_to": self.options.force_storm_bells_up_to.value,
            # Progression Direction: 0 forward, 1 reverse (runs start Overcranked, each bell lowers the floor).
            "progression_direction": self.options.progression_direction.value,
            # Bell levels (items.STORM_BELL_LEVELS). The client keeps the old 7-level steps (5 storm
            # points, up to 10, Overcrank) for seeds without it or with fewer than 11.
            "storm_bell_levels": items.STORM_BELL_LEVELS,
            # The bell pool fits the goal (items.storm_bells_in_pool) and the Final Boss goal has no
            # Sunbringer; Universal Tracker rebuilds seeds without this key the old way.
            "goal_sized_bells": self.goal_sized_bells,
            # New Challenges: the client detects the "challenge:ap:<slug>" checks, and the charm
            # challenges send one check, not two.
            "new_challenges": bool(self.options.new_challenges),
            "death_link": bool(self.options.death_link),
            # How hard a received death hits the leader (the client's DeathLinkHandler); 100 flees.
            "death_link_damage_percent": self.options.death_link_damage_percent.value,
            "game_speed_up": bool(self.options.game_speed_up),
            "starting_pet": self.starting_pet,
            # Unlimited leader rerolls on the leader select screen (the client's LeaderReroll).
            "leader_reroll": bool(self.options.leader_reroll),
            # The Final Boss keeps its default deck instead of your last winning deck (the client's
            # DefaultFinalBossDeck).
            "disable_possessed_final_boss": bool(self.options.disable_possessed_final_boss),
            # Which bells Force Storm Bells Up To forces, by the run clan's packs.
            "bell_kits": rules.bell_kits(self.true_final_bells),
            # For the client's tracker: what each location needs, in item keys (rules.rule_json).
            # Sent as one JSON string: Archipelago 0.6.8's Python clients (Universal Tracker, the Text
            # Client) drop any message nested over 16 deep (NetUtils._check_depth, AP PR #6378), and
            # the rules nest up to 15 inside slot_data. A string counts as no depth (found 2026-11-13).
            "location_rules": json.dumps(self.location_rules, separators=(",", ":")),
            # The extensions this seed uses (PLAN.md §10): the client checks their mods are loaded, and
            # Universal Tracker that the same files are installed.
            "extensions": [extensions.LOADED[mod].meta() for mod in sorted(self.extensions)],
            # The True Final Boss's storm point threshold: 10, or the most a slot's storm bells reach when its
            # extensions remove too many (the client moves the Lumin Vase to it).
            "true_final_points": self.true_final_points,
            # Spare "#2" checks added for room (locations.spare_checks), for Universal Tracker's rebuild.
            "spare_checks": sorted(self.spare_checks or ()),
        }
