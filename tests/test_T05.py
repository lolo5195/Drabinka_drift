"""T-05: create_bracket — TOP32 seeding and static match connections."""

from logic.bracket import SEED_PAIRS, create_bracket
from models import Driver, QualificationResult


EXPECTED_SEED_PAIRS: list[tuple[int, int]] = [
    (1, 32),
    (16, 17),
    (8, 25),
    (9, 24),
    (4, 29),
    (13, 20),
    (5, 28),
    (12, 21),
    (2, 31),
    (15, 18),
    (7, 26),
    (10, 23),
    (3, 30),
    (14, 19),
    (6, 27),
    (11, 22),
]


def _make_main_standings(count: int) -> list[QualificationResult | None]:
    """Create an ordered ranking and pad its missing places up to TOP32."""
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
    """Return a known populated seed and make that test assumption explicit."""
    result = standings[seed - 1]
    assert result is not None
    return result.driver


# --- Bracket structure and initial state ---

def test_create_bracket_builds_all_32_matches():
    bracket = create_bracket(_make_main_standings(32))

    expected_ids = (
        {f"T32_{number}" for number in range(1, 17)}
        | {f"T16_{number}" for number in range(1, 9)}
        | {f"T8_{number}" for number in range(1, 5)}
        | {"T4_1", "T4_2", "FINAL", "PLAYOFF"}
    )

    assert set(bracket.matches) == expected_ids
    assert len(bracket.matches) == 32
    assert all(match.winner is None for match in bracket.matches.values())
    assert bracket.podium == {1: None, 2: None, 3: None, 4: None}

    # Only TOP32 receives drivers while the next rounds wait for T-06.
    for match_id in expected_ids - {
        f"T32_{number}" for number in range(1, 17)
    }:
        assert bracket.matches[match_id].slot_top is None
        assert bracket.matches[match_id].slot_bottom is None


# --- DoD 1: exact TOP32 seed pairs ---

def test_create_bracket_uses_seed_pairs_from_plan():
    standings = _make_main_standings(32)
    bracket = create_bracket(standings)

    assert SEED_PAIRS == EXPECTED_SEED_PAIRS

    for match_number, (top_seed, bottom_seed) in enumerate(
        EXPECTED_SEED_PAIRS,
        start=1,
    ):
        match = bracket.matches[f"T32_{match_number}"]
        # Identity checks guarantee that matches keep Driver references.
        assert match.slot_top is _driver_at_seed(standings, top_seed)
        assert match.slot_bottom is _driver_at_seed(standings, bottom_seed)


# --- DoD 2: missing seeds 29–32 become four exact bottom slots ---

def test_create_bracket_with_28_drivers_places_missing_seeds_as_none():
    bracket = create_bracket(_make_main_standings(28))

    empty_slots = {
        (match_id, side)
        for match_id, match in bracket.matches.items()
        if match_id.startswith("T32_")
        for side, driver in (
            ("top", match.slot_top),
            ("bottom", match.slot_bottom),
        )
        if driver is None
    }

    assert empty_slots == {
        ("T32_1", "bottom"),
        ("T32_5", "bottom"),
        ("T32_9", "bottom"),
        ("T32_13", "bottom"),
    }


# --- DoD 3: regular rounds and the semifinal split are connected ---

def test_create_bracket_connects_regular_round_winners():
    matches = create_bracket(_make_main_standings(32)).matches

    for round_name, match_count, next_round in (
        ("T32", 16, "T16"),
        ("T16", 8, "T8"),
        ("T8", 4, "T4"),
    ):
        for match_number in range(1, match_count + 1):
            expected_target = (
                f"{next_round}_{(match_number + 1) // 2}",
                "top" if match_number % 2 == 1 else "bottom",
            )
            assert (
                matches[f"{round_name}_{match_number}"].winner_goes_to
                == expected_target
            )

    assert matches["T32_1"].winner_goes_to == ("T16_1", "top")
    assert matches["T32_2"].winner_goes_to == ("T16_1", "bottom")


def test_create_bracket_connects_both_semifinals():
    matches = create_bracket(_make_main_standings(32)).matches

    assert matches["T4_1"].winner_goes_to == ("FINAL", "top")
    assert matches["T4_1"].loser_goes_to == ("PLAYOFF", "top")
    assert matches["T4_2"].winner_goes_to == ("FINAL", "bottom")
    assert matches["T4_2"].loser_goes_to == ("PLAYOFF", "bottom")


def test_create_bracket_accepts_an_empty_ranking():
    bracket = create_bracket([])

    assert len(bracket.matches) == 32
    for match_number in range(1, 17):
        match = bracket.matches[f"T32_{match_number}"]
        assert match.slot_top is None
        assert match.slot_bottom is None
