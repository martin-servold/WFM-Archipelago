from ..data import CARDS, ITEMS, LOCATIONS, PACK_SIZE
from ..items import PACK_KEYS, STORM_BELL, STORM_BELL_LEVELS
from ..rules import TRIBE_ITEM, TRUE_FINAL_BELLS as TRUE_FINAL_BELLS_NEEDED, required_tribes
from . import WildfrostTestBase


class TestDefaultPool(WildfrostTestBase):
    def test_no_cards_at_start(self) -> None:
        # Only the starting tribe.
        self.assertEqual([i.name for i in self.multiworld.precollected_items[self.player]], ["Snowdwellers"])

    def test_every_card_in_exactly_one_pack(self) -> None:
        packs = self.world.pack_contents
        self.assertEqual(sorted(packs), sorted(PACK_KEYS))
        dealt = [card for cards in packs.values() for card in cards]
        self.assertEqual(sorted(dealt), sorted(key for key, _, _ in CARDS))
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
        for tribe, item in TRIBE_ITEM.items():
            if item == "Snowdwellers":
                continue  # the starting tribe here; TestStartingTribe covers it
            gated = [name for key, name, _, info in LOCATIONS
                     if tribe in required_tribes(key, info) and not info.get("true_final")]
            gated.append(f"Victory ({item})")
            with self.subTest(tribe=tribe):
                self.assertTrue(gated)
                self.assertAccessDependency(gated, [[item]])


class TestBattlesPerTribe(WildfrostTestBase):
    def test_every_battle_once_per_tribe(self) -> None:
        battles = [info for key, _, _, info in LOCATIONS if key.startswith("battle:")]
        self.assertEqual({info["run_tribe"] for info in battles}, {"Basic", *TRIBE_ITEM})
        self.assertEqual(len(battles) % 3, 0)

    def test_snowdweller_battles_need_nothing(self) -> None:
        for key, name, _, info in LOCATIONS:
            if key.startswith("battle:") and info["run_tribe"] == "Basic" and not info["tribe"] and info["tier"] <= 4:
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

    def test_needs_both_tribes(self) -> None:
        self.collect_all_but(["Shademancers", "Victory"])
        self.assertFalse(self.multiworld.can_beat_game(self.multiworld.state))
        self.assertTrue(self.can_reach_location("Victory (Snowdwellers)"))


class TestGoalTrueFinalBoss(BellTestBase):
    options = {**WildfrostTestBase.options, "goal": "true_final_boss_each_clan", "extra_storm_bells": 2}

    def test_true_final_boss_checks_need_six_bells(self) -> None:
        self.assertTrue(TRUE_FINAL)
        self.collect_all_but([STORM_BELL, "Victory"])
        self.collect_bells(5)
        for name in TRUE_FINAL + VICTORIES:
            with self.subTest(location=name):
                self.assertFalse(self.can_reach_location(name))
        self.collect_bells(1)
        for name in TRUE_FINAL + VICTORIES:
            with self.subTest(location=name):
                self.assertTrue(self.can_reach_location(name))

    def test_extra_bells(self) -> None:
        pool = [i.name for i in self.multiworld.itempool]
        self.assertEqual(pool.count(STORM_BELL), STORM_BELL_LEVELS + 2)


class TestGoalOvercranked(BellTestBase):
    options = {**WildfrostTestBase.options, "goal": "overcranked_each_clan"}

    def test_victory_needs_every_level(self) -> None:
        self.collect_all_but([STORM_BELL, "Victory"])
        self.collect_bells(STORM_BELL_LEVELS - 1)
        self.assertTrue(self.can_reach_location(TRUE_FINAL[0]))
        self.assertFalse(self.can_reach_location("Victory (Snowdwellers)"))
        self.collect_bells(1)
        self.assertTrue(self.multiworld.can_beat_game(self.multiworld.state))


class TestForceStormBells(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "force_storm_bells": True}

    def test_slot_data(self) -> None:
        self.assertIs(self.world.fill_slot_data()["force_storm_bells"], True)
        self.assertIs(self.world.fill_slot_data()["force_overcrank"], False)


class TestForceOvercrank(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "force_overcrank": True}

    def test_slot_data(self) -> None:
        self.assertIs(self.world.fill_slot_data()["force_overcrank"], True)


