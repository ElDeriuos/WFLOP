import os
import subprocess

import pytest

from main import format_config, simulator_config_values

pytestmark = pytest.mark.integration

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM = os.path.join(ROOT, "build", "simulator")
CONFIG = os.path.join(ROOT, "inputs", "config.inp")
CSV = os.path.join(ROOT, "outputs", "final_pareto_front.csv")


@pytest.fixture(scope="module", autouse=True)
def built_simulator():
    if not (os.path.exists(CONFIG) and os.path.exists(CSV)):
        pytest.skip("needs inputs/config.inp and outputs/final_pareto_front.csv")
    subprocess.run(["make", "simulator", "soga_optimizer", "moga_optimizer"], cwd=ROOT, check=True, capture_output=True)


def write_wind(path, n_nodes, n_steps=3):
    # Minimal filtered_wind.txt: 2 header lines, "nodes steps", node coords, then u v per node per step
    rows = ["header", "header", f"{n_nodes} {n_steps}"] + ["0 0"] * n_nodes
    for t in range(1, n_steps + 1):
        rows += [str(t)] + ["8.0 3.0"] * n_nodes
    path.write_text("\n".join(rows) + "\n")


def run(tmp_path, csv_path, rows):
    # Simulator config written the same way as the GUI's manual mode: tiny time-series
    # wind file and outputs in tmp_path, so real results stay untouched
    header = open(CSV).readline().split(",")
    write_wind(tmp_path / "wind.txt", sum(h.startswith("gene_") for h in header))
    values = simulator_config_values(
        turb="./inputs/turbine_spec.txt", mesh="./inputs/windfarm_rocol.txt",
        wind1=str(tmp_path / "wind.txt"), bathy="./inputs/farm_bathymetry.dat",
        dist="./inputs/site_distances.txt", out_dir=str(tmp_path), workability=0.7,
    )
    config = tmp_path / "config.inp"
    config.write_text(format_config(values))
    return subprocess.run([SIM, str(config), str(csv_path), rows], cwd=ROOT, capture_output=True, text=True)


def test_row_beyond_end_stops_with_error(tmp_path):
    result = run(tmp_path, CSV, "1,99999")
    assert result.returncode != 0
    assert "99999" in result.stdout + result.stderr
    assert not (tmp_path / "simulation_summary.csv").exists()


def test_invalid_gene_stops_with_error(tmp_path):
    header, first = open(CSV).read().splitlines()[:2]
    names, values = header.split(","), first.split(",")
    values[names.index("gene_1")] = "999"
    bad = tmp_path / "bad.csv"
    bad.write_text(header + "\n" + ",".join(values) + "\n")
    result = run(tmp_path, bad, "all")
    assert result.returncode != 0
    assert not (tmp_path / "simulation_summary.csv").exists()


def test_valid_row_still_works(tmp_path):
    result = run(tmp_path, CSV, "1")
    assert result.returncode == 0, result.stdout
    assert (tmp_path / "simulation_summary.csv").exists()


@pytest.mark.parametrize("exe, opt_mode, obj_2", [("soga_optimizer", 1, 0), ("moga_optimizer", 2, 3)])
def test_optimizers_read_commented_config(tmp_path, exe, opt_mode, obj_2):
    # Optimizers read ./inputs/config.inp from the CWD, so run them in a scratch copy
    values = simulator_config_values(
        turb=os.path.join(ROOT, "inputs", "turbine_spec.txt"), mesh=os.path.join(ROOT, "inputs", "windfarm_rocol.txt"),
        wind1="unused", bathy=os.path.join(ROOT, "inputs", "farm_bathymetry.dat"),
        dist=os.path.join(ROOT, "inputs", "site_distances.txt"), out_dir=str(tmp_path / "out"), workability=0.7,
    )
    values.update(it_max=2, n_pop=4, max_turbs=20, min_turbs=5, opt_mode=opt_mode, obj_2=obj_2,
                  wind_mode=2, f_wind2=os.path.join(ROOT, "inputs", "wind_rose_matrix.dat"))
    (tmp_path / "inputs").mkdir()
    (tmp_path / "out").mkdir()
    (tmp_path / "inputs" / "Turbines").symlink_to(os.path.join(ROOT, "inputs", "Turbines"))  # curve paths are relative
    (tmp_path / "inputs" / "config.inp").write_text(format_config(values))
    result = subprocess.run([os.path.join(ROOT, "build", exe)], cwd=tmp_path, capture_output=True, text=True, timeout=600)
    assert result.returncode == 0, result.stdout[-2000:]
    assert any((tmp_path / "out").iterdir())
