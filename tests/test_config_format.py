from main import CONFIG_FIELDS, format_config, simulator_config_values
from source import visualizer


def sample_values():
    values = simulator_config_values(
        turb="./inputs/turbine_spec.txt", mesh="./inputs/windfarm_rocol.txt",
        wind1="C:\\data\\wind.txt", bathy="./inputs/farm_bathymetry.dat",
        dist="./inputs/site_distances.txt", out_dir="./outputs/", workability=0.7,
    )
    values.update(opt_mode=2, obj_1=3, obj_2=4)
    return values


def test_one_line_per_fortran_read_in_reader_order():
    lines = format_config(sample_values()).splitlines()
    assert len(lines) == 26
    assert lines[0].split()[0] == "1"            # it_max
    assert lines[8].split()[0] == "0.7"          # workability
    assert lines[12].split()[0] == "1"           # wind_mode forced to time-series
    assert lines[21].split()[0] == '"C:/data/wind.txt"'  # backslashes normalised, quoted
    assert lines[25].split()[0] == '"./outputs/"'


def test_every_line_is_commented():
    for line, (key, _) in zip(format_config(sample_values()).splitlines(), CONFIG_FIELDS):
        assert "! " + key in line


def test_visualizer_reads_objectives_from_commented_config(tmp_path, monkeypatch):
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs" / "config.inp").write_text(format_config(sample_values()))
    monkeypatch.chdir(tmp_path)
    obj1, obj2 = visualizer._get_moga_objectives()
    assert obj1[0] == "raw_aep" and obj2[0] == "raw_fatigue"
