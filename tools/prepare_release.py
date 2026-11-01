"""Clean the deployed mod folder for a Steam Workshop upload.

The Mods screen's Workshop button uploads the mod's folder as it is, so this removes what only
development and local play leave there: the survey log, the content dump, the old connection.txt
copy, config.cfg with the player's own server and settings, and an empty offline check queue folder. The game writes a fresh config.cfg
with the defaults the next time it loads the mod. What stays: the mod DLL, the client library, the
icon, wildfrost.apworld and the Source mirror (all put there by PostBuild).

Run after building, close the game first if you want the folder to stay clean until you publish:
    python3 -I tools/prepare_release.py
"""

import sys
from pathlib import Path

MOD_DIR = Path.home() / ".local/share/Steam/steamapps/common/Wildfrost/Modded/Wildfrost_Data/StreamingAssets/Mods/archipelago"
REMOVE = ["survey.log", "content_dump.txt", "connection.txt.old", "connection.txt", "config.cfg"]
EXPECTED = {"WildfrostArchipelago.dll", "Archipelago.MultiClient.Net.dll", "icon.png", "wildfrost.apworld", "Source"}


def main() -> int:
    if not MOD_DIR.is_dir():
        sys.exit(f"No mod folder at {MOD_DIR}")

    config = MOD_DIR / "config.cfg"
    if config.exists():
        print("config.cfg had (shown so it can be re-entered; the game rewrites the defaults):")
        for line in config.read_text(encoding="utf-8").splitlines():
            if not line.startswith("//") and line.strip():
                print("   ", line.split(" : ", 1)[-1])

    for name in REMOVE:
        path = MOD_DIR / name
        if path.exists():
            path.unlink()
            print("removed", name)

    # The offline check queue (one file per AP profile). Empty once everything was sent.
    pending = MOD_DIR / "pending"
    if pending.is_dir() and not any(pending.iterdir()):
        pending.rmdir()
        print("removed pending (empty)")

    present = {p.name for p in MOD_DIR.iterdir()}
    missing, extra = EXPECTED - present, present - EXPECTED
    for name in sorted(missing):
        print("MISSING", name, "(build the mod, and put the apworld in dist/ first)")
    for name in sorted(extra):
        print("unexpected", name, "(would be uploaded too)")
    print("ready to publish" if not missing and not extra else "not ready")
    return 1 if missing or extra else 0


if __name__ == "__main__":
    sys.exit(main())
