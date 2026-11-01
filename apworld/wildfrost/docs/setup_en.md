# Wildfrost Setup Guide

## Required software

- Wildfrost (Steam), launched in its modded mode
- The Wildfrost Archipelago mod

## Installation

1. Put the mod folder in `Wildfrost/Modded/Wildfrost_Data/StreamingAssets/Mods/archipelago`.
2. Start Wildfrost in modded mode and enable the "Archipelago" mod.

## Connecting

Press **Play** on the main menu. If the mod isn't connected yet, it asks for the server (for example
`archipelago.gg:12345`), your slot name and the room password, then connects and starts the game on a save profile of
that seed's own. **Play without Archipelago** plays your normal profile instead.

The settings are remembered in `config.cfg` in the mod folder (the Mods screen's folder button opens it), with a copy
in the `Archipelago` folder next to Wildfrost's saves so a mod update can't reset them, and the mod connects with them
by itself the next time the game starts. If the connection drops while you play, the mod
reconnects by itself, and checks you make meanwhile are sent once it's back.

The overlay in the top left corner shows the connection status and messages. F7 hides it, F9 reconnects. Press
Enter to type: `!help` and other `!` commands go to the server, other text is chat, and `/connect`, `/disconnect` and
`/help` are local commands.
