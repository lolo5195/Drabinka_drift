from models import QualificationResult

def sort_key(r: QualificationResult) -> tuple[int, int, int]:
    """
    Sort key for QualificationResult.
    Sort by best run (descending), then by worst run (descending) then by driver ID (ascending).
    """
    return (-r.best, -r.worst, r.driver.id)

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
    scored = sort_qualification_results([r for r in results if not r.is_zero])
    zeros = [r for r in results if r.is_zero]
    main = scored[:32] + [None] * max(0, 32 - len(scored))
    extra = scored[32:] + zeros
    return main, extra