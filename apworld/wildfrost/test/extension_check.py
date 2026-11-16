"""
Run by test_extensions.py in its own process, from Archipelago's folder, with WILDFROST_EXTENSIONS_DIR
pointing at test/extensions: extensions load when the apworld is imported, so a test process that has
already imported it can't add one. Prints one JSON object of findings.
"""

import json
import sys

sys.path.insert(0, ".")

import worlds  # noqa: E402,F401  (first: some apworlds import Fill while loading)
from BaseClasses import CollectionState  # noqa: E402
from Fill import distribute_items_restrictive  # noqa: E402
from Options import OptionError  # noqa: E402
from test.general import gen_steps, setup_multiworld  # noqa: E402
from worlds.AutoWorld import call_all  # noqa: E402
from worlds.wildfrost import extensions  # noqa: E402
from worlds.wildfrost.world import WildfrostWorld, read_location_rules, rebuilt_extensions  # noqa: E402

BASE = {"starting_tribe": "snowdwellers", "goal": "final_boss", "clans_required": 1, "trap_percentage": 0}


def generate(options: dict, fill: bool = True):
    multiworld = setup_multiworld(WildfrostWorld, gen_steps, seed=7, options={**BASE, **options})
    if fill:
        distribute_items_restrictive(multiworld)
        call_all(multiworld, "post_fill")
    return multiworld


out: dict = {"loaded": sorted(extensions.LOADED), "failed": extensions.FAILED}

with_mod = generate({"mod_content": ["SampleMod"]})
world = with_mod.worlds[1]
pool = [item.name for item in with_mod.itempool]
slot_data = world.fill_slot_data()
rules = read_location_rules(slot_data["location_rules"])
out["with"] = {
    "locations": sorted(loc.name for loc in with_mod.get_locations(1) if (loc.address or 0) >= extensions.ID_BASE),
    "items": sorted(n for n in pool if n.startswith("SampleMod") or n == "Sample Bog Charm"),
    "troll_pack": world.pack_contents.get("pack:Basic:Companion:SampleMod-Troll"),
    "packs_with_mod_cards": sorted(k for k, cards in world.pack_contents.items()
                                   if any(c.startswith("card:Sample") for c in cards)),
    "mod_cards_dealt": sorted(c for cards in world.pack_contents.values() for c in cards if c.startswith("card:Sample")),
    # The mod's cards only in its own packs (the user's call, 2026-11-15), and ours only in ours.
    "mixed_packs": sorted(k for k, cards in world.pack_contents.items()
                          if any(c.startswith("card:Sample") for c in cards) != ("SampleMod" in k)),
    "excluded": [loc.name for loc in with_mod.get_locations(1) if loc.name == "Challenge - Win with 3 Shrooms"
                 and loc.progress_type.name == "EXCLUDED"],
    "rule_hammer": rules.get("challenge:SampleMod Challenge 1"),
    # Its "applies:Bog" group lists the Clunkmasters, whose leaders (in the sample) apply Bog.
    "bog_rule_has_tribe": "tribe:Clunk" in json.dumps(rules.get("challenge:SampleMod Challenge 2")),
    "applies_rule": rules.get("challenge:SampleMod Challenge 4"),
    "extensions": slot_data["extensions"],
    "beatable": with_mod.can_beat_game(CollectionState(with_mod)),
    "pool_fits": len(pool) == len([loc for loc in with_mod.get_locations(1) if loc.address is not None]),
}

without = generate({}, fill=False)
out["without"] = {
    "locations": sorted(loc.name for loc in without.get_locations(1) if (loc.address or 0) >= extensions.ID_BASE),
    "items": sorted(i.name for i in without.itempool if i.name.startswith("SampleMod") or i.name == "Sample Bog Charm"),
    "mod_cards_dealt": sorted(c for cards in without.worlds[1].pack_contents.values() for c in cards if c.startswith("card:Sample")),
    "extensions": without.worlds[1].fill_slot_data()["extensions"],
}

