import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from .. import extensions
from ..extensions import ExtensionError, parse

HERE = Path(__file__).parent
SAMPLE = HERE / "extensions" / "SampleMod.wildfrost.json"


def sample() -> dict:
    return json.loads(SAMPLE.read_text())


def parsed(doc: dict) -> extensions.Extension:
    return parse("test.wildfrost.json", json.dumps(doc).encode())


class TestExtensionFile(unittest.TestCase):
    """The checks an extension file must pass to load (extensions.parse)."""

    def assert_refused(self, doc: dict, message: str) -> None:
        with self.assertRaises(ExtensionError) as caught:
            parsed(doc)
        self.assertIn(message, str(caught.exception))

    def test_sample_loads(self) -> None:
        ext = parsed(sample())
        self.assertEqual((ext.mod, ext.id_block, len(ext.items), len(ext.locations), len(ext.cards)), ("SampleMod", 0, 4, 8, 7))
        self.assertTrue(all(info["ext"] == "SampleMod" for _, _, _, info in ext.items + ext.locations))

    def test_wrong_format(self) -> None:
        self.assert_refused({**sample(), "format": 2}, "format should be 1")

    def test_id_outside_block(self) -> None:
        doc = sample()
        doc["ap_items"]["Pack"][0]["id"] = extensions.ID_BASE + extensions.BLOCK_SIZE  # the next block's first ID
        self.assert_refused(doc, "outside block 0")

    def test_battle_key_must_match(self) -> None:
        doc = sample()
        doc["ap_locations"]["battles"][0]["area"] = 2
        self.assert_refused(doc, "a battle's key")

    def test_pack_key_leads_with_clan_and_kind(self) -> None:
        doc = sample()
        doc["ap_items"]["Pack"][0]["key"] = "pack:SampleMod:Item:1"
        self.assert_refused(doc, "a pack has card_kind")

    def test_charm_needs_its_card(self) -> None:
        doc = sample()
        del doc["cards"]["charms"]
        self.assert_refused(doc, "a charm has a key")

    def test_unknown_rule_form(self) -> None:
        doc = sample()
        doc["ap_locations"]["challenges"][0]["rule"] = ["python", "import os"]
        self.assert_refused(doc, "a rule is a list starting with")

    def test_removes_names_base_game_content(self) -> None:
        self.assert_refused({**sample(), "removes": {"cards": ["NotACard"]}}, "doesn't have: NotACard")
        self.assert_refused({**sample(), "removes": {"tribes": ["Basic"]}}, "removes takes")

    def test_bosses_cant_be_removed(self) -> None:
        self.assert_refused({**sample(), "removes": {"battles": ["Final Boss"]}}, "can't be removed")
        self.assert_refused({**sample(), "removes": {"battles": ["Split Boss"]}}, "can't be removed")

    def test_cards_need_their_packs(self) -> None:
        doc = sample()
        doc["ap_items"]["Pack"] = [i for i in doc["ap_items"]["Pack"] if i["key"] != "pack:Basic:Companion:SampleMod-1"]
        self.assert_refused(doc, "no Basic Companion pack")

    def test_themed_pack_lists_its_own_cards(self) -> None:
        doc = sample()
        doc["ap_items"]["Pack"][-1]["cards"] = ["card:SampleHammer"]  # a General Item card in a Basic Companion pack
        self.assert_refused(doc, "lists this extension's Basic Companion cards")

    def test_cards_by_kind_and_clan(self) -> None:
        self.assert_refused({**sample(), "cards": {"weapons": {}}}, "cards has companions, items, charms")
        self.assert_refused({**sample(), "cards": {"items": {"Pirates": []}}}, "clans are General, Basic, Magic, Clunk")

    def test_items_by_kind(self) -> None:
        self.assert_refused({**sample(), "ap_items": {"Event": []}}, "an extension's items are Pack, Charm, Pet or Tribe")

    def test_new_challenges_keys_are_ours(self) -> None:
        doc = sample()
        doc["ap_locations"]["challenges"][0]["key"] = "challenge:ap:sample"
        self.assert_refused(doc, "this apworld's own New Challenges")

    def test_true_final_challenge(self) -> None:
        """A challenge can be the True Final Boss fight itself, like Sunbringer: its bells and kit (rules.area_kit)."""
        doc = sample()
        doc["ap_locations"]["challenges"][0]["true_final"] = True
        info = next(info for key, _, _, info in parsed(doc).locations if key == doc["ap_locations"]["challenges"][0]["key"])
        self.assertTrue(info["true_final"])
        doc["ap_locations"]["challenges"][0]["true_final"] = "yes"
        self.assert_refused(doc, "true_final")


