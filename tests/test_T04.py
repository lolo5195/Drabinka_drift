"""T-04: split_standings — main table (places 1–32) vs extra table (33+)."""

from models import Driver, QualificationResult
from logic.qualification import split_standings


def _make_positive_results(count: int) -> list[QualificationResult]:
    """Build `count` non-zero results with a predictable ranking.

    Driver i gets run1 = 100 - i (and run2 = 0), so higher id = weaker score.
    After sorting: id 0 is 1st, id 1 is 2nd, ..., id (count-1) is last.
    Note: (N, 0) is NOT a zero result — only (0, 0) has is_zero == True.
    """
    drivers = [Driver(id=i, name=f"Driver {i}") for i in range(count)]
    return [
        QualificationResult(driver=drivers[i], run1=100 - i, run2=0)
        for i in range(count)
    ]


# --- DoD 1: 28 positive results → places 1–28 filled, 29–32 are None ---

def test_split_28_positive_pads_main_with_none():
    # Fewer than 32 scored drivers: main must still be length 32, with None = "-"
    results = _make_positive_results(28)

    main, extra = split_standings(results)

    assert len(main) == 32
    # First 28 slots hold the ranked drivers (best → worst)
    assert all(r is not None for r in main[:28])
    assert [r.driver.id for r in main[:28]] == list(range(28))
    # Slots 29–32 (0-based indices 28–31) are empty placeholders
    assert main[28:] == [None, None, None, None]
    # No overflow and no zeros → extra table stays empty
    assert extra == []


# --- DoD 2: 5 zero results → second table; numbering conceptually starts at 33 ---

def test_split_zeros_go_to_extra_table():
    # Mix a few positive scores with true (0, 0) zeros
    positives = _make_positive_results(3)
    zero_drivers = [Driver(id=100 + i, name=f"Zero {i}") for i in range(5)]
    zeros = [
        QualificationResult(driver=d, run1=0, run2=0) for d in zero_drivers
    ]

    main, extra = split_standings(positives + zeros)

    # Positives occupy the top of main; remaining slots are None
    assert len(main) == 32
    assert [r.driver.id for r in main[:3]] == [0, 1, 2]
    assert main[3:] == [None] * 29

    # All five (0, 0) land in extra (the 33+ table), in input order
    assert len(extra) == 5
    assert all(r.is_zero for r in extra)
    assert [r.driver.id for r in extra] == [100, 101, 102, 103, 104]


# --- DoD 3: 0 drivers → 32 × None and empty 33+ list ---

def test_split_empty_input():
    main, extra = split_standings([])

    assert main == [None] * 32
    assert extra == []


# --- DoD 4: 35 positive → 3 overflow drivers at the start of the 33+ list ---

def test_split_35_positive_overflow_goes_to_extra():
    # Exactly 35 non-zero results — no (0, 0) mixed in
    results = _make_positive_results(35)

    main, extra = split_standings(results)

    # Top 32 fill the main table completely (no None padding needed)
    assert len(main) == 32
    assert all(r is not None for r in main)
    assert [r.driver.id for r in main] == list(range(32))

    # The 3 weakest (ids 32, 33, 34) start the extra / 33+ list
    assert len(extra) == 3
    assert [r.driver.id for r in extra] == [32, 33, 34]
    assert all(not r.is_zero for r in extra)


# --- T-04 opis / §2.1: rows without a name are ignored before sorting ---

def test_split_ignores_rows_without_name():
    named = QualificationResult(driver=Driver(id=1, name="Driver 1"), run1=70, run2=0)
    unnamed_scored = QualificationResult(driver=Driver(id=2, name=""), run1=90, run2=0)
    unnamed_zero = QualificationResult(driver=Driver(id=3, name="   "), run1=0, run2=0)

    main, extra = split_standings([unnamed_scored, named, unnamed_zero])

    # Unnamed rows appear in neither table, even though one of them scored higher
    assert main[0] is named
    assert main[1:] == [None] * 31
    assert extra == []
