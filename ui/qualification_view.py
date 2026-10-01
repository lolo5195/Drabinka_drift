"""Tab "Kwalifikacje" - entry of drivers and their two qualification runs (T-09)."""

from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from ui.state import AppState, EntryRow

SCORE_ERROR = "Wpisz liczbę całkowitą 0–100"

# L.p. | name | run 1 | run 2: the name column takes all the remaining width.
GRID_COLUMNS = "3rem 1fr 8rem 8rem"
HEADERS = ("L.p.", "Imię i nazwisko nr startowy", "Wynik 1", "Wynik 2")


def is_valid_score(text: str | None) -> bool:
    """True for an empty field or an integer 0-100 written with digits only.

    The digit-only check rejects "-5", "+5", "8.5", "1e2" and letters before
    int() sees them; isascii() also rules out Unicode digits such as "²".
    """
    text = (text or "").strip()
    return text == "" or (text.isascii() and text.isdigit() and int(text) <= 100)


def parse_score(text: str | None) -> int | None:
    """Return the value kept in AppState: the score, or None if empty or invalid."""
    text = (text or "").strip()
    return int(text) if text and is_valid_score(text) else None


def build_qualification_view(state: AppState) -> None:
    """Build the entry table from `state.entries` inside the current tab panel.

    `items-start` aligns the tops of the cells: score fields reserve space for
    their error message below, so they are taller than the name field.
    """
    with ui.grid(columns=GRID_COLUMNS).classes("w-full items-start gap-2") as grid:
        for header in HEADERS:
            ui.label(header).classes("font-bold")
        for row in state.entries:
            _build_row(state, grid, row)


def _build_row(state: AppState, grid: ui.grid, row: EntryRow) -> None:
    """Add one table row (four grid cells) whose fields write into `row`."""

    def on_name_change(e: ValueChangeEventArguments) -> None:
        row.name = e.value or ""
        if state.add_row_if_last_named():
            # Append only the new cells. Rebuilding the grid (ui.refreshable)
            # would delete the field being typed in, losing focus and keystrokes.
            with grid:
                _build_row(state, grid, state.entries[-1])

    ui.label(f"{row.driver_id}.")
    ui.input(
        value=row.name,
        placeholder="np. Jan Kowalski #77",
        on_change=on_name_change,
    ).mark(f"name-{row.driver_id}")
    _score_input(row, "run1")
    _score_input(row, "run2")


def _score_input(row: EntryRow, attribute: str) -> ui.input:
    """Create the field for `row.run1` or `row.run2` (`attribute` names which).

    An invalid value turns the field red with SCORE_ERROR and stores None, so
    AppState never holds a score the operator did not type correctly.
    """
    current = getattr(row, attribute)
    return ui.input(
        value="" if current is None else str(current),
        validation={SCORE_ERROR: is_valid_score},
        on_change=lambda e: setattr(row, attribute, parse_score(e.value)),
    ).mark(f"{attribute}-{row.driver_id}")
