# WFLOP — Offshore Wind-Farm Layout Optimizer

WFLOP is a research prototype for **heterogeneous offshore wind-farm layout optimization**. It combines a Python/CustomTkinter desktop interface and preprocessing/post-processing tools with a Fortran 90 computational backend.

The program was developed for a thesis study of offshore layout design in which turbine **location and turbine type** are optimized together. The design objectives are:

- maximize annual energy production (AEP);
- minimize capital expenditure (CAPEX);
- minimize levelized cost of energy (LCOE); and
- maximize normalized structural fatigue life.

The repository supports both single-objective genetic optimization (SOGA) and multi-objective NSGA-II (MOGA). It also provides a chronological wind time-series simulator for validating layouts produced by the optimizer.

> **Research scope.** WFLOP is intended for preliminary engineering studies and thesis reproducibility. Its analytical wake, fatigue, cost, and weather models are not a replacement for CFD/LES, aeroelastic, hydrodynamic, geotechnical, or bankable financial analysis.

---

## 1. Workflow at a glance

```text
KML boundaries ───────────────┐
GEBCO ASCII bathymetry ───────┼─> Python preprocessing ─> Fortran input files
ERA5 NetCDF wind files ──────┘             │
                                           v
Turbine catalogue + constraints ─────> SOGA or NSGA-II
                                           │
                  ┌────────────────────────┼────────────────────────┐
                  v                        v                        v
           CSV optimization results   Pareto/convergence plots   3-D/MP4 views
                  │
                  v
       Optional time-series re-simulation and validation reports
```

The normal order is:

1. generate a candidate-node mesh from one or more KML polygons;
2. extract bathymetry at every mesh node;
3. process ERA5 wind data either as a chronological time series or as a statistical wind rose;
4. calculate distances to shore/landfall, grid connection, and port;
5. provide a turbine catalogue and configure the farm constraints;
6. compile and run SOGA or NSGA-II;
7. inspect the generated CSVs and visualizations;
8. optionally compile/run the simulator against selected result rows.

The GUI runs long preprocessing, compilation, optimization, and rendering actions in worker threads. The live console streams subprocess output and the abort button terminates the active Fortran optimizer process.

---

## 2. Repository layout

| Path | Purpose |
|---|---|
| `main.py` | CustomTkinter GUI and end-to-end workflow controller. |
| `source/mesh_generator.py` | Parses KML polygons, projects them to UTM, creates mesh-generator input, and runs `polygon3`. |
| `source/bathymetry_generator.py` | Maps mesh nodes back to WGS 84, samples a GEBCO ESRI ASCII grid, and writes Tecplot-style bathymetry. |
| `source/wind_generator.py` | Reads ERA5 NetCDF files, filters/interpolates `u10`/`v10`, writes time-series input, or bins a wind rose. |
| `source/distance_calculator.py` | Calculates center-to-shore, center-to-grid, and center-to-port distances from KML geometry. |
| `source/visualizer.py` | Wind-resource plots, Pareto/convergence plots, PyVista layouts, and FFmpeg animations. |
| `source/wflop_core.f90` | Fortran types, input loading, cost model, wake/power/fatigue physics, NSGA-II, SOGA, and output writers. |
| `source/main_soga.f90` | SOGA driver. |
| `source/main_moga.f90` | NSGA-II driver. |
| `source/simulation.f90` | Re-simulates optimizer CSV rows using the time-series physics. |
| `source/main_simulator.f90` | Command-line simulator driver and row-selector parser. |
| `source/polygon3.for` | Legacy fixed-format Fortran polygon-to-grid mesh generator. |
| `Makefile` | Builds the simulator and both optimizer executables under `build/`. |
| `inputs/` | Generated and user-supplied Fortran input files. |
| `outputs/` | Optimization, simulation, plots, and animation outputs. |
| `tests/` | Python tests for the wake-model implementation. |
| `thesis_ver5.pdf` | Thesis draft describing the research model and case-study methodology. |

The checked-in `source/` directory may contain prebuilt binaries and object files. Rebuilding is recommended when changing compilers, platforms, or Fortran sources.

---

## 3. Installation

### Required tools

- Python version compatible with `pyproject.toml` (`>=3.14` as currently declared).
- GNU Fortran (`gfortran`), with OpenMP support.
- GNU Make.
- FFmpeg, required for MP4 animations.
- A desktop environment/display for the CustomTkinter GUI and PyVista viewer.

The Python dependencies are declared in `pyproject.toml`:

