"""AppState - the single source of truth for the GUI (PLAN §1.2, T-08).

main.py creates exactly one AppState and passes it to every view. Views read
and change only this object, so no module keeps its own globals and later
tickets (T-09..T-16) extend the state in exactly one place.
"""

from dataclasses import dataclass, field

from models import QualificationResult, TournamentBracket

# Tab names are both the values of `ui.tabs` and the labels the operator sees.
TAB_QUALIFICATION = "Kwalifikacje"
TAB_RESULTS = "Wyniki"
TAB_BRACKET = "Drabinka TOP32"


@dataclass
class AppState:
    """Everything the GUI shows; one instance lives for the whole process."""

    # Bound to `ui.tabs`, so the selected tab survives a page reload (F5).
    active_tab: str = TAB_QUALIFICATION

    # Output of `split_standings`. An empty list means "not generated yet";
    # after generation `main_standings` always holds exactly 32 entries.
    main_standings: list[QualificationResult | None] = field(default_factory=list)
    extra_standings: list[QualificationResult] = field(default_factory=list)

    # None until the operator generates the bracket from the standings.
    bracket: TournamentBracket | None = None
