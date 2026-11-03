from BaseClasses import LocationProgressType
from test.bases import WorldTestBase

from ..items import PROGRESSION_PETS
from ..world import WildfrostWorld


class WildfrostTestBase(WorldTestBase):
    """
    Tests start as Snowdwellers unless they say otherwise (the option's default is random), on a plain
    win with each clan, no extra bells and no traps: the shortest logic to reason about. The defaults
    themselves are tested in TestDefaults. The starting pet
    is always random, so a Spike, Loki or Sneezle one is taken out of the test state: logic counts those three, and the
    card challenge tests would pass or fail by seed. Which pet a seed starts with is checked through
    precollected_items.
    """

    game = "Wildfrost"
    world: WildfrostWorld
    options = {"starting_tribe": "snowdwellers", "goal": "win_each_clan", "clans_required": 3,
               "extra_storm_bells": 0, "trap_percentage": 0}

    def world_setup(self, *args, **kwargs) -> None:
        super().world_setup(*args, **kwargs)
        for item in self.multiworld.precollected_items.get(self.player, []):
            if item.name in PROGRESSION_PETS:
                self.multiworld.state.remove(item)

    def assert_filler_only(self, challenge: str, filler_only: bool) -> None:
        """Whether a challenge's two checks are excluded (filler only)."""
        for name in (f"Challenge - {challenge}", f"Challenge - {challenge} #2"):
            with self.subTest(location=name):
                location = self.multiworld.get_location(name, self.player)
                self.assertEqual(location.progress_type == LocationProgressType.EXCLUDED, filler_only)
