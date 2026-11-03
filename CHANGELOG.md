# Changelog

## 0.2.0 (2026-11-03)

Seeds made with 0.1.0 don't work with this version. Generate a new seed with the new `wildfrost.apworld`.

### Options

- **New options:**
  - **Clans Required** (1 to 3): how many clans need the goal's win.
  - **Game Speed Up:** lets F6 run the game at 1.5x or 2x.
  - **Leader Reroll** (on by default): reroll the leaders as often as you like.
- **New defaults:** one True Final Boss win with one clan, 1 extra Storm Bell and 10% traps.
- **Random starting pet:** every seed starts with one of the 7 pets. Snoof is now a pet item like the others.

### Items and checks

- **Charms are separate items**, each named for its charm (61 in all). Charm packs are gone.
- **Second checks:** every boss and every charm-unlock challenge sends a second "#2" check, to make room for the charm items.
- **Filler only:** Gnomebringer always holds filler. Sunbringer holds filler when the goal is a plain win, or when only one clan is required, which includes the default.

### Logic

- **Charms count toward deck strength**, at 3 charms for each pack:
  - Final Boss: a companion pack, plus an item pack or 6 charms.
  - True Final Boss: 2 companion packs, 2 item packs and 3 charms.
  - Overcranked win: 2 companion packs, 3 item packs and 6 charms.
- **Force Storm Bells and Force Overcrank:**
  - Each adds one more pack, or 3 charms, to every win.
  - They only force the bells a tribe's packs can carry.
- **More challenge rules:**
  - These challenges now require the right cards: Berry Good, Snowball Fight, Big Hitter, Bigger Hitter, Hoarder, Minimalist and Kill 3 Demonized.
  - Beastmaster, Long Live the King and 6x Kill Combo need certain packs.
  - Equip 10 Charms needs one charm.
  - Buy 5 discounted items needs two item packs, more with a Force option.
- **Pets in logic:** Spike, Loki and Sneezle count toward logic.

### In game

- **Connect popup on every Play:**
  - Continue, Connect, Continue offline, or Play without Archipelago.
  - Switch to another seed from the main menu. Each seed keeps its own offline queue.
- **Offline play:**
  - A notice appears when you go offline or the connection is lost.
  - Checks made offline, including "#2" checks and the goal, are sent when you reconnect.
- **H panel tabs:**
  - Hints, which opens by itself when someone needs a hint from you.
  - The checks in logic now.
  - What each pack holds.
- **Rewards draw when you reach them:**
  - Reward nodes, shops and boss rewards pick their cards when you enter them, not when the map is made.
  - No card, charm or bell repeats within a run.
  - Nodes that will give Bling say so on the map.
- **Traps and boons:**
  - Effects stop when a battle ends or your leader dies, and the rest wait for the next battle.
  - Slapcrackers hits are spaced out, and a Slapcrackers counts once one of its hits lands.
  - Health effects skip Clunkers that only have Scrap.
- **Smaller changes:**
  - The end-of-run Town Progress panel is faster.
  - The pet house hides pets you haven't received, and the town flag shows the right pet.
  - Map nodes with nothing left to give hand out 1 Bling.
- **Fixes:**
  - A crash at the end of a battle when several traps landed at once.
  - A rare case that could lose queued checks.
  - "Goal complete!" no longer repeats on every reconnect.

## 0.1.0 (2026-10-31)

First release.
