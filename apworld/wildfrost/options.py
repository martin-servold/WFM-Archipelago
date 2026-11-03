from dataclasses import dataclass

from Options import Choice, DeathLink, DefaultOnToggle, PerGameCommonOptions, Range, Toggle


class Goal(Choice):
    """
    What finishes the seed. Each clan (Snowdwellers, Shademancers, Clunkmasters) needs a winning run of its own, and
    the run that completes the last clan Clans Required asks for ends the seed.
    Win Each Clan: win a run with each clan.
    True Final Boss Each Clan: beat the True Final Boss (10 storm points of bells) with each clan.
    Overcranked Each Clan: beat the True Final Boss on an Overcranked run (every bell) with each clan.
    """

    display_name = "Goal"
    option_win_each_clan = 0
    option_true_final_boss_each_clan = 1
    option_overcranked_each_clan = 2
    # One 10-bell win (with Clans Required 1) by default (the user's call, 2026-11-02).
    default = 1


class ClansRequired(Range):
    """
    How many clans need a winning run (as the Goal describes it) to finish the seed. Fewer makes the stretch from
    getting every Storm Bell to the end shorter.
    """

    display_name = "Clans Required"
    range_start = 1
    range_end = 3
    default = 1


class StartingTribe(Choice):
    """
    The tribe you can play from the start. The other two tribes are items in the multiworld.
    """

    display_name = "Starting Tribe"
    option_snowdwellers = 0
    option_shademancers = 1
    option_clunkmasters = 2
    default = "random"


class ExtraStormBells(Range):
    """
    Progressive Storm Bells beyond the 7 levels (unlock the bells at 5 storm points, raise the cap to 10, Overcrank).
    Extras make the ones the goal needs turn up sooner.
    """

    display_name = "Extra Storm Bells"
    range_start = 0
    range_end = 7
    default = 1


class ForceStormBells(Toggle):
    """
    Every run must be played at your full storm bell strength: a run won't start until the bells you've rung add up to
    your current storm point limit, so each Progressive Storm Bell makes all later runs harder. Only the bells a run's
    tribe has the packs for are forced (the packs logic expects for a win at that strength). Logic expects one more pack
    of any kind for every win.
    """

    display_name = "Force Storm Bells"


class ForceOvercrank(Toggle):
    """
    Once you have every Progressive Storm Bell level (the 7th unlocks the Overcrank lever), a run won't start until the
    Overcrank lever is pulled. Off: the lever is there once you have it, but pulling it is up to you. Force Storm Bells
    only ever forces up to 10 storm points, not Overcrank. Only forced once a run's tribe has the packs logic expects
    for an Overcranked win. Logic expects one more pack of any kind for every win.
    """

    display_name = "Force Overcrank"


class LeaderReroll(DefaultOnToggle):
    """
    The leader select screen gets a button (or R) to reroll the leaders, as often as you like, to go for a check that
    needs a particular kind of leader. Off: the leaders are as dealt.
    """

    display_name = "Leader Reroll"


class GameSpeedUp(Toggle):
    """
    Lets F6 speed the game up (1.5x or 2x) while you play this slot. Off: the game always runs at normal speed.
    """

    display_name = "Game Speed Up"


class TrapPercentage(Range):
    """
    Percentage of filler items that are traps (losing Bling, Slapcrackers on your units, a Berry Bell for the enemy,
    Demonize on your unit, Teeth for an enemy). The rest of the filler is Bling and boons.
    """

    display_name = "Trap Percentage"
    range_start = 0
    range_end = 100
    default = 10


@dataclass
class WildfrostOptions(PerGameCommonOptions):
    goal: Goal
    clans_required: ClansRequired
    starting_tribe: StartingTribe
    extra_storm_bells: ExtraStormBells
    force_storm_bells: ForceStormBells
    force_overcrank: ForceOvercrank
    trap_percentage: TrapPercentage
    game_speed_up: GameSpeedUp
    leader_reroll: LeaderReroll
    death_link: DeathLink
