# CLAUDE.md

This is a Wildfrost mod that integrates the game with Archipelago, a multiworld randomizer. It has two parts: the C# client mod (`Wildfrost Archipelago/`) and the Python apworld (`apworld/wildfrost/`). The design and milestones are in `PLAN.md`, and that file is the source of truth for decisions.

## Build

```
dotnet build "Wildfrost Archipelago/Wildfrost Archipelago.csproj"
```

The project setup is the same as `../WFM-Companion-Start/`: an old-style net472 csproj, game references through absolute HintPaths, and a `PostBuild.ps1` deploy into the game's `StreamingAssets/Mods/archipelago`. Read that project's CLAUDE.md for the build and deploy caveats. The differences here:
- `lib/Archipelago.MultiClient.Net.dll` (NuGet 6.7.0, net45) is committed. PostBuild copies it next to the mod DLL, and the game's mod Bootstrap resolves it by assembly name.
- Newtonsoft.Json is **not** shipped. The mod binds to the game's own 13.0 copy.
- PostBuild also mirrors the solution into the mod's `Source` folder (without bin, obj, .vs, .git, dist, data or `__pycache__` at any depth, nor CLAUDE.md and `Steam Workshop Page.txt`) and copies `dist/*.apworld` to the mod root. Building the .csproj directly leaves `$(SolutionDir)` undefined, so the csproj falls back to the folder above the project.
- Release: build, package the apworld into `dist/` (below), then run `python3 -I tools/prepare_release.py`. It strips the deployed folder to what ships (removing config.cfg with the local settings, survey.log and content_dump.txt) and says when it's ready. **The mod always ships with the default settings** (the user's rule), so the script also sets aside the settings copy in the game's save folder (`Archipelago/connection.txt`), which the mod would otherwise restore into config.cfg at game start. Then publish from the game's Mods screen, which uploads that folder as it is, and run `python3 -I tools/prepare_release.py --restore` to put the local settings back.
- The settings (server, slot, password, debug, speed) are `[ConfigItem]` fields on `ArchipelagoMod`, kept in the game's per-mod `config.cfg` in the deployed mod folder. The game only ever writes that file with the defaults, so `ConnectionConfig.Save` writes it in the game's format. An old `connection.txt` is moved over once. Every Play opens the connect popup (`ConnectPopup`). `debug=true` turns on F8, F10, the survey log and the content dump that `tools/gen_data.py` needs.

## Local AP server

The reference clone is `../Archipelago/`, with a Python 3.13 venv at `.venv` (system Python 3.14 is too new). Generate a seed, then serve it:
```
cd ../Archipelago
.venv/bin/python Generate.py --player_files_path <dir with yaml> --outputpath <out>
.venv/bin/python MultiServer.py --port 38281 <out>/AP_*.zip
```

## Threading rule

MultiClient.Net callbacks run on socket threads. They may only enqueue to `ArchipelagoClient`, which drains its queue on the main thread from `ArchipelagoOverlay.Update`. Never touch Unity or game state inside a callback.

## AP mode

The client only applies AP rules while this slot's own profile, `Archipelago_<slot>_<seed>`, is loaded (`ApMode.Active`). Every patch, and every check sent, must check `ApMode.Active` first so the player's own profiles stay vanilla. Profile switches go through `ProfileSwitch.SetProfile`, which reloads the game systems that cache save data. See PLAN.md §2a for why.

## APWorld

- `apworld/wildfrost/` is symlinked to `../Archipelago/worlds/wildfrost`. Run the tests from `../Archipelago` with `.venv/bin/python -m pytest -p no:cacheprovider worlds/wildfrost` (and `test/general` for AP's cross-world checks).
- Package with Archipelago's own builder (it adds the `version`/`compatible_version` manifest fields; never write those by hand), then copy the result to `dist/`:
  ```
  cd ../Archipelago && .venv/bin/python Launcher.py "Build APWorlds" -- --skip_open_folder Wildfrost
  cp build/apworlds/wildfrost.apworld ../WFM-Archipelago/dist/
  ```
  Versions are `final.apworld.mod` (the user's scheme): the first number marks final releases, the second is the apworld version and the third a non-breaking mod update. Bump `world_version` in `apworld/wildfrost/archipelago.json` only when the apworld changes, and keep the client's first two numbers equal to it (client 0.2.1 goes with apworld 0.2.0).
- `apworld/wildfrost/data.py` is generated. After the game writes a new `content_dump.txt` (on every mod load with `debug=true` in config.cfg), copy it to `data/` and run `python3 -I tools/gen_data.py`. IDs are frozen: existing keys keep their ID, and new ones are appended. Never renumber.
- Locations and items are matched by **key** (`battle:<areaIndex>:<BattleData>:<ClassData>`, `challenge:<ChallengeData>`, `card:<CardData>`, ...), which `fill_slot_data` sends to the client. Display names can change without breaking the client.
