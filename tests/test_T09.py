"""T-09: dynamic entry table - rows grow with names, scores accept only 0-100."""

import pytest
from nicegui import ui
from nicegui.testing import User

from ui.qualification_view import SCORE_ERROR, is_valid_score, parse_score
from ui.state import AppState, EntryRow


# --- AppState rows: plain unit tests, no GUI ---------------------------------

def test_app_state_starts_with_two_empty_rows():
    state = AppState()

    assert state.entries == [EntryRow(driver_id=1), EntryRow(driver_id=2)]
    assert state.entries[0].run1 is None and state.entries[0].run2 is None


def test_row_is_added_only_when_last_row_gets_a_name():
    state = AppState()

    assert state.add_row_if_last_named() is False   # last row still empty
    state.entries[0].name = "Jan Kowalski #77"
    assert state.add_row_if_last_named() is False   # only an earlier row named
    state.entries[-1].name = "   "
    assert state.add_row_if_last_named() is False   # spaces are not a name
    assert len(state.entries) == 2

    state.entries[-1].name = "Piotr Nowak #12"
    assert state.add_row_if_last_named() is True

    # The new row continues the numbering and starts empty.
    assert [row.driver_id for row in state.entries] == [1, 2, 3]
    assert state.entries[-1] == EntryRow(driver_id=3)


def test_repeated_calls_add_exactly_one_row():
    # Every keystroke calls the method; only the first one may add a row.
    state = AppState()
    state.entries[-1].name = "P"

    added = [state.add_row_if_last_named() for _ in range(5)]

    assert added == [True, False, False, False, False]
    assert len(state.entries) == 3


def test_app_state_instances_do_not_share_entries():
    first, second = AppState(), AppState()

    first.entries[0].name = "Jan Kowalski #77"
    first.entries.append(EntryRow(driver_id=3))

    assert second.entries == [EntryRow(driver_id=1), EntryRow(driver_id=2)]


# --- Score parsing: plain unit tests, no GUI ---------------------------------

@pytest.mark.parametrize(("text", "expected"), [
    ("", None),       # empty field stays empty, it is not 0 while typing
    (None, None),     # ui.input reports None after its value is cleared
    ("0", 0),
    ("81", 81),
    ("100", 100),
    (" 81 ", 81),     # an accidental space is tolerated
])
def test_valid_scores_are_accepted(text, expected):
    assert is_valid_score(text) is True
    assert parse_score(text) == expected


@pytest.mark.parametrize("text", [
    "abc", "8a",      # text
    "-5",             # negative
    "101", "150",     # above 100
    "8.5", "1e2",     # not an integer written with digits only
    "+5",             # sign
    "²",              # Unicode digit, int() would fail on it
])
def test_invalid_scores_are_rejected(text):
    assert is_valid_score(text) is False
    assert parse_score(text) is None


# --- GUI: NiceGUI's simulated user runs main.py, no browser needed -----------
# Each test gets a fresh AppState (main.py runs again). The state lives inside
# main.py, so tests check what reached it by reloading the page: the new page
# is built only from AppState.

def _field(user: User, marker: str) -> ui.input:
    """Return the single input with this marker on the currently open page."""
    return next(iter(user.find(marker=marker).elements))


async def test_entry_table_starts_with_two_rows(user: User) -> None:
    await user.open("/")

    await user.should_see(marker="name-1")
    await user.should_see(marker="name-2")
    await user.should_not_see(marker="name-3")


async def test_name_in_last_row_adds_next_row_with_next_number(user: User) -> None:
    await user.open("/")

    user.find(marker="name-2").type("Piotr Nowak #12")
    await user.should_see(marker="name-3")
    await user.should_see(kind=ui.label, content="3.")

    user.find(marker="name-3").type("Adam Wiśniewski #5")
    await user.should_see(marker="name-4")
    await user.should_see(kind=ui.label, content="4.")


async def test_fast_typing_adds_one_row_and_keeps_the_field(user: User) -> None:
    await user.open("/")
    name_field = _field(user, "name-2")

    # One change event per character, like a fast typist in the browser.
    for char in "Jan Kowalski #77":
        user.find(marker="name-2").type(char)

    await user.should_see(marker="name-3")
    await user.should_not_see(marker="name-4")
    # Same element object: the field was never rebuilt, so it keeps the focus.
    assert _field(user, "name-2") is name_field
    assert name_field.value == "Jan Kowalski #77"


async def test_editing_earlier_row_works_and_adds_no_rows(user: User) -> None:
    await user.open("/")
    user.find(marker="name-2").type("Piotr Nowak #12")   # row 3 appears

    user.find(marker="name-1").type("Jan Kowalski #77")
    user.find(marker="run1-1").type("81")
    user.find(marker="run2-1").type("76")
    await user.should_not_see(marker="name-4")

    await user.open("/")   # like F5

    assert _field(user, "name-1").value == "Jan Kowalski #77"
    assert _field(user, "run1-1").value == "81"
    assert _field(user, "run2-1").value == "76"
    await user.should_see(marker="name-3")
    await user.should_not_see(marker="name-4")


@pytest.mark.parametrize("text", ["abc", "-5", "101"])
async def test_invalid_score_shows_error_and_is_not_stored(user: User, text: str) -> None:
    await user.open("/")

    # Character by character: "101" passes through the valid "10" on the way,
    # which must not stay in AppState once the field becomes invalid.
    for char in text:
        user.find(marker="run1-1").type(char)
    assert _field(user, "run1-1").error == SCORE_ERROR

    await user.open("/")
    # AppState got None, so the rebuilt field is empty and has no error.
    assert _field(user, "run1-1").value == ""


async def test_valid_score_is_stored(user: User) -> None:
    await user.open("/")

    user.find(marker="run2-1").type("81")
    assert _field(user, "run2-1").error is None

    await user.open("/")
    assert _field(user, "run2-1").value == "81"
