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

# Match destinations use the same tuple shape for regular slots and podium
# places, e.g. ("T16_1", "top") or ("PODIUM", "1").
_PODIUM_TARGET = "PODIUM"


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
    matches["FINAL"] = Match(
        match_id="FINAL",
        winner_goes_to=(_PODIUM_TARGET, "1"),
        loser_goes_to=(_PODIUM_TARGET, "2"),
    )
    matches["PLAYOFF"] = Match(
        match_id="PLAYOFF",
        winner_goes_to=(_PODIUM_TARGET, "3"),
        loser_goes_to=(_PODIUM_TARGET, "4"),
    )

    return TournamentBracket(matches=matches)


def _place(
    bracket: TournamentBracket,
    destination: tuple[str, str] | None,
    driver: Driver | None,
) -> None:
    """Place a driver in a match slot or in a podium position."""
    if destination is None:
        return

    target_id, target_slot = destination
    if target_id == _PODIUM_TARGET:
        bracket.podium[int(target_slot)] = driver
        return

    target_match = bracket.matches[target_id]
    if target_slot == "top":
        target_match.slot_top = driver
    else:
        target_match.slot_bottom = driver


def _clear_destination(
    bracket: TournamentBracket,
    destination: tuple[str, str] | None,
    driver: Driver | None,
) -> None:
    """Remove one driver's effects from a destination and all later rounds."""
    if destination is None or driver is None:
        return

    target_id, target_slot = destination
    if target_id == _PODIUM_TARGET:
        podium_place = int(target_slot)
        if bracket.podium[podium_place] == driver:
            bracket.podium[podium_place] = None
        return

    target_match = bracket.matches[target_id]
    current_driver = (
        target_match.slot_top
        if target_slot == "top"
        else target_match.slot_bottom
    )
    if current_driver != driver:
        return

    if target_match.winner is not None:
        # Clear later results while both original slots still identify the
        # winner and loser of this match.
        clear_downstream(bracket, target_match)
        target_match.winner = None

    if target_slot == "top":
        target_match.slot_top = None
    else:
        target_match.slot_bottom = None


def clear_downstream(bracket: TournamentBracket, match: Match) -> None:
    """Clear every result produced by a match, including podium positions."""
    if match.winner is None:
        return

    old_winner = match.winner
    old_loser = (
        match.slot_bottom
        if old_winner == match.slot_top
        else match.slot_top
    )
    _clear_destination(bracket, match.winner_goes_to, old_winner)
    _clear_destination(bracket, match.loser_goes_to, old_loser)


def set_winner(
    bracket: TournamentBracket,
    match_id: str,
    side: str,
) -> None:
    """Select a winner and propagate the match result through the bracket."""
    match = bracket.matches[match_id]
    clicked = match.slot_top if side == "top" else match.slot_bottom

    # A dash cannot win, and clicking the current winner changes no state.
    if clicked is None or clicked == match.winner:
        return

    if match.winner is not None:
        clear_downstream(bracket, match)

    match.winner = clicked
    loser = match.slot_bottom if side == "top" else match.slot_top
    _place(bracket, match.winner_goes_to, clicked)
    _place(bracket, match.loser_goes_to, loser)
