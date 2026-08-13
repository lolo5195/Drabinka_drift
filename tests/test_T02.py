from dataclasses import FrozenInstanceError
import pytest

from models import Driver, QualificationResult

def test_qualification_result():
    driver = Driver(id=1, name="Gabriel Kossakowski")
    res1 = QualificationResult(driver=driver, run1=81, run2=76)
    assert res1.best == 81
    assert res1.worst == 76

    res2 = QualificationResult(driver=driver, run1=0, run2=81)
    assert res2.best == 81
    assert res2.worst == 0

    res3 = QualificationResult(driver=driver, run1=0, run2=0)
    assert res3.is_zero

def test_driver_is_frozen():
    driver = Driver(id=1, name="Gabriel Kossakowski")
    with pytest.raises(FrozenInstanceError):
        driver.name = "New Name"