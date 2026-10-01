"""T-08: application skeleton - three tabs and AppState as the only state."""

from nicegui import ui
from nicegui.testing import User

from ui.state import TAB_BRACKET, TAB_QUALIFICATION, TAB_RESULTS, AppState

EXPECTED_TABS = [TAB_QUALIFICATION, TAB_RESULTS, TAB_BRACKET]


# --- AppState: plain unit tests, no GUI --------------------------------------

def test_app_state_starts_empty_on_qualification_tab():
    state = AppState()

    assert state.active_tab == TAB_QUALIFICATION
    assert state.main_standings == []
    assert state.extra_standings == []
    assert state.bracket is None


def test_app_state_instances_do_not_share_lists():
    first, second = AppState(), AppState()

    first.main_standings.append(None)

    assert second.main_standings == []


# --- GUI: NiceGUI's simulated user runs main.py, no browser needed -----------
# The `user` fixture fails a test on any ERROR log, which covers the DoD
# "zakładki przełączają się bez błędów w konsoli".

def _tab_panels(user: User) -> ui.tab_panels:
    """Return the single `ui.tab_panels` element of the currently open page."""
    return next(iter(user.find(ui.tab_panels).elements))


async def test_page_has_three_tabs_in_order(user: User) -> None:
    await user.open("/")

    # Element ids grow in creation order, so sorting by id restores the layout.
    tabs = sorted(user.find(ui.tab).elements, key=lambda tab: tab.id)
    assert [tab.props["name"] for tab in tabs] == EXPECTED_TABS


async def test_clicking_tabs_switches_panels(user: User) -> None:
    await user.open("/")
    panels = _tab_panels(user)
    assert panels.value == TAB_QUALIFICATION

    for name in (TAB_RESULTS, TAB_BRACKET, TAB_QUALIFICATION):
        # `kind=ui.tab` is needed: "Wyniki" also appears in a label in a panel.
        user.find(kind=ui.tab, content=name).click()
        assert panels.value == name


async def test_views_render_placeholders_from_empty_state(user: User) -> None:
    await user.open("/")

    await user.should_see("Wyniki nie zostały jeszcze wygenerowane.")
    await user.should_see("Drabinka nie została jeszcze wygenerowana.")


async def test_selected_tab_is_kept_in_app_state_after_reload(user: User) -> None:
    await user.open("/")
    user.find(kind=ui.tab, content=TAB_BRACKET).click()

    # Like F5: NiceGUI builds a brand-new page, which reads the tab from AppState.
    await user.open("/")

    assert _tab_panels(user).value == TAB_BRACKET
