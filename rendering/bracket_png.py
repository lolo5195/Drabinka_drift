"""T-14: draw the TOP32 bracket as a transparent PNG with Pillow (no UI).

The picture follows the client's own template (the graphic attached to the
requirements) and their sketch of the centre:

* left wing ``T32 -> T16 -> T8 -> T4``, right wing mirrored, seeds 1/32 at
  the top left and 2/31 at the top right, exactly like ``SEED_PAIRS``;
* seed badges next to the TOP32 slots: magenta for the higher seed on top,
  slate for the lower seed below — the colour code of the template;
* consecutive round columns overlap horizontally and the winner's box sits
  *on* the vertical line joining the pair that feeds it — the trick the
  template uses to fit four rounds per wing into a 1920 px wide image while
  keeping names readable;
* centre column: ``FINAŁ`` (two stacked rows fed by the semi-final winners),
  ``PLAY-OFF`` for third place (semi-final losers) and the podium 1–4.

The module is split in two pure steps so the geometry can be unit-tested
without looking at pixels:

* `compute_layout` turns a `TournamentBracket` into boxes, badges, labels and
  connector polylines in logical pixels;
* `render_bracket` paints that layout through `Painter`.

Rendering any state is supported — empty (fresh bracket), partially played,
finished with a full podium — because the picture is derived purely from the
`TournamentBracket` produced by ``logic/``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from PIL import Image

from logic.bracket import SEED_PAIRS
from models import Driver, Match, TournamentBracket
from rendering.style import (
    CLIENT_LIGHT,
    Box,
    Painter,
    Theme,
    Weight,
    fit_text,
)

SlotKey = tuple[str, str]           # (match_id, "top" | "bottom")
Align = Literal["left", "right", "center"]
SlotState = Literal["winner", "loser", "pending", "empty"]

#: Regular rounds with the column index their *winner* lands in.
_FEEDING_ROUNDS: tuple[tuple[str, int, int], ...] = (
    ("T32", 16, 1),
    ("T16", 8, 2),
    ("T8", 4, 3),
)
_ROUND_LABELS: tuple[str, ...] = ("TOP 32", "TOP 16", "TOP 8", "TOP 4")


@dataclass(frozen=True)
class BracketStyle:
    """Geometry of the bracket in logical pixels (default width 1920)."""

    width: int = 1920
    margin: int = 40
    slot_w: int = 200           # name plate width (all rounds)
    slot_h: int = 34
    row_pitch: int = 50         # vertical distance between TOP32 rows
    badge_w: int = 36           # seed badge next to TOP32 slots
    badge_gap: int = 6
    first_gap: int = 36         # TOP32 plates -> TOP16 plates (no overlap)
    stub: int = 14              # horizontal stub from a plate to the pair line
    line_w: float = 2.0
    radius: int = 4
    pad: int = 10               # text padding inside a plate
    name_size: int = 17
    name_min_size: int = 13
    badge_size: int = 15
    label_size: int = 15
    title_size: int = 30
    subtitle_size: int = 18
    label_gap: int = 30         # room for round labels above the first row
    center_w: int = 300         # FINAL / PLAY-OFF / podium block width
    center_divider: int = 2     # gap between the two rows of FINAL / PLAY-OFF
    center_gap: int = 24        # elbow distance in front of the FINAL box
    center_block_gap: int = 36  # FINAL -> PLAY-OFF -> PODIUM spacing
    podium_pitch: int = 42

    @property
    def column_shift(self) -> float:
        """Horizontal shift between overlapping columns.

        Chosen so the vertical pair line (``plate right edge + stub``) runs
        through the middle of the next round's plate.
        """
        return self.slot_w / 2 + self.stub


@dataclass(frozen=True)
class Label:
    """Free-standing text drawn in the accent colour (no plate)."""

    text: str
    x: float
    y: float
    size: float
    weight: Weight = "bold"
    anchor: str = "mm"


@dataclass
class BracketLayout:
    """Everything `render_bracket` needs, in logical pixels."""

    width: int
    height: int
    slots: dict[SlotKey, Box] = field(default_factory=dict)
    slot_align: dict[SlotKey, Align] = field(default_factory=dict)
    badges: dict[SlotKey, tuple[Box, int]] = field(default_factory=dict)
    podium: dict[int, tuple[Box, Box]] = field(default_factory=dict)
    labels: list[Label] = field(default_factory=list)
    connectors: list[list[tuple[float, float]]] = field(default_factory=list)

    def all_boxes(self) -> list[Box]:
        """Every opaque box — used to assert the layout has no collisions."""
        boxes = list(self.slots.values())
        boxes.extend(box for box, _seed in self.badges.values())
        for badge, name in self.podium.values():
            boxes.extend((badge, name))
        return boxes


# --- Layout ------------------------------------------------------------------

def _pair_connector(
    a: Box,
    b: Box,
    *,
    left: bool,
    style: BracketStyle,
    into: Box,
) -> list[list[tuple[float, float]]]:
    """Connector for the pair (a, b) whose winner lands in `into`.

    Draws a bracket-shaped polyline: stub from `a`, vertical line, stub back
    to `b`. When `into` overlaps that vertical line horizontally (the
    compact columns), the plate is simply painted over the line later; when
    it does not (TOP32 -> TOP16), a horizontal lead reaches `into`.
    """
    if left:
        x_edge, x_line = a.right, a.right + style.stub
    else:
        x_edge, x_line = a.x, a.x - style.stub
    lines = [[(x_edge, a.cy), (x_line, a.cy), (x_line, b.cy), (x_edge, b.cy)]]
    if not into.x <= x_line <= into.right:
        cy = (a.cy + b.cy) / 2
        x_target = into.x if left else into.right
        lines.append([(x_line, cy), (x_target, cy)])
    return lines


def compute_layout(
    bracket: TournamentBracket,
    style: BracketStyle = BracketStyle(),
    *,
    title: str | None = None,
    subtitle: str | None = None,
) -> BracketLayout:
    """Compute boxes, badges, labels and connectors for `bracket`.

    Only the wiring (`winner_goes_to`) of the bracket is used, so the same
    layout is produced for an empty, partial or finished tournament — the
    picture changes, the geometry does not.
    """
    st = style
    layout = BracketLayout(width=st.width, height=0)
    center_x = st.width / 2

    # Title block (optional), then a row of round labels, then the rows.
    top = float(st.margin)
    if title:
        layout.labels.append(Label(title, center_x, top + st.title_size / 2, st.title_size))
        top += st.title_size + 8
        if subtitle:
            layout.labels.append(
                Label(subtitle, center_x, top + st.subtitle_size / 2, st.subtitle_size),
            )
            top += st.subtitle_size + 8
        top += 8
    label_y = top + st.label_gap / 2
    y0 = top + st.label_gap + st.slot_h / 2          # centre of TOP32 row 0

    # Column x positions for the left wing; the right wing is mirrored.
    x_cols = [st.margin + st.badge_w + st.badge_gap]
    x_cols.append(x_cols[0] + st.slot_w + st.first_gap)
    x_cols.append(x_cols[1] + st.column_shift)
    x_cols.append(x_cols[2] + st.column_shift)

    def slot_x(column: int, left: bool) -> float:
        x = x_cols[column]
        return x if left else st.width - x - st.slot_w

    # Round labels above both wings.
    first_center = st.margin + (st.badge_w + st.badge_gap + st.slot_w) / 2
    for column, text in enumerate(_ROUND_LABELS):
        cx = first_center if column == 0 else x_cols[column] + st.slot_w / 2
        layout.labels.append(Label(text, cx, label_y, st.label_size))
        layout.labels.append(Label(text, st.width - cx, label_y, st.label_size))

    # TOP32 slots and seed badges: match i occupies rows 2(i-1) and 2(i-1)+1
    # of its wing; matches 1-8 are the left wing, 9-16 the right wing.
    for number, (seed_top, seed_bottom) in enumerate(SEED_PAIRS, start=1):
        match_id = f"T32_{number}"
        left = number <= 8
        first_row = 2 * ((number - 1) % 8)
        for side, seed, row in (("top", seed_top, first_row), ("bottom", seed_bottom, first_row + 1)):
            cy = y0 + row * st.row_pitch
            key: SlotKey = (match_id, side)
            layout.slots[key] = Box(slot_x(0, left), cy - st.slot_h / 2, st.slot_w, st.slot_h)
            layout.slot_align[key] = "left" if left else "right"
            badge_x = st.margin if left else st.width - st.margin - st.badge_w
            layout.badges[key] = (Box(badge_x, cy - st.slot_h / 2, st.badge_w, st.slot_h), seed)

    # Later rounds: the slot a match feeds sits at the mean y of its two
    # slots (the wiring comes from logic/, not from a second copy of the rule).
    for round_name, count, next_column in _FEEDING_ROUNDS:
        for number in range(1, count + 1):
            match = bracket.matches[f"{round_name}_{number}"]
            if match.winner_goes_to is None:
                raise ValueError(f"{match.match_id} has no winner destination")
            target: SlotKey = match.winner_goes_to
            a = layout.slots[(match.match_id, "top")]
            b = layout.slots[(match.match_id, "bottom")]
            left = number <= count / 2
            cy = (a.cy + b.cy) / 2
            layout.slots[target] = Box(slot_x(next_column, left), cy - st.slot_h / 2, st.slot_w, st.slot_h)
            layout.slot_align[target] = "left" if left else "right"
            layout.connectors.extend(_pair_connector(a, b, left=left, style=st, into=layout.slots[target]))

    # Centre column: FINAL at the convergence point, then PLAY-OFF, then podium.
    y_mid = y0 + 7.5 * st.row_pitch
    box_x = center_x - st.center_w / 2
    final_top = Box(box_x, y_mid - st.center_divider / 2 - st.slot_h, st.center_w, st.slot_h)
    final_bottom = Box(box_x, y_mid + st.center_divider / 2, st.center_w, st.slot_h)
    layout.slots[("FINAL", "top")] = final_top
    layout.slots[("FINAL", "bottom")] = final_bottom
    layout.slot_align[("FINAL", "top")] = layout.slot_align[("FINAL", "bottom")] = "center"
    layout.labels.append(Label("FINAŁ", center_x, final_top.y - st.label_size, st.label_size))

    playoff_label_y = final_bottom.bottom + st.center_block_gap
    playoff_top_y = playoff_label_y + st.label_size
    layout.labels.append(Label("PLAY-OFF · 3. MIEJSCE", center_x, playoff_label_y, st.label_size))
    layout.slots[("PLAYOFF", "top")] = Box(box_x, playoff_top_y, st.center_w, st.slot_h)
    layout.slots[("PLAYOFF", "bottom")] = Box(
        box_x, playoff_top_y + st.slot_h + st.center_divider, st.center_w, st.slot_h,
    )
    layout.slot_align[("PLAYOFF", "top")] = layout.slot_align[("PLAYOFF", "bottom")] = "center"

    # Each semi-final feeds both centre matches: its winner goes to FINAL and
    # its loser to PLAY-OFF. Follow the bracket wiring rather than duplicating
    # those destination slots here.
    for match_id, left in (("T4_1", True), ("T4_2", False)):
        match = bracket.matches[match_id]
        if match.winner_goes_to is None or match.loser_goes_to is None:
            raise ValueError(f"{match_id} has incomplete centre destinations")
        a = layout.slots[(match_id, "top")]
        b = layout.slots[(match_id, "bottom")]
        x_edge, x_line = (a.right, a.right + st.stub) if left else (a.x, a.x - st.stub)
        junction_y = (a.cy + b.cy) / 2
        x_elbow = box_x - st.center_gap if left else box_x + st.center_w + st.center_gap
        layout.connectors.append([(x_edge, a.cy), (x_line, a.cy), (x_line, b.cy), (x_edge, b.cy)])
        layout.connectors.append([(x_line, junction_y), (x_elbow, junction_y)])
        for destination in (match.winner_goes_to, match.loser_goes_to):
            target = layout.slots[destination]
            x_target = target.x if left else target.right
            layout.connectors.append(
                [(x_elbow, junction_y), (x_elbow, target.cy), (x_target, target.cy)],
            )

    podium_label_y = layout.slots[("PLAYOFF", "bottom")].bottom + st.center_block_gap
    layout.labels.append(Label("PODIUM", center_x, podium_label_y, st.label_size))
    podium_top = podium_label_y + st.label_size
    name_x = box_x + st.badge_w + st.badge_gap
    name_w = st.center_w - st.badge_w - st.badge_gap
    for place in (1, 2, 3, 4):
        y = podium_top + (place - 1) * st.podium_pitch
        layout.podium[place] = (
            Box(box_x, y, st.badge_w, st.slot_h),
            Box(name_x, y, name_w, st.slot_h),
        )

    wing_bottom = y0 + 15 * st.row_pitch + st.slot_h / 2
    podium_bottom = layout.podium[4][1].bottom
    layout.height = round(max(wing_bottom, podium_bottom) + st.margin)
    return layout


# --- Painting ----------------------------------------------------------------

def slot_state(match: Match, driver: Driver | None) -> SlotState:
    """Classify a slot for styling: winner / loser / pending / empty ("-")."""
    if driver is None:
        return "empty"
    if match.winner is None:
        return "pending"
    return "winner" if match.winner == driver else "loser"


def _draw_plate(
    painter: Painter,
    box: Box,
    driver: Driver | None,
    state: SlotState,
    align: Align,
    theme: Theme,
    style: BracketStyle,
) -> None:
    """Draw one name plate. Winners get the magenta fill and bold text."""
    if state == "winner":
        fill, text_fill, weight = theme.accent, theme.accent_text, "bold"
        outline = None
    elif state == "loser":
        fill, text_fill, weight = theme.plate, theme.text_muted, "regular"
        outline = theme.plate_border
    else:
        fill, text_fill, weight = theme.plate, theme.text, "regular"
        outline = theme.plate_border
    painter.rect(box, fill=fill, outline=outline, radius=style.radius)

    if driver is None:
        painter.text((box.cx, box.cy), "-", size=style.name_size, weight="regular",
                     fill=theme.text_muted, anchor="mm")
        return

    label, size = fit_text(
        painter, driver.name, weight=weight, size=style.name_size,
        min_size=style.name_min_size, max_width=box.w - 2 * style.pad,
    )
    if align == "left":
        painter.text((box.x + style.pad, box.cy), label, size=size, weight=weight, fill=text_fill, anchor="lm")
    elif align == "right":
        painter.text((box.right - style.pad, box.cy), label, size=size, weight=weight, fill=text_fill, anchor="rm")
    else:
        painter.text((box.cx, box.cy), label, size=size, weight=weight, fill=text_fill, anchor="mm")


def _draw_badge(painter: Painter, box: Box, text: str, *, accent: bool, theme: Theme, style: BracketStyle) -> None:
    fill = theme.accent if accent else theme.dark
    text_fill = theme.accent_text if accent else theme.dark_text
    painter.rect(box, fill=fill, radius=style.radius)
    painter.text((box.cx, box.cy), text, size=style.badge_size, weight="bold", fill=text_fill, anchor="mm")


def render_bracket(
    bracket: TournamentBracket,
    *,
    title: str | None = None,
    subtitle: str | None = None,
    theme: Theme = CLIENT_LIGHT,
    style: BracketStyle = BracketStyle(),
    scale: int = 1,
) -> Image.Image:
    """Render `bracket` to a transparent RGBA image (``style.width * scale`` px wide).

    Paint order matters: connectors first, then plates and badges on top, so
    the compact columns hide the pair line behind the winner's plate exactly
    like in the client's template.
    """
    layout = compute_layout(bracket, style, title=title, subtitle=subtitle)
    painter = Painter(layout.width, layout.height, scale=scale)

    for points in layout.connectors:
        painter.polyline(points, fill=theme.line, width=style.line_w)

    for label in layout.labels:
        painter.text((label.x, label.y), label.text, size=label.size, weight=label.weight,
                     fill=theme.accent, anchor=label.anchor)

    for (_match_id, side), (box, seed) in layout.badges.items():
        _draw_badge(painter, box, str(seed), accent=(side == "top"), theme=theme, style=style)

    for (match_id, side), box in layout.slots.items():
        match = bracket.matches[match_id]
        driver = match.slot_top if side == "top" else match.slot_bottom
        _draw_plate(painter, box, driver, slot_state(match, driver),
                    layout.slot_align[(match_id, side)], theme, style)

    for place, (badge, name_box) in layout.podium.items():
        driver = bracket.podium[place]
        _draw_badge(painter, badge, str(place), accent=(place == 1), theme=theme, style=style)
        state: SlotState = "empty" if driver is None else ("winner" if place == 1 else "pending")
        _draw_plate(painter, name_box, driver, state, "left", theme, style)

    return painter.finish()
