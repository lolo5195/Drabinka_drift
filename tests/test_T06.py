"""T-06: match resolution, walkovers, podium flow, and corrections."""

from copy import deepcopy

from logic.bracket import create_bracket, set_winner
from models import Driver, Match, QualificationResult, TournamentBracket


def _make_main_standings(count: int) -> list[QualificationResult | None]:
    """Create a seed-ordered ranking and pad missing places to TOP32."""
    standings: list[QualificationResult | None] = [
        QualificationResult(
            driver=Driver(id=seed, name=f"Driver {seed}"),
            run1=101 - seed,
            run2=0,
        )
        for seed in range(1, count + 1)
    ]
    standings.extend([None] * (32 - count))
    return standings


def _driver_at_seed(
    standings: list[QualificationResult | None],
    seed: int,
) -> Driver:
    """Return a populated seed used by an assertion."""
    result = standings[seed - 1]
    assert result is not None
    return result.driver


def _higher_seed_side(match: Match) -> str | None:
    """Choose the existing driver with the lower, therefore better, seed."""
    if match.slot_top is None and match.slot_bottom is None:
        return None
    if match.slot_top is None:
        return "bottom"
    if match.slot_bottom is None:
        return "top"
    return "top" if match.slot_top.id < match.slot_bottom.id else "bottom"


def _play_match_if_possible(
    bracket: TournamentBracket,
    match_id: str,
) -> None:
    """Resolve a populated match and leave a None-vs-None match untouched."""
    side = _higher_seed_side(bracket.matches[match_id])
    if side is not None:
        set_winner(bracket, match_id, side)


def _play_round(
    bracket: TournamentBracket,
    round_name: str,
    match_count: int,
) -> None:
    for match_number in range(1, match_count + 1):
        _play_match_if_possible(
            bracket,
            f"{round_name}_{match_number}",
        )


def _finish_higher_seed_tournament(bracket: TournamentBracket) -> None:
    """Resolve every possible match, including walkovers and the podium."""
    for round_name, match_count in (
        ("T32", 16),
        ("T16", 8),
        ("T8", 4),
        ("T4", 2),
    ):
        _play_round(bracket, round_name, match_count)

    _play_match_if_possible(bracket, "FINAL")
    _play_match_if_possible(bracket, "PLAYOFF")


# --- DoD 1 and 2: full flow through FINAL, PLAYOFF, and podium ---

def test_higher_seed_wins_full_tournament():
    standings = _make_main_standings(32)
    bracket = create_bracket(standings)

    for round_name, match_count in (
        ("T32", 16),
        ("T16", 8),
        ("T8", 4),
        ("T4", 2),
    ):
        _play_round(bracket, round_name, match_count)

    final = bracket.matches["FINAL"]
    playoff = bracket.matches["PLAYOFF"]
    assert final.slot_top is _driver_at_seed(standings, 1)
    assert final.slot_bottom is _driver_at_seed(standings, 2)
    assert playoff.slot_top is _driver_at_seed(standings, 4)
    assert playoff.slot_bottom is _driver_at_seed(standings, 3)

    _play_match_if_possible(bracket, "FINAL")
    _play_match_if_possible(bracket, "PLAYOFF")

    assert bracket.podium[1] is _driver_at_seed(standings, 1)
    assert bracket.podium[2] is _driver_at_seed(standings, 2)
    assert bracket.podium[3] is _driver_at_seed(standings, 3)
    assert bracket.podium[4] is _driver_at_seed(standings, 4)


def test_semifinal_losers_fill_correct_playoff_slots():
    standings = _make_main_standings(32)
    bracket = create_bracket(standings)
    for round_name, match_count in (
        ("T32", 16),
        ("T16", 8),
        ("T8", 4),
    ):
        _play_round(bracket, round_name, match_count)

    _play_match_if_possible(bracket, "T4_1")
    assert (
        bracket.matches["PLAYOFF"].slot_top
        is _driver_at_seed(standings, 4)
    )
    assert bracket.matches["PLAYOFF"].slot_bottom is None

    _play_match_if_possible(bracket, "T4_2")
    assert (
        bracket.matches["PLAYOFF"].slot_bottom
        is _driver_at_seed(standings, 3)
    )


