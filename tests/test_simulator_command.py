import pytest

from main import build_simulator_command


def test_all_rows_selector():
    assert build_simulator_command("sim", "c.inp", "r.csv", "all") == ["sim", "c.inp", "r.csv", "all"]


def test_blank_selector_means_all():
    assert build_simulator_command("sim", "c.inp", "r.csv", "  ") == ["sim", "c.inp", "r.csv", "all"]


def test_row_list_spaces_stripped():
    assert build_simulator_command("sim", "c.inp", "r.csv", " 1, 4 ,7") == ["sim", "c.inp", "r.csv", "1,4,7"]


@pytest.mark.parametrize("bad", ["0", "1,,2", "a", "-3", "1.5"])
def test_invalid_selector_rejected(bad):
    with pytest.raises(ValueError):
        build_simulator_command("sim", "c.inp", "r.csv", bad)
