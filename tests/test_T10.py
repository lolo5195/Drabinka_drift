"""T-10: results view - standings 1-32 and 33+, the better run in bold."""

import pytest
from nicegui import ui
from nicegui.testing import User

from models import Driver, QualificationResult, TournamentBracket
from ui.results_view import GENERATE_LABEL
from ui.state import TAB_QUALIFICATION, TAB_RESULTS, AppState, EntryRow


# --- AppState.generate_results: plain unit tests, no GUI ---------------------

def _state(*rows: tuple[str, int | None, int | None]) -> AppState:
    """AppState whose entry table holds `rows` as (name, run1, run2), ids 1..n."""
    state = AppState()
    state.entries = [
        EntryRow(driver_id=row_id, name=name, run1=run1, run2=run2)
        for row_id, (name, run1, run2) in enumerate(rows, start=1)
    ]
    return state


def _names(results: list[QualificationResult | None]) -> list[str | None]:
    """Driver names in table order; None stays None (a row of dashes)."""
    return [r.driver.name if r is not None else None for r in results]


@pytest.mark.parametrize(("rows", "expected"), [
    # Spec example typed in shuffled order: (81,76) > (56,81) > (81,0).
    ([("Driver 3", 81, 0), ("Driver 1", 81, 76), ("Driver 2", 56, 81)],
     ["Driver 1", "Driver 2", "Driver 3"]),
    # Full tie: the driver typed first stays first.
    ([("Driver 2", 81, 76), ("Driver 1", 81, 76)], ["Driver 2", "Driver 1"]),
    # (0, 81) counts as best 81, not as a zero result.
    ([("Driver 2", 80, 79), ("Driver 1", 0, 81)], ["Driver 1", "Driver 2"]),
], ids=["spec-example", "full-tie", "zero-first-run"])
def test_generated_order_matches_T03(rows, expected):
    state = _state(*rows)

    state.generate_results()

    assert _names(state.main_standings) == expected + [None] * (32 - len(expected))
    assert state.extra_standings == []


def test_28_drivers_leave_places_29_to_32_empty():
    state = _state(*[(f"Driver {i}", 100 - i, None) for i in range(1, 29)])

    state.generate_results()

    assert _names(state.main_standings) == [f"Driver {i}" for i in range(1, 29)] + [None] * 4
    assert state.extra_standings == []


def test_35_drivers_overflow_to_extra():
    state = _state(*[(f"Driver {i}", 100 - i, None) for i in range(1, 36)])

    state.generate_results()

    assert _names(state.main_standings) == [f"Driver {i}" for i in range(1, 33)]
    assert _names(state.extra_standings) == ["Driver 33", "Driver 34", "Driver 35"]


def test_generate_results_converts_typed_rows():
    state = _state(
        ("  Jan Kowalski #77 ", 81, None),   # empty run 2, stray spaces
        ("", 95, 90),                        # scores but no name
        ("Piotr Nowak #12", None, None),     # name only
        ("", None, None),                    # the empty last row (T-09)
    )

    state.generate_results()

    # Empty field -> 0, name trimmed, Driver.id is the row id (not the place).
    assert state.main_standings[0] == QualificationResult(Driver(1, "Jan Kowalski #77"), 81, 0)
    # The unnamed row is ignored even though it scored best.
    assert state.main_standings[1:] == [None] * 31
    # A name without scores becomes (0, 0) and goes to the 33+ table.
    assert state.extra_standings == [QualificationResult(Driver(3, "Piotr Nowak #12"), 0, 0)]


def test_generate_results_leaves_bracket_untouched():
    state = _state(("Jan Kowalski #77", 81, 76))
    bracket = TournamentBracket()
    state.bracket = bracket

    state.generate_results()

    assert state.bracket is bracket


# --- GUI: NiceGUI's simulated user runs main.py, no browser needed -----------
# The operator types drivers on "Kwalifikacje" and clicks "Generuj wyniki".
# refresh() rebuilds the tables on the next event-loop step, so every test
# first awaits `should_see` (it retries) and only then reads the labels.

def _enter(user: User, row_id: int, name: str, run1: str = "", run2: str = "") -> None:
    """Type one driver into row `row_id` of the entry table; "" leaves a field empty."""
    user.find(marker=f"name-{row_id}").type(name)
    if run1:
        user.find(marker=f"run1-{row_id}").type(run1)
    if run2:
        user.find(marker=f"run2-{row_id}").type(run2)


