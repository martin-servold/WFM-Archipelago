import json
import unittest
from unittest import mock

from BaseClasses import ItemClassification, LocationProgressType

from ..data import CARDS, ITEMS, LOCATIONS
from ..items import INFO_BY_KEY, INFO_BY_NAME, PACK_KEYS, PET_NAMES, STORM_BELL, STORM_BELL_LEVELS, pet_names, storm_bells_in_pool
from ..items import TRUE_FINAL_BELLS as TRUE_FINAL_BELLS_NEEDED
from ..locations import CLANS, included
from ..rules import required_tribes
from ..world import progression_direction, read_location_rules
from . import WildfrostTestBase
from .. import items as items_module, locations as locations_module

# The tools (gen_data.py, /generate) write one pack row per 3 cards; generation just deals a
# group's cards evenly across its packs.
PACK_SIZE = 3

# The tables above list every loaded extension's content too (whatever is in custom_worlds when the tests run);
# these test slots pick none, so they compare against the base game's share, and check the rest stays out.
BASE_PETS = [name for name in PET_NAMES if "ext" not in INFO_BY_NAME[name]]
BASE_PACKS = [key for key in PACK_KEYS if "ext" not in INFO_BY_KEY[key]]

# Sunbringer's row: the challenge that is the True Final Boss fight ("true_final").
SUNBRINGER = next(info for key, _, _, info in LOCATIONS if key == "challenge:Challenge Charm 16")

# Spare "#2" checks are only in seeds short of room (locations.spare_checks), never in these tests.
LOCATIONS = [row for row in LOCATIONS if not row[3].get("spare")]
LOCATION_NAMES = {name for _, name, _, info in LOCATIONS}


def with_seconds(names: list[str]) -> list[str]:
    """The names and their "#2" checks, which share their first's rule."""
    return names + [f"{name} #2" for name in names if f"{name} #2" in LOCATION_NAMES]


class TestDefaultPool(WildfrostTestBase):
    def test_no_cards_at_start(self) -> None:
        # Only the starting tribe and the random starting pet.
        self.assertEqual([i.name for i in self.multiworld.precollected_items[self.player]], ["Snowdwellers", self.world.starting_pet])

    def test_every_card_in_exactly_one_pack(self) -> None:
        packs = self.world.pack_contents
        self.assertEqual(sorted(packs), sorted(BASE_PACKS))
        dealt = [card for cards in packs.values() for card in cards]
        # Charms are items one by one; every other card is in exactly one pack.
        self.assertEqual(sorted(dealt), sorted(key for key, _, info in CARDS if info["kind"] != "Charm"))
        charm_items = sorted(info["card"] for _, _, _, info in ITEMS if info["kind"] == "Charm")
        self.assertEqual(charm_items, sorted(key for key, _, info in CARDS if info["kind"] == "Charm"))
        for key, cards in packs.items():
            with self.subTest(pack=key):
                self.assertTrue(1 <= len(cards) <= PACK_SIZE)
        # Spread evenly: a group's packs differ by at most one card.
        sizes: dict[tuple[str, str], list[int]] = {}
        for key, cards in packs.items():
            sizes.setdefault(tuple(key.split(":")[1:3]), []).append(len(cards))
        for group, group_sizes in sizes.items():
            with self.subTest(group=group):
                self.assertLessEqual(max(group_sizes) - min(group_sizes), 1)
                self.assertGreaterEqual(min(group_sizes), PACK_SIZE - 1)
                kinds = {info["kind"] for k, _, info in CARDS if k in cards}
                clans = {info["clan"] for k, _, info in CARDS if k in cards}
                self.assertEqual((kinds, clans), ({key.split(":")[2]}, {key.split(":")[1]}))

    def test_all_packs_in_pool(self) -> None:
        pool = [i.name for i in self.multiworld.itempool]
        for _, name, _, info in ITEMS:
            if info["kind"] == "Pack":
                self.assertIn(name, pool)

    def test_tribe_locations_need_tribe(self) -> None:
        self.assertEqual(self.world.tribes, ("Basic", "Magic", "Clunk"))  # no extension picked
        for tribe in self.world.tribes:
            item = CLANS[tribe]
            if item == "Snowdwellers":
                continue  # the starting tribe here; TestStartingTribe covers it
            gated = [name for key, name, _, info in LOCATIONS
                     if tribe in required_tribes(key, info) and not info.get("true_final") and not info.get("ap")
                     and not info.get("spare")]
            gated.append(f"Victory ({item})")
            if item == "Clunkmasters":
                # Minimalist isn't: the Gunk Bugs fight comes up in any run since battles lost their tribe locks
                # (the user's call, 2026-11-25).
                gated += with_seconds(["Challenge - Hoarder"])
            if item == "Shademancers":
                # Every sacrifice card and every Mask is a Shademancer card (the user's rules, 2026-11-24: the cards,
                # not the tribe, so a modded tribe sharing their pools can do them too).
                gated += with_seconds(["Challenge - Ritual", "Challenge - Summon 50 allies"])
            with self.subTest(tribe=tribe):
                self.assertTrue(gated)
                self.assertAccessDependency(gated, [[item]])


class TestBattlesPerTribe(WildfrostTestBase):
    def test_every_battle_once_per_tribe(self) -> None:
        battles = [info for key, _, _, info in LOCATIONS if key.startswith("battle:")]
        self.assertEqual({info["run_tribe"] for info in battles}, set(self.world.tribes))
        self.assertEqual(len(battles) % 3, 0)

    def test_snowdweller_battles_need_nothing(self) -> None:
        for key, name, _, info in LOCATIONS:
            if key.startswith("battle:") and info["run_tribe"] == "Basic" and info["tier"] <= 4:
                with self.subTest(location=name):
                    self.assertTrue(self.can_reach_location(name))


class BellTestBase(WildfrostTestBase):
    _bells_taken = 0

    def collect_bells(self, count: int) -> None:
        """collect_by_name takes every copy of a name; this takes the next `count`."""
        bells = self.get_items_by_name(STORM_BELL)
        self.collect(bells[self._bells_taken:self._bells_taken + count])
        self._bells_taken += count


TRUE_FINAL = [name for _, name, _, info in LOCATIONS if info.get("true_final")]
VICTORIES = ["Victory (Snowdwellers)", "Victory (Shademancers)", "Victory (Clunkmasters)"]


