import pytest
from logic.qualification import sort_qualification_results
from models import Driver, QualificationResult


# Fixture tworzący przykładowych kierowców do testów
@pytest.fixture
def drivers():
    return [
        Driver(id=1, name="Driver 1"),
        Driver(id=2, name="Driver 2"),
        Driver(id=3, name="Driver 3"),
    ]


# 1. Pomieszana kolejność wejściowa (kluczowy test!)
def test_sort_qualification_results_shuffled_input(drivers):
    d1, d2, d3 = drivers

    # Przekazujemy dane w wymieszanej kolejności (3 -> 1 -> 2)
    results = [
        QualificationResult(driver=d3, run1=81, run2=0),    # Powinien być 3. miejsce (best: 81, 2nd: 0)
        QualificationResult(driver=d1, run1=81, run2=76),   # Powinien być 1. miejsce (best: 81, 2nd: 76)
        QualificationResult(driver=d2, run1=56, run2=81),   # Powinien być 2. miejsce (best: 81, 2nd: 56)
    ]

    sorted_results = sort_qualification_results(results)

    # Sprawdzamy wyciągniętą listę kierowców w jednym eleganckim assert
    assert [r.driver for r in sorted_results] == [d1, d2, d3]


# 2. Wyższy Najlepszy Przejazd wygrywa (nie suma punktów!)
def test_sort_highest_single_run_wins(drivers):
    d1, d2, _ = drivers

    results = [
        # Driver 2 ma wyższą SUMĘ (160), ale gorszy NAJLEPSZY przejazd (80)
        QualificationResult(driver=d2, run1=80, run2=80),
        # Driver 1 ma niższą SUMĘ (100), ale wyższy NAJLEPSZY przejazd (90)
        QualificationResult(driver=d1, run1=90, run2=10),
    ]

    sorted_results = sort_qualification_results(results)

    assert sorted_results[0].driver == d1
    assert sorted_results[1].driver == d2


# 3. Remis w najlepszym przejeździe -> rozstrzygnięcie drugim przejazdem (Tie-breaker)
def test_sort_tie_breaker_on_second_run(drivers):
    d1, d2, _ = drivers

    results = [
        QualificationResult(driver=d2, run1=85, run2=40),   # Best: 85, 2nd: 40
        QualificationResult(driver=d1, run1=50, run2=85),   # Best: 85, 2nd: 50 -> Wyższy drugi przejazd
    ]

    sorted_results = sort_qualification_results(results)

    assert sorted_results[0].driver == d1
    assert sorted_results[1].driver == d2


# 4. Pełny remis (identyczna para wyników) -> kolejność wpisania (PLAN §2.1: stabilne sorted)
def test_sort_full_tie_keeps_input_order(drivers):
    d1, d2, _ = drivers

    # d2 wpisany jako pierwszy, choć ma wyższe id — decyduje wyłącznie kolejność wpisania
    results = [
        QualificationResult(driver=d2, run1=81, run2=76),
        QualificationResult(driver=d1, run1=81, run2=76),
    ]

    sorted_results = sort_qualification_results(results)

    assert [r.driver for r in sorted_results] == [d2, d1]


# 5. (0,81) sortuje się jak best=81, a nie jak wynik zerowy
def test_sort_zero_first_run_counts_as_best_81(drivers):
    d1, d2, _ = drivers

    results = [
        QualificationResult(driver=d2, run1=80, run2=79),   # Best: 80
        QualificationResult(driver=d1, run1=0, run2=81),    # Best: 81, 2nd: 0 -> wyżej
    ]

    sorted_results = sort_qualification_results(results)

    assert [r.driver for r in sorted_results] == [d1, d2]


# 6. Skrajne przypadki (Edge Cases)
def test_sort_empty_list():
    assert sort_qualification_results([]) == []


def test_sort_single_driver(drivers):
    d1 = drivers[0]
    result = QualificationResult(driver=d1, run1=50, run2=60)
    assert sort_qualification_results([result]) == [result]
