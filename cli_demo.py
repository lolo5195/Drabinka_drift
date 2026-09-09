"""T-07: console prototype — the first working product without any GUI.

The script wires the finished engine (`logic/`) into a terminal session:

1. print the qualification standings for a hardcoded set of drivers,
2. build the TOP32 bracket from those standings,
3. let the operator resolve matches by typing ``<match_id> <top|bottom>``,
4. stop when all four podium places are filled.

Everything that prints or parses text lives here; the engine itself is not
touched. Input and output are injectable (``input_fn`` / ``output_fn``) so the
whole loop can be driven by tests without a real terminal.

Run it with ``python cli_demo.py``.
"""

from collections.abc import Callable

from logic.bracket import create_bracket, set_winner
from logic.qualification import split_standings
from models import Driver, QualificationResult, TournamentBracket


# --- Sample data -------------------------------------------------------------

# Twelve hardcoded entries: ten with a positive score and two with (0, 0).
# This is the mandatory edge case from PLAN.md §4.3 ("10 drivers > 0"), so the
# demo shows dashes for places 11-32, a 33+ table, walkovers, and "-" vs "-"
# matches. The first four entries reproduce the tie-break example from §2.1:
# (81,76) beats (56,81) beats (81,0), and (0,81) counts as best=81, worst=0.
SAMPLE_RESULTS: list[QualificationResult] = [
    QualificationResult(Driver(1, "Jan Kowalski #77"), run1=81, run2=76),
    QualificationResult(Driver(2, "Piotr Nowak #12"), run1=56, run2=81),
    QualificationResult(Driver(3, "Adam Wiśniewski #5"), run1=81, run2=0),
    QualificationResult(Driver(4, "Marek Zieliński #23"), run1=0, run2=81),
    QualificationResult(Driver(5, "Tomasz Lewandowski #99"), run1=74, run2=79),
    QualificationResult(Driver(6, "Krzysztof Wójcik #31"), run1=68, run2=70),
    QualificationResult(Driver(7, "Michał Kamiński #8"), run1=65, run2=0),
    QualificationResult(Driver(8, "Paweł Kaczmarek #44"), run1=60, run2=62),
    QualificationResult(Driver(9, "Łukasz Szymański #17"), run1=55, run2=58),
    QualificationResult(Driver(10, "Robert Woźniak #3"), run1=40, run2=51),
    QualificationResult(Driver(11, "Andrzej Dąbrowski #66"), run1=0, run2=0),
    QualificationResult(Driver(12, "Grzegorz Kozłowski #21"), run1=0, run2=0),
]


# --- Constants ---------------------------------------------------------------

# Regular rounds in display order; FINAL and PLAYOFF are printed separately.
ROUNDS: tuple[tuple[str, int], ...] = (
    ("T32", 16),
    ("T16", 8),
    ("T8", 4),
    ("T4", 2),
)

# The two slot names accepted on the command line; they match `set_winner`.
SIDES: tuple[str, str] = ("top", "bottom")

# Typing any of these ends the session before the podium is complete.
QUIT_COMMANDS: frozenset[str] = frozenset({"q", "quit"})

# Column widths shared by the standings and the bracket printouts.
NAME_WIDTH = 26

PROMPT = "Mecz i strona (np. T32_1 top), q = koniec: "


# --- Formatting --------------------------------------------------------------

def driver_label(driver: Driver | None) -> str:
    """Return the driver's name, or "-" for an empty slot (None)."""
    return driver.name if driver is not None else "-"


def _standings_row(place: int, result: QualificationResult | None) -> str:
    """Format one table row; a None result becomes a row full of dashes."""
    if result is None:
        return f"{place:>4}.  {'-':<{NAME_WIDTH}} {'-':>7}  {'-':>7}"
    return (
        f"{place:>4}.  {result.driver.name:<{NAME_WIDTH}} "
        f"{result.run1:>7}  {result.run2:>7}"
    )


def format_standings(
    main: list[QualificationResult | None],
    extra: list[QualificationResult],
) -> str:
    """Render the 1-32 table and, only when needed, the 33+ table.

    `main` always has exactly 32 entries (None = dashes) and `extra` holds
    zero results plus any overflow, numbered from 33 — exactly what
    `split_standings` returns.
    """
    header = f"{'L.p.':>5}  {'Zawodnik':<{NAME_WIDTH}} {'Wynik 1':>7}  {'Wynik 2':>7}"
    lines = ["=== WYNIKI KWALIFIKACJI (miejsca 1-32) ===", header]
    lines.extend(
        _standings_row(place, result)
        for place, result in enumerate(main, start=1)
    )

    # The 33+ table only appears when there is something to show in it.
    if extra:
        lines.append("--- Miejsca 33+ ---")
        lines.extend(
            _standings_row(place, result)
            for place, result in enumerate(extra, start=33)
        )

    return "\n".join(lines)


