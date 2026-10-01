"""Tab "Kwalifikacje" - entry of drivers and their two qualification runs."""

from nicegui import ui

from ui.state import AppState


def build_qualification_view(state: AppState) -> None:
    """Build the tab content inside the current container (the tab panel).

    `state` is not read yet: every view takes AppState so all tabs share one
    contract, and the entry table (T-09) will keep its rows in it.
    """
    ui.label("Tu pojawi się tabela wprowadzania zawodników i wyników.")