def _generate(user: User) -> None:
    """Open the "Wyniki" tab and click "Generuj wyniki", like the operator."""
    user.find(kind=ui.tab, content=TAB_RESULTS).click()
    user.find(kind=ui.button, content=GENERATE_LABEL).click()


def _label(user: User, marker: str) -> ui.label:
    """Return the single label with this marker on the currently open page."""
    return next(iter(user.find(marker=marker).elements))


def _is_bold(user: User, marker: str) -> bool:
    return "font-bold" in _label(user, marker).classes


async def test_generate_shows_standings_in_logic_order(user: User) -> None:
    await user.open("/")
    # The T-03 spec example, typed in shuffled order.
    _enter(user, 1, "Adam Wiśniewski #5", "81", "0")
    _enter(user, 2, "Jan Kowalski #77", "81", "76")
    _enter(user, 3, "Piotr Nowak #12", "56", "81")
    expected = ["Jan Kowalski #77", "Piotr Nowak #12", "Adam Wiśniewski #5"]

    _generate(user)

    await user.should_see(marker="result-name-1")
    assert [_label(user, f"result-name-{place}").text for place in (1, 2, 3)] == expected

    await user.open("/")   # like F5: the page is rebuilt only from AppState
    await user.should_see(marker="result-name-1")
    assert [_label(user, f"result-name-{place}").text for place in (1, 2, 3)] == expected


async def test_better_run_is_bold(user: User) -> None:
    await user.open("/")
    _enter(user, 1, "Jan Kowalski #77", "81", "76")
    _enter(user, 2, "Piotr Nowak #12", "56", "81")
    _enter(user, 3, "Adam Wiśniewski #5", "81", "81")

    _generate(user)
    await user.should_see(marker="result-name-1")

    # Place 1: (81, 81) - equal runs, both bold.
    assert _label(user, "result-name-1").text == "Adam Wiśniewski #5"
    assert _is_bold(user, "result-run1-1") and _is_bold(user, "result-run2-1")
    # Place 2: (81, 76) - only run 1 is bold.
    assert _label(user, "result-name-2").text == "Jan Kowalski #77"
    assert _is_bold(user, "result-run1-2") and not _is_bold(user, "result-run2-2")
    # Place 3: (56, 81) - only run 2 is bold.
    assert _label(user, "result-name-3").text == "Piotr Nowak #12"
    assert not _is_bold(user, "result-run1-3") and _is_bold(user, "result-run2-3")


async def test_28_drivers_show_dashes_in_places_29_to_32(user: User) -> None:
    await user.open("/")
    for row_id in range(1, 29):
        _enter(user, row_id, f"Driver {row_id}", str(100 - row_id))

    _generate(user)

    await user.should_see(marker="result-name-29")
    assert _label(user, "result-name-28").text == "Driver 28"
    for place in range(29, 33):
        for column in ("name", "run1", "run2"):
            assert _label(user, f"result-{column}-{place}").text == "-"
    # No (0, 0) results and no overflow: there is no 33+ table.
    await user.should_not_see(marker="extra-standings")


async def test_extra_table_appears_only_with_zero_results(user: User) -> None:
    await user.open("/")
    _enter(user, 1, "Jan Kowalski #77", "81", "76")
    _enter(user, 2, "Andrzej Dąbrowski #66")   # name only: (0, 0) at generation

    _generate(user)

    await user.should_see(marker="extra-standings")
    assert _label(user, "result-name-2").text == "-"
    # The 33+ table continues the numbering at 33.
    assert _label(user, "result-name-33").text == "Andrzej Dąbrowski #66"
    assert _label(user, "result-run1-33").text == "0"
    assert _label(user, "result-run2-33").text == "0"


async def test_generate_again_reflects_corrected_scores(user: User) -> None:
    await user.open("/")
    _enter(user, 1, "Jan Kowalski #77", "70")
    _enter(user, 2, "Piotr Nowak #12")   # score forgotten: (0, 0) -> 33+
    _generate(user)
    await user.should_see(marker="extra-standings")
    assert _label(user, "result-name-1").text == "Jan Kowalski #77"

    # The operator goes back, adds the missing score and generates again.
    user.find(kind=ui.tab, content=TAB_QUALIFICATION).click()
    user.find(marker="run1-2").type("90")
    _generate(user)

    await user.should_see(marker="result-name-1", content="Piotr Nowak #12")
    assert _label(user, "result-name-2").text == "Jan Kowalski #77"
    await user.should_not_see(marker="extra-standings")
