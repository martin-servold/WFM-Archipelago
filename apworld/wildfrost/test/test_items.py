from ..data import CARDS, ITEMS, LOCATIONS, PACK_SIZE
from ..items import PACK_KEYS, PET_NAMES, STORM_BELL, STORM_BELL_LEVELS
from ..locations import CLANS
from ..rules import TRUE_FINAL_BELLS as TRUE_FINAL_BELLS_NEEDED, required_tribes
from . import WildfrostTestBase


LOCATION_NAMES = {name for _, name, _, _ in LOCATIONS}


def with_seconds(names: list[str]) -> list[str]:
    """The names and their "#2" checks, which share their first's rule."""
    return names + [f"{name} #2" for name in names if f"{name} #2" in LOCATION_NAMES]


class TestDefaultPool(WildfrostTestBase):
    def test_no_cards_at_start(self) -> None:
        # Only the starting tribe and the random starting pet.
        self.assertEqual([i.name for i in self.multiworld.precollected_items[self.player]], ["Snowdwellers", self.world.starting_pet])

    def test_every_card_in_exactly_one_pack(self) -> None:
        packs = self.world.pack_contents
        self.assertEqual(sorted(packs), sorted(PACK_KEYS))
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
        for tribe, item in CLANS.items():
            if item == "Snowdwellers":
                continue  # the starting tribe here; TestStartingTribe covers it
            gated = [name for key, name, _, info in LOCATIONS
                     if tribe in required_tribes(key, info) and not info.get("true_final")]
            gated.append(f"Victory ({item})")
            if item == "Clunkmasters":
                # Toaster and the Gunk Bugs fight are both Clunkmaster.
                gated += with_seconds(["Challenge - Minimalist", "Challenge - Hoarder"])
            with self.subTest(tribe=tribe):
                self.assertTrue(gated)
                self.assertAccessDependency(gated, [[item]])


class TestBattlesPerTribe(WildfrostTestBase):
    def test_every_battle_once_per_tribe(self) -> None:
        battles = [info for key, _, _, info in LOCATIONS if key.startswith("battle:")]
        self.assertEqual({info["run_tribe"] for info in battles}, {"Basic", *CLANS})
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
        self.assertIs(self.world.fill_slot_data()["game_speed_up"], False)  # off by default

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


class TestForceOvercrank(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "force_overcrank": True}

    def test_slot_data(self) -> None:
        self.assertIs(self.world.fill_slot_data()["force_overcrank"], True)


class TestRandomStartingPet(WildfrostTestBase):
    def test_one_pet_precollected_not_in_pool(self) -> None:
        pet = self.world.starting_pet
        self.assertIn(pet, PET_NAMES)
        self.assertIn(pet, [i.name for i in self.multiworld.precollected_items[self.player]])
        pool = [i.name for i in self.multiworld.itempool]
        self.assertNotIn(pet, pool)
        self.assertEqual(sorted(p for p in PET_NAMES if p != pet), sorted(p for p in pool if p in PET_NAMES))
        self.assertEqual(self.world.fill_slot_data()["starting_pet"], pet)

    def test_snoof_is_a_pet(self) -> None:
        # Snoof (Wolfie) is always there in vanilla; here it's the 7th pet, and can be the starting one.
        self.assertIn("Snoof Pet", PET_NAMES)
        self.assertEqual(len(PET_NAMES), 7)


class TestLeaderReroll(WildfrostTestBase):
    def test_on_by_default(self) -> None:
        self.assertIs(self.world.fill_slot_data()["leader_reroll"], True)


class TestLeaderRerollOff(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "leader_reroll": False}

    def test_slot_data(self) -> None:
        self.assertIs(self.world.fill_slot_data()["leader_reroll"], False)


class TestGameSpeedUp(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "game_speed_up": True}

    def test_slot_data(self) -> None:
        self.assertIs(self.world.fill_slot_data()["game_speed_up"], True)


class TestForceBoth(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "force_storm_bells": True, "force_overcrank": True}

    def test_win_needs_two_more_packs(self) -> None:
        self.collect_by_name([pack("General", "Companion"), pack("General", "Item")] + charms("General", 3))
        self.assertFalse(self.can_reach_location("Victory (Snowdwellers)"))
        self.collect_by_name([pack("Basic", "Companion")])
        self.assertTrue(self.can_reach_location("Victory (Snowdwellers)"))


