"""Tab "Wyniki" - qualification standings (places 1-32 and 33+)."""

from nicegui import ui

from ui.state import AppState


def build_results_view(state: AppState) -> None:
    """Build the tab content from the standings kept in AppState."""
    # An empty list means the operator has not generated the results yet.
    if not state.main_standings:
        ui.label("Wyniki nie zostały jeszcze wygenerowane.")
