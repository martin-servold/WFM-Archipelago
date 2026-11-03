# Wildfrost Setup Guide

## Required software

- Wildfrost (Steam), launched in its modded mode
- The Wildfrost Archipelago mod

## Installation

1. Put the mod folder in `Wildfrost/Modded/Wildfrost_Data/StreamingAssets/Mods/archipelago`.
2. Start Wildfrost in modded mode and enable the "Archipelago" mod.

## Connecting

Press **Play** on the main menu. The mod asks for the server (for example `archipelago.gg:12345`), your slot name and
the room password, then connects and starts the game on a save profile of that seed's own. **Play without Archipelago**
plays your normal profile instead. It asks on every Play: once connected, Enter or **Continue** carries on, and changing
the settings and pressing **Connect** moves to another room (after a re-seed, or for another multiworld). Each seed
plays on its own profile with its own offline checks, so switching back and forth loses nothing. If you're
disconnected, the popup offers **Connect** first and **Continue offline** beside it; offline, your progress stays on
your computer, and your checks are sent when you reconnect (F9).

The settings are remembered in `config.cfg` in the mod folder (the Mods screen's folder button opens it), with a copy
in the `Archipelago` folder next to Wildfrost's saves so a mod update can't reset them, and the mod connects with them
by itself the next time the game starts. If the connection drops while you play, the mod
reconnects by itself, and checks you make meanwhile are sent once it's back.

The overlay in the top left corner shows the connection status and messages. F7 hides it, F9 reconnects. Press
Enter to type: `!help` and other `!` commands go to the server, other text is chat, and `/connect`, `/disconnect` and
`/help` are local commands.

H opens a panel at the top right; Tab switches its tabs. **Hints** lists hints for your items and for items you hold
for others. A new hint for an item someone else is waiting on opens it by itself. **Checks** counts the checks sent and
lists the ones in logic now (PgUp/PgDn for more). **Packs** shows what each pack holds this seed (PgUp/PgDn for the other packs), so you know
which one to `!hint`. [Universal Tracker](https://github.com/FarisTheAncient/Archipelago/releases) also works with
Wildfrost and can say what each check needs.

With the Game Speed Up option on, F6 speeds the game up (1x, 1.5x, 2x) while you play your
Archipelago profile.
