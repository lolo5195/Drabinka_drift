"""Shared look-and-feel for the PNG exports: palette, fonts, canvas, text fit.

Both renderers (`table_png.py`, `bracket_png.py`) draw through the `Painter`
defined here so that the standings table and the bracket share one palette,
one font family and one anti-aliasing strategy. Nothing in this module knows
about NiceGUI — the rendering layer must work (and is tested) without the UI.

Design decisions, in short:

* Colours are the client's own: sampled from the TOP32 graphic they attached
  to the requirements (magenta ``#C01D80``, slate ``#333C44``, connector grey
  ``#C8C8C8``). Matching their existing material beats inventing a palette.
* Every piece of text sits on an opaque plate. The PNG has a transparent
  background and will be composited over unknown backgrounds (stream video,
  white print, dark social-media templates); text drawn straight onto the
  transparent canvas would disappear on one of them.
* Fonts are bundled ``.ttf`` files from ``assets/fonts`` (Inter, SIL OFL).
  System fonts differ between Windows and macOS, and Pillow cannot synthesise
  a bold weight, so "bold" is a separate file rather than a fake stroke.
* Shapes are drawn at ``scale * SUPERSAMPLE`` and downsampled with Lanczos.
  ``ImageDraw`` does not anti-alias rectangles and lines; supersampling gives
  smooth edges and rounded corners at exactly the requested output size.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

RGBA = tuple[int, int, int, int]
Weight = Literal["regular", "bold"]

#: Internal oversampling factor used for anti-aliasing (see module docstring).
SUPERSAMPLE = 2

_FONT_FILES: dict[Weight, str] = {
    "regular": "Inter-Regular.ttf",
    "bold": "Inter-Bold.ttf",
}


# --- Palette -----------------------------------------------------------------

@dataclass(frozen=True)
class Theme:
    """Colours for one visual variant. All values are opaque RGBA."""

    accent: RGBA            # client's magenta: winners, headers, top seeds
    accent_text: RGBA       # text drawn on `accent`
    dark: RGBA              # client's slate: bottom seeds, secondary headers
    dark_text: RGBA         # text drawn on `dark`
    plate: RGBA             # background of a name / score cell
    plate_alt: RGBA         # alternating table rows
    plate_border: RGBA      # 1 px outline of a plate
    text: RGBA              # primary text on a plate
    text_muted: RGBA        # eliminated drivers, dashes, captions
    line: RGBA              # bracket connectors and table separators


#: Looks like the client's graphic: white cells, dark text. Default.
CLIENT_LIGHT = Theme(
    accent=(192, 29, 128, 255),
    accent_text=(255, 255, 255, 255),
    dark=(51, 60, 68, 255),
    dark_text=(255, 255, 255, 255),
    plate=(255, 255, 255, 255),
    plate_alt=(245, 246, 248, 255),
    plate_border=(208, 212, 216, 255),
    text=(31, 38, 46, 255),
    text_muted=(138, 147, 156, 255),
    line=(200, 200, 200, 255),
)

#: Same palette on slate cells for dark stream overlays.
CLIENT_DARK = Theme(
    accent=(192, 29, 128, 255),
    accent_text=(255, 255, 255, 255),
    dark=(90, 100, 110, 255),
    dark_text=(255, 255, 255, 255),
    plate=(51, 60, 68, 255),
    plate_alt=(58, 68, 77, 255),
    plate_border=(84, 95, 105, 255),
    text=(255, 255, 255, 255),
    text_muted=(160, 170, 180, 255),
    line=(130, 140, 150, 255),
)


# --- Geometry ----------------------------------------------------------------

@dataclass(frozen=True)
class Box:
    """Axis-aligned rectangle in logical pixels (before scaling)."""

    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def intersects(self, other: Box) -> bool:
        """True when the two boxes share any area (touching edges do not count)."""
        return (
            self.x < other.right
            and other.x < self.right
            and self.y < other.bottom
            and other.y < self.bottom
        )


# --- Fonts -------------------------------------------------------------------

def fonts_dir() -> Path:
    """Directory with the bundled ``.ttf`` files.

    Uses PyInstaller's unpack directory when the app is frozen (T-17), so the
    same code works from a checkout and from a one-file executable.
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "assets" / "fonts"


