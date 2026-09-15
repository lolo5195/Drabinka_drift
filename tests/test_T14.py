"""T-14: TOP32 bracket rendered to a transparent PNG without the UI."""

from itertools import combinations
from statistics import mean

import pytest
from PIL import Image

from cli_demo import SAMPLE_RESULTS
from logic.bracket import create_bracket, set_winner
from logic.qualification import split_standings
from models import Driver, Match, QualificationResult, TournamentBracket
from rendering.bracket_png import (
    BracketStyle,
    compute_layout,
    render_bracket,
    slot_state,
)
from rendering.style import CLIENT_DARK, CLIENT_LIGHT

STYLE = BracketStyle()
ALL_MATCHES: tuple[str, ...] = (
    *(f"T32_{i}" for i in range(1, 17)),
    *(f"T16_{i}" for i in range(1, 9)),
    *(f"T8_{i}" for i in range(1, 5)),
    "T4_1", "T4_2", "FINAL", "PLAYOFF",
)


# --- Helpers -----------------------------------------------------------------

def _standings(count: int) -> list[QualificationResult | None]:
    """Seed-ordered field of `count` drivers padded with None to 32 places."""
    rows: list[QualificationResult | None] = [
        QualificationResult(Driver(seed, f"Driver {seed}"), run1=101 - seed, run2=0)
        for seed in range(1, count + 1)
    ]
    rows.extend([None] * (32 - count))
    return rows


def _playable_side(match: Match) -> str | None:
    if match.slot_top is not None:
        return "top"
    if match.slot_bottom is not None:
        return "bottom"
    return None


def _play_everything(bracket: TournamentBracket) -> None:
    """Resolve every match (top slot preferred), skipping "-" vs "-"."""
    for match_id in ALL_MATCHES:
        side = _playable_side(bracket.matches[match_id])
        if side is not None:
            set_winner(bracket, match_id, side)


def _rgb_close(pixel: tuple[int, ...], colour: tuple[int, ...], tolerance: int = 3) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(pixel[:3], colour[:3]))


def _probe(image: Image.Image, x: float, y: float) -> tuple[int, ...]:
    return image.getpixel((int(x), int(y)))


# --- Layout geometry -----------------------------------------------------------

def test_fed_slot_sits_at_mean_height_of_its_feeders():
    bracket = create_bracket([None] * 32)
    layout = compute_layout(bracket)

    for match_id in ("T32_1", "T32_7", "T32_12", "T16_3", "T16_8", "T8_2", "T8_4"):
        match = bracket.matches[match_id]
        assert match.winner_goes_to is not None
        target = layout.slots[match.winner_goes_to]
        feeders = [layout.slots[(match_id, "top")].cy, layout.slots[(match_id, "bottom")].cy]
        assert target.cy == pytest.approx(mean(feeders))


def test_seed_badges_follow_seed_pairs():
    layout = compute_layout(create_bracket([None] * 32))

    assert layout.badges[("T32_1", "top")][1] == 1
    assert layout.badges[("T32_1", "bottom")][1] == 32
    assert layout.badges[("T32_2", "top")][1] == 16
    assert layout.badges[("T32_9", "top")][1] == 2
    assert layout.badges[("T32_9", "bottom")][1] == 31


def test_right_wing_mirrors_left_wing():
    layout = compute_layout(create_bracket([None] * 32))

    for left_id, right_id in (("T32_1", "T32_9"), ("T16_1", "T16_5"), ("T8_1", "T8_3"), ("T4_1", "T4_2")):
        for side in ("top", "bottom"):
            left = layout.slots[(left_id, side)]
            right = layout.slots[(right_id, side)]
            assert right.x == pytest.approx(STYLE.width - left.x - left.w)
            assert right.cy == pytest.approx(left.cy)
    left_badge = layout.badges[("T32_1", "top")][0]
    right_badge = layout.badges[("T32_9", "top")][0]
    assert right_badge.x == pytest.approx(STYLE.width - left_badge.x - left_badge.w)


def test_no_two_boxes_overlap():
    """The compact overlapping columns must never put two plates on top of each other."""
    layout = compute_layout(create_bracket([None] * 32), title="Tytuł", subtitle="Podtytuł")
    boxes = layout.all_boxes()

    assert len(boxes) == 32 + 16 + 8 + 4 + 2 + 2 + 32 + 8   # slots, badges, podium
    for a, b in combinations(boxes, 2):
        assert not a.intersects(b), (a, b)


def test_all_boxes_lie_inside_the_canvas():
    layout = compute_layout(create_bracket([None] * 32))

    for box in layout.all_boxes():
        assert 0 <= box.x and box.right <= layout.width
        assert 0 <= box.y and box.bottom <= layout.height


def test_layout_does_not_depend_on_results():
    empty = create_bracket(_standings(32))
    finished = create_bracket(_standings(32))
    _play_everything(finished)

    assert compute_layout(empty).slots == compute_layout(finished).slots
    assert compute_layout(empty).connectors == compute_layout(finished).connectors