def _slot_label(match_driver: Driver | None, winner: Driver | None) -> str:
    """Return a slot name with a trailing "*" when that driver won the match."""
    label = driver_label(match_driver)
    if match_driver is not None and match_driver == winner:
        label += " *"
    return label


def _match_line(bracket: TournamentBracket, match_id: str) -> str:
    """Format one match as ``ID  top  vs  bottom`` with the winner starred."""
    match = bracket.matches[match_id]
    top = _slot_label(match.slot_top, match.winner)
    bottom = _slot_label(match.slot_bottom, match.winner)
    return f"{match_id:<8} {top:<{NAME_WIDTH + 2}} vs  {bottom}"


def format_bracket(bracket: TournamentBracket) -> str:
    """Render every round, the final, the play-off, and the podium as text.

    Match ids are printed exactly as the operator has to type them, so the
    printout doubles as the command reference for the input loop.
    """
    lines: list[str] = []

    for round_name, match_count in ROUNDS:
        lines.append(f"=== {round_name} ===")
        lines.extend(
            _match_line(bracket, f"{round_name}_{number}")
            for number in range(1, match_count + 1)
        )

    lines.append("=== FINAL / PLAYOFF ===")
    lines.append(_match_line(bracket, "FINAL"))
    lines.append(_match_line(bracket, "PLAYOFF"))

    lines.append("=== PODIUM ===")
    lines.append(
        "   ".join(
            f"{place}. {driver_label(bracket.podium[place])}"
            for place in (1, 2, 3, 4)
        )
    )

    return "\n".join(lines)


# --- Input handling ----------------------------------------------------------

def parse_command(raw: str, bracket: TournamentBracket) -> tuple[str, str]:
    """Turn a typed line into ``(match_id, side)`` accepted by `set_winner`.

    Input is case-insensitive and tolerant of extra spaces, e.g.
    ``" t32_1  TOP "`` -> ``("T32_1", "top")``. Anything else raises
    ValueError with a Polish message that the loop prints to the operator;
    the loop never crashes on a typo.
    """
    parts = raw.split()
    if len(parts) != 2:
        raise ValueError(
            "Wpisz identyfikator meczu i stronę, np. 'T32_1 top'."
        )

    match_id = parts[0].upper()
    side = parts[1].lower()

    if match_id not in bracket.matches:
        raise ValueError(f"Nieznany mecz: {parts[0]}.")
    if side not in SIDES:
        raise ValueError(f"Nieznana strona: {parts[1]}. Użyj 'top' lub 'bottom'.")

    return match_id, side


def _podium_complete(bracket: TournamentBracket) -> bool:
    """True once FINAL and PLAYOFF have both filled their podium places."""
    return all(driver is not None for driver in bracket.podium.values())


# --- Main loop ---------------------------------------------------------------

def run_demo(
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> TournamentBracket:
    """Run the whole demo: standings, bracket, and the interactive loop.

    `input_fn` and `output_fn` default to the real terminal, but tests pass a
    scripted reader and a list collector instead. The bracket is returned so
    callers (tests) can inspect the final state.
    """
    main, extra = split_standings(SAMPLE_RESULTS)
    output_fn(format_standings(main, extra))

    bracket = create_bracket(main)
    output_fn("")
    output_fn(format_bracket(bracket))

    while not _podium_complete(bracket):
        try:
            raw = input_fn(PROMPT)
        except EOFError:
            # Ctrl-D (or an exhausted script) ends the session like "q".
            output_fn("Koniec sesji.")
            return bracket

        if raw.strip().lower() in QUIT_COMMANDS:
            output_fn("Koniec sesji.")
            return bracket

        try:
            match_id, side = parse_command(raw, bracket)
        except ValueError as error:
            # Bad input is reported and the loop simply asks again.
            output_fn(f"Błąd: {error}")
            continue

        match = bracket.matches[match_id]
        chosen = match.slot_top if side == "top" else match.slot_bottom
        if chosen is None:
            # `set_winner` would ignore this anyway; say why nothing happened.
            output_fn(f"Błąd: slot {side} w meczu {match_id} jest pusty (-).")
            continue

        set_winner(bracket, match_id, side)
        output_fn(f"{match_id}: wygrywa {chosen.name}")
        output_fn("")
        output_fn(format_bracket(bracket))

    output_fn("")
    output_fn("Zawody zakończone — podium jest kompletne.")
    return bracket


if __name__ == "__main__":
    try:
        run_demo()
    except KeyboardInterrupt:
        # Ctrl-C should end the demo quietly instead of printing a traceback.
        print("\nPrzerwano.")
