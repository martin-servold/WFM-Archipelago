from BaseClasses import Tutorial
from worlds.AutoWorld import WebWorld


class WildfrostWebWorld(WebWorld):
    game = "Wildfrost"
    theme = "ice"
    bug_report_page = "https://github.com/martin-servold/WFM-Archipelago/issues"

    setup_en = Tutorial(
        "Multiworld Setup Guide",
        "A guide to setting up Wildfrost for Archipelago.",
        "English",
        "setup_en.md",
        "setup/en",
        ["fuko"],
    )

    tutorials = [setup_en]