class TestGoalWinEachClan(WildfrostTestBase):
    def test_no_true_final_boss_checks(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertFalse(names & set(TRUE_FINAL))

    def test_bells_in_pool(self) -> None:
        pool = [i.name for i in self.multiworld.itempool]
        self.assertEqual(pool.count(STORM_BELL), STORM_BELL_LEVELS)

    def test_bells_are_filler(self) -> None:
        # Nothing needs them: they only raise (and force) the difficulty (the user's call, 2026-11-08).
        for bell in self.get_items_by_name(STORM_BELL):
            self.assertEqual(bell.classification, ItemClassification.filler)

    def test_no_sunbringer(self) -> None:
        # Its rule needs bells logic can't count, so it went with the True Final Boss checks.
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertNotIn("Challenge - Sunbringer", names)
        self.assertNotIn("Challenge - Sunbringer #2", names)
        self.assertNotIn("challenge:Challenge Charm 16", read_location_rules(self.world.fill_slot_data()["location_rules"]))

    def test_bell_levels_in_slot_data(self) -> None:
        # The client steps by 2 storm points with 11 levels, and keeps the old 7 steps without the key.
        self.assertEqual(STORM_BELL_LEVELS, 11)
        self.assertEqual(self.world.fill_slot_data()["storm_bell_levels"], STORM_BELL_LEVELS)

    def test_needs_both_tribes(self) -> None:
        self.collect_all_but(["Shademancers", "Victory"])
        self.assertFalse(self.multiworld.can_beat_game(self.multiworld.state))
        self.assertTrue(self.can_reach_location("Victory (Snowdwellers)"))


class TestGoalTrueFinalBoss(BellTestBase):
    options = {**WildfrostTestBase.options, "goal": "true_final_boss", "extra_storm_bells": 2}

    def test_true_final_boss_checks_need_ten_storm_points(self) -> None:
        self.assertTrue(TRUE_FINAL)
        self.collect_all_but([STORM_BELL, "Victory"])
        self.collect_bells(TRUE_FINAL_BELLS_NEEDED - 1)
        for name in TRUE_FINAL + VICTORIES:
            with self.subTest(location=name):
                self.assertFalse(self.can_reach_location(name))
        self.collect_bells(1)
        for name in TRUE_FINAL + VICTORIES:
            with self.subTest(location=name):
                self.assertTrue(self.can_reach_location(name))

    def test_extra_bells(self) -> None:
        # Only the 5 bells the goal needs, plus the extras (the user's call, 2026-11-08).
        pool = [i.name for i in self.multiworld.itempool]
        self.assertEqual(pool.count(STORM_BELL), TRUE_FINAL_BELLS_NEEDED + 2)
        for bell in self.get_items_by_name(STORM_BELL):
            self.assertEqual(bell.classification, ItemClassification.progression)


class TestGoalOvercranked(BellTestBase):
    options = {**WildfrostTestBase.options, "goal": "overcranked_true_final_boss"}

    def test_victory_needs_every_level(self) -> None:
        self.collect_all_but([STORM_BELL, "Victory"])
        self.collect_bells(STORM_BELL_LEVELS - 1)
        self.assertTrue(self.can_reach_location(TRUE_FINAL[0]))
        self.assertFalse(self.can_reach_location("Victory (Snowdwellers)"))
        self.collect_bells(1)
        self.assertTrue(self.multiworld.can_beat_game(self.multiworld.state))


class TestForceStormBells(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "force_storm_bells_up_to": 10}

    def test_slot_data(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["force_storm_bells_up_to"], 10)
        self.assertIs(self.world.fill_slot_data()["game_speed_up"], True)  # on by default (the user's call, 2026-11-08)

    def test_discounted_items_need_three_item_packs(self) -> None:
        location = "Challenge - Buy 5 discounted items"
        self.collect_by_name([pack("General", "Item", 1), pack("General", "Item", 2)])
        self.assertFalse(self.can_reach_location(location))
        self.collect_by_name([pack("General", "Item", 3)])
        self.assertTrue(self.can_reach_location(location))

    def test_win_needs_one_more_pack(self) -> None:
        self.collect_by_name([pack("General", "Companion"), pack("General", "Item")])
        self.assertFalse(self.can_reach_location("Victory (Snowdwellers)"))
        # The extra is one more companion or item pack, or three charms.
        self.collect_by_name(charms("General", 2))
        self.assertFalse(self.can_reach_location("Victory (Snowdwellers)"))
        self.collect_by_name(charms("Basic", 1))
        self.assertTrue(self.can_reach_location("Victory (Snowdwellers)"))


class TestLogicSection(WildfrostTestBase):
    """Kits, bell steps, goals and Reverse come from base.wildfrost.json's "logic" (PLAN.md §10, phase 3)."""

    def test_every_goal_has_an_entry(self) -> None:
        from ..data import LOGIC
        from ..options import Goal
        self.assertEqual(set(LOGIC["goals"]), set(Goal.name_lookup.values()))

    def test_bells_for_storm_points(self) -> None:
        from ..rules import bells_for
        self.assertEqual([bells_for(p) for p in (0, 2, 8, 10, 14, 20, 22)], [0, 1, 4, 5, 7, 10, STORM_BELL_LEVELS])
        # A lowered True Final Boss threshold (an extension removed bells) carries up through it.
        self.world.true_final_bells = 4
        self.assertEqual([bells_for(p, self.world) for p in (8, 10, 14, 22)], [4, 4, 6, STORM_BELL_LEVELS])

    def test_sunbringer_is_the_true_final_fight(self) -> None:
        from ..rules import challenge_kit, rule_json
        kit = rule_json(challenge_kit(SUNBRINGER, 0))
        self.assertIn(["has", "storm_bell", TRUE_FINAL_BELLS_NEEDED], _leaves(kit))


def _leaves(rule) -> list:
    if rule[0] in ("and", "or"):
        return [leaf for child in rule[1] for leaf in _leaves(child)]
    return [rule]


class TestForcedPackSteps(WildfrostTestBase):
    """The client's forcing ramp (bell_kits), not logic."""

    def test_steps(self) -> None:
        from ..rules import forced_pack_extra
        self.assertEqual([forced_pack_extra(p) for p in range(0, 23, 2)], [0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2])  # 0, 2 | 4-12 | 14-22


class TestForceStormBellsFourteen(WildfrostTestBase):
    """The client's ramp asks two more packs from 14 on; logic stays at one (the user's call)."""
    options = {**WildfrostTestBase.options, "force_storm_bells_up_to": 14}

    def test_win_needs_one_more_pack(self) -> None:
        self.collect_by_name([pack("General", "Companion"), pack("General", "Item")])
        self.assertFalse(self.can_reach_location("Victory (Snowdwellers)"))
        self.collect_by_name([pack("Basic", "Companion")])
        self.assertTrue(self.can_reach_location("Victory (Snowdwellers)"))


class TestForceStormBellsTwo(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "force_storm_bells_up_to": 2}

    def test_win_needs_one_more_pack(self) -> None:
        self.collect_by_name([pack("General", "Companion"), pack("General", "Item")])
        self.assertFalse(self.can_reach_location("Victory (Snowdwellers)"))
        self.collect_by_name([pack("Basic", "Companion")])
        self.assertTrue(self.can_reach_location("Victory (Snowdwellers)"))


class TestForceStormBellsOdd(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "force_storm_bells_up_to": 15}

    def test_rounds_down_to_even(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["force_storm_bells_up_to"], 14)


class TestSecondsKept(WildfrostTestBase):
    """A vanilla seed keeps its "#2" checks: without the bosses' it'd have under 15% filler (2026-11-25)."""

    def test_vanilla_keeps_its_seconds(self) -> None:
        self.assertEqual(self.world.dropped_seconds, set())
        self.assertTrue(any(loc.name.endswith(" #2") for loc in self.multiworld.get_locations(self.player)))


class TestSecondsDropped(WildfrostTestBase):
    """Dropping "#2" checks with room to spare (the user's calls, 2026-11-25): whole groups, bosses' first, then the
    charm challenges', each only if 15% of the checks stay filler. Real item counts are made up here."""
    options = {**WildfrostTestBase.options, "new_challenges": False}

    def dropped_with(self, real: int) -> set[str]:
        # This seed sits just under the filler floor, so spare_checks gave it a spare; these counts are made up.
        self.world.spare_checks = set()
        with mock.patch.object(items_module, "real_item_count", return_value=real):
            try:
                return locations_module.dropped_seconds(self.world)
            finally:
                self.world.dropped_seconds = set()

    def test_groups(self) -> None:
        self.world.dropped_seconds = set()
        checks = [key for key, _, _, info in LOCATIONS if included(self.world, info, key)]
        bosses = {k for k in checks if k.startswith("battle:") and k.endswith("#2")}
        charms = {k for k in checks if k.startswith("challenge:Challenge Charm ") and k.endswith("#2")}
        self.assertTrue(bosses and charms)
        after_bosses, after_both = len(checks) - len(bosses), len(checks) - len(bosses) - len(charms)
        self.assertEqual(self.dropped_with(10), bosses | charms)
        # Room for the bosses' group but not the charm challenges' too: only the bosses' go.
        real = int(after_both * (1 - locations_module.FILLER_FLOOR)) + 1
        self.assertLessEqual(real, after_bosses * (1 - locations_module.FILLER_FLOOR))
        self.assertEqual(self.dropped_with(real), bosses)
        # No room for the bosses' group: nothing goes, the charm challenges' neither.
        self.assertEqual(self.dropped_with(int(after_bosses * (1 - locations_module.FILLER_FLOOR)) + 1), set())


class TestRegularBattlesDropped(WildfrostTestBase):
    """A slot with 5 or more tribes drops every tribe's regular battles (the user's calls, 2026-11-27): all or nothing,
    only if 15% of the checks stay filler, with the challenges' spare "#2"s added to get there. The tribe pool and
    real item counts are made up here; the vanilla rows stand in for a large pool's."""
    options = {**WildfrostTestBase.options, "new_challenges": True}

    def drop_with(self, real: int, tribes: tuple = ("Basic", "Magic", "Clunk", "ModA", "ModB")) -> bool:
        world = self.world
        saved = world.tribes, world.battles_dropped, world.spare_checks, world.dropped_seconds
        world.tribes, world.spare_checks, world.dropped_seconds = tribes, None, set()
        try:
            with mock.patch.object(items_module, "real_item_count", return_value=real):
                return locations_module.drop_regular_battles(world)
        finally:
            self.result = world.battles_dropped, world.spare_checks
            world.tribes, world.battles_dropped, world.spare_checks, world.dropped_seconds = saved

    def checks(self, dropped: bool, spares=()) -> list:
        world = self.world
        saved = world.battles_dropped, world.spare_checks, world.dropped_seconds
        world.battles_dropped, world.spare_checks, world.dropped_seconds = dropped, set(spares), set()
        try:
            return [(key, info) for key, _, _, info in LOCATIONS if included(world, info, key)]
        finally:
            world.battles_dropped, world.spare_checks, world.dropped_seconds = saved

    def test_few_tribes_keep_them(self) -> None:
        self.assertFalse(self.drop_with(10, ("Basic", "Magic", "Clunk", "ModA")))
        self.assertEqual(self.result, (False, None))

    def test_only_regular_battles_go(self) -> None:
        self.assertTrue(self.drop_with(10))
        self.assertEqual(self.result, (True, set()))
        kept = self.checks(True)
        battles = [info for key, info in kept if key.startswith("battle:")]
        self.assertTrue(battles)
        self.assertTrue(all(info.get("boss") or info.get("true_final") or info.get("second") for info in battles))
        self.assertTrue(any(key.endswith("#2") for key, _ in kept if key.startswith("battle:")))

    def test_spares_get_it_over_the_floor(self) -> None:
        left = len(self.checks(True))
        floor = locations_module.FILLER_FLOOR
        real = int(left * (1 - floor)) + 3  # just under the floor without spares
        self.assertTrue(self.drop_with(real))
        dropped, spares = self.result
        self.assertTrue(spares)
        self.assertTrue(all(key.startswith("challenge:") and key.endswith("#2") for key in spares))
        total = left + len(spares)
        self.assertGreaterEqual(total - real, floor * total)
        self.assertLess(total - 1 - real, floor * (total - 1))  # no more spares than needed

    def test_no_room_keeps_every_battle(self) -> None:
        self.assertFalse(self.drop_with(len(self.checks(False))))
        self.assertEqual(self.result, (False, None))


class TestRandomStartingPet(WildfrostTestBase):
    def test_one_pet_precollected_not_in_pool(self) -> None:
        pet = self.world.starting_pet
        self.assertEqual(pet_names(self.world), BASE_PETS)  # no extension picked
        self.assertIn(pet, BASE_PETS)
        self.assertIn(pet, [i.name for i in self.multiworld.precollected_items[self.player]])
        pool = [i.name for i in self.multiworld.itempool]
        self.assertNotIn(pet, pool)
        # Every other pet is in the pool, and no unpicked extension's pet.
        self.assertEqual(sorted(p for p in BASE_PETS if p != pet), sorted(p for p in pool if p in PET_NAMES))
        self.assertEqual(self.world.fill_slot_data()["starting_pet"], pet)

    def test_snoof_is_a_pet(self) -> None:
        # Snoof (Wolfie) is always there in vanilla; here it's the 7th pet, and can be the starting one.
        self.assertIn("Snoof Pet", BASE_PETS)
        self.assertEqual(len(BASE_PETS), 7)


class TestLeaderReroll(WildfrostTestBase):
    def test_on_by_default(self) -> None:
        self.assertIs(self.world.fill_slot_data()["leader_reroll"], True)


class TestLeaderRerollOff(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "leader_reroll": False}

    def test_slot_data(self) -> None:
        self.assertIs(self.world.fill_slot_data()["leader_reroll"], False)


class TestOldOptionNames(WildfrostTestBase):
    """yamls from before 0.3.0 still generate with the old Goal and Progression Direction choice names."""
    options = {**WildfrostTestBase.options, "goal": "overcranked_each_clan", "progression_direction": "normal"}

    def test_aliases(self) -> None:
        self.assertEqual(self.world.options.goal.value, 2)
        self.assertEqual(self.world.options.progression_direction.value, 0)


class TestDirectionFromOldSlotData(unittest.TestCase):
    """Universal Tracker: seeds made before the rename sent the direction as "storm_bells"."""

    def test_fallback(self) -> None:
        self.assertEqual(progression_direction({"progression_direction": 1}), 1)
        self.assertEqual(progression_direction({"storm_bells": 1}), 1)
        self.assertEqual(progression_direction({}), 0)


class TestDeathLinkDamage(WildfrostTestBase):
    def test_flee_by_default(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["death_link_damage_percent"], 100)


class TestDeathLinkDamageSet(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "death_link": True, "death_link_damage_percent": 40}

    def test_slot_data(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["death_link_damage_percent"], 40)


class TestPossessedFinalBoss(WildfrostTestBase):
    def test_vanilla_by_default(self) -> None:
        self.assertIs(self.world.fill_slot_data()["disable_possessed_final_boss"], False)


class TestPossessedFinalBossOff(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "disable_possessed_final_boss": True}

    def test_slot_data(self) -> None:
        self.assertIs(self.world.fill_slot_data()["disable_possessed_final_boss"], True)


class TestGameSpeedUp(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "game_speed_up": True}

    def test_slot_data(self) -> None:
        self.assertIs(self.world.fill_slot_data()["game_speed_up"], True)


class TestForceOvercrank(WildfrostTestBase):
    """22 also forces Overcrank, as Force Storm Bells and Force Overcrank together did."""
    options = {**WildfrostTestBase.options, "force_storm_bells_up_to": 22}

    def test_slot_data(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["force_storm_bells_up_to"], 22)

    def test_win_needs_two_more_packs(self) -> None:
        self.collect_by_name([pack("General", "Companion"), pack("General", "Item")] + charms("General", 3))
        self.assertFalse(self.can_reach_location("Victory (Snowdwellers)"))
        self.collect_by_name([pack("Basic", "Companion")])
        self.assertTrue(self.can_reach_location("Victory (Snowdwellers)"))


class TestForcePointsFromOldSeeds(WildfrostTestBase):
    def test_old_toggles(self) -> None:
        from ..world import force_points
        self.assertEqual(force_points({"force_storm_bells_up_to": 12}), 12)
        # Each old toggle added one pack: one of them is 20 (one pack), both 22 (two).
        self.assertEqual(force_points({"force_storm_bells": True, "force_overcrank": False}), 20)
        self.assertEqual(force_points({"force_storm_bells": True, "force_overcrank": True}), 22)
        self.assertEqual(force_points({"force_storm_bells": False, "force_overcrank": True}), 20)
        self.assertEqual(force_points({"force_storm_bells": False, "force_overcrank": False}), 0)


def pack(clan: str, kind: str, n: int = 1) -> str:
    return next(name for _, name, _, info in ITEMS if info["kind"] == "Pack" and info["clan"] == clan
                and info["card_kind"] == kind and name.endswith(f" {n}"))


def charms(clan: str, n: int) -> list[str]:
    """The first n charm items of a clan."""
    return [name for _, name, _, info in ITEMS if info["kind"] == "Charm" and info["clan"] == clan][:n]


SNOW_LATE = [name for key, name, _, info in LOCATIONS
             if key.startswith("battle:") and info["run_tribe"] == "Basic"
             and 5 <= info["tier"] <= 7]


class TestDeckStrength(WildfrostTestBase):
    def test_late_fights_need_cards(self) -> None:
        self.assertTrue(SNOW_LATE)
        for name in SNOW_LATE + ["Victory (Snowdwellers)"]:
            with self.subTest(location=name):
                self.assertFalse(self.can_reach_location(name))

    def test_companion_and_item_pack(self) -> None:
        self.collect_by_name([pack("General", "Companion"), pack("General", "Item")])
        for name in SNOW_LATE + ["Victory (Snowdwellers)"]:
            with self.subTest(location=name):
                self.assertTrue(self.can_reach_location(name))

    def test_companion_and_six_charms(self) -> None:
        self.collect_by_name([pack("Basic", "Companion")] + charms("General", 3) + charms("Basic", 3))
        self.assertTrue(self.can_reach_location("Victory (Snowdwellers)"))

    def test_five_charms_are_not_enough(self) -> None:
        self.collect_by_name([pack("General", "Companion")] + charms("General", 5))
        self.assertFalse(self.can_reach_location("Victory (Snowdwellers)"))

    def test_other_clans_packs_do_not_count(self) -> None:
        self.collect_by_name([pack("Magic", "Companion"), pack("Magic", "Item")])
        self.assertFalse(self.can_reach_location("Victory (Snowdwellers)"))
        self.collect_by_name(["Shademancers"])
        self.assertTrue(self.can_reach_location("Victory (Shademancers)"))


class TestTrueFinalKit(BellTestBase):
    options = {**WildfrostTestBase.options, "goal": "true_final_boss"}

    def test_needs_packs_and_bells(self) -> None:
        self.collect_bells(TRUE_FINAL_BELLS_NEEDED)
        self.collect_by_name([pack("General", "Companion", 1), pack("General", "Companion", 2),
                              pack("General", "Item", 1)] + charms("General", 3))
        self.assertFalse(self.can_reach_location("Victory (Snowdwellers)"))
        self.collect_by_name([pack("General", "Item", 2)])
        self.assertTrue(self.can_reach_location("Victory (Snowdwellers)"))


class TestTrueFinalKitForced(BellTestBase):
    options = {**WildfrostTestBase.options, "goal": "true_final_boss", "force_storm_bells_up_to": 10}

    def test_needs_one_more_pack(self) -> None:
        self.collect_bells(TRUE_FINAL_BELLS_NEEDED)
        self.collect_by_name([pack("General", "Companion", 1), pack("General", "Companion", 2),
                              pack("General", "Item", 1), pack("General", "Item", 2)] + charms("General", 3))
        self.assertFalse(self.can_reach_location("Victory (Snowdwellers)"))
        self.collect_by_name(charms("General", 6)[3:])
        self.assertTrue(self.can_reach_location("Victory (Snowdwellers)"))


class TestFiller(WildfrostTestBase):
    def test_no_traps_at_zero(self) -> None:
        kinds = {info["kind"] for _, name, _, info in ITEMS for i in self.multiworld.itempool if i.name == name}
        self.assertNotIn("Trap", kinds)
        self.assertIn("Filler", kinds)


class TestAllTraps(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "trap_percentage": 100}

    def test_filler_is_traps(self) -> None:
        names = {name for _, name, _, info in ITEMS if info["kind"] == "Filler"}
        self.assertFalse([i.name for i in self.multiworld.itempool if i.name in names])
        self.assertTrue([i for i in self.multiworld.itempool if i.trap])


class TestCardChallenges(WildfrostTestBase):
    """Challenges that need particular cards: the pack holding one this seed, and its clan's tribe."""

    def pack_name(self, card: str) -> str:
        """The item that brings a card: its pack this seed, or for a charm the charm itself."""
        charm = next((name for _, name, _, info in ITEMS if info.get("card") == f"card:{card}"), None)
        if charm:
            return charm
        pack = next(key for key, cards in self.world.pack_contents.items() if f"card:{card}" in cards)
        return next(name for key, name, _, _ in ITEMS if key == pack)

    def collect_card(self, card: str) -> None:
        self.collect_by_name(self.pack_name(card))

    def test_toxic_needs_two_shroom_cards(self) -> None:
        self.assertFalse(self.can_reach_location("Challenge - Toxic"))
        self.collect_card("Shroominator")
        pack = next(cards for cards in self.world.pack_contents.values() if "card:Shroominator" in cards)
        shares = any(f"card:{c}" in pack for c in ("Fulbert", "Fungoose", "Wort", "HongosHammer", "SporePack", "ShroomLauncher"))
        self.assertEqual(self.can_reach_location("Challenge - Toxic"), shares)
        self.collect_card("Wort")
        self.assertTrue(self.can_reach_location("Challenge - Toxic"))

    def test_teeth_with_spike_or_shademancer_cards(self) -> None:
        location = "Challenge - Kill 10 enemies with Teeth"
        self.assertFalse(self.can_reach_location(location))
        spike = self.world.create_item("Spike Pet")  # fresh: it may be the starting pet, out of the pool
        self.collect(spike)
        self.assertTrue(self.can_reach_location(location))
        self.remove(spike)
        self.collect_card("Tusk")
        self.assertFalse(self.can_reach_location(location))
        self.collect_by_name("Shademancers")
        self.assertTrue(self.can_reach_location(location))

    def test_ritual_needs_two_sacrifice_cards(self) -> None:
        self.collect_by_name("Shademancers")
        self.collect_card("SnufferMask")
        pack = next(cards for cards in self.world.pack_contents.values() if "card:SnufferMask" in cards)
        shares = any(f"card:{c}" in pack for c in ("SnowMaul", "ZapOrb", "TailsFive", "TheBaker", "Boggler"))
        self.assertEqual(self.can_reach_location("Challenge - Ritual"), shares)
        self.collect_card("Boggler")
        self.assertTrue(self.can_reach_location("Challenge - Ritual"))

    def test_clunker_challenges(self) -> None:
        # Woodhead, in every Snowdweller starting deck, blocks.
        self.assertTrue(self.can_reach_location("Challenge - Block 10 hits with Clunkers"))
        self.assertFalse(self.can_reach_location("Challenge - Add 3 Clunkers to your deck"))
        self.collect_card("Bitebox")
        self.assertTrue(self.can_reach_location("Challenge - Add 3 Clunkers to your deck"))
        self.assertFalse(self.can_reach_location("Challenge - Add 10 Scrap to Clunkers"))
        self.collect_by_name("Clunkmasters")
        self.assertTrue(self.can_reach_location("Challenge - Add 10 Scrap to Clunkers"))

    def test_berry_good_needs_pinkberry_juice(self) -> None:
        self.assertFalse(self.can_reach_location("Challenge - Berry Good"))
        self.collect_card("PinkberryJuice")
        self.assertTrue(self.can_reach_location("Challenge - Berry Good"))

    def test_snowball_fight_needs_snowcake(self) -> None:
        self.assertFalse(self.can_reach_location("Challenge - Snowball Fight"))
        self.collect_card("Snowcake")
        self.assertTrue(self.can_reach_location("Challenge - Snowball Fight"))

    def test_bigger_hitter_is_filler_only(self) -> None:
        """Filler only, like Gnomebringer (the user's call, 2026-11-24): too hard to put a rule on."""
        self.assert_filler_only("Bigger Hitter", True)

    def test_big_hitter_needs_a_pair(self) -> None:
        location = "Challenge - Big Hitter"
        self.assertFalse(self.can_reach_location(location))
        self.collect_card("Chompom")
        pack = next(cards for cards in self.world.pack_contents.values() if "card:Chompom" in cards)
        shares = any(f"card:{c}" in pack for c in ("ShellShield", "Shellbo", "Kernel", "Shelly"))
        self.assertEqual(self.can_reach_location(location), shares)
        self.collect_card("Kernel")
        self.assertTrue(self.can_reach_location(location))

    def test_big_hitter_shademancer_pair(self) -> None:
        location = "Challenge - Big Hitter"
        self.collect_card("TailsFive")
        self.collect_card("Monch")
        self.assertFalse(self.can_reach_location(location))
        self.collect_by_name("Shademancers")
        self.assertTrue(self.can_reach_location(location))

    def test_minimalist_with_toaster(self) -> None:
        location = "Challenge - Minimalist"
        self.collect_by_name("Clunkmasters")
        self.assertFalse(self.can_reach_location(location))
        self.collect_card("Havok")
        self.assertTrue(self.can_reach_location(location))

    def test_minimalist_through_gunk_bugs(self) -> None:
        # The Gunk Bugs are an Area 3 fight, in any run (no tribe lock since 2026-11-25): a run that gets there.
        location = "Challenge - Minimalist"
        self.assertFalse(self.can_reach_location(location))
        self.collect_by_name([pack("General", "Companion"), pack("General", "Item")])
        self.assertTrue(self.can_reach_location(location))

    def test_companion_and_item_pack_challenges(self) -> None:
        for location in ("Challenge - Beastmaster", "Challenge - Long Live the King"):
            with self.subTest(location=location):
                self.assertFalse(self.can_reach_location(location))
        self.collect_by_name([pack("Basic", "Companion"), pack("General", "Item")])
        for location in ("Challenge - Beastmaster", "Challenge - Long Live the King"):
            with self.subTest(location=location):
                self.assertTrue(self.can_reach_location(location))

    def test_six_kill_combo(self) -> None:
        location = "Challenge - Achieve a 6x Kill Combo"
        self.collect_by_name([pack("General", "Companion", 1), pack("General", "Companion", 2)] + charms("General", 2))
        self.assertFalse(self.can_reach_location(location))
        self.collect_by_name(charms("General", 3)[2:])
        self.assertTrue(self.can_reach_location(location))

    def test_discounted_items_need_two_item_packs(self) -> None:
        location = "Challenge - Buy 5 discounted items"
        self.collect_by_name([pack("General", "Item", 1)])
        self.assertFalse(self.can_reach_location(location))
        self.collect_by_name([pack("General", "Item", 2)])
        self.assertTrue(self.can_reach_location(location))

    def test_equip_ten_charms(self) -> None:
        location = "Challenge - Equip 10 Charms"
        self.assertFalse(self.can_reach_location(location))
        # A single charm (the user's call): a Shademancer one needs the Shademancers.
        self.collect_by_name(charms("Magic", 1))
        self.assertFalse(self.can_reach_location(location))
        self.collect_by_name(["Shademancers"])
        self.assertTrue(self.can_reach_location(location))
        self.remove_by_name(["Shademancers"] + charms("Magic", 1))
        self.collect_by_name(charms("General", 1))
        self.assertTrue(self.can_reach_location(location))

    def test_high_roller_needs_four_charms(self) -> None:
        # Buy 3 charms in one shop: 4 charms of one clan's pool (the user's call, 2026-11-13).
        for location in ("Challenge - High Roller", "Challenge - High Roller #2"):
            with self.subTest(location=location):
                self.collect_by_name(charms("General", 3))
                self.assertFalse(self.can_reach_location(location))
                self.collect_by_name(charms("Basic", 1))
                self.assertTrue(self.can_reach_location(location))
                self.remove_by_name(charms("General", 3) + charms("Basic", 1))
                # Shademancer charms count only with the Shademancers.
                self.collect_by_name(charms("General", 3) + charms("Magic", 1))
                self.assertFalse(self.can_reach_location(location))
                self.collect_by_name(["Shademancers"])
                self.assertTrue(self.can_reach_location(location))
                self.remove_by_name(["Shademancers"] + charms("General", 3) + charms("Magic", 1))

    def test_demonized_by_what_applies_it(self) -> None:
        """["applies", "Demonize"] (the user's call, 2026-11-24, in place of the demonize group): Snowdweller and
        Shademancer leaders apply it, so the Snowdwellers start with it; the rule lists the cards and the Loki pet too."""
        location = "Challenge - Kill 3 Demonized enemies"
        self.assertTrue(self.can_reach_location(location))
        rule = json.dumps(self.world.location_rules["challenge:Challenge Pet 2"])
        for need in ("tribe:Basic", "tribe:Magic", "pet:DemonPet"):
            with self.subTest(need=need):
                self.assertIn(need, rule)

    def test_hoarder(self) -> None:
        """A Trash floor (the junk leaders or Trash cards) and a draw source; or starting with Junkhead and one more draw
        or Trash effect (the user's call, 2026-11-24). A Clunkmaster run has both: Junkhead, and its junk leaders."""
        location = "Challenge - Hoarder"
        self.collect_card("CardUpgradePunchfist")
        self.assertFalse(self.can_reach_location(location))  # no Trash and no Junkhead as Snowdwellers
        self.remove_by_name([self.pack_name("CardUpgradePunchfist")])
        self.collect_by_name("Clunkmasters")
        self.assertTrue(self.can_reach_location(location))
        rule = json.dumps(self.world.location_rules["challenge:Challenge Charm 18"])
        self.assertIn("tribe:Clunk", rule)
        self.assertIn("pet:DrawPet", rule)

    def test_counted_pets_are_progression(self) -> None:
        # Made fresh: either one may be the starting pet, and then it isn't in the pool.
        self.assertTrue(self.world.create_item("Spike Pet").advancement)
        self.assertTrue(self.world.create_item("Loki Pet").advancement)
        self.assertTrue(self.world.create_item("Sneezle Pet").advancement)


class TestStartingTribe(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "starting_tribe": "clunkmasters"}
    pack_name = TestCardChallenges.pack_name

    def test_start_tribe_precollected_not_in_pool(self) -> None:
        self.assertEqual([i.name for i in self.multiworld.precollected_items[self.player]], ["Clunkmasters", self.world.starting_pet])
        pool = [i.name for i in self.multiworld.itempool]
        self.assertNotIn("Clunkmasters", pool)
        self.assertIn("Snowdwellers", pool)
        self.assertEqual(self.world.fill_slot_data()["starting_tribe"], "Clunkmasters")

    def test_snowdwellers_gated(self) -> None:
        gated = [name for key, name, _, info in LOCATIONS
                 if "Basic" in required_tribes(key, info) and not info.get("true_final") and not info.get("ap")
                 and not info.get("spare")]
        # ...and the challenges whose cards are all Snowdweller cards, or whose effect only Snowdweller cards
        # and leaders apply (Shroom, Shell: ["applies", ...]).
        gated += ["Victory (Snowdwellers)"] + with_seconds(["Challenge - Tough Nut", "Challenge - Toxic", "Challenge - Bigger Hitter",
                                                            "Challenge - Kill 15 enemies with Shroom", "Challenge - Apply 60 Shell"])
        # One Punch needs the Scrappy Sword, which only the Snowdwellers start with (["starts_with", "Sword"]).
        gated += with_seconds(["Challenge - One Punch"])
        self.assertAccessDependency(gated, [["Snowdwellers"]])

    def test_clunkmaster_battles_need_nothing(self) -> None:
        for key, name, _, info in LOCATIONS:
            if key.startswith("battle:") and info["run_tribe"] == "Clunk" and info["tier"] <= 4:
                with self.subTest(location=name):
                    self.assertTrue(self.can_reach_location(name))

    def test_smackback_needs_a_smackback_source(self) -> None:
        # Clunkmaster leaders have no Smackback: another clan, Gojiber or the Punchfist Charm.
        location = "Challenge - Use Smackback to kill 20 enemies"
        self.assertFalse(self.can_reach_location(location))
        for items in (["Snowdwellers"], ["Shademancers"], [self.pack_name("Noggin")],
                      [self.pack_name("CardUpgradePunchfist")]):
            with self.subTest(items=items):
                self.collect_by_name(items)
                self.assertTrue(self.can_reach_location(location))
                self.remove_by_name(items)


class TestDefaults(WildfrostTestBase):
    """With no options set: one True Final Boss win, one extra bell, 10% traps (the user's call, 2026-11-02)."""

    options = {}

    def test_defaults(self) -> None:
        slot_data = self.world.fill_slot_data()
        self.assertEqual(slot_data["goal"], 1)
        self.assertEqual(slot_data["clans_required"], 1)
        self.assertEqual(slot_data["extra_storm_bells"], 1)
        self.assertEqual(slot_data["force_storm_bells_up_to"], 10)  # on by default (the user's call, 2026-11-06)
        self.assertEqual(self.world.options.trap_percentage.value, 10)
        self.assertEqual([i.name for i in self.multiworld.itempool].count(STORM_BELL), TRUE_FINAL_BELLS_NEEDED + 1)
        self.assertTrue(slot_data["goal_sized_bells"])
        self.assertTrue(TRUE_FINAL[0] in {loc.name for loc in self.multiworld.get_locations(self.player)})
        self.assertTrue(slot_data["new_challenges"])  # on by default (the user's call, 2026-11-08)


AP_CHALLENGES = [name for key, name, _, info in LOCATIONS if info.get("ap") and not info.get("spare")]
CHARM_SECONDS = [name for key, name, _, info in LOCATIONS
                 if info.get("second") and info.get("internal", "").startswith("Challenge Charm ")]


class TestNewChallengesOff(WildfrostTestBase):
    def test_twins_kept(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertFalse(names & set(AP_CHALLENGES))
        self.assertIn("Challenge - Big Hitter #2", names)
        self.assertFalse(self.world.fill_slot_data()["new_challenges"])
        self.assertEqual(self.world.create_item("Binku Pet").classification, ItemClassification.useful)
        self.assertEqual(self.world.create_item("Charm Merchant").classification, ItemClassification.useful)


class NewChallengesBase(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "goal": "true_final_boss", "new_challenges": True}
    pack_name = TestCardChallenges.pack_name


class TestNewChallenges(NewChallengesBase):
    def test_swap(self) -> None:
        # The 26 charm challenge twins go, the 25 new challenges come in; the boss twins stay.
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertEqual(len(AP_CHALLENGES), 25)
        self.assertEqual(len(CHARM_SECONDS), 26)
        self.assertTrue(set(AP_CHALLENGES) <= names)
        self.assertFalse(names & set(CHARM_SECONDS))
        self.assertTrue(any(n.endswith(" #2") and "Boss" in n for n in names))
        self.assertTrue(self.world.fill_slot_data()["new_challenges"])

    def test_bling_boss_filler_only(self) -> None:
        location = self.multiworld.get_location("Challenge - Reach a boss holding 200 or more Bling", self.player)
        self.assertEqual(location.progress_type, LocationProgressType.EXCLUDED)

    def test_events_and_binku_progression(self) -> None:
        for name in ("Charm Merchant", "Shade Sculptor", "Gnome Traveller", "Binku Pet"):
            with self.subTest(item=name):
                self.assertEqual(self.world.create_item(name).classification, ItemClassification.progression)

    def test_icgm_needs_its_pack_and_clunkmasters(self) -> None:
        location = "Challenge - Fire the I.C.G.M"
        self.assertFalse(self.can_reach_location(location))
        self.collect_by_name([self.pack_name("OhNo")])
        self.assertFalse(self.can_reach_location(location))
        self.collect_by_name(["Clunkmasters"])
        self.assertTrue(self.can_reach_location(location))

    def test_bell_challenges_need_a_bell(self) -> None:
        location = "Challenge - Apply 3 Cursed Crowns"
        self.assertFalse(self.can_reach_location(location))
        self.collect(self.get_items_by_name(STORM_BELL)[:1])
        self.assertTrue(self.can_reach_location(location))

    def test_charm_merchant_needs_event_four_packs_six_charms(self) -> None:
        location = "Challenge - Buy 2 upgraded cards from the Charm Merchant"
        self.collect_by_name(["Charm Merchant"] + charms("General", 6)
                             + [pack("General", "Companion", n) for n in (1, 2)] + [pack("General", "Item", 1)])
        self.assertFalse(self.can_reach_location(location))
        self.collect_by_name([pack("General", "Item", 2)])
        self.assertTrue(self.can_reach_location(location))

    def test_spice_needs_two_spice_cards(self) -> None:
        location = "Challenge - Stack 20 Spice on a single unit"
        self.collect_by_name(["Snowdwellers", self.pack_name("Pyra")])
        cards_in_pack = [c for p, c in self.world.pack_contents.items() if "card:Pyra" in c][0]
        spice_together = sum(f"card:{c}" in cards_in_pack for c in
                             ("PepperFlag", "Pyra", "SpiceStones", "Peppereaper", "Pimento", "DragonflamePepper"))
        self.assertEqual(self.can_reach_location(location), spice_together >= 2)
        self.collect_by_name([self.pack_name("Pimento")])
        self.assertTrue(self.can_reach_location(location))


class TestNewChallengesFinalBoss(NewChallengesBase):
    options = {**NewChallengesBase.options, "goal": "final_boss"}

    def test_one_bell_progression(self) -> None:
        # Final Boss bells are filler, but the bell challenges need one (the user's call, 2026-11-08).
        classes = [bell.classification for bell in self.get_items_by_name(STORM_BELL)]
        self.assertEqual(classes.count(ItemClassification.progression), 1)
        self.assertEqual(classes.count(ItemClassification.filler), len(classes) - 1)


class TestNewChallengesReverse(NewChallengesBase):
    options = {**NewChallengesBase.options, "progression_direction": "reverse"}

    def test_bell_challenges_need_no_bell(self) -> None:
        # Reverse runs start with every bell rung.
        self.assertTrue(self.can_reach_location("Challenge - Apply 3 Cursed Crowns"))


class TestRandomStartingTribe(WildfrostTestBase):
    options = {}

    def test_one_tribe_precollected(self) -> None:
        start = [i.name for i in self.multiworld.precollected_items[self.player]]
        tribes = [name for name in start if name in CLANS.values()]
        self.assertEqual(len(tribes), 1)
        # And the starting pet (random with all defaults).
        self.assertEqual(len(start), 2)
        self.assertIn(self.world.starting_pet, start)


class TestClansRequired(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "clans_required": 1}

    def test_one_clan_finishes(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["clans_required"], 1)
        self.collect_by_name([pack("General", "Companion"), pack("General", "Item")])
        self.assertBeatable(True)


class TestClansRequiredThree(WildfrostTestBase):
    def test_three_need_every_clan(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["clans_required"], 3)
        self.collect_by_name([pack("General", "Companion"), pack("General", "Item")])
        self.assertBeatable(False)


def evaluate(rule: list, have: dict[str, int]) -> bool:
    """The client's reading of a slot_data location rule (ApTracker.Evaluate)."""
    kind = rule[0]
    if kind == "and":
        return all(evaluate(r, have) for r in rule[1])
    if kind == "or":
        return any(evaluate(r, have) for r in rule[1])
    if kind == "has":
        return have.get(rule[1], 0) >= rule[2]
    if kind == "all":
        return all(have.get(k, 0) for k in rule[1])
    if kind == "any":
        return sum(1 for k in rule[1] if have.get(k, 0)) >= rule[2]
    if kind == "packs":
        _, clan, card_kind, count = rule
        if card_kind == "Charm":
            return sum(1 for k in have if k.startswith("charm:") and k.split(":")[1] in ("General", clan)) >= count
        return sum(1 for k in have if k.startswith("pack:") and k.split(":")[1] in ("General", clan)
                   and card_kind in ("", k.split(":")[2])) >= count
    raise ValueError(kind)


class TestLocationRulesForClient(BellTestBase):
    options = {**WildfrostTestBase.options, "goal": "true_final_boss", "force_storm_bells_up_to": 10}

    def check_matches(self) -> None:
        rules = read_location_rules(self.world.fill_slot_data()["location_rules"])
        key_of = {name: key for key, name, _, _ in ITEMS}
        state = self.multiworld.state
        have = {key_of[name]: count for name, count in state.prog_items[self.player].items() if name in key_of}
        key_of_location = {name: key for key, name, _, _ in LOCATIONS}
        for location in self.multiworld.get_locations(self.player):
            if location.address is None:
                continue  # the Victory events: the client sends the goal itself
            key = key_of_location[location.name]
            with self.subTest(location=location.name):
                self.assertEqual(evaluate(rules[key], have) if key in rules else True, location.can_reach(state))

    def test_matches_logic(self) -> None:
        self.check_matches()
        self.collect_by_name(["Clunkmasters", pack("General", "Companion"), pack("General", "Item")])
        self.check_matches()
        self.collect_bells(TRUE_FINAL_BELLS_NEEDED)
        self.collect_by_name([pack("General", "Companion", 2), pack("General", "Item", 2), "Shademancers"]
                             + charms("General", 6))
        self.collect(self.world.create_item("Loki Pet"))
        self.check_matches()
        self.collect(self.get_items_by_name([name for name in {i.name for i in self.multiworld.itempool}]))
        self.check_matches()

    def test_bell_kits(self) -> None:
        kits = self.world.fill_slot_data()["bell_kits"]
        # 2 storm points, 4-8, 10 (the True Final Boss), 12, then 14-20 and Overcrank.
        self.assertEqual([levels for levels, _ in kits], [1, 4, 5, 6, 11])
        # Each level's forced extra: none at 2, one at 4-12, two from 14: a companion or item pack, or three charms.
        extra = lambda n: {"extra": n, "charms_per_pack": 3}
        self.assertEqual(kits[0][1], [{"Companion": 1, "Item": 1, "Charm": 0, **extra(0)}, {"Companion": 1, "Item": 0, "Charm": 6, **extra(0)}])
        self.assertEqual(kits[1][1], [{"Companion": 1, "Item": 1, "Charm": 0, **extra(1)}, {"Companion": 1, "Item": 0, "Charm": 6, **extra(1)}])
        self.assertEqual(kits[2][1], [{"Companion": 2, "Item": 2, "Charm": 3, **extra(1)}])
        self.assertEqual(kits[3][1], [{"Companion": 2, "Item": 3, "Charm": 6, **extra(1)}])
        self.assertEqual(kits[4][1], [{"Companion": 2, "Item": 3, "Charm": 6, **extra(2)}])


class TestSecondChecks(BellTestBase):
    options = {**WildfrostTestBase.options, "goal": "true_final_boss"}

    def test_seconds_share_their_first_rule(self) -> None:
        seconds = [name for _, name, _, info in LOCATIONS if info.get("second") and not info.get("spare")]
        # Every boss (18) and every challenge that unlocks a charm in vanilla (26); spares aren't in the seed.
        self.assertEqual(len(seconds), 44)
        rules = read_location_rules(self.world.fill_slot_data()["location_rules"])
        key_of = {name: key for key, name, _, _ in LOCATIONS}
        for name in seconds:
            first = name.removesuffix(" #2")
            with self.subTest(location=name):
                self.assertIn(first, LOCATION_NAMES)
                self.assertEqual(rules.get(key_of[name]), rules.get(key_of[first]))

    def test_gnomebringer_filler_only(self) -> None:
        self.assert_filler_only("Gnomebringer", True)

    def test_sunbringer_counts_with_three_clans(self) -> None:
        self.assert_filler_only("Sunbringer", False)

    def test_sunbringer_needs_the_true_final_kit(self) -> None:
        self.collect_bells(TRUE_FINAL_BELLS_NEEDED)
        self.collect_by_name([pack("General", "Companion", 1), pack("General", "Companion", 2),
                              pack("General", "Item", 1)] + charms("General", 3))
        self.assertFalse(self.can_reach_location("Challenge - Sunbringer"))
        self.collect_by_name([pack("General", "Item", 2)])
        self.assertTrue(self.can_reach_location("Challenge - Sunbringer"))


class TestTrueFinalBossForcingCap(WildfrostTestBase):
    """Forcing goes no higher than the bells in a True Final Boss pool reach: 10, plus 2 for each extra."""

    options = {**WildfrostTestBase.options, "goal": "true_final_boss", "extra_storm_bells": 2,
               "force_storm_bells_up_to": 22}

    def test_capped(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["force_storm_bells_up_to"], 14)


class TestTrueFinalBossThreeClans(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "goal": "true_final_boss"}

    def test_bells_in_pool(self) -> None:
        pool = [i.name for i in self.multiworld.itempool]
        self.assertEqual(pool.count(STORM_BELL), TRUE_FINAL_BELLS_NEEDED)


class TestReverseBellsInPool(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "progression_direction": "reverse"}

    def test_every_level(self) -> None:
        # Reverse needs every bell (its goal is the True Final Boss on a no-bell run), and they count in logic.
        pool = [i.name for i in self.multiworld.itempool]
        self.assertEqual(pool.count(STORM_BELL), STORM_BELL_LEVELS)
        for bell in self.get_items_by_name(STORM_BELL):
            self.assertEqual(bell.classification, ItemClassification.progression)


class TestOlderSeedBells(WildfrostTestBase):
    """Universal Tracker rebuilds a seed from before goal_sized_bells with every bell level and Sunbringer."""

    def test_old_pool(self) -> None:
        self.world.goal_sized_bells = False
        self.world.options.goal.value = self.world.options.goal.option_true_final_boss
        self.assertEqual(storm_bells_in_pool(self.world), STORM_BELL_LEVELS)
        self.world.options.goal.value = self.world.options.goal.option_final_boss
        self.assertTrue(included(self.world, SUNBRINGER))
        self.assertEqual(self.world.create_item(STORM_BELL).classification, ItemClassification.progression)
        self.world.goal_sized_bells = True
        self.assertFalse(included(self.world, SUNBRINGER))
        self.assertEqual(self.world.create_item(STORM_BELL).classification, ItemClassification.filler)


class TestOvercrankedBellsInPool(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "goal": "overcranked_true_final_boss", "extra_storm_bells": 1}

    def test_every_level(self) -> None:
        pool = [i.name for i in self.multiworld.itempool]
        self.assertEqual(pool.count(STORM_BELL), STORM_BELL_LEVELS + 1)


class TestSunbringerIsTheGoal(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "goal": "true_final_boss", "clans_required": 1}

    def test_filler_only(self) -> None:
        self.assert_filler_only("Sunbringer", True)


class TestSunbringerIsTheOvercrankedGoal(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "goal": "overcranked_true_final_boss", "clans_required": 1}

    def test_filler_only(self) -> None:
        self.assert_filler_only("Sunbringer", True)


class TestSunbringerCountsWithTwoClans(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "goal": "true_final_boss", "clans_required": 2}

    def test_not_filler_only(self) -> None:
        self.assert_filler_only("Sunbringer", False)


class TestSunbringerCountsOvercrankedEachClan(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "goal": "overcranked_true_final_boss"}

    def test_not_filler_only(self) -> None:
        self.assert_filler_only("Sunbringer", False)


class TestReverseStormBells(BellTestBase):
    """Reverse Storm Bells: start Overcranked, each bell lowers the floor (rules.REVERSE_PACKS)."""
    options = {**WildfrostTestBase.options, "progression_direction": "reverse", "force_storm_bells_up_to": 22,
               "goal": "final_boss", "clans_required": 1}

    def test_options_set(self) -> None:
        slot_data = self.world.fill_slot_data()
        self.assertEqual(slot_data["progression_direction"], 1)
        self.assertEqual(slot_data["goal"], 1)  # the True Final Boss, whatever the yaml said
        self.assertEqual(slot_data["force_storm_bells_up_to"], 0)
        self.assertTrue(TRUE_FINAL)

    def test_area_1_fights_from_the_start(self) -> None:
        self.assertTrue(self.can_reach_location("Area 1 Battle - The Snowbo Squad (Snowdwellers)"))
        self.assertTrue(self.can_reach_location("Area 1 Battle - The Frost Shades (Snowdwellers)"))
        self.assertFalse(self.can_reach_location("Area 1 Boss - Bamboozle (Snowdwellers)"))

    def test_area_1_boss_by_packs_or_bells(self) -> None:
        boss = "Area 1 Boss - Bamboozle (Snowdwellers)"
        # Overcranked: two packs, one of them as three charms.
        self.collect_by_name([pack("General", "Companion")])
        self.assertFalse(self.can_reach_location(boss))
        self.collect_by_name(charms("Basic", 3))
        self.assertTrue(self.can_reach_location(boss))

    def test_area_1_boss_by_bells(self) -> None:
        boss = "Area 1 Boss - Bamboozle (Snowdwellers)"
        self.collect_bells(8)
        self.assertFalse(self.can_reach_location(boss))
        self.collect_bells(1)  # down to 4 storm points: no packs needed
        self.assertTrue(self.can_reach_location(boss))

    def test_true_final_boss_needs_no_bell_run(self) -> None:
        self.collect_all_but([STORM_BELL, "Victory"])
        self.collect_bells(STORM_BELL_LEVELS - 1)
        for name in TRUE_FINAL + ["Victory (Snowdwellers)"]:
            with self.subTest(location=name):
                self.assertFalse(self.can_reach_location(name))
        self.collect_bells(1)
        for name in TRUE_FINAL + ["Victory (Snowdwellers)"]:
            with self.subTest(location=name):
                self.assertTrue(self.can_reach_location(name))


class TestSlotDataDepth(WildfrostTestBase):
    """
    Archipelago 0.6.8's Python clients (Universal Tracker, the Text Client) drop any message nested over
    16 deep (NetUtils._check_depth), so a Connected packet with this slot_data must pass it. Overcranked
    with forcing at 22 gives the deepest kits; New Challenges the deepest challenge rules.
    """
    options = {**WildfrostTestBase.options, "goal": "overcranked_true_final_boss", "force_storm_bells_up_to": 22,
               "extra_storm_bells": 4, "new_challenges": True}

    def test_connected_packet_passes_the_depth_limit(self) -> None:
        from NetUtils import _check_depth, encode
        slot_data = self.world.fill_slot_data()
        packet = encode([{"cmd": "Connected", "team": 0, "slot": self.player, "players": [], "missing_locations": [],
                          "checked_locations": [], "slot_data": slot_data, "slot_info": {}, "hint_points": 0}])
        _check_depth(packet)  # raises ValueError("JSON document too complex")
        self.assertTrue(read_location_rules(slot_data["location_rules"]))


class TestSlotDataDepthReverse(TestSlotDataDepth):
    options = {**WildfrostTestBase.options, "progression_direction": "reverse", "new_challenges": True}


class TestRuleChanges20261116(WildfrostTestBase):
    """The user's rule changes of 2026-11-16 (base.wildfrost.json)."""
    options = {**WildfrostTestBase.options, "goal": "final_boss"}

    def test_rampage_one_frenzy_card_and_a_winnable_run(self) -> None:
        # A reusable Frenzy source isn't enough alone: the fight still has to be won (Area 3, the Final
        # Boss kit; the user's call, 2026-11-16).
        location = "Challenge - Rampage"
        self.collect_by_name([TestCardChallenges.pack_name(self, "TinyTyko")])
        self.assertFalse(self.can_reach_location(location))
        self.collect_by_name([pack("General", "Companion", 1), pack("General", "Item", 1)])
        self.assertTrue(self.can_reach_location(location))

    def test_icemaster_open_from_the_start(self) -> None:
        # Every clan has leaders that apply Block (["applies", "Block"]).
        self.assertTrue(self.can_reach_location("Challenge - Icemaster"))

    def test_feed_the_beast_needs_a_consume_card(self) -> None:
        location = "Challenge - Feed the Beast"
        self.assertFalse(self.can_reach_location(location))
        self.collect_by_name([TestCardChallenges.pack_name(self, "BlazeTea")])  # Blaze Tea: Consume
        self.assertTrue(self.can_reach_location(location))

    def test_area_4_takes_the_true_final_boss_packs(self) -> None:
        # Undefeated and Charmless: the True Final Boss kit's packs (2 companion packs, 2 item packs, 3
        # charms of one clan), no bells, so they stay possible in a Final Boss goal seed.
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        for location in ("Challenge - Undefeated", "Challenge - Charmless"):
            with self.subTest(location=location):
                self.assertIn(location, names)
                self.collect_by_name([pack("General", "Companion", 1), pack("General", "Item", 1)])
                self.assertFalse(self.can_reach_location(location))  # the Final Boss kit isn't enough
                self.collect_by_name([pack("General", "Companion", 2), pack("General", "Item", 2)] + charms("General", 3))
                self.assertTrue(self.can_reach_location(location))
                self.remove_by_name([pack("General", "Companion", n) for n in (1, 2)]
                                    + [pack("General", "Item", n) for n in (1, 2)] + charms("General", 3))


class TestSparesFillerFloor(WildfrostTestBase):
    """Spare "#2" checks also keep FILLER_FLOOR of the checks filler (the user's call, 2026-11-27), challenges'
    first, as far as the spares go. Real item counts are made up here."""

    def spares_with(self, real: int) -> set[str]:
        self.world.spare_checks = set()
        with mock.patch.object(items_module, "real_item_count", return_value=real):
            try:
                return locations_module.spare_checks(self.world)
            finally:
                self.world.spare_checks = set()

    def test_floor(self) -> None:
        self.world.spare_checks = set()
        left = sum(1 for key, _, _, info in LOCATIONS if included(self.world, info, key))
        floor = locations_module.FILLER_FLOOR
        # Room for the items and the floor: no spares.
        self.assertEqual(self.spares_with(int(left * (1 - floor))), set())
        # Room for the items but under the floor: just enough spares to reach it, challenges' first.
        real = int(left * (1 - floor)) + 3
        chosen = self.spares_with(real)
        self.assertTrue(chosen)
        self.assertTrue(all(key.startswith("challenge:") for key in chosen))
        total = left + len(chosen)
        self.assertGreaterEqual(total - real, floor * total)
        self.assertLess(total - 1 - real, floor * (total - 1))