- `customtkinter`
- `numpy`, `pandas`, `scipy`
- `matplotlib`, `pyvista`, `ffmpeg`
- `xarray`, `netCDF4`
- `pyproj`
- `pytest`, `hypothesis`
- `fortls` for Fortran-language tooling

A typical setup with `uv` is:

```bash
uv sync
```

Alternatively, create a virtual environment with Python and install the project dependencies using your preferred package manager. On Linux, install the system packages separately, for example:

```bash
# Distribution-specific package names may differ
sudo dnf install gcc-gfortran make ffmpeg
```

On Windows, use a MinGW-w64/MSYS2 `gfortran` installation and ensure both `gfortran` and `ffmpeg` are on `PATH`.

### Build the Fortran programs

Build all three modern executables:

```bash
make all
```

This creates:

```text
build/simulator
build/soga_optimizer
build/moga_optimizer
```

Build individual targets with:

```bash
make simulator
make soga_optimizer
make moga_optimizer
```

The GUI’s **Compile SOGA/MOGA** buttons use a separate direct command and place the resulting optimizer in `source/` (`source/soga_optimizer` or `source/moga_optimizer`). The GUI expects to be launched from the repository root because its paths are relative to the current working directory:

```bash
python main.py
```

For debugging, the GUI uses `-Wall -Wextra -g -O0 -fcheck=all -fbacktrace -fopenmp`; its fast build uses `-O3 -fopenmp`.

---

## 4. Preparing the inputs

The GUI’s **Pre-Processing** tab creates the files consumed by the Fortran core. The paths below are the defaults written by `main.py`; they can be changed in the **Farm Setup** tab.

### 4.1 Candidate mesh from KML

Select one or more KML files and set `dx` and `dy` in metres. `mesh_generator.py`:

1. extracts `<coordinates>` blocks;
2. converts longitude/latitude from WGS 84 to the UTM zone computed from the mean longitude and latitude;
3. identifies the largest polygon as the macro-boundary;
4. shifts coordinates so the minimum projected `x` and `y` are zero;
5. writes `xycoordinates.txt` and `Polygon_project.txt`/`polygon_project.txt`;
6. executes `source/polygon3` (or `polygon3.exe` on Windows); and
7. stores UTM metadata in `inputs/mesh_metadata.json`.

`polygon3` rasterizes the polygon edges at the requested spacing and writes `inputs/windfarm_rocol.txt`, which contains candidate node coordinates and element/connectivity records. Nodes are the chromosome positions used by the optimizer.

The current implementation preserves intermediate mesh files for inspection. Run this step before bathymetry, wind, or distance processing.

### 4.2 Bathymetry

Select a GEBCO ESRI ASCII grid (`.asc`) and click **Extract Depths**. The extractor:

- reads node coordinates from `inputs/windfarm_rocol.txt`;
- restores the UTM offset from `mesh_metadata.json`;
- inverse-projects the nodes to WGS 84;
- samples the GEBCO raster; and
- writes negative underwater elevations, while land, nodata, and out-of-bounds locations are written as `0.0`.

The output is `inputs/farm_bathymetry.dat`, with a nine-line Tecplot-style header followed by `x y z` node records. The Fortran cost and visualizer routines read the depth at the same node index as the mesh.

### 4.3 Wind resource processing

Select a directory containing ERA5 NetCDF files. Files are concatenated along `valid_time`; only `u10` and `v10` are retained when those variables are present. The mesh bounding box is transformed back to WGS 84 and the dataset is spatially sliced with a 0.3-degree margin.

The time filters support hour, day, month, and year ranges. A range may wrap around, for example hour `22` to hour `4`. Leave a pair blank or use `All` to disable that filter.

#### Time-Series mode

Time-Series mode interpolates the filtered ERA5 vector wind to every mesh node in chunks of 1000 time steps and writes:

```text
inputs/filtered_wind.txt
```

The file contains the node count, time-step count, relative node coordinates, and `u10`/`v10` values for every node and time step. The Fortran loader derives wind speed and uses the Cartesian flow angle convention:

```text
wd = atan2(v, u), normalized to [0, 2π)
```

#### Wind Rose Binning mode

Wind Rose Binning mode samples the geographic farm center, computes wind speed and meteorological direction, and bins their joint distribution. It then fits a two-parameter Weibull distribution to speed magnitudes.

Defaults are 12 direction sectors and a 1 m/s velocity step. It writes:

- `inputs/wind_rose_matrix.dat`: nonzero `(direction, speed, probability)` states for the Fortran solver;
- `inputs/wind_analytics.json`: Weibull parameters, bins, joint probabilities, and histogram data.