def pack(clan: str, kind: str, n: int = 1) -> str:
    return next(name for _, name, _, info in ITEMS if info["kind"] == "Pack" and info["clan"] == clan
                and info["card_kind"] == kind and name.endswith(f" {n}"))


SNOW_LATE = [name for key, name, _, info in LOCATIONS
             if key.startswith("battle:") and info["run_tribe"] == "Basic" and not info["tribe"]
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

    def test_companion_and_two_charm_packs(self) -> None:
        self.collect_by_name([pack("Basic", "Companion"), pack("General", "Charm", 1), pack("Basic", "Charm", 1)])
        self.assertTrue(self.can_reach_location("Victory (Snowdwellers)"))

    def test_one_charm_pack_is_not_enough(self) -> None:
        self.collect_by_name([pack("General", "Companion"), pack("General", "Charm")])
        self.assertFalse(self.can_reach_location("Victory (Snowdwellers)"))

    def test_other_clans_packs_do_not_count(self) -> None:
        self.collect_by_name([pack("Magic", "Companion"), pack("Magic", "Item")])
        self.assertFalse(self.can_reach_location("Victory (Snowdwellers)"))
        self.collect_by_name(["Shademancers"])
        self.assertTrue(self.can_reach_location("Victory (Shademancers)"))


class TestTrueFinalKit(BellTestBase):
    options = {**WildfrostTestBase.options, "goal": "true_final_boss_each_clan"}

    def test_needs_packs_and_bells(self) -> None:
        self.collect_bells(TRUE_FINAL_BELLS_NEEDED)
        self.collect_by_name([pack("General", "Companion", 1), pack("General", "Companion", 2),
                              pack("General", "Item", 1), pack("General", "Charm", 1)])
        self.assertFalse(self.can_reach_location("Victory (Snowdwellers)"))
        self.collect_by_name([pack("General", "Item", 2)])
        self.assertTrue(self.can_reach_location("Victory (Snowdwellers)"))


class TestFiller(WildfrostTestBase):
    def test_no_traps_by_default(self) -> None:
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

    def collect_card(self, card: str) -> None:
        pack = next(key for key, cards in self.world.pack_contents.items() if f"card:{card}" in cards)
        self.collect_by_name(next(name for key, name, _, _ in ITEMS if key == pack))

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
        self.collect_by_name("Spike Pet")
        self.assertTrue(self.can_reach_location(location))
        self.remove_by_name("Spike Pet")
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

    def test_spike_pet_is_progression(self) -> None:
        self.assertTrue(self.get_item_by_name("Spike Pet").advancement)


class TestStartingTribe(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "starting_tribe": "clunkmasters"}

    def test_start_tribe_precollected_not_in_pool(self) -> None:
        self.assertEqual([i.name for i in self.multiworld.precollected_items[self.player]], ["Clunkmasters"])
        pool = [i.name for i in self.multiworld.itempool]
        self.assertNotIn("Clunkmasters", pool)
        self.assertIn("Snowdwellers", pool)
        self.assertEqual(self.world.fill_slot_data()["starting_tribe"], "Clunkmasters")

    def test_snowdwellers_gated(self) -> None:
        gated = [name for key, name, _, info in LOCATIONS
                 if "Basic" in required_tribes(key, info) and not info.get("true_final")]
        # ...and the challenges whose cards are all Snowdweller cards.
        gated += ["Victory (Snowdwellers)", "Challenge - Tough Nut", "Challenge - Toxic"]
        self.assertIn("Challenge - One Punch", gated)
        self.assertIn("Challenge - Block 10 hits with Clunkers", gated)
        self.assertAccessDependency(gated, [["Snowdwellers"]])

    def test_clunkmaster_battles_need_nothing(self) -> None:
        for key, name, _, info in LOCATIONS:
            if key.startswith("battle:") and info["run_tribe"] == "Clunk" and not info["tribe"] and info["tier"] <= 4:
                with self.subTest(location=name):
                    self.assertTrue(self.can_reach_location(name))


class TestRandomStartingTribe(WildfrostTestBase):
    options = {}

    def test_one_tribe_precollected(self) -> None:
        start = [i.name for i in self.multiworld.precollected_items[self.player]]
        self.assertEqual(len(start), 1)
        self.assertIn(start[0], TRIBE_ITEM.values())
