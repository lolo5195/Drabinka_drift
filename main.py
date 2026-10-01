"""GUI entry point: builds the page skeleton and starts NiceGUI.

Run with ``python main.py``; NiceGUI opens http://localhost:8080.
"""

from functools import partial

from nicegui import ui

# `from ui.x import ...` binds only the imported names, so `ui` in this module
# stays NiceGUI's `ui`. Never write `import ui.state` here: it would rebind
# `ui` to the local package and shadow NiceGUI.
from ui.bracket_view import build_bracket_view
from ui.qualification_view import build_qualification_view
from ui.results_view import build_results_view
from ui.state import TAB_BRACKET, TAB_QUALIFICATION, TAB_RESULTS, AppState


def build_page(state: AppState) -> None:
    """Build the header with three tabs and one panel per tab.

    NiceGUI calls this on every page load (also after F5); all content comes
    from `state`, so a reload shows the same thing as before.
    """
    with ui.header():
        # Two-way binding: clicking a tab writes its name to state.active_tab.
        with ui.tabs().bind_value(state, "active_tab") as tabs:
            ui.tab(TAB_QUALIFICATION)
            ui.tab(TAB_RESULTS)
            ui.tab(TAB_BRACKET)

    # The panels follow `tabs`. `value` is required: on the first sync NiceGUI
    # copies the panels' value into the tabs, and None would reset active_tab.
    with ui.tab_panels(tabs, value=state.active_tab).classes("w-full"):
        with ui.tab_panel(TAB_QUALIFICATION):
            build_qualification_view(state)
        with ui.tab_panel(TAB_RESULTS):
            build_results_view(state)
        with ui.tab_panel(TAB_BRACKET):
            build_bracket_view(state)


# "__mp_main__" is the module name in the worker process of the auto-reloader.
if __name__ in {"__main__", "__mp_main__"}:
    app_state = AppState()  # the only state instance for the whole process
    ui.run(partial(build_page, app_state), title="Wyniki i drabinka TOP32")
