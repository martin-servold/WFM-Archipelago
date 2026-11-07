from dataclasses import dataclass

from Options import Choice, DeathLink, DefaultOnToggle, PerGameCommonOptions, Range, Toggle


class Goal(Choice):
    """
    The win each clan needs. Goal Clans Required sets how many clans (Snowdwellers, Shademancers, Clunkmasters) need
    it, each with a run of its own; the run that completes the last one ends the seed.
    Final Boss: win a run.
    True Final Boss: beat the True Final Boss (10 storm points of bells).
    Overcranked True Final Boss: beat the True Final Boss on an Overcranked run (every bell).
    """

    display_name = "Goal"
    option_final_boss = 0
    option_true_final_boss = 1
    option_overcranked_true_final_boss = 2
    # The names before 0.3.0, so older yamls still generate.
    alias_win_each_clan = 0
    alias_true_final_boss_each_clan = 1
    alias_overcranked_each_clan = 2
    # One 10-bell win (with Goal Clans Required 1) by default (the user's call, 2026-11-02).
    default = 1


class ClansRequired(Range):
    """
    How many clans need the Goal's win, each with a run of its own, to finish the seed. Fewer makes the stretch from
    getting every Storm Bell to the end shorter.
    """

    display_name = "Goal Clans Required"
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
    Progressive Storm Bells beyond the 11 levels (storm point caps 2, 4, ... 20, then Overcrank).
    Extras make the ones the goal needs turn up sooner.
    """

    display_name = "Extra Storm Bells"
    range_start = 0
    range_end = 7
    default = 1


class ProgressionDirection(Choice):
    """
    Which way the Progressive Storm Bells take your runs.
    Forward: runs start with no storm bells, and each Progressive Storm Bell raises the cap by 2 storm points (2, 4, ...
    20; 10 reaches the True Final Boss), and the last unlocks Overcrank.
    Reverse: runs start Overcranked, and each Progressive Storm Bell lowers the bells a run must start with: Overcranked,
    20, 18, ... 2 storm points, then no bells. A run may ring more than that. The True Final Boss only comes on a
    run with no bells, so the goal is the True Final Boss with Goal Clans Required clans, and Force Storm Bells Up To
    is ignored.
    """

    display_name = "Progression Direction"
    option_forward = 0
    option_reverse = 1
    # The name before 0.3.0, so older yamls still generate.
    alias_normal = 0
    default = 0


class ForceStormBellsUpTo(Range):
    """
    Runs must be played at your storm bell strength, up to this many storm points: a run won't start until the bells
    you've rung reach your storm point limit or this, whichever is lower, so each Progressive Storm Bell up to it makes
    all later runs harder. 22 also forces Overcrank: once you have every bell level, a run won't start until the
    Overcrank lever is pulled. 0 turns it off. Odd numbers count as the even number below. Only the bells a run's tribe
    has the packs for are forced (the packs logic expects for a win at that strength). Logic expects one more pack of
    any kind for every win, and one more again at 22. Ignored with Progression Direction: Reverse.
    """

    display_name = "Force Storm Bells Up To"
    range_start = 0
    range_end = 22
    # 10, the old Force Storm Bells' most, on by default (decided by the user 2026-11-06).
    default = 10


class LeaderReroll(DefaultOnToggle):
    """
    The leader select screen gets a button (or R) to reroll the leaders, as often as you like, to go for a check that
    needs a particular kind of leader. Off: the leaders are as dealt.
    """

    display_name = "Leader Reroll"


class DisablePossessedFinalBoss(Toggle):
    """
    After a win the game turns your winning deck into the next Final Boss fight (your old leader and companions,
    possessed). On: the Final Boss always fights with its default deck. Off: vanilla. Either way, the companions you
    have packs for can still be offered (vanilla holds back the ones on the possessed boss).
    """

    display_name = "Disable Possessed Final Boss"


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


class DeathLinkDamagePercent(Range):
    """
    With DeathLink on, how hard a received death hits: this percentage of your leader's max health, rounded up, at the
    next battle (units heal after every battle, so on the map it waits). If it takes the leader to 0, the leader flees
    and the battle is lost. A death your leader survives also adds a Gunk Fruit to your deck for the rest of the run
    (and to your hand in a battle). 100: every received death makes your leader flee straight away, ending the run.
    0: no damage, only the Gunk Fruit.
    """

    display_name = "Death Link Damage Percent"
    range_start = 0
    range_end = 100
    # 100, the leader fleeing, as before the option (DeathLink's usual meaning).
    default = 100


@dataclass
class WildfrostOptions(PerGameCommonOptions):
    starting_tribe: StartingTribe
    progression_direction: ProgressionDirection
    goal: Goal
    clans_required: ClansRequired
    extra_storm_bells: ExtraStormBells
    force_storm_bells_up_to: ForceStormBellsUpTo
    trap_percentage: TrapPercentage
    game_speed_up: GameSpeedUp
    leader_reroll: LeaderReroll
    disable_possessed_final_boss: DisablePossessedFinalBoss
    death_link: DeathLink
    death_link_damage_percent: DeathLinkDamagePercent
