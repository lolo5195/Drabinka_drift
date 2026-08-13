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