# Changelog

## 0.3.0 (2026-11-07)

Install the new `wildfrost.apworld` to make seeds with the new options. Seeds made with 0.2.x still work with this version of the mod, with their old settings, and yamls written for 0.2.x still generate. Their `force_storm_bells` and `force_overcrank` lines are ignored with a warning, so they get Force Storm Bells Up To's default of 10: set `force_storm_bells_up_to` instead (0 for off).

- **Storm bells in steps of 2:** there are 11 Progressive Storm Bells instead of 7. Each one raises the storm point limit by 2 (2, 4, ... 20, past vanilla's 10), and the 11th unlocks Overcrank. The True Final Boss needs 5 (10 points). In Reverse, each bell lowers the floor by 2, from Overcranked through 20, 18, ... 2 to none. Seeds made before this keep the old 7 steps.
- **Force Storm Bells Up To** (new option, 10 by default) replaces Force Storm Bells and Force Overcrank: runs must start at your storm point limit, up to this number. 22 also forces Overcrank, and 0 turns it off. It's now on by default. Higher levels are only forced once your packs carry them: one more pack from 4 storm points, two more from 14. Seeds made before this keep their old settings.
- **Reverse Storm Bells** (new option, Progression Direction: Reverse): runs start Overcranked, and each Progressive Storm Bell lowers the bells a run must start with, down to none; the bell board shows that floor as "Storm Strength Minimum". The True Final Boss only comes on a run with no bells, and it's the goal. The logic was tuned from playtests.
- **Options renamed and reordered:** the Goal choices are now Final Boss, True Final Boss and Overcranked True Final Boss (how many clans is Goal Clans Required, formerly Clans Required). Starting Tribe and Progression Direction come first. yamls with the old names still work.
- **Death Link Damage Percent** (new option, 100 by default): a received death takes this share of your leader's max health in your next battle, and only makes it flee if that takes it to 0. A death your leader survives also adds a Gunk Fruit to your deck for the rest of the run (and to your hand in a battle). 100 is the old flee, 0 no damage. Several deaths arriving together now each count.
- **Disable Possessed Final Boss** (new option, off by default): the Final Boss always fights with its default deck instead of your last winning deck.
- **Possessed Final Boss companions:** after a win, the base game stops offering the companions in your winning deck while they're on the boss. Seeds no longer do that, so every companion you have the pack for can turn up.
- **Fix:** Reroll leaders is hidden while a leader is picked, where rerolling jumbled the cards, and while the storm bell window is open.
- **Fix:** the Final Boss's reward bells could repeat bells offered or taken at an earlier boss. It now picks its rewards when you enter it, like the other bosses.
- **Checks tab:** a check and its "#2" twin (bosses, charm challenges) share one line, marked "(2 checks)".
- **Run summary:** each run ends with a line in the log: the bells, the packs and charms the tribe had, and how far it got.
- **Logic:** Kill 15 enemies with Shroom and Apply 60 Shell need Snowdwellers, whose leaders bring Shroom and Shell. Use Smackback to kill 20 enemies needs Snowdwellers or Shademancers (Clunkmaster leaders have no Smackback), Gojiber or the Punchfist Charm.
- **Back To Town:** the pause menu has a Back To Town line during a run. It keeps the run saved, like Back To Menu.
- **Map battles:** battles you haven't checked yet are twice as likely to come up on the map.
- **Mods:** turning mods on or off while playing a seed also saves them to your own profile, so they stay that way on the next launch.

## 0.2.1 (2026-11-04)

Seeds made with 0.2.0 still work, and the 0.2.0 `wildfrost.apworld` is still current.

- **Fixes:**
  - A crash when connecting to a seed you'd already played and receiving items.
  - Pressing Enter to continue on the connect popup left the popup open in town.

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
