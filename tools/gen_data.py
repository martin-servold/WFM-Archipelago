"""Generate apworld/wildfrost/data.py from data/content_dump.txt (written in game by ContentDump.cs).

IDs are frozen: entries already in the existing data.py keep their ID, and new entries are appended
after the highest ID in their range. Never renumber, because seeds and saves refer to IDs.

Usage: python3 -I tools/gen_data.py
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DUMP = ROOT / "data" / "content_dump.txt"
OUT = ROOT / "apworld" / "wildfrost" / "data.py"

AREA_OF_TIER = {0: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 1, 6: 2, 7: 2, 8: 2}
BOSS_TIERS = {2, 5, 7, 8}
# Challenge Charm 14 is "Win a Daily Voyage": daily runs are a different game mode, dropped.
EXCLUDED_CHALLENGES = {"Challenge Charm 14"}
# Two checks (decided by the user 2026-11-02): every boss, and every challenge that unlocks a charm in
# vanilla (first Bigger Hitter, One Punch, Charmless and Sunbringer, then all of them, for filler
# room). The second is "<key>#2", "<name> #2", with the same info, so it shares the first's area and
# rule; the client sends both together.
def doubled_challenge(internal: str) -> bool:
    return internal.startswith("Challenge Charm ")
# Tier 8's "Final Final Boss" is the True Final Boss, only fought with 10 storm points of bells.
# Its checks only exist for the goals that need it (the world drops them otherwise).
TRUE_FINAL_BATTLES = {"Final Final Boss": "True Final Boss"}
TRIBES = {"Magic": "Shademancers", "Clunk": "Clunkmasters"}
# Every battle is a check once per tribe you win it with. All three tribes are items; the
# starting_tribe option puts one in the starting inventory.
RUN_TRIBES = {"Basic": "Snowdwellers", **TRIBES}
# Item names are the events' in-game names (the user's call, 2026-10-31).
EVENT_NODES = {
    "CampaignNodeCopyItem": "Shade Sculptor",
    "CampaignNodeCharmShop": "Charm Merchant",
    "CampaignNodeCurseItems": "Gnome Traveller",
}

# Cards come in packs: one item is PACK_SIZE cards of one clan and kind. Which cards each pack
# holds is shuffled per seed (world.py); only the number of packs per group is fixed here.
PACK_SIZE = 3
# The Snow pools are general (every tribe draws from them), so they count as General.
CLAN_OF_POOL = {"General": "General", "Snow": "General", "Basic": "Basic", "Magic": "Magic", "Clunk": "Clunk"}
CLAN_LABEL = {"General": "General", "Basic": "Snowdweller", "Magic": "Shademancer", "Clunk": "Clunkmaster"}

# ID ranges. Locations and items have separate ID spaces.
LOC_BATTLE, LOC_CHALLENGE, LOC_SECOND = 1000, 2000, 3000
ITEM_TRIBE, ITEM_EVENT, ITEM_PET, ITEM_BELL, ITEM_PACK, ITEM_FILLER = 100, 200, 300, 400, 3000, 9000
ITEM_TRAP, ITEM_BOON = 9100, 9200
# Charms are items one by one, not in packs (decided by the user 2026-11-02): a charm pack brought
# three at once, which made early runs charm-heavy. Companions and items stay in packs.
ITEM_CHARM = 5000

# Filler with an effect (decided by the user 2026-10-31). "Bling" gives 25-50 Bling. Battle effects
# wait for the next battle of a run.
TRAPS = {
    "trap:lose_bling": "Bling Thief Trap",        # lose 25-50 Bling
    "trap:slapcrackers": "Slapcrackers Trap",     # 1 damage x4, aimless, on one of your rows
    "trap:berry_bell": "Berry Bell Trap",         # +1 health and max health to an enemy row
    "trap:demonize": "Demonize Trap",             # Demonize one of your units
    "trap:teeth": "Teeth Trap",                   # 1 Teeth on an enemy
}
BOONS = {
    "boon:slapcrackers": "Slapcrackers Boon",     # 1 damage x4, aimless, on an enemy row
    "boon:pinkberry": "Pinkberry Juice Boon",     # +4 health and max health on one of your units
    "boon:kill": "Kill Enemy Boon",                 # kill an enemy that isn't a boss or miniboss
    "boon:demonize": "Demonize Boon",             # Demonize an enemy
}


def section(text, title):
    m = re.search(r"^## " + re.escape(title) + r".*?\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        sys.exit(f"missing section {title!r} in dump")
    return m.group(1)


def main():
    text = DUMP.read_text(encoding="utf-8")

    titles = {}
    for m in re.finditer(r'^    (\S+) "([^"]*)"', text, re.M):
        titles.setdefault(m.group(1), m.group(2))

    battle_names = {}
    for m in re.finditer(r'^  (.+?) "(.*?)" name="(.*?)"', section(text, "BattleData"), re.M):
        battle_names[m.group(1)] = m.group(3) or m.group(2)

    tiers = section(text, "Campaign tiers")
    tribe_locks = {}
    for m in re.finditer(r"battle lock .*? battle=(.+?) challenge=Challenge (Tribe \d)", tiers):
        tribe_locks[m.group(1)] = {"Tribe 1": "Magic", "Tribe 2": "Clunk"}[m.group(2)]

    # (key, name, area, boss, tribe the battle is locked behind, tribe the run is played with, true final,
    # map tier: 0-1 battles, 2 first boss, 3-4 battles, 5 second boss, 6 battles, 7 Final Boss, 8 True Final Boss)
    battles = []
    for m in re.finditer(r"^  tier (\d+) .*? battles=\[(.*?)\] rewardNodes", tiers, re.M):
        tier = int(m.group(1))
        area = AREA_OF_TIER[tier]
        for b in re.finditer(r'(.+?) "[^"]*"(?:, |$)', m.group(2)):
            internal = b.group(1)
            label = "Boss" if tier in BOSS_TIERS else "Battle"
            for run_tribe, tribe_name in RUN_TRIBES.items():
                shown = TRUE_FINAL_BATTLES.get(internal) or battle_names.get(internal, internal)
                name = f"Area {area + 1} {label} - {shown} ({tribe_name})"
                battles.append((f"battle:{area}:{internal}:{run_tribe}", name, area, tier in BOSS_TIERS,
                                tribe_locks.get(internal), run_tribe, internal in TRUE_FINAL_BATTLES, tier))

    challenges = []  # (key, name, internal, text)
    for m in re.finditer(r'^  (Challenge .+?) goal=(\d+) .*?title="(.*?)" text="(.*?)"$',
                         section(text, "ChallengeData"), re.M):
        internal, goal, title, desc = m.groups()
        if internal in EXCLUDED_CHALLENGES:
            continue
        desc = desc.replace("{0}", goal)
        challenges.append((f"challenge:{internal}", f"Challenge - {title or desc}", internal, desc))

    cards = {}  # internal -> (kind, pool)
    pools = section(text, "ClassData")
    clan = None
    for line in pools.splitlines():
        m = re.match(r"  (\w+) id=", line)
        if m:
            clan = m.group(1)
            continue
        m = re.match(r"    pool (\w+) type=(\w+) .*?: (.*)", line)
        if m and clan != "Tutorial" and m.group(2) in ("Items", "Units", "Charms"):
            for n in m.group(3).split(", "):
                cards.setdefault(n, (m.group(2), m.group(1)))

    # Every pet, Wolfie (Snoof) too: it has no unlock (always available in vanilla), and became a pet
    # item like the others (the user's call, 2026-11-02); the client locks it.
    pets = [m.group(1) for m in re.finditer(r"^  (\w+) ->", section(text, "Pets"), re.M)]

    old_loc, old_item = {}, {}
    if OUT.exists():
        tree = ast.parse(OUT.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and node.targets[0].id == "LOCATIONS":
                old_loc = {e[0]: e[2] for e in ast.literal_eval(node.value)}
            if isinstance(node, ast.Assign) and node.targets[0].id == "ITEMS":
                old_item = {e[0]: e[2] for e in ast.literal_eval(node.value)}

    def assign(keys, old, base):
        used = {old[k] for k in keys if k in old}
        nxt = max([i for i in used if base <= i < base + 1000] + [base - 1]) + 1
        out = {}
        for k in keys:
            if k in old:
                out[k] = old[k]
            else:
                out[k] = nxt
                nxt += 1
        return out

    battle_ids = assign([b[0] for b in battles], old_loc, LOC_BATTLE)
    challenge_ids = assign([c[0] for c in challenges], old_loc, LOC_CHALLENGE)
    seconds = [b[0] for b in battles if b[3]] + [c[0] for c in challenges if doubled_challenge(c[2])]
    second_ids = assign([k + "#2" for k in seconds], old_loc, LOC_SECOND)

    tribe_keys = [f"tribe:{t}" for t in RUN_TRIBES]
    event_keys = [f"event:{e}" for e in EVENT_NODES]
    pet_keys = [f"pet:{p}" for p in pets]
    card_keys = [f"card:{c}" for c in sorted(cards)]
    kind_label = {"Items": "Item", "Units": "Companion", "Charms": "Charm"}
    card_rows = []  # (key, name, info)
    for k in card_keys:
        kind, pool = cards[k[5:]]
        clan = CLAN_OF_POOL[re.match(r"(General|Snow|Basic|Magic|Clunk)", pool).group(1)]
        card_rows.append((k, titles[k[5:]], {"kind": kind_label[kind], "clan": clan, "pool": pool}))
    charm_keys = [f"charm:{i['clan']}:{k[5:]}" for k, _, i in card_rows if i["kind"] == "Charm"]
    pack_keys = []
    for clan in CLAN_LABEL:
        for kind in ("Item", "Companion"):
            n = sum(1 for _, _, i in card_rows if i["clan"] == clan and i["kind"] == kind)
            pack_keys += [f"pack:{clan}:{kind}:{i + 1}" for i in range(-(-n // PACK_SIZE))]
    item_ids = {}
    item_ids.update(assign(tribe_keys, old_item, ITEM_TRIBE))
    item_ids.update(assign(event_keys, old_item, ITEM_EVENT))
    item_ids.update(assign(pet_keys, old_item, ITEM_PET))
    item_ids.update(assign(pack_keys, old_item, ITEM_PACK))
    item_ids.update(assign(charm_keys, old_item, ITEM_CHARM))
    item_ids.update(assign(["storm_bell"], old_item, ITEM_BELL))
    item_ids["bling"] = old_item.get("bling", ITEM_FILLER)
    item_ids.update(assign(list(TRAPS), old_item, ITEM_TRAP))
    item_ids.update(assign(list(BOONS), old_item, ITEM_BOON))

    locations = [(k, n, battle_ids[k], {"area": a, "boss": boss, "tribe": t, "run_tribe": rt, "true_final": tf, "tier": tier})
                 for k, n, a, boss, t, rt, tf, tier in battles]
    locations += [(k, n, challenge_ids[k], {"internal": i, "text": d}) for k, n, i, d in challenges]
    locations += [(k + "#2", n + " #2", second_ids[k + "#2"], {**info, "second": True})
                  for k, n, _, info in list(locations) if k in seconds]
    items = [(k, RUN_TRIBES[k.split(":")[1]], item_ids[k], {"kind": "Tribe"}) for k in tribe_keys]
    items += [(k, EVENT_NODES[k.split(":")[1]], item_ids[k], {"kind": "Event"}) for k in event_keys]
    items += [(k, f"{titles.get(k[4:], k[4:])} Pet", item_ids[k], {"kind": "Pet"}) for k in pet_keys]
    for k in pack_keys:
        _, clan, kind, n = k.split(":")
        items.append((k, f"{CLAN_LABEL[clan]} {kind} Pack {n}", item_ids[k], {"kind": "Pack", "clan": clan, "card_kind": kind}))
    title_of = {k: n for k, n, _ in card_rows}
    for k in charm_keys:
        _, clan, card = k.split(":")
        items.append((k, title_of[f"card:{card}"], item_ids[k], {"kind": "Charm", "clan": clan, "card": f"card:{card}"}))
    # One copy per bell level (items.STORM_BELL_LEVELS): storm point caps 2, 4, ... 20, then Overcrank.
    items.append(("storm_bell", "Progressive Storm Bell", item_ids["storm_bell"], {"kind": "StormBell"}))
    items.append(("bling", "Bling", item_ids["bling"], {"kind": "Filler"}))
    items += [(k, n, item_ids[k], {"kind": "Trap"}) for k, n in TRAPS.items()]
    items += [(k, n, item_ids[k], {"kind": "Filler"}) for k, n in BOONS.items()]

    for what, rows in (("location", locations), ("item", items)):
        names = [r[1] for r in rows]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            sys.exit(f"duplicate {what} names: {sorted(dupes)}")

    def fmt(rows):
        return "[\n" + "".join(f"    {r!r},\n" for r in rows) + "]"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        '"""Generated by tools/gen_data.py from data/content_dump.txt. Do not edit by hand.\n\n'
        "Each row is (key, display name, id, info). The key is what the client matches against game\n"
        'data (it is sent to the client in slot_data); the display name is what players see."""\n\n'
        f"PACK_SIZE = {PACK_SIZE}\n\nLOCATIONS = {fmt(locations)}\n\nITEMS = {fmt(items)}\n\n"
        "# Not items themselves: the cards that packs are filled with. (key, display name, info)\n"
        f"CARDS = {fmt(card_rows)}\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT}: {len(locations)} locations ({len(battles)} battles, {len(challenges)} challenges), "
          f"{len(items)} items ({len(pack_keys)} packs of {len(card_rows)} cards)")


if __name__ == "__main__":
    main()