Use **Plot Wind Rose** and **Plot Weibull Fit** after this step to inspect the resource statistics.

### 4.4 Logistics distances

Select any available shoreline, grid-connection, and port KML files, then click **Calculate Distances**. The module finds the mean mesh-node position in UTM coordinates and computes the minimum point-to-polyline distance for each selected geometry.

It writes one line to `inputs/site_distances.txt`:

```text
shoreline_distance_km grid_connection_distance_km port_distance_km
```

Missing optional KMLs default to `0.0`; at least one KML must be selected in the GUI.

### 4.5 Turbine catalogue

The default turbine file is `inputs/turbine_spec.txt`. Its structure is:

1. a header line;
2. the number of real turbine types;
3. two additional header lines;
4. one row per turbine with:

   ```text
   rotor_diameter rated_power cut_in cut_off hub_height r_pile t_tower
   ```

5. one power/thrust-curve path after each turbine row.

Each curve file is expected to have a header followed by rows containing:

```text
wind_speed power Cp thrust Ct
```

The backend uses the wind-speed, `Cp`, and `Ct` columns and linearly interpolates them. Gene `1` is reserved for an empty node; real turbine types begin at gene `2` in the Fortran representation. Hub heights are deduplicated into levels for the dense visualization field.

---

## 5. Configuring and running optimization

### Farm Setup

The GUI writes `inputs/config.inp` immediately before an optimization. The first values are:

| Position | Meaning |
|---:|---|
| 1 | maximum generations (`it_max`) |
| 2 | population size (`n_pop`) |
| 3 | crossover probability |
| 4 | mutation probability |
| 5 | mutation intensity `mu` |
| 6 | maximum turbine count |
| 7 | minimum turbine count |
| 8 | SOGA stall tolerance in generations |
| 9 | construction workability fraction |
| 10 | optimization mode: `1` SOGA, `2` MOGA |
| 11 | objective 1: `1` LCOE, `2` CAPEX, `3` AEP, `4` fatigue life |
| 12 | objective 2; used by MOGA |
| 13 | wind mode: `1` time series, `2` wind rose |
| 14–19 | soft-constraint switch, thresholds, weights, and penalty exponent |
| 20–26 | turbine, mesh, wind, rose, bathymetry, distance, and output paths |

The Fortran reader sets `max_iter = 20` for the all-to-all wake iteration and `farmlifetime = 25` years. These values are currently backend defaults rather than GUI fields.

#### Soft constraints

Soft constraints do not overwrite raw CAPEX or AEP. When enabled, the backend computes normalized violations:

```text
AEP violation   = max(0, (minimum AEP - raw AEP) / minimum AEP)
CAPEX violation = max(0, (raw CAPEX - maximum CAPEX) / maximum CAPEX)
```

The configured weights and penalty power modify the GA-facing objective values. A threshold of `0` disables that individual threshold. Hard turbine-count violations are always rejected by the optimizer.

### SOGA

SOGA minimizes a scalar mapped objective. Maximization objectives are negated internally so that lower fitness remains better. The core uses:

- tournament selection by scalar fitness;
- uniform two-child crossover;
- Poisson step mutation on a random subset of genes;
- explicit gene bounds (`1` through the number of turbine types); and
- elitist survival from the merged parent/offspring population.

The evaluator lazily runs only the required expensive modules: CAPEX is needed for LCOE/CAPEX, while wake/power/fatigue physics is needed for LCOE/AEP/fatigue. A positive stall tolerance stops the run after that many generations without improvement.

The GUI controls are initially SOGA generation `100`, population `50`, crossover `0.50`, mutation `0.50`, mutation step `0.08`, and stall tolerance `50`.

Run from the GUI after building `source/soga_optimizer`, or directly with:

```bash
./build/soga_optimizer
```

The direct executable expects to run from the repository root and reads `./inputs/config.inp`.

### MOGA / NSGA-II

MOGA maps both selected objectives to minimization values, then applies Deb-style NSGA-II:

1. evaluate the initial population;
2. rank by fast non-dominated sorting;
3. compute crowding distance;
4. create crossover and mutation offspring;
5. merge parents and offspring;
6. re-rank and select the best `n_pop` individuals; and
7. record the first front for each generation.

The GUI prevents the two objective selectors from being identical. The initial GUI defaults are generation `200`, population `100`, crossover `0.50`, mutation `0.50`, and mutation step `0.08`.

Run from the GUI after building `source/moga_optimizer`, or directly with:

```bash
./build/moga_optimizer
```