remover = generate({"mod_content": ["RemoverMod"], "new_challenges": True})
names = {loc.name for loc in remover.get_locations(1)}
dealt = {c for cards in remover.worlds[1].pack_contents.values() for c in cards}
out["remover"] = {
    "gone": sorted(n for n in ("Challenge - Don't break the Egg", "Challenge - Berry Good", "Challenge - High Roller",
                               "Area 3 Battle - The Gunk Bugs (Snowdwellers)", "Challenge - Kill 3 Gobblers") if n not in names),
    "kept": sorted(n for n in ("Challenge - Minimalist", "Challenge - Apply 40 Ink") if n in names),
    "cards_dealt": sorted(c for c in ("card:Egg", "card:PinkberryJuice") if c in dealt),
    "squid_charm_in_pool": any(i.name == "Squid Charm" for i in remover.itempool),
    "beatable": remover.can_beat_game(CollectionState(remover)),
    "pool_fits": len(remover.itempool) == len([loc for loc in remover.get_locations(1) if loc.address is not None]),
}
# BellMod leaves 5 of the base game's 22 storm points and adds a 2-point bell: 7 in all, so the True
# Final Boss comes at 7 (4 Progressive Storm Bells), and forcing stops at 7 too.
bellmod = generate({"mod_content": ["BellMod"], "goal": "true_final_boss", "new_challenges": True,
                    "force_storm_bells_up_to": 10})
bworld = bellmod.worlds[1]
names = {loc.name for loc in bellmod.get_locations(1)}
brules = read_location_rules(bworld.fill_slot_data()["location_rules"])
out["bellmod"] = {
    "true_final_points": bworld.fill_slot_data()["true_final_points"],
    "true_final_bells": bworld.true_final_bells,
    "bells_in_pool": sum(1 for i in bellmod.itempool if i.name == "Progressive Storm Bell"),
    "force": bworld.options.force_storm_bells_up_to.value,
    "gone": sorted(n for n in ("Challenge - Apply 3 Cursed Crowns", "Challenge - Kill 3 Gobblers") if n not in names),
    "kept": sorted(n for n in ("Challenge - Injure 3 companions", "Challenge - Ring the Troll Bell") if n in names),
    "troll_rule": brules.get("challenge:BellMod Challenge 1"),
    "beatable": bellmod.can_beat_game(CollectionState(bellmod)),
    # The forcing table: (most levels, the first alternative's companion packs) per kit.
    "bell_kits": [[levels, alts[0]["Companion"], alts[0]["Item"]] for levels, alts in bworld.fill_slot_data()["bell_kits"]],
}
# TribeMod adds a tribe, Bogfolk, sharing the Snowdweller pools (the user's calls, 2026-11-16).
TRIBE = "TribeMod.Bogfolk"
tribal = generate({"mod_content": ["TribeMod"], "clans_required": 4, "starting_tribe": "any_tribe"})
tworld = tribal.worlds[1]
tslot = tworld.fill_slot_data()
trules = read_location_rules(tslot["location_rules"])
out["tribe"] = {
    "tribes": tslot["tribes"],
    "clans_required": tworld.options.clans_required.value,
    "victories": sorted(loc.name for loc in tribal.get_locations(1) if loc.name.startswith("Victory")),
    "battles": sum(1 for loc in tribal.get_locations(1) if loc.name.endswith("(Bogfolk)")),
    "twins": sum(1 for loc in tribal.get_locations(1) if loc.name.endswith("(Bogfolk) #2")),
    "tribe_item": sum(1 for i in tribal.itempool if i.name == "Bogfolk") + sum(
        1 for i in tribal.precollected_items[1] if i.name == "Bogfolk"),
    "starting": tslot["starting_tribe"],
    # A Bogfolk boss needs the Bogfolk item and the kit from General, Snowdweller and Bogfolk packs.
    "boss_rule": trules.get(f"battle:1:Toadstool Boss:{TRIBE}"),
    "win_challenge": trules.get("challenge:TribeMod Challenge 1"),
    "bog_rule": trules.get("challenge:TribeMod Challenge 2"),
    "beatable": tribal.can_beat_game(CollectionState(tribal)),
    "pool_fits": len(tribal.itempool) == len([loc for loc in tribal.get_locations(1) if loc.address is not None]),
    # Tough Nut's shell cards are Snowdweller cards: Bogfolk shares the Snowdweller pools, so a Bogfolk run
    # can be offered them too (the user's call, 2026-11-16).
    "shell_rule": json.dumps(trules.get("challenge:Challenge Charm 5")),
    # Its True Final Boss row is the True Final Boss: not in this Final Boss goal seed.
    "true_final_battle": any(loc.name == "Area 3 Boss - True Final Boss (Bogfolk)" for loc in tribal.get_locations(1)),
}
tf_tribal = generate({"mod_content": ["TribeMod"], "goal": "true_final_boss"}, fill=False)
out["tribe"]["true_final_rule"] = json.dumps(read_location_rules(
    tf_tribal.worlds[1].fill_slot_data()["location_rules"]).get(f"battle:2:Final Final Boss:{TRIBE}"))
