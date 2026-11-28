import json
import os
import subprocess
import tempfile
import sys
import unittest
from unittest import mock
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
        self.assertEqual((ext.mod, ext.id_block, len(ext.items), len(ext.locations), len(ext.cards)), ("SampleMod", extensions.block_for("test.wildfrost.samplemod"), 4, 8, 7))
        self.assertTrue(all(info["ext"] == "SampleMod" for _, _, _, info in ext.items + ext.locations))

    def test_wrong_format(self) -> None:
        self.assert_refused({**sample(), "format": 2}, "format should be 1")

    def test_id_outside_block(self) -> None:
        doc = sample()
        low = extensions.ID_BASE + doc["id_block"] * extensions.BLOCK_SIZE
        doc["ap_items"]["Pack"][0]["id"] = low + extensions.BLOCK_SIZE  # the next block's first ID
        self.assert_refused(doc, f"outside block {doc['id_block']}")

    def test_retired_ids(self) -> None:
        """Retired IDs (keys the mod no longer has) are kept in the file and never used again (review, 2026-11-24)."""
        doc = sample()
        pack = doc["ap_items"]["Pack"][0]
        parsed({**doc, "retired": {"items": {"pack:Gone": pack["id"] + 500}}})
        self.assert_refused({**doc, "retired": {"items": {"pack:Gone": pack["id"]}}}, "in use again")
        self.assert_refused({**doc, "retired": {"items": {"pack:Gone": 5}}}, "outside block")
        self.assert_refused({**doc, "retired": {"things": {}}}, "retired has items and locations")
        self.assert_refused({**doc, "retired": {"items": {"a": pack["id"] + 500, "b": pack["id"] + 500}}}, "two keys")

    def test_block_comes_from_guid(self) -> None:
        """The block is the GUID's hash (the user's call, 2026-11-24): a file can't pick another."""
        self.assert_refused({**sample(), "id_block": sample()["id_block"] + 1}, "id_block should be")
        self.assert_refused({**sample(), "guid": "someone.else"}, "the block of guid someone.else")
        self.assert_refused({**sample(), "id_salt": -1}, "id_salt should be")
        self.assert_refused({**sample(), "id_salt": True}, "id_salt should be")

    def test_salt_moves_the_block(self) -> None:
        """Raising id_salt gives a new block, which a file with its IDs moved there loads with."""
        doc = sample()
        old, new = doc["id_block"], extensions.block_for(doc["guid"], 1)
        self.assertNotEqual(old, new)
        self.assertEqual(extensions.block_for(doc["guid"], 0), old)
        shift = (new - old) * extensions.BLOCK_SIZE
        for row in [r for rows in doc["ap_items"].values() for r in rows] + \
                [r for k, rows in doc["ap_locations"].items() if isinstance(rows, list) for r in rows]:
            row["id"] += shift
        for k in ("twins", "spares"):
            doc["ap_locations"][k] = {key: i + shift for key, i in doc["ap_locations"].get(k, {}).items()}
        self.assert_refused({**doc, "id_block": new}, "id_block should be")  # no salt: still the old block
        ext = parsed({**doc, "id_block": new, "id_salt": 1})
        self.assertEqual(ext.id_block, new)

    def test_block_from_guid_and_salt(self) -> None:
        """Files don't list their ID block (the user's call, 2026-11-25): it comes from the GUID and salt."""
        doc = sample()
        block = doc.pop("id_block")
        self.assertEqual(parsed(doc).id_block, block)
        self.assert_refused({**doc, "id_salt": 1}, f"outside block {extensions.block_for(doc['guid'], 1)}")

    def test_duplicates_within_a_file(self) -> None:
        """Two rows of one file with the same ID or name are refused (found in review, 2026-11-24)."""
        for field in ("id", "name"):
            doc = sample()
            packs = doc["ap_items"]["Pack"]
            packs[1][field] = packs[0][field]
            with tempfile.TemporaryDirectory() as folder:
                path = os.path.join(folder, "Dup.wildfrost.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(doc, f)
                loaded, failed = extensions.load([path])
            with self.subTest(field=field):
                self.assertEqual(loaded, {})
                self.assertIn("in this file", failed["SampleMod"])

    def test_block_clash_names_the_fix(self) -> None:
        """Two files on one block (here: one GUID, two names) load the first and refuse the second."""
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            paths = []
            for name in ("SampleA", "SampleB"):
                path = os.path.join(folder, f"{name}.wildfrost.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({**sample(), "mod": name}, f)
                paths.append(path)
            loaded, failed = extensions.load(paths)
        self.assertEqual(list(loaded), ["SampleA"])
        self.assertIn("raises its id_salt", failed["SampleB"])

    def load_with_built_in(self, built_in: dict, loose: list[dict]) -> tuple[dict, dict]:
        """Loads one built-in file (as if inside the apworld) and the given loose files."""
        with tempfile.TemporaryDirectory() as folder:
            paths = []
            for n, doc in enumerate(loose):
                path = os.path.join(folder, f"Loose{n}.wildfrost.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(doc, f)
                paths.append(path)
            official = [("official/SampleMod.wildfrost.json", json.dumps(built_in).encode())]
            return extensions.load(paths, official)

    def test_newer_version_wins(self) -> None:
        """A loose file of a built-in mod is used when its version is higher; otherwise the built-in one is
        (the user's call, 2026-11-24: a player can fix a broken built-in file)."""
        for built_in, loose, winner in (("1.0.0", "1.0.1", "Loose0"), ("1.2.0", "1.10.0", "Loose0"),
                                        ("1.0.1", "1.0.0", "official"), ("1.0.0", "1.0.0", "official")):
            with self.subTest(built_in=built_in, loose=loose):
                loaded, failed = self.load_with_built_in({**sample(), "version": built_in},
                                                         [{**sample(), "version": loose}])
                self.assertEqual(failed, {})
                self.assertIn(winner, loaded["SampleMod"].path)

    def test_broken_newer_falls_back(self) -> None:
        """A newer loose file that fails to read leaves the built-in one in use; its error is filed under the
        file's name, not the mod's (so a yaml asking for the mod still works)."""
        loaded, failed = self.load_with_built_in(sample(), [{**sample(), "version": "9.0.0", "format": 2}])
        self.assertIn("official", loaded["SampleMod"].path)
        self.assertEqual(list(failed), ["Loose0"])

    def test_two_loose_copies_still_clash(self) -> None:
        """Without a built-in file, two loose files of one mod are refused as before: the second is filed under
        its file name, since the mod itself loaded."""
        with tempfile.TemporaryDirectory() as folder:
            paths = []
            for n in range(2):
                path = os.path.join(folder, f"Copy{n}.wildfrost.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({**sample(), "version": f"1.0.{n}"}, f)
                paths.append(path)
            loaded, failed = extensions.load(paths)
        self.assertIn("Copy0", loaded["SampleMod"].path)
        self.assertNotIn("SampleMod", failed)
        self.assertIn("already loaded mod", failed["Copy1.wildfrost.json"])

    def test_version_key(self) -> None:
        self.assertGreater(extensions.version_key("1.10"), extensions.version_key("1.9"))
        self.assertGreater(extensions.version_key("1.0.1"), extensions.version_key("1.0"))
        self.assertLess(extensions.version_key("beta"), extensions.version_key("0.1"))

    def test_battle_key_must_match(self) -> None:
        doc = sample()
        doc["ap_locations"]["battles"][0]["area"] = 2
        self.assert_refused(doc, "should match the key")

    # Short battle rows (the user's calls, 2026-11-25): only the key and ID are needed, the rest is worked out.
    def test_short_rows_load_the_same(self) -> None:
        doc = json.loads((HERE / "extensions" / "TribeMod.wildfrost.json").read_text())
        full = parsed(doc).locations
        for row in doc["ap_locations"]["battles"]:
            if row["key"].split(":")[2] in extensions.BASE_BATTLES:
                for field in list(row):
                    if field not in ("key", "id"):
                        del row[field]
        self.assertEqual(parsed(doc).locations, full)

    def test_own_battle_short_row(self) -> None:
        doc = sample()
        full = parsed(doc).locations[0]
        doc["ap_locations"]["battles"][0] = {"key": "battle:1:SampleTrolls:Basic", "id": full[2],
                                             "title": "The Sample Trolls", "tier": 4}
        self.assertEqual(parsed(doc).locations[0], full)

    def test_own_battle_needs_tier_and_title(self) -> None:
        doc = sample()
        del doc["ap_locations"]["battles"][0]["tier"]
        self.assert_refused(doc, "needed for a battle of the mod's own")
        doc = sample()
        del doc["ap_locations"]["battles"][0]["name"]
        self.assert_refused(doc, "needs a name or a title")

    def test_listed_name_wins(self) -> None:
        doc = sample()
        doc["ap_locations"]["battles"][0]["name"] = "Trolls, but renamed"
        self.assertEqual(parsed(doc).locations[0][1], "Trolls, but renamed")

    def test_renaming_a_tribe_renames_its_battles(self) -> None:
        doc = json.loads((HERE / "extensions" / "TribeMod.wildfrost.json").read_text())
        for row in doc["ap_locations"]["battles"]:
            if row["key"].split(":")[2] in extensions.BASE_BATTLES:
                row.pop("name", None)
        for tribe in doc["ap_items"]["Tribe"]:
            tribe["name"] = "Marshfolk"
        # The Abyss, the mod's own battle, keeps its written name: a listed name wins.
        names = [name for key, name, _, _ in parsed(doc).locations
                 if key.endswith(":TribeMod.Bogfolk") and key.split(":")[2] in extensions.BASE_BATTLES]
        self.assertTrue(names)
        self.assertTrue(all(name.endswith("(Marshfolk)") for name in names), names)

    # Short pack and charm rows (the user's call, 2026-11-25): the key holds the clan, kind and card.
    def test_short_item_rows_load_the_same(self) -> None:
        for name in ("SampleMod", "TribeMod", "OverflowMod"):
            doc = json.loads((HERE / "extensions" / f"{name}.wildfrost.json").read_text())
            full = parsed(doc).items
            for kind in ("Pack", "Charm"):
                for row in doc["ap_items"].get(kind, []):
                    numbered = row["key"].rsplit("-", 1)[-1].isdigit()
                    for field in list(row):
                        if field not in ("key", "id", "cards") and (field != "name" or kind == "Charm" or numbered):
                            del row[field]
            with self.subTest(extension=name):
                self.assertEqual(parsed(doc).items, full)

    def test_unnumbered_pack_needs_a_name(self) -> None:
        doc = sample()
        troll = next(r for r in doc["ap_items"]["Pack"] if not r["key"][-1].isdigit())
        del troll["name"]
        self.assert_refused(doc, "needs a name")

    def test_listed_fields_must_match_the_key(self) -> None:
        doc = sample()
        doc["ap_items"]["Pack"][0]["clan"] = "Magic"
        self.assert_refused(doc, "the one in its key")
        doc = sample()
        charm = doc["ap_items"]["Charm"][0]
        charm["card"] = "card:SomethingElse"
        self.assert_refused(doc, "a charm has a key")

    def test_renaming_a_tribe_renames_its_packs(self) -> None:
        doc = json.loads((HERE / "extensions" / "TribeMod.wildfrost.json").read_text())
        for row in doc["ap_items"]["Pack"]:
            row.pop("name", None)
        doc["ap_items"]["Tribe"][0]["name"] = "Marshfolk"
        names = [name for key, name, _, info in parsed(doc).items if info["kind"] == "Pack"]
        self.assertEqual(names[0], "TribeMod Marshfolk Companion Pack 1")

    def test_true_final_only_on_the_true_final_boss(self) -> None:
        """Review fix, 2026-11-25: a mod tribe's row of a base game battle may say true_final only for the True Final
        Boss fight."""
        doc = json.loads((HERE / "extensions" / "TribeMod.wildfrost.json").read_text())
        row = next(r for r in doc["ap_locations"]["battles"] if r["key"] == "battle:0:Snowbos:TribeMod.Bogfolk")
        row["true_final"] = True
        self.assert_refused(doc, "true_final")
        doc = json.loads((HERE / "extensions" / "TribeMod.wildfrost.json").read_text())
        row = next(r for r in doc["ap_locations"]["battles"] if r["key"] == "battle:2:Final Final Boss:TribeMod.Bogfolk")
        row["true_final"] = False
        self.assert_refused(doc, "true_final")

    def test_old_tribe_lock_ignored(self) -> None:
        doc = sample()
        doc["ap_locations"]["battles"][0]["tribe"] = "Clunk"
        self.assertNotIn("tribe", parsed(doc).locations[0][3])

    def test_pack_key_leads_with_clan_and_kind(self) -> None:
        doc = sample()
        doc["ap_items"]["Pack"][0]["key"] = "pack:SampleMod:Item:1"
        self.assert_refused(doc, "the one in its key")

    def test_charm_needs_its_card(self) -> None:
        doc = sample()
        del doc["cards"]["charms"]
        self.assert_refused(doc, "a charm has a key")

    def test_unknown_rule_form(self) -> None:
        doc = sample()
        doc["ap_locations"]["challenges"][0]["rule"] = ["python", "import os"]
        self.assert_refused(doc, "a rule is a list starting with")

    def test_rule_counts(self) -> None:
        """"has" and "any" counts are 1 or more, and "any" asks no more than its list holds (review, 2026-11-24)."""
        for rule in (["has", "pack:x", 0], ["has", "pack:x", True], ["any", ["pack:x"], 2], ["any", ["pack:x"], 0]):
            doc = sample()
            doc["ap_locations"]["challenges"][0]["rule"] = rule
            with self.subTest(rule=rule):
                self.assert_refused(doc, "count")

    def test_file_size_cap(self) -> None:
        raw = json.dumps(sample()).encode()
        with self.assertRaises(ExtensionError) as caught:
            parse("test.wildfrost.json", raw + b" " * (extensions.MAX_FILE_BYTES - len(raw) + 1))
        self.assertIn("over 5 MB", str(caught.exception))

    def test_json_nested_too_deep(self) -> None:
        with self.assertRaises(ExtensionError) as caught:
            parse("test.wildfrost.json", b"[" * 100_000 + b"]" * 100_000)
        self.assertIn("nested too deep", str(caught.exception))

    def test_rule_depth_cap(self) -> None:
        def nested(depth: int) -> list:
            rule = ["has", "pack:General:Item:1", 1]
            for _ in range(depth - 1):
                rule = ["and", [rule]]
            return rule
        doc = sample()
        doc["ap_locations"]["challenges"][0]["rule"] = nested(extensions.MAX_RULE_DEPTH)
        parsed(doc)
        doc["ap_locations"]["challenges"][0]["rule"] = nested(extensions.MAX_RULE_DEPTH + 1)
        self.assert_refused(doc, f"rules nest more than {extensions.MAX_RULE_DEPTH} deep")

    def test_removes_names_base_game_content(self) -> None:
        self.assert_refused({**sample(), "removes": {"cards": ["NotACard"]}}, "doesn't have: NotACard")
        self.assert_refused({**sample(), "removes": {"tribes": ["Basic"]}}, "removes takes")

    def test_each_boss_tier_keeps_a_boss(self) -> None:
        """The user's call, 2026-11-26: bosses may go as long as every boss tier keeps one, a base one or the mod's."""
        self.assertEqual(parsed({**sample(), "removes": {"battles": ["Split Boss"]}}).removes["battles"], {"Split Boss"})
        self.assert_refused({**sample(), "removes": {"battles": ["Split Boss", "Frenzy Boss"]}}, "every boss of map tier 2")
        self.assert_refused({**sample(), "removes": {"battles": ["Final Boss"]}}, "every boss of map tier 7")
        # TribeMod's own tier 8 fight, The Abyss, can stand in for the base game's True Final Boss.
        tribe_mod = json.loads((HERE / "extensions" / "TribeMod.wildfrost.json").read_text())
        self.assertEqual(parsed({**tribe_mod, "removes": {"battles": ["Final Final Boss"]}}).removes["battles"],
                         {"Final Final Boss"})
        self.assert_refused({**sample(), "removes": {"battles": ["Final Final Boss"]}}, "every boss of map tier 8")

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

    def test_own_true_final_battle(self) -> None:
        """A battle of the extension's own in the True Final Boss's tier must be flagged, and only there (2026-11-24)."""
        doc = sample()
        row = doc["ap_locations"]["battles"][0]
        row["true_final"] = True
        self.assert_refused(doc, "only a battle of its own in tier 8")
        row.update({"key": row["key"].replace("battle:1:", "battle:2:"), "area": 2, "tier": 8, "boss": True})
        del row["true_final"]
        self.assert_refused(doc, "is a True Final Boss fight")
        row["true_final"] = True
        info = next(info for key, _, _, info in parsed(doc).locations if key == row["key"])
        self.assertTrue(info["true_final"])

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
        self.assertEqual(self.out["loaded"], ["BellMod", "OverflowMod", "PoolMod", "RemoverMod", "SampleMod", "TribeMod"])
        self.assertEqual(self.out["failed"], {})

    def test_built_in_files_load(self) -> None:
        """Every file in OFFICIAL_DIR (Companion Start, 2026-11-28) loads with the test files beside it."""
        names = [where for where, _ in extensions.official_files()]
        self.assertEqual(sorted(self.out["built_in"]), sorted(names))

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
        self.assertEqual(got["loki"], [False, False, False])
        self.assertTrue(got["pool_fits"])
        self.assertTrue(got["beatable"])
        self.assertEqual(len(self.out["without"]["kept"]), 3)

    def test_starts_with(self) -> None:
        """["starts_with", card]: a run of a tribe whose starting deck has it (the user's call, 2026-11-24)."""
        got = self.out["tribe"]
        self.assertIn("Bogfolk", got["starts_with"])
        self.assertIn("Bogfolk", got["starts_with_kit"])
        self.assertEqual(got["starts_with_none"], "impossible")

    def test_start_decks_only_own_tribes(self) -> None:
        doc = sample()
        doc["start_decks"] = {"Basic": ["Sword"]}
        with self.assertRaises(ExtensionError) as caught:
            parsed(doc)
        self.assertIn("own tribes", str(caught.exception))

    def test_modded_only(self) -> None:
        """Tribes: Modded Only (the user's call, 2026-11-24): the mod's tribes alone, even when Starting Tribe names
        a vanilla one; no vanilla tribe items or battle checks, and no challenge that needs a vanilla tribe."""
        got = self.out["modded_only"]
        self.assertEqual((got["tribes"], got["starting"], got["clans_required"]), (["TribeMod.Bogfolk"], "Bogfolk", 1))
        self.assertEqual((got["vanilla_items"], got["vanilla_battles"]), ([], 0))
        # Bogfolk shares the Snowdweller pools: no Shademancer or Clunkmaster packs or charms (no tribe draws them).
        self.assertEqual(got["pool_clans"], ["Basic", "General", "TribeMod.Bogfolk"])
        # All 24 of its rows but the True Final Boss, which this seed's goal doesn't reach. Before 2026-11-25 six
        # more were left out, locked behind the Shademancers or Clunkmasters; there are no battle locks now.
        self.assertEqual(got["bogfolk_battles"], 23)
        self.assertEqual(got["victories"], ["Victory (Bogfolk)"])
        self.assertGreater(got["vanilla_tribe_challenges"], 0)
        self.assertEqual(got["tribe_challenges"], [])
        self.assertEqual(got["selection"], 2)
        self.assertTrue(got["pool_fits"])
        self.assertTrue(got["beatable"])
        self.assertTrue(got["rebuild_same"])

    def test_vanilla_only(self) -> None:
        """Tribes: Vanilla Only keeps a mod's content but not its tribe, nor what needs that tribe or its cards (Bog
        is only applied by Bogfolk cards, which no vanilla tribe draws)."""
        got = self.out["vanilla_only"]
        self.assertEqual(got["tribes"], ["Basic", "Magic", "Clunk"])
        self.assertIn(got["starting"], ("Snowdwellers", "Shademancers", "Clunkmasters"))
        self.assertEqual(got["bogfolk"], 0)
        self.assertEqual(got["mod_challenges"], [])
        self.assertTrue(got["beatable"])

    def test_modded_clans(self) -> None:
        """Modded Clans (the user's call, 2026-11-27): half or a quarter of each mod's tribes, rounded up, picked at
        random; the vanilla three stay, and the left-out ones go to the client."""
        for label in ("half", "quarter"):
            got = self.out["modded_clans_" + label]
            pool = [t for t in got["tribes"] if t.startswith("PoolMod.")]
            self.assertEqual(got["tribes"][:3], ["Basic", "Magic", "Clunk"])
            self.assertEqual(len(pool), 1)
            self.assertIn("TribeMod.Bogfolk", got["tribes"])
            self.assertEqual(len(got["tribes"]), 5)
            self.assertEqual(got["left_out"], sorted({"PoolMod.Frost", "PoolMod.Ember"} - set(pool)))
            self.assertEqual(got["clans_required"], 5)
            self.assertTrue(got["beatable"])
            self.assertTrue(got["pool_fits"])
            self.assertTrue(got["rebuild_same"])
        self.assertEqual(self.out["modded_clans_picks"], ["PoolMod.Ember", "PoolMod.Frost"])

    def test_modded_only_needs_mod_tribes(self) -> None:
        self.assertIn("adds no tribes", self.out["modded_only_no_tribes"] or "")

    def test_shared_pool_clan(self) -> None:
        """Tribes drawing a mod's shared pool and not General (the user's calls, 2026-11-27): the pool's packs are
        items, General's aren't (nothing in the seed draws them), and logic counts only what the tribes draw."""
        got = self.out["pool"]
        self.assertEqual(sorted(got["tribes"], key=lambda t: t["class"]), [
            {"class": "PoolMod.Ember", "name": "Ember", "shares": ["test.wildfrost.poolmod.pool.Enemy"], "general": False},
            {"class": "PoolMod.Frost", "name": "Frost", "shares": ["test.wildfrost.poolmod.pool.Enemy"], "general": False}])
        self.assertEqual(got["reuses"], {"PoolMod.Frost": ["CardUpgradeSpice", "Peppering", "Yuki"]})
        # A Snowdweller pack holding one of Frost's reused cards counts as that share of a pack; whole Enemy packs as 1.
        for kind in ("Item", "Companion"):
            self.assertEqual(got[kind]["weight"], f"1/{got[kind]['size']}" if got[kind]["size"] > 1 else "1")
            self.assertEqual(got[kind]["enemy"], ["1", "1"])
            self.assertEqual(got[kind]["other_snowdweller"], 0)
        self.assertEqual(got["charms"], ["Enemy Charm", "Spice Charm"])
        self.assertEqual(got["ember_charms"], ["Enemy Charm"])
        # Two whole Enemy item packs aren't three packs' worth; a third of a Snowdweller pack doesn't make it either.
        self.assertFalse(got["two_enemy_packs"])
        self.assertFalse(got["plus_pepper_pack"])
        self.assertEqual(got["pool_clans"], {"test.wildfrost.poolmod.pool.Enemy": "Enemy"})
        self.assertEqual(got["enemy_packs"], ["PoolMod Enemy Companion Pack 1", "PoolMod Enemy Companion Pack 2",
                                              "PoolMod Enemy Item Pack 1", "PoolMod Enemy Item Pack 2"])
        self.assertEqual(got["frost_pack"], ["PoolMod Frost Companion Pack 1"])
        self.assertEqual(got["general_items"], [])
        self.assertGreater(got["snowdweller_packs"], 0)
        self.assertEqual(got["clunk_packs"], 0)
        self.assertIn('["packs", "PoolMod.Frost", "Companion", 1]', got["boss_rule"])
        self.assertEqual(got["frost_packs"], ["Enemy Charm", "PoolMod Enemy Companion Pack 1", "PoolMod Enemy Companion Pack 2",
                                              "PoolMod Enemy Item Pack 1", "PoolMod Enemy Item Pack 2",
                                              "PoolMod Frost Companion Pack 1"])
        self.assertTrue(got["beatable"])
        self.assertTrue(got["pool_fits"])

    def test_tribe(self) -> None:
        """An extension's tribe (the user's calls, 2026-11-16): an item, full battle checks, a Victory that counts."""
        got = self.out["tribe"]
        self.assertEqual(got["tribes"][-1], {"class": "TribeMod.Bogfolk", "name": "Bogfolk", "shares": ["Basic"]})
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
        # Its own tier 8 battle, The Abyss, likewise: no checks in a Final Boss goal seed, the bells where it's in.
        self.assertEqual(got["own_true_final"], [])
        self.assertEqual(sorted(got["own_true_final_rules"]),
                         sorted([f"battle:2:TribeMod.Abyss:{t}" for t in ("Basic", "Magic", "Clunk", "TribeMod.Bogfolk")]))
        # No twin: a tribe's battles leave this seed room to spare, so the bosses' "#2"s are dropped (2026-11-25).
        for rule in got["own_true_final_rules"].values():
            self.assertIn('["has", "storm_bell", 5]', rule)
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


def run_with_extensions(files: dict[str, dict], code: str) -> dict:
    """Runs code in a process of its own whose extensions are these files; it prints RESULT <json>."""
    import tempfile
    import Utils
    with tempfile.TemporaryDirectory() as folder:
        for name, doc in files.items():
            with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
                f.write(doc if isinstance(doc, str) else json.dumps(doc))
        prelude = "import json, sys\nsys.path.insert(0, '.')\nimport worlds\n"
        run = subprocess.run([sys.executable, "-c", prelude + code], cwd=Utils.local_path(),
                             env={**os.environ, extensions.FOLDER_ENV: folder}, capture_output=True, text=True, timeout=600)
    lines = [line for line in run.stdout.splitlines() if line.startswith("RESULT ")]
    if not lines:
        raise AssertionError(f"no result:\n{run.stdout[-3000:]}\n{run.stderr[-3000:]}")
    return json.loads(lines[-1].removeprefix("RESULT "))


class TestFilesInOwnProcess(unittest.TestCase):
    """Cases that need their own set of installed files (review fixes, 2026-11-24)."""

    def test_two_mods_cant_empty_a_boss_tier(self) -> None:
        """Each file keeps a boss in every tier, but two together can't take a tier's last one (2026-11-26)."""
        one = {**sample(), "removes": {"battles": ["Split Boss"]}}
        other = json.loads((HERE / "extensions" / "RemoverMod.wildfrost.json").read_text())
        other.setdefault("removes", {}).setdefault("battles", []).append("Frenzy Boss")
        got = run_with_extensions(
            {"SampleMod.wildfrost.json": one, "RemoverMod.wildfrost.json": other},
            "from Options import OptionError\n"
            "from test.general import gen_steps, setup_multiworld\n"
            "from worlds.wildfrost.world import WildfrostWorld\n"
            "try:\n"
            "    setup_multiworld(WildfrostWorld, gen_steps, seed=1, options={'mod_content': ['SampleMod', 'RemoverMod']})\n"
            "    out = 'generated'\n"
            "except OptionError as e:\n"
            "    out = str(e)\n"
            "print('RESULT ' + json.dumps(out))")
        self.assertIn("removes every boss of map tier 2", got)

    def test_rules_naming_items(self) -> None:
        """Review fix, 2026-11-25: a rule naming a pet or a map event makes it progression, so the check can be reached;
        one naming an item this slot's pool doesn't have (here a tribe Modded Only leaves out) drops its challenge."""
        doc = sample()
        rules = [["has", "pet:Wolfie", 1], ["has", "event:CampaignNodeCopyItem", 1], ["has", "tribe:Magic", 1],
                 ["any", ["tribe:Magic", "pet:Wolfie"], 1]]
        for challenge, rule in zip(doc["ap_locations"]["challenges"], rules):
            challenge["rule"] = rule
        names = [c["name"] for c in doc["ap_locations"]["challenges"]]
        tribe_mod = json.loads((HERE / "extensions" / "TribeMod.wildfrost.json").read_text())
        got = run_with_extensions(
            {"SampleMod.wildfrost.json": doc, "TribeMod.wildfrost.json": tribe_mod},
            "from BaseClasses import CollectionState\n"
            "from Fill import distribute_items_restrictive\n"
            "from test.general import gen_steps, setup_multiworld\n"
            "from worlds.AutoWorld import call_all\n"
            "from worlds.wildfrost.items import create_item\n"
            "from worlds.wildfrost.world import WildfrostWorld\n"
            "out = {}\n"
            "for nc in (False, True):\n"
            "    mw = setup_multiworld(WildfrostWorld, gen_steps, seed=4, options={'mod_content': ['SampleMod', 'TribeMod'],\n"
            "        'tribes': 'modded_only', 'new_challenges': nc, 'goal': 'final_boss'})\n"
            "    distribute_items_restrictive(mw); call_all(mw, 'post_fill')\n"
            "    state = CollectionState(mw); state.sweep_for_advancements()\n"
            "    w = mw.worlds[1]\n"
            "    out[str(nc)] = {'names': sorted(l.name for l in mw.get_locations(1)),\n"
            "        'unreachable': [l.name for l in mw.get_locations(1) if not l.can_reach(state)],\n"
            "        'progression': [n for n in ('Snoof Pet', 'Shade Sculptor') if create_item(w, n).advancement]}\n"
            "print('RESULT ' + json.dumps(out))")
        for nc, case in got.items():
            with self.subTest(new_challenges=nc):
                self.assertEqual(case["unreachable"], [])
                self.assertEqual(case["progression"], ["Snoof Pet", "Shade Sculptor"])
                self.assertIn(names[0], case["names"])
                self.assertIn(names[1], case["names"])
                self.assertNotIn(names[2], case["names"])  # needs the Shademancers, which Modded Only leaves out
                self.assertIn(names[3], case["names"])  # the pet alternative is still there

    def test_malformed_files_fail_alone(self) -> None:
        """A file of the wrong shape is left out with an error; the apworld still imports."""
        pack_string = sample()
        pack_string["ap_items"]["Pack"][0] = "pack"
        themed_dict = sample()
        themed_dict["ap_items"]["Pack"][-1]["cards"] = [{"card": 1}]
        bad_clans = sample()
        bad_clans["ap_locations"]["challenges"][0]["rule"] = ["any_card", "trolls", [[1]]]
        got = run_with_extensions(
            {"A.wildfrost.json": pack_string, "B.wildfrost.json": themed_dict, "C.wildfrost.json": bad_clans,
             "D.wildfrost.json": "[1, 2"},
            "from worlds.wildfrost import extensions\n"
            "print('RESULT ' + json.dumps({'loaded': [n for n, e in extensions.LOADED.items() if not e.path.startswith(extensions.OFFICIAL_DIR)], 'failed': extensions.FAILED}))")
        self.assertEqual(got["loaded"], [])
        self.assertEqual(sorted(got["failed"]), ["A", "B", "C", "D"])
        self.assertIn("should be an object", got["failed"]["A"])

    def test_rules_cant_name_another_files_group(self) -> None:
        """
        A rule may name the base game's groups and its file's own, not a group another file made; and two files
        can't make the same new group (found in review, 2026-11-24: both depended on which file loaded first).
        """
        guid = "test.wildfrost.groupreader"

        def reader(mod: str, rule=None, groups=None) -> dict:
            g = f"{guid}.{mod.lower()}"
            low = extensions.ID_BASE + extensions.block_for(g) * extensions.BLOCK_SIZE
            return {"format": 1, "mod": mod, "guid": g, "version": "1.0.0", "id_block": extensions.block_for(g),
                    "groups": groups or {}, "ap_locations": {"challenges": [
                        {"key": f"challenge:{g}.Read", "name": f"Challenge - {mod} read", "id": low, "region": "Area 1",
                         "rule": rule}]}}
        got = run_with_extensions(
            {"A.wildfrost.json": sample(),  # makes the group "applies:Bog"
             "B.wildfrost.json": reader("Reader", ["two_of", "applies:Bog"]),
             "C.wildfrost.json": reader("Maker", None, {"applies:Bog": ["tribe:Clunk"]})},
            "from worlds.wildfrost import content, extensions\n"
            "print('RESULT ' + json.dumps({'loaded': sorted(n for n, e in extensions.LOADED.items() if not e.path.startswith(extensions.OFFICIAL_DIR)), 'failed': extensions.FAILED}))")
        self.assertEqual(got["loaded"], ["SampleMod"])
        self.assertIn("unknown group 'applies:Bog'", got["failed"]["Reader"])
        self.assertIn("is already SampleMod's", got["failed"]["Maker"])

    def test_tribe_without_own_charms(self) -> None:
        """
        A tribe with no charms of its own has exactly Basic's charm set: Basic's charm rules still go to the client
        as Basic's, in a vanilla slot too (found in review: the tribe's name had taken them over).
        """
        tribe = json.loads((HERE / "extensions" / "TribeMod.wildfrost.json").read_text())
        del tribe["cards"]["charms"]
        del tribe["ap_items"]["Charm"]
        got = run_with_extensions(
            {"TribeMod.wildfrost.json": tribe},
            "from worlds.wildfrost import extensions\n"
            "from worlds.wildfrost.rules import PACK_GROUPS, clan_packs\n"
            "from test.general import gen_steps, setup_multiworld\n"
            "from worlds.wildfrost.world import WildfrostWorld, read_location_rules\n"
            "mw = setup_multiworld(WildfrostWorld, gen_steps, seed=3, options={'starting_tribe': 'snowdwellers'})\n"
            "rules = json.dumps(read_location_rules(mw.worlds[1].fill_slot_data()['location_rules']))\n"
            "print('RESULT ' + json.dumps({'loaded': [n for n, e in extensions.LOADED.items() if not e.path.startswith(extensions.OFFICIAL_DIR)], 'failed': extensions.FAILED,\n"
            "    'basic': PACK_GROUPS[frozenset(clan_packs('Basic', 'Charm'))],\n"
            "    'tribe_in_rules': 'TribeMod.Bogfolk' in rules, 'basic_charm_rules': '\"Basic\", \"Charm\"' in rules}))")
        self.assertEqual((got["loaded"], got["failed"]), (["TribeMod"], {}))
        self.assertEqual(got["basic"], ["Basic", "Charm"])
        self.assertFalse(got["tribe_in_rules"])
        self.assertTrue(got["basic_charm_rules"])


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


class TestModContentCase(unittest.TestCase):
    """Mod Content names match exactly, else ignoring case (the user's call, 2026-11-27)."""

    def chosen(self, names, loaded=("Companion Start", "Pokefrost"), failed=()):
        from Options import OptionError
        from .. import extensions as ext_module
        from ..world import chosen_extensions
        with mock.patch.object(ext_module, "LOADED", {n: object() for n in loaded}), \
                mock.patch.object(ext_module, "FAILED", {n: "bad" for n in failed}):
            try:
                return chosen_extensions(names)
            except OptionError as e:
                return str(e)

    def test_exact(self) -> None:
        self.assertEqual(self.chosen(["Companion Start"]), {"Companion Start"})

    def test_any_case_takes_the_files_spelling(self) -> None:
        self.assertEqual(self.chosen(["companion START", "pokefrost"]), {"Companion Start", "Pokefrost"})

    def test_exact_wins_over_a_case_match(self) -> None:
        self.assertEqual(self.chosen(["mymod"], loaded=("MyMod", "mymod")), {"mymod"})

    def test_two_case_matches_ask_for_the_exact_name(self) -> None:
        self.assertIn("write it exactly", self.chosen(["MYMOD"], loaded=("MyMod", "mymod")))

    def test_failed_file_found_ignoring_case(self) -> None:
        self.assertIn("'Broken': its extension file didn't load", self.chosen(["broken"], failed=("Broken",)))

    def test_no_match(self) -> None:
        self.assertIn("needs its extension file (CompanionStart.wildfrost.json)", self.chosen(["CompanionStart"]))
