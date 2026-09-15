"""T-13: draw the qualification standings as a transparent PNG (Pillow, no UI).

Input is exactly what ``logic.qualification.split_standings`` returns:

* ``main``  — 32 entries for places 1–32, ``None`` = row of dashes;
* ``extra`` — places 33+ (drivers with ``(0, 0)`` and any overflow).

The picture reproduces the client's table from the requirements — columns
``Miejsce | Imię i nazwisko nr startowy | Wynik 1. przejazdu | Wynik 2.
przejazdu`` — with the better of the two runs in bold, the 33+ table as a
separate block that only appears when it has rows, and dashes for empty
places. Every cell sits on an opaque plate so the export stays legible on
any background (see ``rendering/style.py``).

``columns=2`` splits places 1–16 | 17–32 side by side: a 32-row table is
taller than a 16:9 frame, and a stream overlay or a social-media post needs a
wide, not a tall, image. The single-column layout matches the spec literally
and stays the default.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from PIL import Image

from models import QualificationResult
from rendering.style import (
    CLIENT_LIGHT,
    Box,
    Painter,
    Theme,
    Weight,
    fit_text,
)

#: Column titles exactly as written in the client's requirements.
HEADERS: tuple[str, str, str, str] = (
    "Miejsce",
    "Imię i nazwisko nr startowy",
    "Wynik 1. przejazdu",
    "Wynik 2. przejazdu",
)

#: Numbering of the first row in the 33+ table (PLAN §2.1).
EXTRA_FIRST_PLACE = 33


@dataclass(frozen=True)
class TableStyle:
    """Geometry of the standings table in logical pixels."""

    margin: int = 16
    col_place: int = 100
    col_name: int = 540
    col_run: int = 190
    header_h: int = 48
    row_h: int = 40
    header_size: int = 17
    text_size: int = 19
    text_min_size: int = 13
    badge_w: int = 36
    badge_h: int = 28
    badge_size: int = 15
    badge_radius: int = 6
    radius: int = 10
    pad: int = 14
    column_gap: int = 32        # between the two halves when columns=2
    table_gap: int = 36         # between the 1–32 table and the 33+ table
    title_size: int = 26

    @property
    def table_w(self) -> int:
        return self.col_place + self.col_name + 2 * self.col_run


def score_weights(run1: int, run2: int) -> tuple[Weight, Weight]:
    """Font weights for the two runs: the better run is bold.

    Equal runs are both bold — there is no "worse" run to demote.
    """
    if run1 == run2:
        return "bold", "bold"
    return ("bold", "regular") if run1 > run2 else ("regular", "bold")


@dataclass(frozen=True)
class _Block:
    """One header + rows block at a given position."""

    x: float
    y: float
    rows: list[tuple[int, QualificationResult | None]]
    accent: bool                # accent header (1–32) or slate header (33+)

    def height(self, style: TableStyle) -> float:
        return style.header_h + len(self.rows) * style.row_h


def _draw_block(painter: Painter, block: _Block, style: TableStyle, theme: Theme) -> None:
    st = style
    x, y = block.x, block.y
    x_name = x + st.col_place
    x_run1 = x_name + st.col_name
    x_run2 = x_run1 + st.col_run

    header_fill = theme.accent if block.accent else theme.dark
    header_text = theme.accent_text if block.accent else theme.dark_text
    header = Box(x, y, st.table_w, st.header_h)
    painter.rect(header, fill=header_fill, radius=st.radius, corners=(True, True, False, False))
    painter.text((x + st.col_place / 2, header.cy), HEADERS[0], size=st.header_size,
                 weight="bold", fill=header_text, anchor="mm")
    painter.text((x_name + st.pad, header.cy), HEADERS[1], size=st.header_size,
                 weight="bold", fill=header_text, anchor="lm")
    painter.text((x_run1 + st.col_run / 2, header.cy), HEADERS[2], size=st.header_size,
                 weight="bold", fill=header_text, anchor="mm")
    painter.text((x_run2 + st.col_run / 2, header.cy), HEADERS[3], size=st.header_size,
                 weight="bold", fill=header_text, anchor="mm")

    if not block.rows:
        return
    body = Box(x, y + st.header_h, st.table_w, len(block.rows) * st.row_h)
    painter.rect(body, fill=theme.plate, radius=st.radius, corners=(False, False, True, True))

    for index, (place, result) in enumerate(block.rows):
        row = Box(x, body.y + index * st.row_h, st.table_w, st.row_h)
        last = index == len(block.rows) - 1
        if index % 2 == 1:
            painter.rect(row, fill=theme.plate_alt, radius=st.radius if last else 0,
                         corners=(False, False, True, True) if last else None)
        if index > 0:
            painter.polyline([(x, row.y), (x + st.table_w, row.y)], fill=theme.line, width=1)

        badge = Box(x + (st.col_place - st.badge_w) / 2, row.cy - st.badge_h / 2, st.badge_w, st.badge_h)
        if result is None:
            # Empty place: outlined badge and dashes in every column (spec).
            painter.rect(badge, outline=theme.plate_border, radius=st.badge_radius)
            painter.text((badge.cx, badge.cy), str(place), size=st.badge_size, weight="bold",
                         fill=theme.text_muted, anchor="mm")
            painter.text((x_name + st.pad, row.cy), "-", size=st.text_size, weight="regular",
                         fill=theme.text_muted, anchor="lm")
            for cx in (x_run1 + st.col_run / 2, x_run2 + st.col_run / 2):
                painter.text((cx, row.cy), "-", size=st.text_size, weight="regular",
                             fill=theme.text_muted, anchor="mm")
            continue

        painter.rect(badge, fill=header_fill, radius=st.badge_radius)
        painter.text((badge.cx, badge.cy), str(place), size=st.badge_size, weight="bold",
                     fill=header_text, anchor="mm")
        name, size = fit_text(painter, result.driver.name, weight="regular", size=st.text_size,
                              min_size=st.text_min_size, max_width=st.col_name - 2 * st.pad)
        painter.text((x_name + st.pad, row.cy), name, size=size, weight="regular",
                     fill=theme.text, anchor="lm")
        weight1, weight2 = score_weights(result.run1, result.run2)
        painter.text((x_run1 + st.col_run / 2, row.cy), str(result.run1), size=st.text_size,
                     weight=weight1, fill=theme.text, anchor="mm")
        painter.text((x_run2 + st.col_run / 2, row.cy), str(result.run2), size=st.text_size,
                     weight=weight2, fill=theme.text, anchor="mm")

    # Outline last so row tints never paint over the border.
    painter.rect(body, outline=theme.plate_border, radius=st.radius, corners=(False, False, True, True))


def render_standings(
    main: list[QualificationResult | None],
    extra: list[QualificationResult],
    *,
    columns: int = 1,
    title: str | None = None,
    theme: Theme = CLIENT_LIGHT,
    style: TableStyle = TableStyle(),
    scale: int = 1,
) -> Image.Image:
    """Render the 1–32 table (and the 33+ table when `extra` is non-empty).

    `columns` is 1 (spec layout, one tall table) or 2 (places 1–16 | 17–32
    side by side). The 33+ block, when present, goes under the first column.
    """
    if columns not in (1, 2):
        raise ValueError("columns must be 1 or 2")
    st = style

    numbered = list(enumerate(main, start=1))
    half = ceil(len(numbered) / 2) if columns == 2 else len(numbered)
    top = float(st.margin)
    if title:
        top += st.title_size + 12

    blocks: list[_Block] = []
    for column in range(columns):
        rows = numbered[column * half:(column + 1) * half]
        x = st.margin + column * (st.table_w + st.column_gap)
        blocks.append(_Block(x, top, rows, accent=True))
    main_bottom = max(block.y + block.height(st) for block in blocks)

    if extra:
        extra_rows = list(enumerate(extra, start=EXTRA_FIRST_PLACE))
        blocks.append(_Block(st.margin, main_bottom + st.table_gap, extra_rows, accent=False))

    width = 2 * st.margin + columns * st.table_w + (columns - 1) * st.column_gap
    height = round(max(block.y + block.height(st) for block in blocks) + st.margin)
    painter = Painter(width, height, scale=scale)

    if title:
        painter.text((st.margin, st.margin + st.title_size / 2), title, size=st.title_size,
                     weight="bold", fill=theme.accent, anchor="lm")
    for block in blocks:
        _draw_block(painter, block, st, theme)
    return painter.finish()
