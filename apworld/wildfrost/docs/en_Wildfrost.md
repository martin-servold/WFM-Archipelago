# Wildfrost

## Where is the options page?

The [player options page for this game](../player-options) contains all the options you need to configure and export a
config file.

## What does randomization do to this game?

Wildfrost's own unlocks are replaced. Every card, companion, charm, pet and tribe that can show up in a run comes from
the multiworld, and anything you haven't received yet is removed from rewards, shops and events. Nothing is unlocked at
the start: cards arrive in packs of 3 from one clan, and which cards a pack holds changes per seed. Until you have a card
of some kind, the map nodes that would offer that kind give Bling instead.

## What is the goal of Wildfrost when randomized?

Win with each clan (Snowdwellers, Shademancers and Clunkmasters). The **Goal** option sets what a win is:

- **Win Each Clan:** win a run.
- **True Final Boss Each Clan:** beat the True Final Boss, which needs 10 storm points of storm bells.
- **Overcranked Each Clan:** beat the True Final Boss on an Overcranked run (every bell on).

The run that completes the last clan finishes the seed.

## What counts as a location check?

- **Battles:** winning each distinct battle in each area with each tribe, for example "Area 2 Battle - The Demonhorn
  Goats (Shademancers)". The battles you meet change from run to run, so finding them all takes several runs.
- **Bosses:** defeating each area's possible bosses.
- **Challenges:** completing any of the game's challenges. They are all active from the start rather than unlocking in
  a chain.

Logic expects no cards for the first five fights of a run (two battles, the first boss, two more battles). From the
second boss on, a clan is expected to have at least one companion pack and either one item pack or two charm packs. Only
General packs and that clan's own count. The True Final Boss expects two companion, two item and one charm pack plus six
storm bells. An Overcranked win expects two companion, three item and two charm packs plus all seven bells.

Some challenges expect particular cards, from the pack that holds each one in your seed, and a tribe that can play
them: Tough Nut a Shell card (Kernel, Shelly, Shell Shield or Shellbo), Rampage a Frenzy card (Blaze Bom, Tiny Tyko or
Mini Mika), Icemaster Ice Dice or Blunky, Toxic two Shroom cards, Ritual the Shademancers and two sacrifice cards (Snuffer
Mask, Yeti Skull, Azul Skull, Chikichi, The Baker or Groff), and Kill 10 enemies with Teeth the Spike pet or a Shademancer
Teeth card (Tiger Skull, Tigris Mask, Taiga or Tusk). Add 3 Clunkers to your deck expects a Clunker card, and Add 10
Scrap to Clunkers the Clunkmasters as well (Block 10 hits with Clunkers only needs the Snowdwellers, who start with
Woodhead). Summon 50 allies expects the Shademancers, and One Punch a Snowdweller win.

You start with one tribe, chosen by the **Starting Tribe** option (random by default); the other two are items, and
each tribe's battles and wins need its tribe. Some battles also only appear once you have the Shademancers or
Clunkmasters tribe. With a True Final Boss goal, beating
the True Final Boss with each tribe is a check too.

Daily Voyages are switched off while you play an Archipelago slot, since their deck of the day isn't the multiworld's.

On the map, a battle whose check you haven't sent yet with this run's tribe has an orange dot at its top right, and
hovering any battle says whether its check was sent.

## Which items can be in another player's world?

Card packs (3 items, companions or charms of one clan: General, Snowdweller, Shademancer or Clunkmaster), the pets, the two tribes you don't start with, and the
map events the miner unlocks in vanilla (the Charm Merchant, Shade Sculptor and Gnome Traveller), and the Progressive Storm Bells.

Storm bells no longer unlock by winning. The first Progressive Storm Bell unlocks them with a 5 storm point limit, the
next five raise it to 10 (enough for the True Final Boss), and the seventh unlocks Overcrank. The **Extra Storm Bells**
option adds spare copies so the ones you need turn up sooner. With **Force Storm Bells** on, a run won't start until
the bells you've rung add up to your current storm point limit (at most 10; it never makes you Overcrank). With
**Force Overcrank** on, once you have the seventh bell a run won't start until the Overcrank lever is pulled.

## What does DeathLink do?

With **DeathLink** on, losing a run sends a death to everyone else with DeathLink. When a death arrives, your leader
flees: the current battle is lost and the run ends, with a message naming who died. A death that arrives outside a
battle waits for the next battle of the run; one that arrives outside a run is ignored.

## What are the filler items?

**Bling** gives 25-50 Bling. Boons help in your next battle: Slapcrackers on an enemy row (1 damage, 4 times), Pinkberry
Juice on one of your units (+4 health), Demonize on an enemy, or killing an enemy that isn't a boss. With **Trap
Percentage** above 0, some filler is traps instead: losing 25-50 Bling, Slapcrackers on one of your rows, a Berry Bell
for an enemy row (+1 health), Demonize on one of your units, or 1 Teeth for an enemy. Battle effects received outside a
battle wait for the next one.

## When the player receives an item, what happens?

The item is unlocked straight away. A pack's cards join the current run's rewards if your tribe can draw them, and every
later run's.