class TestExtensionGeneration(unittest.TestCase):
    """
    Generation with the sample extension, in a process of its own (test/extension_check.py): extensions
    load when the apworld is imported, which has already happened in this one.
    """

    @classmethod
    def setUpClass(cls) -> None:
        import Utils
        env = {**os.environ, extensions.FOLDER_ENV: str(HERE / "extensions")}
        run = subprocess.run([sys.executable, str(HERE / "extension_check.py")], cwd=Utils.local_path(), env=env,
                             capture_output=True, text=True, timeout=600)
        lines = [line for line in run.stdout.splitlines() if line.startswith("RESULT ")]
        if not lines:
            raise AssertionError(f"extension_check.py printed no result:\n{run.stdout[-3000:]}\n{run.stderr[-3000:]}")
        cls.out = json.loads(lines[-1].removeprefix("RESULT "))

    def test_loaded(self) -> None:
        self.assertEqual(self.out["loaded"], ["BellMod", "OverflowMod", "RemoverMod", "SampleMod", "TribeMod"])
        self.assertEqual(self.out["failed"], {})

    def test_slot_with_the_mod(self) -> None:
        got = self.out["with"]
        self.assertEqual(len(got["locations"]), 7)
        self.assertEqual(got["items"], ["Sample Bog Charm", "SampleMod General Item Pack 1", "SampleMod Snowdweller Companion Pack 1",
                                        "SampleMod Troll Pack"])
        # The themed pack holds its card every seed.
        self.assertEqual(got["troll_pack"], ["card:SampleTroll"])
        # The mod's six cards are dealt into its own packs only.
        self.assertEqual(len(got["mod_cards_dealt"]), 6)
        self.assertEqual(got["mixed_packs"], [])
        self.assertEqual(got["excluded"], ["Challenge - Win with 3 Shrooms"])
        self.assertEqual(got["rule_hammer"][0], "has")
        self.assertTrue(got["bog_rule_has_tribe"])
        # ["applies", "SampleMod.Bog"]: the card that applies it (the Hammer's pack).
        self.assertEqual(got["applies_rule"], ["has", "pack:General:Item:SampleMod-1", 1])
        self.assertEqual([e["mod"] for e in got["extensions"]], ["SampleMod"])
        self.assertTrue(got["pool_fits"])
        self.assertTrue(got["beatable"])

    def test_slot_without_the_mod(self) -> None:
        got = self.out["without"]
        self.assertEqual((got["locations"], got["items"], got["mod_cards_dealt"], got["extensions"]), ([], [], [], []))

    def test_removals(self) -> None:
        got = self.out["remover"]
        # Removed: High Roller (a challenge), the Gunk Bugs (a battle), the Egg and Pinkberry Juice (cards),
        # so the challenges needing only them go too. Minimalist keeps Toaster, Apply 40 Ink the
        # Clunkmasters and Binku, though the Squid Charm is gone.
        # Its removed Gobbler Bell takes Kill 3 Gobblers with it.
        self.assertEqual(got["gone"], ["Area 3 Battle - The Gunk Bugs (Snowdwellers)", "Challenge - Berry Good",
                                       "Challenge - Don't break the Egg", "Challenge - High Roller",
                                       "Challenge - Kill 3 Gobblers"])
        self.assertEqual(got["kept"], ["Challenge - Apply 40 Ink", "Challenge - Minimalist"])
        self.assertEqual(got["cards_dealt"], [])
        self.assertFalse(got["squid_charm_in_pool"])
        self.assertTrue(got["pool_fits"])
        self.assertTrue(got["beatable"])
        self.assertEqual(len(self.out["without"]["kept"]), 3)

    def test_tribe(self) -> None:
        """An extension's tribe (the user's calls, 2026-11-16): an item, full battle checks, a Victory that counts."""
        got = self.out["tribe"]
        self.assertEqual(got["tribes"][-1], {"class": "TribeMod.Bogfolk", "name": "Bogfolk", "shares": "Basic"})
        self.assertEqual(got["clans_required"], 4)
        self.assertEqual(got["victories"], ["Victory (Bogfolk)", "Victory (Clunkmasters)", "Victory (Shademancers)",
                                            "Victory (Snowdwellers)"])
        # 22 battles and its Victory, 5 bosses' "#2": a Final Boss goal seed has no True Final Boss checks.
        self.assertEqual((got["battles"], got["twins"], got["tribe_item"]), (23, 5, 1))
        # Its runs draw from General, Snowdweller (shared) and its own packs: the client's ["packs", tribe, ...].
        self.assertIn('["all", ["tribe:TribeMod.Bogfolk"]]', json.dumps(got["boss_rule"]))
        self.assertIn('["packs", "TribeMod.Bogfolk", "Companion", 1]', json.dumps(got["boss_rule"]))
        self.assertEqual(got["win_challenge"], got["boss_rule"])
        self.assertEqual(got["bog_rule"], ["has", "tribe:TribeMod.Bogfolk", 1])  # its leader applies Bog
        # Snowdweller cards in logic with either tribe that draws from the Snowdweller pools.
        self.assertIn('["or", [["all", ["tribe:Basic"]], ["all", ["tribe:TribeMod.Bogfolk"]]]]', got["shell_rule"])
        # Its True Final Boss: left out of a Final Boss goal seed, and with the bells where it's in.
        self.assertFalse(got["true_final_battle"])
        self.assertIn('["has", "storm_bell", 5]', got["true_final_rule"])
        self.assertTrue(got["beatable"])
        self.assertTrue(got["pool_fits"])
        self.assertEqual(self.out["tribe_without"], {"clans_required": 3, "tribes": ["Basic", "Magic", "Clunk"],
                                                     "bogfolk": False})
        self.assertIn("Bogfolk", self.out["any_tribe_starts"])

    def test_tribe_file_checks(self) -> None:
        doc = json.loads((HERE / "extensions" / "TribeMod.wildfrost.json").read_text())
        doc["ap_items"]["Tribe"][0]["shares"] = "General"
        with self.assertRaises(ExtensionError):
            parsed(doc)
        doc["ap_items"]["Tribe"][0]["shares"] = "Basic"
        doc["leaders"] = {"Basic": []}
        with self.assertRaises(ExtensionError):
            parsed(doc)

    def test_storm_bells(self) -> None:
        got = self.out["bellmod"]
        self.assertEqual(self.out["vanilla_true_final_points"], 10)
        # 5 of the base game's points left plus the mod's 2: the Lumin Vase comes at 7, 4 bells in (5 in
        # the pool with the default Extra Storm Bell), and forcing stops at 6 (7, in steps of 2).
        self.assertEqual((got["true_final_points"], got["true_final_bells"], got["bells_in_pool"], got["force"]), (7, 4, 5, 6))
        self.assertEqual(got["gone"], ["Challenge - Apply 3 Cursed Crowns", "Challenge - Kill 3 Gobblers"])
        self.assertEqual(got["kept"], ["Challenge - Injure 3 companions", "Challenge - Ring the Troll Bell"])
        self.assertEqual(got["troll_rule"], ["has", "storm_bell", 1])
        self.assertTrue(got["beatable"])
        # Forcing: the 4th bell (8 storm points) passes the lowered threshold, so it takes the True Final
        # Boss kit (two companion and two item packs), not the 5th; the Overcranked kit moves down with it.
        self.assertEqual(got["bell_kits"], [[1, 1, 1], [3, 1, 1], [4, 2, 2], [6, 2, 3], [11, 2, 3]])

    def test_room_for_every_item(self) -> None:
        # OverflowMod: 150 packs and no checks. Every spare "#2" (challenges', then battles') isn't enough,
        # so its packs get fuller until the pool fits; New Challenges on has more spares (the charm
        # challenges' own "#2"s and the New Challenges'), so its packs stay fuller in number.
        off, on = self.out["overflow_off"], self.out["overflow_on"]
        self.assertEqual(off["spares"], off["spare_candidates"])
        self.assertLess(off["mod_packs"], 150)
        self.assertEqual(off["mod_cards_dealt"], 450)
        self.assertGreater(on["spares"], off["spares"])
        self.assertGreater(on["mod_packs"], off["mod_packs"])
        self.assertEqual(on["mod_cards_dealt"], 450)
        for got in (off, on):
            self.assertTrue(got["pool_fits"])
            self.assertTrue(got["beatable"])
            self.assertEqual(got["spares"], got["slot_data_spares"])
            self.assertTrue(got["rebuild_same"])

    def test_mod_not_installed(self) -> None:
        self.assertIn("needs its extension file (NotInstalled.wildfrost.json)", self.out["unknown_mod"])

    def test_universal_tracker_checks_the_file(self) -> None:
        self.assertEqual(self.out["rebuild_same"], ["SampleMod"])
        self.assertIn("this seed used SampleMod 0.9.0", self.out["rebuild_other"])