# --- DoD 3: None clicks, walkovers, and repeated clicks ---

def test_none_click_is_noop_and_walkover_advances_driver():
    standings = _make_main_standings(28)
    bracket = create_bracket(standings)

    before_none_click = deepcopy(bracket)
    set_winner(bracket, "T32_1", "bottom")
    assert bracket == before_none_click

    set_winner(bracket, "T32_1", "top")
    assert bracket.matches["T32_1"].winner is _driver_at_seed(standings, 1)
    assert (
        bracket.matches["T16_1"].slot_top
        is _driver_at_seed(standings, 1)
    )

    before_repeated_click = deepcopy(bracket)
    set_winner(bracket, "T32_1", "top")
    assert bracket == before_repeated_click


def test_ten_driver_bracket_reaches_complete_podium():
    standings = _make_main_standings(10)
    bracket = create_bracket(standings)

    _finish_higher_seed_tournament(bracket)

    # T32_2 starts as None vs None, while T32_1 is a walkover.
    assert bracket.matches["T32_2"].winner is None
    assert bracket.matches["T32_1"].winner is _driver_at_seed(standings, 1)
    assert bracket.podium[1] is _driver_at_seed(standings, 1)
    assert bracket.podium[2] is _driver_at_seed(standings, 2)
    assert bracket.podium[3] is _driver_at_seed(standings, 3)
    assert bracket.podium[4] is _driver_at_seed(standings, 4)


# --- DoD 4: a correction removes only dependent results ---

def test_t32_correction_clears_path_and_preserves_independent_matches():
    standings = _make_main_standings(32)
    bracket = create_bracket(standings)
    _finish_higher_seed_tournament(bracket)

    independent_ids = ("T32_2", "T16_2", "T8_2", "T4_2")
    independent_before = {
        match_id: deepcopy(bracket.matches[match_id])
        for match_id in independent_ids
    }

    # Seed 32 replaces seed 1 as the winner of the opening match.
    set_winner(bracket, "T32_1", "bottom")

    assert bracket.matches["T32_1"].winner is _driver_at_seed(
        standings,
        32,
    )
    assert bracket.matches["T16_1"].slot_top is _driver_at_seed(
        standings,
        32,
    )
    for match_id in ("T16_1", "T8_1", "T4_1", "FINAL", "PLAYOFF"):
        assert bracket.matches[match_id].winner is None

    # Slots supplied by independent matches remain available for a replay.
    assert bracket.matches["T16_1"].slot_bottom is _driver_at_seed(
        standings,
        16,
    )
    assert bracket.matches["T8_1"].slot_bottom is _driver_at_seed(
        standings,
        8,
    )
    assert bracket.matches["T4_1"].slot_bottom is _driver_at_seed(
        standings,
        4,
    )
    assert bracket.matches["FINAL"].slot_top is None
    assert bracket.matches["FINAL"].slot_bottom is _driver_at_seed(
        standings,
        2,
    )
    assert bracket.matches["PLAYOFF"].slot_top is None
    assert bracket.matches["PLAYOFF"].slot_bottom is _driver_at_seed(
        standings,
        3,
    )
    assert bracket.podium == {1: None, 2: None, 3: None, 4: None}

    for match_id, old_match in independent_before.items():
        assert bracket.matches[match_id] == old_match


def test_correction_clears_result_when_changed_driver_had_lost():
    standings = _make_main_standings(32)
    bracket = create_bracket(standings)

    set_winner(bracket, "T32_1", "top")
    set_winner(bracket, "T32_2", "top")
    # Seed 16 wins T16_1, so seed 1 is the participant later removed.
    set_winner(bracket, "T16_1", "bottom")
    assert bracket.matches["T8_1"].slot_top is _driver_at_seed(
        standings,
        16,
    )

    set_winner(bracket, "T32_1", "bottom")

    assert bracket.matches["T16_1"].winner is None
    assert bracket.matches["T16_1"].slot_top is _driver_at_seed(
        standings,
        32,
    )
    assert bracket.matches["T16_1"].slot_bottom is _driver_at_seed(
        standings,
        16,
    )
    assert bracket.matches["T8_1"].slot_top is None
