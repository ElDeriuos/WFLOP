# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

WFLOP is a research prototype for heterogeneous offshore wind-farm layout optimization (turbine location *and* type optimized together). A Python/CustomTkinter GUI (`main.py`) handles preprocessing, configuration, and visualization; a Fortran 90 backend does the optimization (SOGA and NSGA-II) and time-series re-simulation. `README.md` is the authoritative reference for input file formats, `config.inp` field positions, and output CSV schemas.

## Commands

Always run from the repository root — the GUI, Python modules, and Fortran executables all use paths relative to the CWD (e.g. `./inputs/config.inp`).

```bash
uv sync                      # Python deps (requires Python >=3.14)
python main.py               # launch the GUI (needs a display)

make all                     # build/simulator, build/soga_optimizer, build/moga_optimizer, source/polygon3
make soga_optimizer          # or: simulator, moga_optimizer
make clean

./build/soga_optimizer       # reads ./inputs/config.inp
./build/moga_optimizer
./build/simulator inputs/config.inp outputs/final_pareto_front.csv all   # or row selector like 1,4,7

uv run pytest tests/                                   # full suite
uv run pytest tests/test_wake_growth_rate.py -v        # single file
uv run pytest -m integration tests/                    # tests that build + run the Fortran simulator
```

Note: the `tests/` directory currently contains only `__pycache__` in the working tree; the test sources are not checked in.

Two separate build paths exist: the `Makefile` builds into `build/`, while the GUI's "Compile SOGA/MOGA" buttons invoke `gfortran` directly (`main.py` ~line 1185) and place binaries in `source/` (`source/soga_optimizer`, `source/moga_optimizer`), which is where the GUI runs them from. GUI debug flags: `-Wall -Wextra -g -O0 -fcheck=all -fbacktrace -fopenmp`; fast: `-O3 -fopenmp`. Binaries are not tracked in git; `make polygon3` is required before the GUI's mesh step works.

## Architecture

**Pipeline:** KML polygons → `source/mesh_generator.py` (projects to UTM, shifts to origin, runs the legacy `source/polygon3` Fortran mesher → `inputs/windfarm_rocol.txt` + `inputs/mesh_metadata.json`) → `bathymetry_generator.py` (GEBCO `.asc` → `inputs/farm_bathymetry.dat`) → `wind_generator.py` (ERA5 NetCDF → either `filtered_wind.txt` time series or `wind_rose_matrix.dat` + `wind_analytics.json`) → `distance_calculator.py` (`site_distances.txt`) → GUI writes `inputs/config.inp` → Fortran optimizer → CSVs in `outputs/` → `visualizer.py` (matplotlib plots, PyVista 3-D, ffmpeg MP4s).

The mesh step must run first: every later step indexes by mesh node, and `mesh_metadata.json` holds the UTM zone/offset needed to map nodes back to WGS 84.

**Chromosome encoding:** one gene per mesh node, in mesh node order. Gene `1` = empty node; real turbine types start at gene `2` (indexing into `inputs/turbine_spec.txt`). Output CSVs carry `gene_1..gene_N` columns, which the simulator discovers by header name.

**Fortran core (`source/wflop_core.f90`)** is a single file of modules, compiled before any driver: `precision`, `types`, `inputs` (config/mesh/wind/turbine loaders), `costs` (CAPEX), `physics` (wake/power/fatigue with all-to-all wake iteration, `max_iter = 20`), `NSGA_II`, `SOGA`, `outputs`. Thin drivers: `main_soga.f90`, `main_moga.f90`; `simulation.f90` + `main_simulator.f90` reuse the core for re-simulation (forces time-series mode).

Key backend behaviors:
- Everything is minimized internally; maximization objectives (AEP, fatigue life) are negated.
- Soft constraints (min AEP / max CAPEX) penalize the GA-facing objective but never overwrite raw metrics; turbine-count limits are hard.
- The SOGA evaluator lazily computes only the modules its objective needs.
- RNG is clock-seeded — runs are not reproducible.
- `config.inp` is positional (see README §5 for the field table); `farmlifetime = 25` and `max_iter` are hardcoded in the reader, not GUI fields.

**GUI (`main.py`)** runs long tasks in worker threads, streams subprocess stdout to a live console, and keeps `self.running_process` so the abort button can kill the optimizer.