### Important stochastic behavior

The Fortran drivers seed their random number generator from the system clock. Repeated runs with identical inputs are therefore not expected to produce identical populations or fronts unless deterministic seeding is added in a future change.

---

## 6. Models implemented in the backend

### 6.1 Layout chromosome

A chromosome has one integer gene per mesh node:

```text
gene = 1       empty candidate node
gene >= 2      turbine type from turbine_spec.txt
```

The number of active turbines is the count of genes greater than `1`. Layouts below `min_turbs` or above `max_turbs` receive invalid/very poor objective values before expensive evaluation.

### 6.2 Wind shear and power

For each turbine hub-height level, the backend applies a power-law profile with exponent `α = 1/7` to the reference wind speed. Power is evaluated from the turbine-specific interpolated `Cp` curve:

```text
P = 0.5 ρ A Cp(U) U³
```

where `ρ = 1.225 kg/m³`. The optimizer uses wind-rose probabilities in rose mode and equal probability for each retained time step in time-series mode.

### 6.3 Wake model

The sparse optimizer solver uses the Bastankhah Gaussian deficit formulation with Niayifar & Porté-Agel dynamic wake growth. For a wake-producing turbine:

```text
k* = 0.3837 I_local + 0.003678
σ/D = k* (x/D) + 0.2 √β
```

Only downstream turbines within the current six-rotor-diameter lateral search band are affected. The `Ct` curve supplies the induction/thrust coefficient used in the Gaussian deficit.

For each environmental state, the all-to-all solver iterates local wind speeds and turbulence until the maximum speed change is below `1e-4 m/s`, or until `max_iter` is reached. If the limit is reached, the last iteration is used and a warning is printed.

Overlapping wakes are combined as follows:

- velocity deficits are summed linearly;
- the largest added-turbulence contribution is retained; and
- local turbulence is recomputed as the ambient-plus-dominant contribution.

The dense field used for animations follows the same dynamic `k*` expression and linear velocity-deficit accumulation, but it is a visualization grid calculation rather than the sparse per-turbine objective evaluator.

### 6.4 AEP

The backend accumulates farm power over time-series or wind-rose states and annualizes it:

```text
AEP_GWh = sum(power_W × state_probability) × 8760 / 1e9
```

For time-series mode, each retained step has probability `1 / nsteps`. For rose mode, the probability comes from `wind_rose_matrix.dat`.

### 6.5 Fatigue life

The Yang-style fatigue routine estimates operational cycles for each turbine state:

1. derive mean thrust from `Ct` and local wind speed;
2. apply a 3-second gust factor using local turbulence;
3. convert thrust to tower-root stress using the turbine’s `r_pile`, `t_tower`, and hub height;
4. apply a Goodman correction;
5. evaluate a two-slope DNV-style S–N relation with thickness correction; and
6. accumulate Miner damage over environmental states.

The effective life is `1 / damage`. The reported optimization metric is the normalized life of the weakest turbine:

```text
raw_fatigue = min(N_opt) / min(N_reference)
```

An average normalized life is also calculated in the source but is not the selected reported objective.

### 6.6 CAPEX and LCOE

The cost module follows the thesis decomposition:

```text
CAPEX = production/acquisition + power transmission + installation/commissioning
```

The implementation includes:

- turbine cost by rated power class;
- depth-dependent monopile dimensions, mass, and support cost;
- onshore/offshore substations;
- array and export cable length/cost;
- radial versus ring-like cable topology decisions;
- port distance, vessel speed, trips, fuel, mobilization, and workability; and
- fixed development and survey costs.

LCOE is mapped as:

```text
LCOE = raw_cost / (raw_aep_gwh × 25 years)
```

This is a simplified lifetime-energy ratio. The current implementation does not provide a complete discounted cash-flow, OPEX, failure, maintenance, or decommissioning model.

### 6.7 Thesis methodology versus current implementation

The thesis draft presents Nash Bargaining Theory as a way to select a balanced compromise from a Pareto front. The current repository writes the complete non-dominated front and offers plots/3-D views, but it does **not** contain a dedicated Nash-bargaining selector. Any compromise selection must therefore be performed externally or added as a future post-processing feature.

Likewise, the thesis reports case-study results for a Persian Gulf site and a 2000–2024 wind period. Those values describe the draft study; they are not guaranteed by the code for arbitrary inputs.

---

## 7. Outputs and visualization

### Optimizer outputs

SOGA writes to the configured output directory:

