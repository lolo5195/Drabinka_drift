"""T-13: standings table rendered to a transparent PNG without the UI."""

import re
from pathlib import Path

import pytest
from PIL import Image

from cli_demo import SAMPLE_RESULTS
from logic.qualification import split_standings
from models import Driver, QualificationResult
from rendering.style import CLIENT_LIGHT, Painter, fit_text, load_font
from rendering.table_png import TableStyle, render_standings, score_weights

RENDERING_DIR = Path(__file__).resolve().parent.parent / "rendering"
STYLE = TableStyle()


# --- Helpers -----------------------------------------------------------------

def _demo_standings() -> tuple[list[QualificationResult | None], list[QualificationResult]]:
    return split_standings(SAMPLE_RESULTS)


def _rgb_close(pixel: tuple[int, ...], colour: tuple[int, ...], tolerance: int = 3) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(pixel[:3], colour[:3]))


# --- DoD 1: transparent background, no white rectangles ----------------------

def test_render_is_rgba_with_transparent_corners():
    main, extra = _demo_standings()
    image = render_standings(main, extra)

    assert image.mode == "RGBA"
    width, height = image.size
    for xy in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)):
        assert image.getpixel(xy)[3] == 0


def test_gap_between_tables_is_transparent():
    """The 33+ table is a separate block; the gap must not be a white plate."""
    main, extra = _demo_standings()
    image = render_standings(main, extra)

    gap_y = STYLE.margin + STYLE.header_h + 32 * STYLE.row_h + STYLE.table_gap // 2
    assert image.getpixel((image.width // 2, gap_y))[3] == 0


def test_header_uses_client_accent_colour():
    main, extra = _demo_standings()
    image = render_standings(main, extra)

    # Right end of the name header cell: inside the magenta bar, no text.
    x = STYLE.margin + STYLE.col_place + STYLE.col_name - 20
    y = STYLE.margin + STYLE.header_h // 2
    assert _rgb_close(image.getpixel((x, y)), CLIENT_LIGHT.accent)


# --- DoD 2: the better run is bold -------------------------------------------

@pytest.mark.parametrize(
    ("run1", "run2", "expected"),
    [
        (81, 76, ("bold", "regular")),
        (56, 81, ("regular", "bold")),
        (0, 81, ("regular", "bold")),
        (81, 81, ("bold", "bold")),
        (0, 0, ("regular", "regular")),
    ],
)
def test_score_weights(run1, run2, expected):
    assert score_weights(run1, run2) == expected


def test_bold_is_a_separate_font_file():
    """Pillow cannot synthesise bold: both weights must ship as .ttf files."""
    regular = load_font("regular", 20)
    bold = load_font("bold", 20)

    assert regular.path != bold.path
    assert Path(regular.path).exists() and Path(bold.path).exists()
    assert bold.getlength("Kowalski") > regular.getlength("Kowalski")


# --- DoD 3: long names stay inside the column --------------------------------

def test_long_name_is_shrunk_or_ellipsised_to_fit():
    painter = Painter(100, 100)
    max_width = STYLE.col_name - 2 * STYLE.pad
    name = "Bartłomiej Krzysztof Wielkopolski-Nowakowski #100 Drift Team Extra Long"

    text, size = fit_text(painter, name, weight="regular", size=STYLE.text_size,
                          min_size=STYLE.text_min_size, max_width=max_width)

    assert painter.text_width(text, size=size, weight="regular") <= max_width
    assert size >= STYLE.text_min_size
    assert text == name or text.endswith("\u2026")


def test_short_name_is_untouched():
    painter = Painter(100, 100)
    text, size = fit_text(painter, "Jan Kowalski #77", weight="regular", size=STYLE.text_size,
                          min_size=STYLE.text_min_size, max_width=STYLE.col_name - 2 * STYLE.pad)

    assert (text, size) == ("Jan Kowalski #77", STYLE.text_size)


# --- DoD 4: saving works without the UI --------------------------------------

def test_saves_png_file_without_ui(tmp_path):
    main, extra = _demo_standings()
    target = tmp_path / "standings.png"

    render_standings(main, extra).save(target)

    with Image.open(target) as saved:
        assert saved.format == "PNG"
        assert saved.mode == "RGBA"


def test_rendering_layer_does_not_import_ui():
    """Architecture rule from PLAN §1.2: rendering/ never touches ui/ or NiceGUI."""
    for path in RENDERING_DIR.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "nicegui" not in source, path
        assert not re.search(r"^\s*(from|import)\s+ui\b", source, re.MULTILINE), path


# --- Layout rules -------------------------------------------------------------

def test_extra_table_only_when_it_has_rows():
    main, extra = _demo_standings()

    with_extra = render_standings(main, extra)
    without_extra = render_standings(main, [])

    assert with_extra.height > without_extra.height
    assert without_extra.height == 2 * STYLE.margin + STYLE.header_h + 32 * STYLE.row_h
    assert without_extra.width == 2 * STYLE.margin + STYLE.table_w


def test_two_columns_is_wider_and_shorter():
    main, extra = _demo_standings()

    single = render_standings(main, [])
    double = render_standings(main, [], columns=2)

    assert double.width == 2 * STYLE.margin + 2 * STYLE.table_w + STYLE.column_gap
    assert double.height == 2 * STYLE.margin + STYLE.header_h + 16 * STYLE.row_h
    assert double.width > single.width and double.height < single.height


def test_invalid_column_count_is_rejected():
    main, extra = _demo_standings()
    with pytest.raises(ValueError):
        render_standings(main, extra, columns=3)


def test_empty_standings_render_as_dashes_without_error():
    image = render_standings([None] * 32, [])
    assert image.size == (2 * STYLE.margin + STYLE.table_w, 2 * STYLE.margin + STYLE.header_h + 32 * STYLE.row_h)


def test_all_zero_field_goes_to_extra_table_only():
    zeros = [QualificationResult(Driver(i, f"Zero {i}"), 0, 0) for i in range(1, 4)]
    main, extra = split_standings(zeros)

    image = render_standings(main, extra)

    expected = 2 * STYLE.margin + 2 * STYLE.header_h + 35 * STYLE.row_h + STYLE.table_gap
    assert image.height == expected


def test_scale_two_doubles_pixel_dimensions():
    main, extra = _demo_standings()
    base = render_standings(main, extra)
    large = render_standings(main, extra, scale=2)

    assert large.size == (base.width * 2, base.height * 2)
