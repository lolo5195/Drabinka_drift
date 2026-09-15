"""Render the sample PNGs used to show the export to the client.

Builds standings and brackets from the ``cli_demo`` data (the mandatory
"10 drivers > 0" scenario from PLAN §4.3, plus two ``(0, 0)`` entries) and
from a full field of 32 drivers, and writes:

* ``standings_demo.png``          – table 1–32 with dashes + table 33+ (spec case)
* ``standings_full32_2col.png``   – 32 drivers, places 1–16 | 17–32 side by side
* ``bracket_demo_empty.png``      – bracket right after "Generuj drabinkę"
* ``bracket_demo_final.png``      – the same bracket played through to the podium
* ``bracket_full32_partial.png``  – 32 drivers, mid-event (TOP32 + TOP16 done)
* ``bracket_full32_partial_dark.png`` – the same on the dark variant of the palette
* ``preview_stream_*.jpg``        – the transparent exports composited on a dark
                                    gradient, i.e. what an OBS overlay would look like

All PNGs have a transparent background. Run ``python demo_png.py`` from the
project root; use ``--out`` to change the folder and ``--scale 2`` for a
retina/print-size version.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from PIL import Image

from cli_demo import SAMPLE_RESULTS
from logic.bracket import create_bracket, set_winner
from logic.qualification import split_standings
from models import Driver, QualificationResult, TournamentBracket
from rendering.bracket_png import render_bracket
from rendering.style import CLIENT_DARK, CLIENT_LIGHT
from rendering.table_png import render_standings

DEFAULT_OUT = Path("assets") / "samples"
EVENT_TITLE = "DRIFT CUP 2026"
BRACKET_SUBTITLE = "DRABINKA TOP 32"
STANDINGS_TITLE = "WYNIKI KWALIFIKACJI"

#: Every match id in the order a real event plays them.
MATCH_ORDER: tuple[str, ...] = (
    *(f"T32_{i}" for i in range(1, 17)),
    *(f"T16_{i}" for i in range(1, 9)),
    *(f"T8_{i}" for i in range(1, 5)),
    "T4_1", "T4_2", "FINAL", "PLAYOFF",
)

_FIRST_NAMES = (
    "Adam", "Bartosz", "Damian", "Filip", "Jakub", "Kacper", "Kamil", "Konrad",
    "Mateusz", "Michał", "Patryk", "Paweł", "Piotr", "Przemysław", "Rafał", "Sebastian",
)
_LAST_NAMES = (
    "Nowicki", "Górski", "Pawlak", "Michalski", "Zając", "Król", "Wieczorek", "Jabłoński",
    "Wróbel", "Majewski", "Olszewski", "Stępień", "Malinowski", "Jaworski", "Adamczyk", "Dudek",
    "Sikora", "Baran", "Rutkowski", "Michalak", "Szewczyk", "Ostrowski", "Tomaszewski", "Pietrzak",
    "Marciniak", "Wróblewski", "Zalewski", "Jakubowski", "Jasiński", "Zawadzki", "Sadowski", "Bąk",
)


def full_field(count: int = 32) -> list[QualificationResult]:
    """Deterministic set of `count` drivers with realistic-looking scores."""
    rng = random.Random(2026)
    results: list[QualificationResult] = []
    for index in range(count):
        name = f"{_FIRST_NAMES[index % len(_FIRST_NAMES)]} {_LAST_NAMES[index]} #{rng.randint(1, 199)}"
        run1 = rng.randint(45, 96)
        run2 = max(0, run1 + rng.randint(-25, 8)) if rng.random() > 0.15 else 0
        results.append(QualificationResult(Driver(index + 1, name), run1=run1, run2=run2))
    return results


def _pick_side(match_top: Driver | None, match_bottom: Driver | None,
               seed_of: dict[Driver, int], rng: random.Random | None) -> str | None:
    """Side to click: the only driver present, else better seed (or random upset)."""
    if match_top is None and match_bottom is None:
        return None
    if match_top is None:
        return "bottom"
    if match_bottom is None:
        return "top"
    if rng is not None and rng.random() < 0.25:
        return rng.choice(("top", "bottom"))          # an upset now and then
    return "top" if seed_of[match_top] < seed_of[match_bottom] else "bottom"


def play(bracket: TournamentBracket, seed_of: dict[Driver, int], match_ids: tuple[str, ...],
         *, upsets: bool = False) -> None:
    """Resolve `match_ids` in order through the real `set_winner`."""
    rng = random.Random(7) if upsets else None
    for match_id in match_ids:
        match = bracket.matches[match_id]
        side = _pick_side(match.slot_top, match.slot_bottom, seed_of, rng)
        if side is not None:
            set_winner(bracket, match_id, side)


def preview_on_dark(image: Image.Image) -> Image.Image:
    """Composite a transparent export on a dark gradient (stream-like backdrop)."""
    gradient = Image.linear_gradient("L").rotate(90).resize(image.size)
    top, bottom = Image.new("RGBA", image.size, (22, 24, 28, 255)), Image.new("RGBA", image.size, (44, 48, 56, 255))
    background = Image.composite(bottom, top, gradient)
    background.alpha_composite(image)
    return background.convert("RGB")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output folder")
    parser.add_argument("--scale", type=int, default=1, help="1 = 1920 px wide bracket, 2 = 3840 px")
    args = parser.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    # --- cli_demo data: 10 drivers > 0, two (0, 0) -------------------------
    main_rows, extra_rows = split_standings(SAMPLE_RESULTS)
    seed_of = {row.driver: seed for seed, row in enumerate(main_rows, start=1) if row is not None}

    standings = render_standings(main_rows, extra_rows, title=STANDINGS_TITLE, scale=args.scale)
    standings.save(out / "standings_demo.png")

    empty = create_bracket(main_rows)
    render_bracket(empty, title=EVENT_TITLE, subtitle=BRACKET_SUBTITLE, scale=args.scale).save(
        out / "bracket_demo_empty.png")

    finished = create_bracket(main_rows)
    play(finished, seed_of, MATCH_ORDER)
    bracket_final = render_bracket(finished, title=EVENT_TITLE, subtitle=BRACKET_SUBTITLE, scale=args.scale)
    bracket_final.save(out / "bracket_demo_final.png")

    # --- full field of 32 ----------------------------------------------------
    full_main, full_extra = split_standings(full_field())
    full_seed_of = {row.driver: seed for seed, row in enumerate(full_main, start=1) if row is not None}
    standings_full = render_standings(full_main, full_extra, columns=2, title=STANDINGS_TITLE, scale=args.scale)
    standings_full.save(out / "standings_full32_2col.png")

    partial = create_bracket(full_main)
    play(partial, full_seed_of, MATCH_ORDER[:24] + ("T8_1", "T8_3"), upsets=True)
    for theme, suffix in ((CLIENT_LIGHT, ""), (CLIENT_DARK, "_dark")):
        render_bracket(partial, title=EVENT_TITLE, subtitle=BRACKET_SUBTITLE, theme=theme, scale=args.scale).save(
            out / f"bracket_full32_partial{suffix}.png")

    # --- previews on a dark backdrop -------------------------------------------
    preview_on_dark(bracket_final).save(out / "preview_stream_bracket.jpg", quality=88)
    preview_on_dark(standings_full).save(out / "preview_stream_standings.jpg", quality=88)

    for path in sorted(out.iterdir()):
        print(f"{path}  ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
