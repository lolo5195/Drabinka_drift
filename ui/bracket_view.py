"""Tab "Drabinka TOP32" - the tournament bracket and the podium."""

from nicegui import ui

from ui.state import AppState


def build_bracket_view(state: AppState) -> None:
    """Build the tab content from the bracket kept in AppState."""
    # None means the bracket has not been generated from the standings yet.
    if state.bracket is None:
        ui.label("Drabinka nie została jeszcze wygenerowana.")