def pack(clan: str, kind: str, n: int = 1) -> str:
    return next(name for _, name, _, info in ITEMS if info["kind"] == "Pack" and info["clan"] == clan
                and info["card_kind"] == kind and name.endswith(f" {n}"))


def charms(clan: str, n: int) -> list[str]:
    """The first n charm items of a clan."""
    return [name for _, name, _, info in ITEMS if info["kind"] == "Charm" and info["clan"] == clan][:n]


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
    options = {**WildfrostTestBase.options, "goal": "true_final_boss_each_clan"}

    def test_needs_packs_and_bells(self) -> None:
        self.collect_bells(TRUE_FINAL_BELLS_NEEDED)
        self.collect_by_name([pack("General", "Companion", 1), pack("General", "Companion", 2),
                              pack("General", "Item", 1)] + charms("General", 3))
        self.assertFalse(self.can_reach_location("Victory (Snowdwellers)"))
        self.collect_by_name([pack("General", "Item", 2)])
        self.assertTrue(self.can_reach_location("Victory (Snowdwellers)"))


class TestTrueFinalKitForced(BellTestBase):
    options = {**WildfrostTestBase.options, "goal": "true_final_boss_each_clan", "force_storm_bells": True}

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

    def test_bigger_hitter_needs_spice_stones(self) -> None:
        self.assertFalse(self.can_reach_location("Challenge - Bigger Hitter"))
        self.collect_card("SpiceStones")
        self.assertTrue(self.can_reach_location("Challenge - Bigger Hitter"))

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
        # The Gunk Bugs are an Area 3 fight, unlocked with Clunkmasters: a run that gets there.
        location = "Challenge - Minimalist"
        self.collect_by_name(["Clunkmasters", pack("General", "Companion"), pack("General", "Item")])
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

    def test_demonized_with_loki_or_cards(self) -> None:
        location = "Challenge - Kill 3 Demonized enemies"
        self.assertFalse(self.can_reach_location(location))
        loki = self.world.create_item("Loki Pet")  # fresh: it may be the starting pet, out of the pool
        self.collect(loki)
        self.assertTrue(self.can_reach_location(location))
        self.remove(loki)
        for card in ("Demonheart", "Dimona", "TotemOfTheGoat"):
            with self.subTest(card=card):
                pack_name = self.pack_name(card)
                self.collect_by_name(pack_name)
                self.assertTrue(self.can_reach_location(location))
                self.remove_by_name(pack_name)

    def test_hoarder(self) -> None:
        location = "Challenge - Hoarder"
        self.collect_card("CardUpgradePunchfist")
        self.assertFalse(self.can_reach_location(location))  # needs a Clunkmaster run
        self.collect_by_name("Clunkmasters")
        self.assertTrue(self.can_reach_location(location))
        self.remove_by_name([self.pack_name("CardUpgradePunchfist")])
        self.assertFalse(self.can_reach_location(location))
        sneezle = self.world.create_item("Sneezle Pet")  # fresh: it may be the starting pet, out of the pool
        self.collect(sneezle)
        self.assertTrue(self.can_reach_location(location))
        self.remove(sneezle)
        for alone, partner in (("Badoo", "CardUpgradeCake"), ("CardUpgradeBoost", "Gearhead")):
            with self.subTest(pair=(alone, partner)):
                self.collect_card(alone)
                self.assertEqual(self.can_reach_location(location), self.pack_name(alone) == self.pack_name(partner))
                self.collect_card(partner)
                self.assertTrue(self.can_reach_location(location))
                self.remove_by_name(list({self.pack_name(alone), self.pack_name(partner)}))

    def test_counted_pets_are_progression(self) -> None:
        # Made fresh: either one may be the starting pet, and then it isn't in the pool.
        self.assertTrue(self.world.create_item("Spike Pet").advancement)
        self.assertTrue(self.world.create_item("Loki Pet").advancement)
        self.assertTrue(self.world.create_item("Sneezle Pet").advancement)