def test_final_and_playoff_are_centred():
    layout = compute_layout(create_bracket([None] * 32))
    for key in (("FINAL", "top"), ("FINAL", "bottom"), ("PLAYOFF", "top"), ("PLAYOFF", "bottom")):
        assert layout.slots[key].cx == pytest.approx(STYLE.width / 2)
    assert layout.slots[("FINAL", "top")].bottom < layout.slots[("FINAL", "bottom")].y


# --- slot_state ---------------------------------------------------------------

def test_slot_state_classification():
    bracket = create_bracket(_standings(32))
    match = bracket.matches["T32_1"]

    assert slot_state(match, None) == "empty"
    assert slot_state(match, match.slot_top) == "pending"
    set_winner(bracket, "T32_1", "top")
    assert slot_state(match, match.slot_top) == "winner"
    assert slot_state(match, match.slot_bottom) == "loser"


# --- Rendering -----------------------------------------------------------------

def test_render_is_rgba_1920_wide_with_transparent_corners():
    image = render_bracket(create_bracket(_standings(32)))

    assert image.mode == "RGBA"
    assert image.width == STYLE.width
    for xy in ((0, 0), (image.width - 1, 0), (0, image.height - 1), (image.width - 1, image.height - 1)):
        assert image.getpixel(xy)[3] == 0


def test_winner_and_loser_plates_reflect_the_bracket_state():
    bracket = create_bracket(_standings(32))
    set_winner(bracket, "T32_1", "top")
    image = render_bracket(bracket)
    layout = compute_layout(bracket)

    winner = layout.slots[("T32_1", "top")]
    loser = layout.slots[("T32_1", "bottom")]
    untouched = layout.slots[("T32_2", "top")]
    # Right end of a left-wing plate: inside the fill, clear of the (left-aligned) name.
    assert _rgb_close(_probe(image, winner.right - 6, winner.cy), CLIENT_LIGHT.accent)
    assert _rgb_close(_probe(image, loser.right - 6, loser.cy), CLIENT_LIGHT.plate)
    assert _rgb_close(_probe(image, untouched.right - 6, untouched.cy), CLIENT_LIGHT.plate)


def test_empty_seed_is_drawn_as_a_plate_with_a_dash():
    main, _extra = split_standings(SAMPLE_RESULTS)          # 10 drivers: seed 16 is "-"
    bracket = create_bracket(main)
    assert bracket.matches["T32_2"].slot_top is None
    image = render_bracket(bracket)
    layout = compute_layout(bracket)

    box = layout.slots[("T32_2", "top")]
    assert _rgb_close(_probe(image, box.x + 6, box.cy), CLIENT_LIGHT.plate)       # plate is there
    assert not _rgb_close(_probe(image, box.cx, box.cy), CLIENT_LIGHT.plate)      # the dash is there


def test_podium_is_highlighted_after_a_finished_tournament():
    bracket = create_bracket(_standings(32))
    _play_everything(bracket)
    assert all(bracket.podium[place] is not None for place in (1, 2, 3, 4))
    image = render_bracket(bracket)
    layout = compute_layout(bracket)

    _badge, first = layout.podium[1]
    _badge, second = layout.podium[2]
    assert _rgb_close(_probe(image, first.right - 6, first.cy), CLIENT_LIGHT.accent)
    assert _rgb_close(_probe(image, second.right - 6, second.cy), CLIENT_LIGHT.plate)


def test_dark_theme_uses_slate_plates():
    bracket = create_bracket(_standings(32))
    image = render_bracket(bracket, theme=CLIENT_DARK)
    box = compute_layout(bracket).slots[("T32_1", "top")]

    assert _rgb_close(_probe(image, box.right - 6, box.cy), CLIENT_DARK.plate)


@pytest.mark.parametrize("count", [0, 1, 10, 28, 32])
def test_any_field_size_renders_in_every_state(count):
    bracket = create_bracket(_standings(count))
    render_bracket(bracket)                    # freshly generated
    _play_everything(bracket)
    image = render_bracket(bracket)            # played as far as possible
    assert image.width == STYLE.width


def test_correction_after_the_final_still_renders():
    bracket = create_bracket(_standings(32))
    _play_everything(bracket)
    set_winner(bracket, "T32_1", "bottom")     # cascades down to the podium
    assert bracket.podium[1] is None

    image = render_bracket(bracket)
    layout = compute_layout(bracket)
    _badge, first = layout.podium[1]
    assert _rgb_close(_probe(image, first.right - 6, first.cy), CLIENT_LIGHT.plate)


def test_title_adds_height_and_scale_doubles_size():
    bracket = create_bracket(_standings(32))
    plain = render_bracket(bracket)
    titled = render_bracket(bracket, title="DRIFT CUP", subtitle="TOP 32")
    large = render_bracket(bracket, scale=2)

    assert titled.height > plain.height
    assert large.size == (plain.width * 2, plain.height * 2)


def test_saves_png_file_without_ui(tmp_path):
    target = tmp_path / "bracket.png"
    render_bracket(create_bracket(_standings(10))).save(target)

    with Image.open(target) as saved:
        assert saved.format == "PNG"
        assert saved.mode == "RGBA"