- `soga_convergence.csv`: generation-by-generation best fitness, raw metrics, LCOE, and soft-constraint diagnostics;
- `soga_best_layout.csv`: the champion metrics and one `gene_N` column per mesh node;
- `animation_data_soga.csv`: dense wind-field data for the champion layout.

MOGA writes:

- `generational_fronts.csv`: rank-1 metrics for every generation;
- `final_pareto_front.csv`: final rank-1 solutions, metrics, soft-constraint diagnostics, and genes;
- `animation_data_obj_1.csv` and `animation_data_obj_2.csv`: dense wind fields for the best rank-1 solution for each configured objective.

The animation CSV schema is:

```text
time,x,y,u_1,v_1,mag_1,u_2,v_2,mag_2,...
```

where each `N` is a unique turbine hub-height level reported by the Fortran loader.

### GUI visualizations

- **SOGA convergence:** `plot_soga_convergence.png`.
- **MOGA evolution:** `plot_evolution.png`.
- **MOGA final front:** `plot_final_pareto.png`.
- **Wind resource:** `wind_rose.png` and `wind_speed_diagnostics.png`.
- **3-D layouts:** PyVista bathymetry and turbine cylinders, with adjustable vertical exaggeration.
- **MP4 flows:** generated from animation CSVs with selectable height level, frame step, and FPS.

The 3-D view uses turbine dimensions from the catalogue. Its vertical and rotor-size exaggerations are presentation settings, not physical changes to the optimizer.

---

## 8. Time-series validation simulator

The simulator re-evaluates layouts using the chronological wind data in `filtered_wind.txt`. It accepts either:

- SOGA `soga_best_layout.csv`; or
- MOGA `final_pareto_front.csv`.

It discovers `gene_1` through `gene_N` by header name, so metadata columns before the genes are ignored. Gene order must match mesh node order. Coordinates stored in the CSV are not used by the parser.

Build and run:

```bash
make simulator

# Simulate every data row
./build/simulator inputs/config.inp outputs/final_pareto_front.csv all

# Simulate only source data rows 1, 4, and 7
./build/simulator inputs/config.inp outputs/final_pareto_front.csv 1,4,7

# Omitting the selector also simulates all rows
./build/simulator inputs/config.inp outputs/soga_best_layout.csv
```

Selectors are 1-based data-row numbers after the CSV header. `solution_id` is the position in the selected list; `source_row` preserves the original CSV row number.

The simulator forces time-series mode while retaining paths and physics settings from `config.inp`. It recalculates financial cost, wake/power physics, AEP, and fatigue. It does not calculate electrical array output.

Generated files are:

- `simulation_farm_timeseries.csv`: `solution_id`, `source_row`, timestep, total power, and capacity factor;
- `simulation_summary.csv`: aggregate power, capacity, annual energy, capacity factor, wake loss, cost, AEP, fatigue, and LCOE;
- `simulation_turbines.csv`: per-installed-turbine aggregate power, speed, turbulence, `Ct`, and thrust; and
- `simulation_summary.json`: JSON form of the aggregate summaries.

The simulator skips malformed, out-of-range, or empty layouts with warnings where possible. A wake iteration that does not converge by `max_iter` produces a warning and uses its last state.

---

## 9. Tests

The wake-model tests are Python implementations of the relevant Fortran formulas and do not require a compiled optimizer for the formula-level checks.

Run the suite with:

```bash
uv run pytest tests/
```

Useful focused runs include:

```bash
uv run pytest tests/test_wake_growth_rate.py -v
uv run pytest -m integration tests/
```

The test coverage includes dynamic wake-growth coefficient behavior, independence between turbines, linear deficit superposition, maximum turbulence selection, no-wake turbulence preservation, iteration limits, coefficient-token precision, and single/two/three-turbine integration scenarios.

---

## 10. Reproducibility and limitations

- Launch the GUI and direct executables from the repository root; most paths are relative.
- Rebuild Fortran binaries after changing compiler, platform, or `.f90` sources.
- The optimizer is stochastic and clock-seeded.
- The wind-rose approximation and time-series validation are different operating modes; use the simulator to compare a selected layout with chronological data.
- The analytical wake model omits near-wake vortex dynamics, wake meandering, transient effects, and full three-dimensional atmospheric coupling.
- Fatigue is a reduced analytical tower-root/monopile model; it does not replace aeroelastic or detailed structural analysis.
- Hydrodynamic loading, tides, soil–pile interaction, OPEX, maintenance, failure, discounting, inflation, and decommissioning are not fully represented.
- These are study-specific inputs, not universal program defaults; if you need to change them, modify the input files or script arguments based on your study's needs.
