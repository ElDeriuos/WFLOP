"""Runs tiny real SOGA and NSGA-II optimizations, then every plot, animation and
3D view the GUI offers, on their outputs. PATH is emptied so no system ffmpeg can
be used: MP4s must come from the bundled imageio-ffmpeg binary."""
import os
import subprocess

import pytest

from main import format_config, simulator_config_values

pytestmark = pytest.mark.integration

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUTS = os.path.join(ROOT, "inputs")
NEEDED = ["turbine_spec.txt", "windfarm_rocol.txt", "farm_bathymetry.dat", "site_distances.txt", "wind_rose_matrix.dat"]


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    if not all(os.path.exists(os.path.join(INPUTS, n)) for n in NEEDED):
        pytest.skip("needs the preprocessed site files in inputs/")
    subprocess.run(["make", "soga_optimizer", "moga_optimizer"], cwd=ROOT, check=True, capture_output=True)
    work = tmp_path_factory.mktemp("project")
    (work / "inputs").mkdir()
    (work / "outputs").mkdir()
    for name in NEEDED + ["Turbines"]:
        (work / "inputs" / name).symlink_to(os.path.join(INPUTS, name))

    for exe, opt_mode, obj_2 in (("soga_optimizer", 1, 0), ("moga_optimizer", 2, 3)):
        values = simulator_config_values(
            turb="./inputs/turbine_spec.txt", mesh="./inputs/windfarm_rocol.txt", wind1="unused",
            bathy="./inputs/farm_bathymetry.dat", dist="./inputs/site_distances.txt",
            out_dir="./outputs/", workability=0.7,
        )
        values.update(it_max=3, n_pop=6, max_turbs=20, min_turbs=5, opt_mode=opt_mode, obj_2=obj_2,
                      wind_mode=2, f_wind2="./inputs/wind_rose_matrix.dat")
        (work / "inputs" / "config.inp").write_text(format_config(values))
        result = subprocess.run([os.path.join(ROOT, "build", exe)], cwd=work, capture_output=True, text=True, timeout=600)
        assert result.returncode == 0, result.stdout[-2000:]
    return work


@pytest.fixture
def viz(project, monkeypatch):
    monkeypatch.chdir(project)
    monkeypatch.setenv("PATH", "")
    import pyvista as pv
    monkeypatch.setattr(pv, "OFF_SCREEN", True)
    from source import visualizer
    return visualizer


def assert_mp4(path):
    assert path and os.path.exists(path)
    with open(path, "rb") as f:
        assert f.read(12)[4:8] == b"ftyp"  # MP4 container signature


def test_pareto_plots(viz):
    assert viz.save_pareto_plots(output_dir="./outputs")
    assert os.path.getsize("outputs/plot_final_pareto.png") > 0


def test_soga_convergence_plot(viz):
    assert os.path.getsize(viz.save_soga_convergence_plot(output_dir="./outputs", target_obj="LCOE")) > 0


def test_moga_animation(viz):
    assert_mp4(viz.generate_mp4_animation("./outputs/animation_data_obj_1.csv", level_idx=1, fps=5))


def test_soga_animation(viz):
    assert_mp4(viz.generate_soga_mp4_animation("./outputs/animation_data_soga.csv", level_idx=1, fps=5))


def test_3d_views_render(viz):
    viz.generate_soga_3d_layout(target_obj="LCOE")
    viz.generate_3d_comparison()
