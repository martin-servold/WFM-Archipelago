from test.bases import WorldTestBase

from ..world import WildfrostWorld


class WildfrostTestBase(WorldTestBase):
    """Tests start as Snowdwellers unless they say otherwise (the option's default is random)."""

    game = "Wildfrost"
    world: WildfrostWorld
    options = {"starting_tribe": "snowdwellers"}
