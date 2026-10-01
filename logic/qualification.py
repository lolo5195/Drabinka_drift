from models import QualificationResult

# Size of the main table (places 1-32), i.e. the drivers seeded into TOP32.
MAIN_PLACES = 32

def sort_key(r: QualificationResult) -> tuple[int, int]:
    """
    Sort key for QualificationResult.
    Sort by best run (descending), then by worst run (descending).
    A full tie keeps the input order because sorted() is stable (PLAN §2.1).
    """
    return (-r.best, -r.worst)

def sort_qualification_results(results: list[QualificationResult]) -> list[QualificationResult]:
    """
    Sort a list of QualificationResult objects.
    """
    return sorted(results, key=sort_key)

def split_standings(results: list[QualificationResult]) -> tuple[list[QualificationResult | None], list[QualificationResult]]:
    """
    Zwraca (miejsca 1-32, miejsca 33+)
    None w tabeli głównej = wiersz wypełniony myślnikami
    """
    named = [r for r in results if r.driver.name.strip()]  # rows without a name are ignored
    scored = sort_qualification_results([r for r in named if not r.is_zero])
    zeros = [r for r in named if r.is_zero]
    main = scored[:MAIN_PLACES] + [None] * max(0, MAIN_PLACES - len(scored))
    extra = scored[MAIN_PLACES:] + zeros
    return main, extra

def is_valid_score(text: str | None) -> bool:
    """True for an empty field or an integer 0-100 written with digits only.

    The digit-only check rejects "-5", "+5", "8.5", "1e2" and letters before
    int() sees them; isascii() also rules out Unicode digits such as "²".
    """
    text = (text or "").strip()
    return text == "" or (text.isascii() and text.isdigit() and int(text) <= 100)

def parse_score(text: str | None) -> int | None:
    """Return the typed score, or None if the field is empty or invalid."""
    text = (text or "").strip()
    return int(text) if text and is_valid_score(text) else None