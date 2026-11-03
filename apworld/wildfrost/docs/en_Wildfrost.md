# Wildfrost

## Where is the options page?

The [player options page for this game](../player-options) contains all the options you need to configure and export a
config file.

## What does randomization do to this game?

Wildfrost's own unlocks are replaced. Every card, companion, charm, pet and tribe that can show up in a run comes from
the multiworld, and anything you haven't received yet is removed from rewards, shops and events. Nothing is unlocked at
the start: companions and items arrive in packs of 3 from one clan (which cards a pack holds changes per seed), and
charms one by one, each named for itself (for example "Greed Charm"). Until you have a card
of some kind, the map nodes that would offer that kind give 1 Bling instead.

## What is the goal of Wildfrost when randomized?

Win with your clans (Snowdwellers, Shademancers and Clunkmasters). The **Goal** option sets what a win is:

- **Win Each Clan:** win a run.
- **True Final Boss Each Clan:** beat the True Final Boss, which needs 10 storm points of storm bells (the default).
- **Overcranked Each Clan:** beat the True Final Boss on an Overcranked run (every bell on).

**Clans Required** (1 to 3, default 1) sets how many clans need such a win. The default finishes the seed with one
win against the True Final Boss.

The run that completes the last clan finishes the seed.

## What counts as a location check?

- **Battles:** winning each distinct battle in each area with each tribe, for example "Area 2 Battle - The Demonhorn
  Goats (Shademancers)". The battles you meet change from run to run, so finding them all takes several runs.
- **Bosses:** defeating each area's possible bosses. Each boss gives two checks ("... #2"), and so does every challenge
  that unlocks a charm in the base game (Sunbringer, beating the True Final Boss, among them).
- **Challenges:** completing any of the game's challenges. Gnomebringer only ever holds filler (it's too much luck),
  and so does Sunbringer when your goal is a plain win or a single True Final Boss win. They are all active from the start rather than unlocking in
  a chain.

Logic expects no cards for the first five fights of a run (two battles, the first boss, two more battles). From the
second boss on, a clan is expected to have at least one companion pack and either one item pack or six charms. Only
General packs and charms and that clan's own count. The True Final Boss expects two companion and two item packs and
three charms plus six storm bells. An Overcranked win expects two companion and three item packs and six charms plus all
seven bells. Force Storm Bells and Force Overcrank each add one more companion or item pack, or three more charms, to all
of these.

Some challenges expect particular cards, from the pack that holds each one in your seed, and a tribe that can play
them: Tough Nut a Shell card (Kernel, Shelly, Shell Shield or Shellbo), Rampage a Frenzy card (Blaze Bom, Tiny Tyko or
Mini Mika), Icemaster Ice Dice or Blunky, Toxic two Shroom cards, Ritual the Shademancers and two sacrifice cards (Snuffer
Mask, Yeti Skull, Azul Skull, Chikichi, The Baker or Groff), and Kill 10 enemies with Teeth the Spike pet or a Shademancer
Teeth card (Tiger Skull, Tigris Mask, Taiga or Tusk). Kill 3 Demonized enemies expects the Loki pet, the Goat Charm, Demonheart, Dimona or Totem of the
Goat. Add 3 Clunkers to your deck expects a Clunker card, and Add 10
Scrap to Clunkers the Clunkmasters as well (Block 10 hits with Clunkers only needs the Snowdwellers, who start with
Woodhead). Summon 50 allies expects the Shademancers, and One Punch a Snowdweller win. Berry Good expects Pinkberry Juice, Snowball Fight
Snowcake, Bigger Hitter
Spice Stones, and Big Hitter a pair that hits hard together: Pepper Flag with Pyra, Spice Stones or Peppereaper, Chikichi
with Monch or Devicro, or Chompom with a Shell card. Minimalist expects Toaster or a run that reaches the Gunk Bugs. Beastmaster
and Long Live the King expect a companion pack and an item pack, and Achieve a 6x Kill Combo two companion
packs and an item pack or three charms. Hoarder (12 cards in hand) expects the Clunkmasters, whose leaders can trash, and one of: Lupa, the Pinch or Gear
Charm, the Sneezle pet, Lumin Ring with Folby, something that gives the leader Frenzy (Blaze Bom, Moko Charm or Blaze
Tea), the Punchfist Charm, or Bom Barrel with the Cake or Frenzy Charm. Equip 10 Charms expects one charm that one of your tribes can use, and Buy 5 discounted items two item packs (three
with Force Storm Bells or Force Overcrank, four with both).

You start with one tribe, chosen by the **Starting Tribe** option (random by default); the other two are items, and
each tribe's battles and wins need its tribe. Some battles also only appear once you have the Shademancers or
Clunkmasters tribe. With a True Final Boss goal, beating
the True Final Boss with each tribe is a check too.

Daily Voyages are switched off while you play an Archipelago slot, since their deck of the day isn't the multiworld's.

On the map, a battle whose check you haven't sent yet with this run's tribe has an orange dot at its top right, and
hovering any battle says whether its check was sent.

## Which items can be in another player's world?

Card packs (3 companions or items of one clan: General, Snowdweller, Shademancer or Clunkmaster), every charm on its own, the pets, the two tribes you don't start with, and the
map events the miner unlocks in vanilla (the Charm Merchant, Shade Sculptor and Gnome Traveller), and the Progressive Storm Bells.

Storm bells no longer unlock by winning. The first Progressive Storm Bell unlocks them with a 5 storm point limit, the
next five raise it to 10 (enough for the True Final Boss), and the seventh unlocks Overcrank. The **Extra Storm Bells**
option (1 by default) adds spare copies so the ones you need turn up sooner. With **Force Storm Bells** on, a run won't start until
the bells you've rung add up to your current storm point limit (at most 10; it never makes you Overcrank). With
**Force Overcrank** on, once you have the seventh bell a run won't start until the Overcrank lever is pulled. Both only
force the bells your packs can carry: a run's tribe needs the packs logic expects for a win at that strength (counting
General packs and the tribe's own), so a seed that hands out bells early doesn't make the first fights unwinnable.

## Do I start with a pet?

Yes, one of the seven at random, Snoof (vanilla's always-there pet) included. The other six are items in the
multiworld.

## Can I pick my leader?

With **Leader Reroll** on (the default), the leader select screen has a button under the leaders, or R, that deals new
ones, as often as you like. Handy for a check that needs a particular kind of leader.

## Can the game run faster?

With **Game Speed Up** on (it's off by default), F6 speeds the game up to 1.5x or 2x while you play this slot.

## What does DeathLink do?

With **DeathLink** on, losing a run sends a death to everyone else with DeathLink. When a death arrives, your leader
flees: the current battle is lost and the run ends, with a message naming who died. A death that arrives outside a
battle waits for the next battle of the run; one that arrives outside a run is ignored.

## What are the filler items?

**Bling** gives 25-50 Bling. Boons help in your next battle: Slapcrackers on an enemy row (1 damage, 4 times), Pinkberry
Juice on one of your units (+4 health), Demonize on an enemy, or killing an enemy that isn't a boss. With **Trap
Percentage** above 0 (it's 10 by default), some filler is traps instead: losing 25-50 Bling, Slapcrackers on one of your rows, a Berry Bell
for an enemy row (+1 health), Demonize on one of your units, or 1 Teeth for an enemy. Battle effects received outside a
battle wait for the next one.

## When the player receives an item, what happens?

The item is unlocked straight away. A pack's cards join the current run's rewards if your tribe can draw them, and every
later run's.