@lru_cache(maxsize=None)
def load_font(weight: Weight, pixel_size: int) -> ImageFont.FreeTypeFont:
    """Load (and cache) one weight at one pixel size."""
    path = fonts_dir() / _FONT_FILES[weight]
    return ImageFont.truetype(str(path), max(1, pixel_size))


# --- Canvas ------------------------------------------------------------------

class Painter:
    """Transparent RGBA canvas addressed in logical pixels.

    All coordinates and sizes passed in are logical; the painter multiplies
    them by ``scale * supersample`` internally and `finish()` returns the
    image at ``logical size * scale``.
    """

    def __init__(
        self,
        width: int,
        height: int,
        *,
        scale: int = 1,
        supersample: int = SUPERSAMPLE,
    ) -> None:
        if scale < 1 or supersample < 1:
            raise ValueError("scale and supersample must be >= 1")
        self.width = width
        self.height = height
        self.scale = scale
        self.supersample = supersample
        self.k = scale * supersample
        self.image = Image.new(
            "RGBA",
            (round(width * self.k), round(height * self.k)),
            (0, 0, 0, 0),
        )
        self.draw = ImageDraw.Draw(self.image)

    def _px(self, value: float) -> int:
        return round(value * self.k)

    def rect(
        self,
        box: Box,
        *,
        fill: RGBA | None = None,
        outline: RGBA | None = None,
        width: float = 1.0,
        radius: float = 0.0,
        corners: tuple[bool, bool, bool, bool] | None = None,
    ) -> None:
        """Fill and/or outline a box; `radius` rounds the corners."""
        xy = (
            self._px(box.x),
            self._px(box.y),
            self._px(box.right) - 1,
            self._px(box.bottom) - 1,
        )
        line_width = max(1, self._px(width)) if outline is not None else 0
        if radius > 0:
            self.draw.rounded_rectangle(
                xy,
                radius=self._px(radius),
                fill=fill,
                outline=outline,
                width=line_width,
                corners=corners,
            )
        else:
            self.draw.rectangle(xy, fill=fill, outline=outline, width=line_width)

    def polyline(
        self,
        points: list[tuple[float, float]],
        *,
        fill: RGBA,
        width: float = 1.0,
    ) -> None:
        """Draw connected straight segments (bracket connectors)."""
        self.draw.line(
            [(self._px(x), self._px(y)) for x, y in points],
            fill=fill,
            width=max(1, self._px(width)),
            joint="curve",
        )

    def text(
        self,
        xy: tuple[float, float],
        text: str,
        *,
        size: float,
        weight: Weight,
        fill: RGBA,
        anchor: str = "lm",
    ) -> None:
        """Draw text; `anchor` follows Pillow (e.g. "lm" = left, middle)."""
        font = load_font(weight, self._px(size))
        self.draw.text(
            (self._px(xy[0]), self._px(xy[1])),
            text,
            font=font,
            fill=fill,
            anchor=anchor,
        )

    def text_width(self, text: str, *, size: float, weight: Weight) -> float:
        """Advance width of `text` in logical pixels."""
        font = load_font(weight, self._px(size))
        return font.getlength(text) / self.k

    def finish(self) -> Image.Image:
        """Return the final image, downsampled to `scale` if supersampled."""
        if self.supersample == 1:
            return self.image
        target = (round(self.width * self.scale), round(self.height * self.scale))
        return self.image.resize(target, Image.Resampling.LANCZOS)


# --- Text fitting ------------------------------------------------------------

ELLIPSIS = "\u2026"


def fit_text(
    painter: Painter,
    text: str,
    *,
    weight: Weight,
    size: float,
    min_size: float,
    max_width: float,
) -> tuple[str, float]:
    """Shrink, then ellipsise, so `text` fits into `max_width`.

    Shrinking first keeps the full name readable whenever possible (a
    "Lewandowski" that lost two points of font size is better than
    "Lewandow…"). Only when the minimum size still overflows do we cut
    characters and append an ellipsis.
    """
    current = size
    while current > min_size and painter.text_width(text, size=current, weight=weight) > max_width:
        current -= 1
    if painter.text_width(text, size=current, weight=weight) <= max_width:
        return text, current

    trimmed = text
    while trimmed and painter.text_width(trimmed + ELLIPSIS, size=current, weight=weight) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed.rstrip() + ELLIPSIS) if trimmed else ELLIPSIS, current