class TestBaseFile(unittest.TestCase):
    """base.wildfrost.json's hand-written rules pass the checks an extension's do (PLAN.md §10, phase 2)."""

    def test_rules_are_valid(self) -> None:
        from .. import content, data
        base = extensions.Extension(mod="Wildfrost", guid="", version="", id_block=0, path=data.BASE_FILE, hash="",
                                    locations=list(data.LOCATIONS))
        ruled = [(key, info["rule"]) for key, _, _, info in data.LOCATIONS if info.get("rule")]
        self.assertGreater(len(ruled), 40)
        for key, rule in ruled:
            with self.subTest(location=key):
                extensions.check_rule(rule, key)
        content._check_references(base)  # raises on an unknown item, card, group, bell or battle

    def test_bom_needs_a_bom_source(self) -> None:
        # Only Clunkmaster leaders apply Bom ("Weakness"): Apply 40 Bom takes them or a card that does
        # (the user's catch, 2026-11-15; it used to take the Snowdwellers too).
        from .. import data
        rule = next(info["rule"] for key, _, _, info in data.LOCATIONS if key == "challenge:ap:bom")
        self.assertEqual(rule, ["applies", "Weakness"])

    def test_every_challenge_has_a_region(self) -> None:
        from .. import data
        for key, _, _, info in data.LOCATIONS:
            if key.startswith("challenge:"):
                with self.subTest(location=key):
                    self.assertIn(info.get("region"), extensions.REGIONS)
