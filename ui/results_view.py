"""Tab "Wyniki" - qualification standings: places 1-32 and 33+ (T-10)."""

from collections.abc import Iterable

from nicegui import ui

from models import QualificationResult
from rendering.style import Weight
# The PNG export (T-13) draws the same table. Sharing its column titles, the
# 33+ numbering and the bold rule keeps the screen and the PNG identical.
from rendering.table_png import EXTRA_FIRST_PLACE, HEADERS, score_weights
from ui.state import AppState

GENERATE_LABEL = "Generuj wyniki"
INVALID_SCORES_MESSAGE = "Popraw wyniki w wierszach:"
OUTDATED_MESSAGE = ("Kwalifikacje zmieniły się od ostatniego generowania — "
                    "kliknij „Generuj wyniki”, aby odświeżyć tabelę.")

# Miejsce | name | run 1 | run 2: the name column takes all the remaining width.
GRID_COLUMNS = "5rem 1fr 10rem 10rem"


def build_results_view(state: AppState) -> None:
    """Build the "Generuj wyniki" button and the standings read from `state`."""

    # Defined here, so each page load gets its own refreshable: refresh()
    # rebuilds only this page's tables, always from AppState.
    @ui.refreshable
    def standings() -> None:
        # An empty list means the operator has not generated the results yet.
        if not state.main_standings:
            ui.label("Wyniki nie zostały jeszcze wygenerowane.")
            return
        _table(enumerate(state.main_standings, start=1))
        # Zero results and the overflow above 32 (PLAN §2.1).
        if state.extra_standings:
            _table(enumerate(state.extra_standings, start=EXTRA_FIRST_PLACE)) \
                .classes("mt-6").mark("extra-standings")

    def on_generate() -> None:
        invalid_rows = state.rows_with_invalid_scores()
        if invalid_rows:
            # Generating anyway would count each typo as 0 and silently
            # change the order, and with it the bracket seeding.
            rows = ", ".join(str(row_id) for row_id in invalid_rows)
            ui.notify(f"{INVALID_SCORES_MESSAGE} {rows}", type="negative")
            return
        state.generate_results()
        standings.refresh()

    ui.button(GENERATE_LABEL, on_click=on_generate)
    # Bound, not refreshed: the flag changes on the other tab while typing.
    ui.label(OUTDATED_MESSAGE).classes("text-orange-700 font-bold") \
        .bind_visibility_from(state, "results_outdated").mark("results-outdated")
    standings()


def _table(rows: Iterable[tuple[int, QualificationResult | None]]) -> ui.grid:
    """Build one table: the header row, then one row per (place, result)."""
    with ui.grid(columns=GRID_COLUMNS).classes("w-full gap-x-4 gap-y-1") as grid:
        for header in HEADERS:
            ui.label(header).classes("font-bold")
        for place, result in rows:
            _row(place, result)
    return grid


def _row(place: int, result: QualificationResult | None) -> None:
    """Add the four cells of one row; None is an empty place shown as dashes."""
    ui.label(f"{place}.")
    if result is None:
        for column in ("name", "run1", "run2"):
            ui.label("-").mark(f"result-{column}-{place}")
        return
    ui.label(result.driver.name).mark(f"result-name-{place}")
    weight1, weight2 = score_weights(result.run1, result.run2)
    _score_cell(result.run1, weight1, f"result-run1-{place}")
    _score_cell(result.run2, weight2, f"result-run2-{place}")


def _score_cell(score: int, weight: Weight, marker: str) -> None:
    """Add one score cell, bold when `score_weights` marks it as the better run."""
    label = ui.label(str(score)).mark(marker)
    if weight == "bold":
        label.classes("font-bold")