# Clans Required past the slot's tribes means every one; without the mod, the vanilla three.
plain = generate({"clans_required": 5}, fill=False)
out["tribe_without"] = {"clans_required": plain.worlds[1].options.clans_required.value,
                        "tribes": [t["class"] for t in plain.worlds[1].fill_slot_data()["tribes"]],
                        "bogfolk": any("Bogfolk" in loc.name for loc in plain.get_locations(1))}
# Any Tribe over seeds: it can start with Bogfolk.
out["any_tribe_starts"] = sorted({setup_multiworld(WildfrostWorld, gen_steps, seed=s, options={
    **BASE, "mod_content": ["TribeMod"], "starting_tribe": "any_tribe"}).worlds[1].fill_slot_data()["starting_tribe"]
    for s in range(1, 13)})

out["vanilla_true_final_points"] = without.worlds[1].fill_slot_data()["true_final_points"]

# A seed without the extension keeps all of it.
names = {loc.name for loc in without.get_locations(1)}
out["without"]["kept"] = sorted(n for n in ("Challenge - Berry Good", "Challenge - High Roller",
                                            "Area 3 Battle - The Gunk Bugs (Snowdwellers)") if n in names)

for label, new_challenges in (("overflow_off", False), ("overflow_on", True)):
    mw = generate({"mod_content": ["OverflowMod"], "new_challenges": new_challenges})
    w = mw.worlds[1]
    from worlds.wildfrost import locations as wf_locations
    chosen = w.spare_checks
    w.spare_checks = {key for key, _, _, info in wf_locations.LOCATIONS if wf_locations.is_spare(w, info)}
    spare_candidates = [key for key, _, _, info in wf_locations.LOCATIONS
                        if wf_locations.is_spare(w, info) and wf_locations.included(w, info, key)]
    w.spare_checks = chosen
    out[label] = {
        "spares": len(w.spare_checks),
        "spare_candidates": len(spare_candidates),
        "slot_data_spares": len(w.fill_slot_data()["spare_checks"]),
        "mod_packs": sum(1 for k, cards in w.pack_contents.items() if "OverflowMod" in k and cards),
        "mod_cards_dealt": sum(len(cards) for k, cards in w.pack_contents.items() if "OverflowMod" in k),
        "pool_fits": len(mw.itempool) == len([loc for loc in mw.get_locations(1) if loc.address is not None]),
        "beatable": mw.can_beat_game(CollectionState(mw)),
    }
    # Universal Tracker's rebuild from slot_data has the same checks and packs.
    overflow_slot_data = w.fill_slot_data()
    rebuilt = setup_multiworld(WildfrostWorld, (), seed=99, options={**BASE, "mod_content": ["OverflowMod"]})
    rebuilt.re_gen_passthrough = {"Wildfrost": overflow_slot_data}
    for step in ("generate_early", "create_regions", "create_items", "set_rules"):
        call_all(rebuilt, step)
    out[label]["rebuild_same"] = (
        {loc.name for loc in rebuilt.get_locations(1)} == {loc.name for loc in mw.get_locations(1)}
        and sorted(i.name for i in rebuilt.itempool if "Pack" in i.name) == sorted(i.name for i in mw.itempool if "Pack" in i.name))

try:
    generate({"mod_content": ["NotInstalled"]}, fill=False)
    out["unknown_mod"] = "no error"
except OptionError as e:
    out["unknown_mod"] = str(e)

meta = dict(slot_data["extensions"][0])
out["rebuild_same"] = sorted(rebuilt_extensions({"extensions": [meta]}))
try:
    rebuilt_extensions({"extensions": [{**meta, "hash": "0" * 16, "version": "0.9.0"}]})
    out["rebuild_other"] = "no error"
except OptionError as e:
    out["rebuild_other"] = str(e)

print("RESULT " + json.dumps(out))