class TestStartingTribe(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "starting_tribe": "clunkmasters"}

    def test_start_tribe_precollected_not_in_pool(self) -> None:
        self.assertEqual([i.name for i in self.multiworld.precollected_items[self.player]], ["Clunkmasters", self.world.starting_pet])
        pool = [i.name for i in self.multiworld.itempool]
        self.assertNotIn("Clunkmasters", pool)
        self.assertIn("Snowdwellers", pool)
        self.assertEqual(self.world.fill_slot_data()["starting_tribe"], "Clunkmasters")

    def test_snowdwellers_gated(self) -> None:
        gated = [name for key, name, _, info in LOCATIONS
                 if "Basic" in required_tribes(key, info) and not info.get("true_final")]
        # ...and the challenges whose cards are all Snowdweller cards.
        gated += ["Victory (Snowdwellers)"] + with_seconds(["Challenge - Tough Nut", "Challenge - Toxic", "Challenge - Bigger Hitter"])
        self.assertIn("Challenge - One Punch", gated)
        self.assertIn("Challenge - Block 10 hits with Clunkers", gated)
        self.assertAccessDependency(gated, [["Snowdwellers"]])

    def test_clunkmaster_battles_need_nothing(self) -> None:
        for key, name, _, info in LOCATIONS:
            if key.startswith("battle:") and info["run_tribe"] == "Clunk" and not info["tribe"] and info["tier"] <= 4:
                with self.subTest(location=name):
                    self.assertTrue(self.can_reach_location(name))


class TestDefaults(WildfrostTestBase):
    """With no options set: one True Final Boss win, one extra bell, 10% traps (the user's call, 2026-11-02)."""

    options = {}

    def test_defaults(self) -> None:
        slot_data = self.world.fill_slot_data()
        self.assertEqual(slot_data["goal"], 1)
        self.assertEqual(slot_data["clans_required"], 1)
        self.assertEqual(slot_data["extra_storm_bells"], 1)
        self.assertEqual(self.world.options.trap_percentage.value, 10)
        self.assertEqual([i.name for i in self.multiworld.itempool].count(STORM_BELL), STORM_BELL_LEVELS + 1)
        self.assertTrue(TRUE_FINAL[0] in {loc.name for loc in self.multiworld.get_locations(self.player)})


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
    options = {**WildfrostTestBase.options, "goal": "true_final_boss_each_clan", "force_storm_bells": True}

    def check_matches(self) -> None:
        rules = self.world.fill_slot_data()["location_rules"]
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
        self.assertEqual([levels for levels, _ in kits], [5, 6, 7])
        # Force Storm Bells adds one more: a companion or item pack, or three charms.
        extra = {"extra": 1, "charms_per_pack": 3}
        self.assertEqual(kits[0][1], [{"Companion": 1, "Item": 1, "Charm": 0, **extra}, {"Companion": 1, "Item": 0, "Charm": 6, **extra}])
        self.assertEqual(kits[1][1], [{"Companion": 2, "Item": 2, "Charm": 3, **extra}])


class TestSecondChecks(BellTestBase):
    options = {**WildfrostTestBase.options, "goal": "true_final_boss_each_clan"}

    def test_seconds_share_their_first_rule(self) -> None:
        seconds = [name for _, name, _, info in LOCATIONS if info.get("second")]
        # Every boss (18) and every challenge that unlocks a charm in vanilla (26).
        self.assertEqual(len(seconds), 44)
        rules = self.world.fill_slot_data()["location_rules"]
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


class TestSunbringerPastWinGoal(WildfrostTestBase):
    def test_filler_only(self) -> None:
        self.assert_filler_only("Sunbringer", True)


class TestSunbringerIsTheGoal(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "goal": "true_final_boss_each_clan", "clans_required": 1}

    def test_filler_only(self) -> None:
        self.assert_filler_only("Sunbringer", True)


class TestSunbringerIsTheOvercrankedGoal(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "goal": "overcranked_each_clan", "clans_required": 1}

    def test_filler_only(self) -> None:
        self.assert_filler_only("Sunbringer", True)


class TestSunbringerCountsWithTwoClans(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "goal": "true_final_boss_each_clan", "clans_required": 2}

    def test_not_filler_only(self) -> None:
        self.assert_filler_only("Sunbringer", False)


class TestSunbringerCountsOvercrankedEachClan(WildfrostTestBase):
    options = {**WildfrostTestBase.options, "goal": "overcranked_each_clan"}

    def test_not_filler_only(self) -> None:
        self.assert_filler_only("Sunbringer", False)
