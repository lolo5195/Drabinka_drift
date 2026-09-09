"""T-07: console prototype — standings printout, bracket printout, input loop."""

import subprocess
import sys
from pathlib import Path

import pytest

from cli_demo import (
    SAMPLE_RESULTS,
    format_bracket,
    format_standings,
    parse_command,
    run_demo,
)
from logic.bracket import create_bracket, set_winner
from logic.qualification import split_standings
from models import Match, TournamentBracket


# --- Helpers -----------------------------------------------------------------

def _scripted_input(commands: list[str]):
    """Return an `input_fn` that replays `commands` and then signals EOF.

    Raising EOFError once the script runs out mirrors Ctrl-D in a terminal,
    so a test that forgets a trailing "q" still terminates instead of hanging.
    """
    remaining = iter(commands)

    def input_fn(_prompt: str) -> str:
        try:
            return next(remaining)
        except StopIteration:
            raise EOFError from None

    return input_fn


def _run_scripted(commands: list[str]) -> tuple[TournamentBracket, str]:
    """Run the demo on `commands` and return the bracket plus joined output."""
    output: list[str] = []
    bracket = run_demo(
        input_fn=_scripted_input(commands),
        output_fn=output.append,
    )
    return bracket, "\n".join(output)


def _existing_side(match: Match) -> str | None:
    """Pick a side that holds a driver, or None for a "-" vs "-" match."""
    if match.slot_top is not None:
        return "top"
    if match.slot_bottom is not None:
        return "bottom"
    return None


def _commands_for_full_tournament() -> list[str]:
    """Build the command script by simulating the tournament on a mirror.

    Each command is only valid once earlier rounds have been resolved, so the
    mirror bracket applies `set_winner` step by step while recording what the
    operator would have to type.
    """
    main, _extra = split_standings(SAMPLE_RESULTS)
    mirror = create_bracket(main)
    commands: list[str] = []

    match_ids = [
        f"{round_name}_{number}"
        for round_name, match_count in (
            ("T32", 16),
            ("T16", 8),
            ("T8", 4),
            ("T4", 2),
        )
        for number in range(1, match_count + 1)
    ] + ["FINAL", "PLAYOFF"]

    for match_id in match_ids:
        side = _existing_side(mirror.matches[match_id])
        if side is None:
            continue  # "-" vs "-" is unresolvable and must be skipped
        set_winner(mirror, match_id, side)
        commands.append(f"{match_id} {side}")

    return commands


# --- Standings and bracket printouts -----------------------------------------

def test_format_standings_shows_dashes_and_extra_table():
    main, extra = split_standings(SAMPLE_RESULTS)

    text = format_standings(main, extra)
    lines = text.splitlines()

    # Ten drivers occupy places 1-10; the tie-break example keeps its order.
    assert lines[2].startswith("   1.  Jan Kowalski #77")
    assert lines[3].startswith("   2.  Piotr Nowak #12")
    assert lines[4].startswith("   3.  Adam Wiśniewski #5")
    assert lines[5].startswith("   4.  Marek Zieliński #23")

    # Places 11-32 are printed as dash rows.
    dash_rows = [line for line in lines if line.endswith("-        -")]
    assert len(dash_rows) == 22
    assert dash_rows[0].startswith("  11.  -")
    assert dash_rows[-1].startswith("  32.  -")

    # Zero results land in the 33+ table, numbered from 33.
    assert "--- Miejsca 33+ ---" in text
    assert "  33.  Andrzej Dąbrowski #66" in text
    assert "  34.  Grzegorz Kozłowski #21" in text


def test_format_standings_hides_extra_table_when_empty():
    main, extra = split_standings(SAMPLE_RESULTS[:10])

    text = format_standings(main, extra)

    assert extra == []
    assert "Miejsca 33+" not in text


def test_format_bracket_marks_empty_slots_and_winner():
    main, _extra = split_standings(SAMPLE_RESULTS)
    bracket = create_bracket(main)

    before = format_bracket(bracket)
    assert "T32_1    Jan Kowalski #77             vs  -" in before
    assert "T32_2    -                            vs  -" in before
    assert "1. -   2. -   3. -   4. -" in before
    assert "*" not in before

    set_winner(bracket, "T32_1", "top")
    after = format_bracket(bracket)

    # The winner is starred in its match and appears unstarred one round later.
    assert "T32_1    Jan Kowalski #77 *" in after
    assert "T16_1    Jan Kowalski #77             vs  -" in after


# --- Command parsing ---------------------------------------------------------

def test_parse_command_normalizes_case_and_whitespace():
    bracket = create_bracket([])

    assert parse_command(" t32_1  TOP ", bracket) == ("T32_1", "top")
    assert parse_command("final Bottom", bracket) == ("FINAL", "bottom")


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "T32_1",
        "T99_1 top",
        "T32_1 middle",
        "abc def ghi",
    ],
)
def test_parse_command_rejects_bad_input(raw: str):
    bracket = create_bracket([])

    with pytest.raises(ValueError):
        parse_command(raw, bracket)


# --- DoD 1: the whole competition can be played to the podium ----------------

def test_scripted_full_tournament_reaches_podium():
    commands = _commands_for_full_tournament()

    bracket, output = _run_scripted(commands)

    # The loop stops by itself once the podium is complete (no "q" needed).
    assert all(driver is not None for driver in bracket.podium.values())
    assert "Zawody zakończone" in output
    assert "Koniec sesji." not in output

    # Ten drivers: the top seed walks over to the title, seed 2 is runner-up.
    assert bracket.podium[1].name == "Jan Kowalski #77"
    assert bracket.podium[2].name == "Piotr Nowak #12"
    assert bracket.matches["FINAL"].winner is bracket.podium[1]

    # "-" vs "-" matches were skipped and stay unresolved without harm.
    assert bracket.matches["T32_2"].winner is None


# --- DoD 2: bad input never crashes the program -------------------------------

def test_invalid_inputs_are_reported_and_do_not_crash():
    commands = [
        "",
        "xyz",
        "T99_1 top",
        "T32_1 middle",
        "T32_2 top",  # "-" vs "-": the chosen slot is empty
        "T32_1 top",  # a valid decision still works after the mistakes
        "q",
    ]

    bracket, output = _run_scripted(commands)

    assert "Błąd: Wpisz identyfikator meczu i stronę" in output
    assert "Błąd: Nieznany mecz: T99_1." in output
    assert "Błąd: Nieznana strona: middle." in output
    assert "Błąd: slot top w meczu T32_2 jest pusty (-)." in output
    assert "T32_1: wygrywa Jan Kowalski #77" in output
    assert output.endswith("Koniec sesji.")

    assert bracket.matches["T32_2"].winner is None
    assert bracket.matches["T32_1"].winner is not None


def test_eof_ends_demo_gracefully():
    bracket, output = _run_scripted([])

    assert output.endswith("Koniec sesji.")
    assert all(match.winner is None for match in bracket.matches.values())


# --- The script runs as a program --------------------------------------------

def test_cli_demo_runs_as_script():
    project_root = Path(__file__).resolve().parent.parent

    completed = subprocess.run(
        [sys.executable, "cli_demo.py"],
        input="q\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=project_root,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    assert "=== WYNIKI KWALIFIKACJI (miejsca 1-32) ===" in completed.stdout
    assert "=== PODIUM ===" in completed.stdout
    assert "Koniec sesji." in completed.stdout
