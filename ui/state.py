"""AppState - the single source of truth for the GUI (PLAN §1.2, T-08).

main.py creates exactly one AppState and passes it to every view. Views read
and change only this object, so no module keeps its own globals and later
tickets (T-09..T-16) extend the state in exactly one place.
"""

from dataclasses import dataclass, field

from logic.qualification import is_valid_score, parse_score, split_standings
from models import Driver, QualificationResult, TournamentBracket

# Tab names are both the values of `ui.tabs` and the labels the operator sees.
TAB_QUALIFICATION = "Kwalifikacje"
TAB_RESULTS = "Wyniki"
TAB_BRACKET = "Drabinka TOP32"


@dataclass
class EntryRow:
    """One row of the "Kwalifikacje" table, kept exactly as the operator typed it.

    Not a QualificationResult: `Driver` is frozen (the name could not be edited
    in place) and an empty score must not count as 0 while typing (PLAN §4.1).
    T-10 turns these rows into `Driver`/`QualificationResult` when generating.
    """

    # Identity given when the row is created; becomes `Driver.id` in T-10.
    # Rows are only ever appended, so the id is also the row's L.p.
    driver_id: int
    name: str = ""
    # Score fields exactly as typed, so an empty field and an invalid one stay
    # distinguishable; both are parsed only at generation (T-10).
    run1: str = ""
    run2: str = ""


@dataclass
class AppState:
    """Everything the GUI shows; one instance lives for the whole process."""

    # Bound to `ui.tabs`, so the selected tab survives a page reload (F5).
    active_tab: str = TAB_QUALIFICATION

    # Output of `split_standings`. An empty list means "not generated yet";
    # after generation `main_standings` always holds exactly 32 entries.
    main_standings: list[QualificationResult | None] = field(default_factory=list)
    extra_standings: list[QualificationResult] = field(default_factory=list)
    # True when the entries changed after the last "Generuj wyniki", so the
    # tables on screen (and a bracket seeded from them) are out of date.
    results_outdated: bool = False

    # None until the operator generates the bracket from the standings.
    bracket: TournamentBracket | None = None

    # Rows of the entry table; the operator starts with two empty rows.
    entries: list[EntryRow] = field(
        default_factory=lambda: [EntryRow(driver_id=1), EntryRow(driver_id=2)])

    def add_row_if_last_named(self) -> bool:
        """Append an empty row once the last row has a name; True if one was added.

        Called on every keystroke in any name field. It looks only at the
        current last row, so right after an append the new empty row is last
        and further calls do nothing - fast typing cannot duplicate rows.
        A name of only spaces counts as no name, like in `split_standings`.
        """
        if not self.entries[-1].name.strip():
            return False
        self.entries.append(EntryRow(driver_id=len(self.entries) + 1))
        return True

    def mark_entries_changed(self) -> None:
        """Called on every edit of a name or score field.

        Before the first generation there is nothing to be out of date.
        """
        self.results_outdated = bool(self.main_standings)

    def rows_with_invalid_scores(self) -> list[int]:
        """L.p. of the rows whose score fields hold something other than 0-100."""
        return [
            row.driver_id
            for row in self.entries
            if not (is_valid_score(row.run1) and is_valid_score(row.run2))
        ]

    def generate_results(self) -> None:
        """Rebuild both standings tables from the typed rows ("Generuj wyniki").

        Only here does an empty score become 0 (PLAN §4.1); the caller must
        first check `rows_with_invalid_scores`, so no typo turns into 0.
        Unnamed rows are passed on as well: `split_standings` already drops
        them (T-04), so that rule stays in one place. `bracket` is not
        touched - it changes only through its own confirmed regeneration
        (PLAN §4.1, T-11).
        """
        results = [
            QualificationResult(
                driver=Driver(id=row.driver_id, name=row.name.strip()),
                run1=parse_score(row.run1) or 0,
                run2=parse_score(row.run2) or 0,
            )
            for row in self.entries
        ]
        self.main_standings, self.extra_standings = split_standings(results)
        self.results_outdated = False
