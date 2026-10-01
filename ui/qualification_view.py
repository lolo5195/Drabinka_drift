"""Tab "Kwalifikacje" - entry of drivers and their two qualification runs (T-09)."""

from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from logic.qualification import is_valid_score
from ui.state import AppState, EntryRow

SCORE_ERROR = "Wpisz liczbę całkowitą 0–100"

# L.p. | name | run 1 | run 2: the name column takes all the remaining width.
GRID_COLUMNS = "3rem 1fr 8rem 8rem"
HEADERS = ("L.p.", "Imię i nazwisko nr startowy", "Wynik 1", "Wynik 2")


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
        state.mark_entries_changed()
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
    _score_input(state, row, "run1")
    _score_input(state, row, "run2")


def _score_input(state: AppState, row: EntryRow, attribute: str) -> ui.input:
    """Create the field for `row.run1` or `row.run2` (`attribute` names which).

    The text goes to AppState exactly as typed. An invalid value turns the
    field red with SCORE_ERROR, and "Generuj wyniki" refuses to run until the
    operator fixes it - it is never silently counted as 0.
    """

    def on_change(e: ValueChangeEventArguments) -> None:
        setattr(row, attribute, e.value or "")
        state.mark_entries_changed()

    field = ui.input(
        value=getattr(row, attribute),
        validation={SCORE_ERROR: is_valid_score},
        on_change=on_change,
    ).mark(f"{attribute}-{row.driver_id}")
    # NiceGUI validates only on change: after F5 the rebuilt field must show
    # the error for an invalid value it starts with.
    field.validate()
    return field
