# Wildfrost Archipelago

Connects [Wildfrost](https://store.steampowered.com/app/1811990/Wildfrost/) to an [Archipelago](https://archipelago.gg)
multiworld randomizer. Your unlocks (cards, companions, charms, pets, tribes, storm bells and the miner's events) are
shuffled into a multiworld with other games. Winning battles, beating bosses and completing challenges sends items to
other players, and theirs send items to you.

Your normal save is never touched: each seed plays on a save profile of its own.

**Steam Workshop:** [Wildfrost Archipelago](https://steamcommunity.com/sharedfiles/filedetails/?id=3831295900)

## What you need

- Wildfrost, started in its Modded mode, with this mod subscribed in steam workshop and enabled on the Mods screen
- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.8 or newer, to generate a seed

## Playing

### 1. Install the APWorld

The mod folder contains `wildfrost.apworld`, which teaches Archipelago how to make Wildfrost seeds. It's also in this
repository's [`dist/`](dist/) folder. Open the mod folder from Wildfrost's Mods screen, or go to:

- Linux: `~/.steam/steam/steamapps/workshop/content/1811990/3831295900`
- Windows: `C:\Program Files (x86)\Steam\steamapps\workshop\content\1811990\3831295900`

If your Steam library is on another drive, start from that library's `steamapps` folder instead.

Double-click `wildfrost.apworld` to install it with the Archipelago Launcher, or copy it into Archipelago's
`custom_worlds` folder.

### 2. Make your options file

In the Archipelago Launcher, run **Generate Template Options**. Edit `Wildfrost.yaml` from the Templates folder (set
your slot name and options) and put it in Archipelago's `Players` folder along with the other players' files.

### 3. Generate and host

Run **Generate** from the Launcher. The website can't generate seeds with custom worlds, so generate on your computer,
then either upload the zip from the output folder at [archipelago.gg/uploads](https://archipelago.gg/uploads) to host a
room, or host it yourself with the Launcher's **Host**.

### 4. Connect

Press **Play** on Wildfrost's main menu. A popup asks for:

- **Server:** your room's address, for example `archipelago.gg:38281` (replace `<port>` with the port shown on your
  room page)
- **Slot name:** the name from your options file
- **Password:** only if the room has one

The mod remembers these and reconnects by itself next time. The popup opens on every Play: **Continue** carries on with
the seed you're connected to, and changing the settings and pressing **Connect** moves to another room. **Play without
Archipelago** plays your normal save instead.

## Options

- **Starting Tribe:** Snowdwellers, Shademancers, Clunkmasters or random. The other two are items.
- **Progression Direction:** Forward (the default): each Progressive Storm Bell raises the storm point limit by 2.
  Reverse: runs start Overcranked, each bell lowers the bells a run must start with, and the goal is the True Final
  Boss, which only comes on a run with no bells.
- **Goal:** Final Boss, True Final Boss (the default) or Overcranked True Final Boss
- **Goal Clans Required:** how many clans (1 to 3) need that win, each with a run of its own, to finish the seed
- **Extra Storm Bells:** spare Progressive Storm Bells, so the ones you need turn up sooner
- **Force Storm Bells Up To** (10 by default): runs must start with as many storm points as you've unlocked, up to
  this number, as far as the tribe's packs carry it. 22 also makes every run Overcranked once Overcrank is unlocked;
  0 turns it off.
- **Trap Percentage:** how much filler is traps instead of Bling and boons
- **Game Speed Up:** lets F6 speed the game up (1.5x or 2x)
- **Leader Reroll:** a button (or R) on the leader select screen rerolls the leaders, as often as you like
- **Disable Possessed Final Boss** (off by default): the Final Boss always fights with its own deck, not your last
  winning deck
- **DeathLink:** losing a run kills the other DeathLink players, and theirs makes your leader flee
- **Death Link Damage Percent** (100 by default): a received death takes this share of your leader's max health in
  the next battle instead, plus a Gunk Fruit in your deck for the run if it survives; 100 makes it flee

The full game page, with what counts as a check and what logic expects, is
[`apworld/wildfrost/docs/en_Wildfrost.md`](apworld/wildfrost/docs/en_Wildfrost.md).

## In game

- Nothing is unlocked at the start except a tribe and a random pet. Companions and items arrive in packs of up to 3,
  charms one by one, and until you have a card of some kind, its map nodes give 1 Bling (hover a node to see).
- Battles whose check you haven't sent yet with this run's tribe have an orange dot on the map.
- The town's challenge stones show which challenges have sent their check.
- **F7** shows or hides the log, **F9** reconnects, and **Enter** opens chat (`!` commands go to the server). With Game
  Speed Up on, **F6** changes the speed.
- **H** opens a panel with your hints, the checks in logic now and what each pack holds (**Tab** switches, **PgUp**/
  **PgDn** pages).
- Daily Voyages are switched off while playing a seed.

## Building from source

The repository has two parts:

- `Wildfrost Archipelago/`: the client mod, a C# .NET Framework 4.7.2 library using Harmony and
  [Archipelago.MultiClient.Net](https://github.com/ArchipelagoMW/Archipelago.MultiClient.Net) (in `lib/`)
- `apworld/wildfrost/`: the Archipelago world

Build the mod with `dotnet build "Wildfrost Archipelago/Wildfrost Archipelago.csproj"`. The csproj references the
game's assemblies by absolute paths to a local Wildfrost install, so adjust its `HintPath`s to yours. The post-build
step copies the mod into the game's `Mods/archipelago` folder.

For the apworld, link or copy `apworld/wildfrost` into an Archipelago checkout's `worlds/` folder and run its tests
with `python -m pytest worlds/wildfrost`. `apworld/wildfrost/data.py` is generated by `tools/gen_data.py` from a
content dump the mod writes with `debug=true`. The dump comes from the game and isn't included here.

[`PLAN.md`](PLAN.md) records the design and the decisions behind it, and [`CHANGELOG.md`](CHANGELOG.md) what changed in each version.

## License

This project's own code and docs are [CC0 1.0](LICENSE). The bundled Archipelago.MultiClient.Net library and the
icon's artwork (Wildfrost's Noomlin and the Archipelago logo) keep their own terms: see [NOTICE.md](NOTICE.md).
