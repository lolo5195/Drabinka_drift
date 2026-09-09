"""Build the initial TOP32 tournament bracket and its match connections."""

from models import Driver, Match, QualificationResult, TournamentBracket


# The order mirrors the bracket layout: left wing first, then right wing.
SEED_PAIRS: list[tuple[int, int]] = [
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


def _driver_at_seed(
    main_standings: list[QualificationResult | None],
    seed: int,
) -> Driver | None:
    """Return the driver at a 1-based seed or None when that seed is empty."""
    index = seed - 1
    if index >= len(main_standings):
        return None

    result = main_standings[index]
    return result.driver if result is not None else None


def _next_round_target(next_round: str, match_number: int) -> tuple[str, str]:
    """Return the next match and slot for a regular-round winner."""
    next_match_number = (match_number + 1) // 2
    slot = "top" if match_number % 2 == 1 else "bottom"
    return f"{next_round}_{next_match_number}", slot


def create_bracket(
    main_standings: list[QualificationResult | None],
) -> TournamentBracket:
    """Create all matches, seed TOP32, and connect consecutive rounds."""
    matches: dict[str, Match] = {}

    for match_number, (top_seed, bottom_seed) in enumerate(
        SEED_PAIRS,
        start=1,
    ):
        match_id = f"T32_{match_number}"
        matches[match_id] = Match(
            match_id=match_id,
            slot_top=_driver_at_seed(main_standings, top_seed),
            slot_bottom=_driver_at_seed(main_standings, bottom_seed),
            winner_goes_to=_next_round_target("T16", match_number),
        )

    # These rounds start empty and will be populated when T-06 resolves matches.
    for round_name, match_count, next_round in (
        ("T16", 8, "T8"),
        ("T8", 4, "T4"),
    ):
        for match_number in range(1, match_count + 1):
            match_id = f"{round_name}_{match_number}"
            matches[match_id] = Match(
                match_id=match_id,
                winner_goes_to=_next_round_target(next_round, match_number),
            )

    # Semifinals split winners into the final and losers into the play-off.
    matches["T4_1"] = Match(
        match_id="T4_1",
        winner_goes_to=("FINAL", "top"),
        loser_goes_to=("PLAYOFF", "top"),
    )
    matches["T4_2"] = Match(
        match_id="T4_2",
        winner_goes_to=("FINAL", "bottom"),
        loser_goes_to=("PLAYOFF", "bottom"),
    )
    matches["FINAL"] = Match(match_id="FINAL")
    matches["PLAYOFF"] = Match(match_id="PLAYOFF")

    return TournamentBracket(matches=matches)
