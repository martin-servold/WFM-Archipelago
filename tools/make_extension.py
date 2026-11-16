"""
Makes or updates a mod's extension file (PLAN.md §10) from its content dump.

Take the dump with this mod (debug = True in its config.cfg) and only that one other mod loaded; the
dump is rewritten whenever another mod loads, so it ends up with everything. Then:

    python3 -I tools/make_extension.py --dump "<mod's content_dump.txt>" --mod MyMod --block 3 [--version 1.0.0]

It compares the dump with the base game's (data/content_dump.txt) and writes <MyMod>.wildfrost.json:
the mod's cards (by reward pool: clan and kind) dealt into its own packs, its charms and pets as items,
its battles (one check per run tribe) and challenges as locations, its storm bells, and what it
removes from the base game. Run it again on a new dump to update the file: IDs already given keep
their numbers, and what a creator wrote by hand stays (each challenge's rule, region, excluded and
name, and the groups). New challenges get no rule: write what they need before shipping.
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gen_data  # noqa: E402

ID_BASE, BLOCK_SIZE = 100_000, 2_000  # apworld/wildfrost/extensions.py
KIND_OF_POOL = {"Units": "Companion", "Items": "Item", "Charms": "Charm"}
CHALLENGE_LINE = re.compile(r'^  (\S.*?) goal=(\d+) .*?title="(.*?)" text="(.*?)"$', re.M)
BELL_LINE = re.compile(r'^  (\S+) points=(\d+) modifier=\S+ title="([^"]*)"', re.M)


def read(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    parsed = gen_data.parse(text)
    parsed["all_challenges"] = {m.group(1): (int(m.group(2)), m.group(3), m.group(4))
                                for m in CHALLENGE_LINE.finditer(gen_data.section(text, "ChallengeData"))}
    try:
        bells = gen_data.section(text, "Storm bells")
    except SystemExit:
        sys.exit(f"{path} has no storm bell section: take the dump with the current Archipelago mod")
    parsed["bells"] = {m.group(1): (int(m.group(2)), m.group(3)) for m in BELL_LINE.finditer(bells)}
    loaded = re.search(r"^## Loaded mods\n(.*?)(?=^## )", text, re.M | re.S)
    parsed["mods"] = re.findall(r'^  (\S+) title="(.*?)"', loaded.group(1), re.M) if loaded else []
    return parsed


# A group stands for the effect most of its cards apply, when at least this share of them do.
GROUP_EFFECT_SHARE = 0.5

effects, leaders = gen_data.effects, gen_data.leaders


def our_groups() -> dict[str, list[str]]:
    return json.loads(gen_data.OUT.read_text(encoding="utf-8")).get("groups", {})


def group_effects(base_effects: dict) -> dict[str, str]:
    """
    Which effect (or "type:<CardType>") each of our groups stands for, from the base game's dump: the one
    most of its cards apply. Groups with no clear effect (sacrifice, for one) get none.
    """
    out = {}
    for group, members in our_groups().items():
        counts: dict[str, int] = {}
        known = [m for m in members if m in base_effects]
        for m in known:
            kind, applied, _ = base_effects[m]
            for effect in applied | {f"type:{kind}"}:
                counts[effect] = counts.get(effect, 0) + 1
        # A card type stands for a group only when every card has it (the clunkers); an effect when most do.
        types = [e for e in counts if e.startswith("type:") and counts[e] == len(known)]
        effect_counts = {e: n for e, n in counts.items() if not e.startswith("type:")}
        if known and types:
            out[group] = types[0]
        elif effect_counts:
            best = max(sorted(effect_counts), key=lambda e: effect_counts[e])
            if effect_counts[best] >= GROUP_EFFECT_SHARE * len(known):
                out[group] = best
    return out


def clan_of(pool: str) -> str | None:
    m = re.match(r"(General|Snow|Basic|Magic|Clunk)", pool)
    return gen_data.CLAN_OF_POOL[m.group(1)] if m else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dump", required=True, type=Path, help="the content dump taken with the mod loaded")
    ap.add_argument("--mod", required=True, help="the extension's name (players type it in Mod Content)")
    ap.add_argument("--block", required=True, type=int, help="the mod's ID block, from the block registry")
    ap.add_argument("--guid", help="the mod's GUID (default: the one other mod in the dump's Loaded mods)")
    ap.add_argument("--version", default="1.0.0", help="the extension's version")
    ap.add_argument("--vanilla", type=Path, default=gen_data.DUMP, help="the base game's dump")
    ap.add_argument("--out", type=Path, help="the extension file (default: <mod>.wildfrost.json here)")
    args = ap.parse_args()

    base, mod = read(args.vanilla), read(args.dump)
    out = args.out or Path(f"{args.mod}.wildfrost.json")
    old = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    if old and old.get("id_block") != args.block:
        sys.exit(f"{out} has id_block {old.get('id_block')}, not {args.block}")
    # Older layouts: flat "items"/"locations" lists, or flat "ap_items"/"ap_locations" (both 2026-11-15).
    old_items = old.pop("ap_items", old.pop("items", []))
    old["ap_items"] = ([{**r, "kind": kind} for kind, rows in old_items.items() for r in rows]
                       if isinstance(old_items, dict) else old_items)
    old["ap_locations"] = gen_data.rows_of(old.pop("ap_locations", old.pop("locations", [])))

    guid = args.guid
    if not guid:
        others = [g for g, _ in mod["mods"] if g not in {g2 for g2, _ in base["mods"]}]
        if len(others) != 1:
            sys.exit(f"pass --guid: the dump's loaded mods besides the base dump's are {others or 'none'}")
        guid = others[0]

    notes = []
    # Cards the mod adds, by the reward pool they're in.
    cards = []
    for name, (pool_type, pool) in sorted(mod["cards"].items()):
        if name in base["cards"]:
            continue
        clan = clan_of(pool)
        if clan is None:
            notes.append(f"skipped {name}: its pool {pool} isn't a clan's or General")
            continue
        cards.append({"key": f"card:{name}", "name": mod["titles"].get(name, name), "kind": KIND_OF_POOL[pool_type],
                      "clan": clan})

    items = []
    for clan in gen_data.CLAN_LABEL:
        for kind in ("Item", "Companion"):
            count = sum(1 for c in cards if c["clan"] == clan and c["kind"] == kind)
            for i in range(math.ceil(count / gen_data.PACK_SIZE)):
                items.append({"key": f"pack:{clan}:{kind}:{args.mod}-{i + 1}",
                              "name": f"{args.mod} {gen_data.CLAN_LABEL[clan]} {kind} Pack {i + 1}",
                              "kind": "Pack", "clan": clan, "card_kind": kind})
    for c in cards:
        if c["kind"] == "Charm":
            items.append({"key": f"charm:{c['clan']}:{c['key'][5:]}", "name": c["name"], "kind": "Charm",
                          "clan": c["clan"], "card": c["key"]})
    for pet in mod["pets"]:
        if pet not in base["pets"]:
            items.append({"key": f"pet:{pet}", "name": f"{mod['titles'].get(pet, pet)} Pet", "kind": "Pet"})

    locations = []
    base_battles = {b[0] for b in base["battles"]}
    for key, name, area, boss, tribe, run_tribe, _, tier in mod["battles"]:
        if key not in base_battles:
            locations.append({"key": key, "name": name, "area": area, "tier": tier, "boss": boss, "tribe": tribe,
                              "run_tribe": run_tribe})
            # Its spare "#2", only in a seed short of checks for its items (written as "spares").
            locations.append({"key": key + "#2"})
    for internal, (goal, title, text) in sorted(mod["all_challenges"].items()):
        if internal not in base["all_challenges"]:
            desc = text.replace("{0}", str(goal))
            locations.append({"key": f"challenge:{internal}", "name": f"Challenge - {title or desc}", "text": desc,
                              "region": "Area 1", "rule": None})
            # Its spare "#2", only in a seed short of checks for its items (written as "spares").
            locations.append({"key": f"challenge:{internal}#2"})

    bells = [{"name": n, "points": p} for n, (p, _) in mod["bells"].items() if n not in base["bells"]]

    # New tribes can't come from an extension yet (PLAN.md §10, "tribes from data"): runs with them send
    # nothing, and cards only in their own reward pools are left out.
    text = args.dump.read_text(encoding="utf-8")
    base_classes = set(re.findall(r"^  (\S+) id=", gen_data.section(args.vanilla.read_text(encoding="utf-8"), "ClassData"), re.M))
    tribe_cards: dict[str, set] = {}
    tribe = None
    for line in gen_data.section(text, "ClassData").splitlines():
        m = re.match(r"  (\S+) id=", line)
        if m:
            tribe = m.group(1) if m.group(1) not in base_classes else None
            continue
        m = re.match(r"    pool (\S+) type=(\w+) .*?: (.*)", line)
        if tribe and m and m.group(2) in KIND_OF_POOL:
            tribe_cards.setdefault(tribe, set()).update(n for n in m.group(3).split(", ") if n not in base["cards"]
                                                        and n not in {c["key"][5:] for c in cards})
    if tribe_cards:
        notes.append(f"{len(tribe_cards)} new tribes aren't supported yet (runs with them send nothing); left out "
                     f"{sum(len(v) for v in tribe_cards.values())} cards only in their pools: "
                     + ", ".join(f"{t.rsplit('.', 1)[-1]} {len(v)}" for t, v in sorted(tribe_cards.items())))

    base_battle_names = {b[0].split(":")[2] for b in base["battles"]}
    mod_battle_names = {b[0].split(":")[2] for b in mod["battles"]}
    removes = {
        "cards": sorted(n for n, (t, _) in base["cards"].items() if t != "Charms" and n not in mod["cards"]),
        "charms": sorted(n for n, (t, _) in base["cards"].items() if t == "Charms" and n not in mod["cards"]),
        "battles": sorted(base_battle_names - mod_battle_names),
        "challenges": sorted(c for c in base["all_challenges"] if c not in mod["all_challenges"]
                             and c.startswith("Challenge ")),
        "bells": sorted(n for n in base["bells"] if n not in mod["bells"]),
    }
    removes = {k: v for k, v in removes.items() if v}

    # Effects (the user's calls, 2026-11-15): each card lists what it applies, for the "applies" rule form
    # (which also counts clans whose leaders apply it), and the mod's cards join our groups whose effect
    # they apply. What the creator added to groups by hand stays; the "note" below says which effect each
    # of our groups stands for.
    base_text, mod_text = args.vanilla.read_text(encoding="utf-8"), args.dump.read_text(encoding="utf-8")
    base_effects = effects(base_text)
    if "## Card effects" in mod_text:
        mod_effects = effects(mod_text)
    else:
        mod_effects = {}
        notes.append("the dump has no effects (an older mod version took it): no 'applies' and no groups for its cards")
    standing = group_effects(base_effects)
    mod_cards = [c["key"][5:] for c in cards]
    # "applies:<Effect>" groups from before the "applies" rule form are dropped.
    groups = {g: list(v) for g, v in old.get("groups", {}).items() if not g.startswith("applies:")}

    def join(group: str, entry: str) -> None:
        groups.setdefault(group, [])
        if entry not in groups[group]:
            groups[group].append(entry)

    for card in mod_cards:
        kind, applied, _ = mod_effects.get(card, ("", set(), set()))
        for group, effect in standing.items():
            if effect in applied or effect == f"type:{kind}":
                join(group, card)
    for c in cards:
        _, applied, traits = mod_effects.get(c["key"][5:], ("", set(), set()))
        if applied:
            c["applies"] = sorted(applied)
        if traits:
            c["traits"] = sorted(traits)
    groups = {g: v for g, v in sorted(groups.items()) if v}
    notes.append("our groups stand for: " + ", ".join(f"{g} = {e}" for g, e in sorted(standing.items())))

    # IDs: kept for keys the old file had, the next free one in the block for new keys.
    low, high = ID_BASE + args.block * BLOCK_SIZE, ID_BASE + (args.block + 1) * BLOCK_SIZE
    for rows, old_rows in ((items, old.get("ap_items", [])), (locations, old.get("ap_locations", []))):
        old_by_key = {r["key"]: r for r in old_rows}
        used = {r["id"] for r in old_rows}
        nxt = low
        for row in rows:
            previous = old_by_key.get(row["key"])
            if previous:
                row["id"] = previous["id"]
                # What the creator wrote by hand stays.
                for field in ("name", "rule", "region", "excluded", "text"):
                    if field in previous and row["key"].startswith("challenge:"):
                        row[field] = previous[field]
                # A themed pack's card list, as the creator wrote it (cards since gone are dropped).
                if "cards" in previous and row.get("kind") == "Pack":
                    row["cards"] = [c for c in previous["cards"] if any(c == card["key"] for card in cards)]
                continue
            while nxt in used:
                nxt += 1
            if nxt >= high:
                sys.exit(f"block {args.block} is full ({low}-{high - 1})")
            row["id"] = nxt
            used.add(nxt)
        gone = sorted(set(old_by_key) - {r["key"] for r in rows})
        if gone:
            notes.append(f"no longer in the dump (their IDs stay retired): {', '.join(gone)}")
        rows.sort(key=lambda r: r["id"])

    # Nested (the user's layout, 2026-11-15): cards by kind then clan, items by kind, battles and challenges.
    def nest(rows: list, outer, inner=None) -> dict:
        out: dict = {}
        for row in rows:
            row = dict(row)
            group = out.setdefault(row.pop(outer) if outer in row else outer, {} if inner else [])
            if inner:
                group.setdefault(row.pop(inner), []).append(row)
            else:
                group.append(row)
        return out

    sections = {"Companion": "companions", "Item": "items", "Charm": "charms"}
    card_tree = nest([{**c, "kind": sections[c["kind"]]} for c in cards], "kind", "clan")
    doc = {"format": 1, "mod": args.mod, "guid": guid, "version": args.version, "id_block": args.block,
           "cards": {s: card_tree[s] for s in sections.values() if s in card_tree},
           "ap_items": nest(items, "kind"),
           "ap_locations": {**{section: [loc for loc in locations if loc["key"].startswith(prefix) and not loc["key"].endswith("#2")]
                               for section, prefix in (("battles", "battle:"), ("challenges", "challenge:"))
                               if any(loc["key"].startswith(prefix) for loc in locations)},
                            "spares": {loc["key"][:-2]: loc["id"] for loc in locations if loc["key"].endswith("#2")}},
           "bells": bells, "groups": groups, "removes": removes}
    out.write_text(gen_data.dump_json(doc), encoding="utf-8")

    unruled = [loc["key"] for loc in locations if loc["key"].startswith("challenge:") and not loc.get("rule")]
    print(f"wrote {out}: {len(cards)} cards, {len(items)} items "
          f"({sum(1 for i in items if i['kind'] == 'Pack')} packs), {len(locations)} locations, {len(bells)} storm bells"
          + (f", removes {', '.join(f'{len(v)} {k}' for k, v in removes.items())}" if removes else ""))
    checks = sum(1 for loc in locations if not loc["key"].endswith("#2"))
    if len(items) > checks:
        # Spare "#2" checks and fuller packs make room in a seed, but they're a fallback: challenges for the
        # mod's content are better (the user, 2026-11-15).
        notes.append(f"{len(items)} items but {checks} checks: consider adding challenges for this mod's content; "
                     "until then seeds make room with spare '#2' checks and, past those, fuller packs")
    if unruled:
        notes.append(f"challenges with no rule yet (in logic from the start): {', '.join(unruled)}")
    for note in notes:
        print("note:", note)


if __name__ == "__main__":
    main()
