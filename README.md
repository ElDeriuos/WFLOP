# OWFLO: Offshore Wind Farm Layout Optimizer

![OWFLO](https://img.shields.io/badge/Status-Active-success) ![Fortran](https://img.shields.io/badge/Backend-Fortran90-734f96) ![Python](https://img.shields.io/badge/Frontend-Python_3-3776ab) ![Wake Model](https://img.shields.io/badge/Wake_Model-Niayifar_2016-orange)

OWFLO is an end-to-end, high-performance software suite for the layout optimization of offshore wind farms. It couples a modern, highly interactive Python Graphical User Interface (GUI) with a blazing-fast Fortran backend to evaluate deep arrays of wind turbines using genetic algorithms.

By balancing aerodynamic wake losses against complex financial capital expenditures (CAPEX), OWFLO allows engineers to discover both the absolute best single-objective layouts (SOGA) and the optimal multi-objective trade-offs (MOGA/NSGA-II).

---

## 🏗️ System Architecture

The OWFLO ecosystem uses a **"Library + Driver"** architecture to maintain high execution speeds while offering a seamless user experience.

1. **The Python Frontend (`main.py`)**: A CustomTkinter-based interface that handles pre-processing (mesh generation, wind data, bathymetry), user parameter staging, automated Fortran compilation, and background job threading.
2. **The Fortran Core (`wflop_core.f90`)**: A monolithic, highly optimized mathematical library containing all physics, cost models, and evolutionary mechanics.
3. **The Fortran Drivers (`main_soga.f90` & `main_moga.f90`)**: Lightweight execution scripts that load the core library and run specific optimization pipelines.
4. **The Python Visualizer (`visualizer.py`)**: A post-processing suite that intercepts Fortran outputs to generate Pareto plots, PyVista 3D interactive layouts, and FFmpeg-powered MP4 wind flow animations.

---

## 🧪 Time-Series Simulation

`run_simulator` validates optimizer layouts against the original hourly wind time series. It accepts both existing optimizer result formats:

- SOGA: `soga_best_layout.csv`, one data row with `fitness,...,gene_1,...,gene_n`.
- MOGA: `final_pareto_front.csv`, one data row per Pareto solution with `LCOE,...,gene_1,...,gene_n`.

The simulator reads only `gene_1` through `gene_n`; metadata columns are ignored. Genes are in mesh row order. Gene `1` means no turbine. Genes `2` through `n_types-1` select turbine profiles from `turbine_spec.txt`. Existing CSV coordinates are not required by the parser and are not validated.

Build and run:

```bash
make simulator
./build/run_simulator inputs/config.inp outputs/final_pareto_front.csv 1,4,7
# Use `all` to simulate every data row; omitting the selector also simulates all rows.
./build/run_simulator inputs/config.inp outputs/soga_best_layout.csv all
```

Selector row numbers are 1-based data-row numbers after the CSV header. `solution_id` is the position within the selected list; `source_row` preserves the original CSV data-row number.

The simulator forces `wind_mode=1` while retaining paths and physics settings from `config.inp`. It recalculates cost and time-series physics using the existing wake solver, AEP, and fatigue routines. It does not calculate electrical array output. Outputs are written under `config%out_dir`:

- `simulation_farm_timeseries.csv`: `solution_id,source_row,timestep,total_power_mw,total_capacity_factor`.
- `simulation_summary.csv`: aggregate power, installed capacity, annual energy (`annual_energy_gwh`), capacity factor, wake-loss percentage, recalculated cost/LCOE, AEP, and fatigue.
- `simulation_turbines.csv`: one aggregate row per installed turbine with node, type, mean/max/total power, mean effective/reference wind power, mean turbulence intensity, mean Ct, and mean thrust force in N. No per-turbine time-series file is produced.
- `simulation_summary.json`: JSON equivalent of aggregate solution summaries.

Power is reported in MW, energy in MWh/GWh, wind speed in m/s, and direction remains the existing radians/towards-flow convention. AEP follows the existing optimizer convention: hourly time-series mean power annualized to 8760 hours. Invalid rows are skipped with warnings and partial output files remain available. Wake non-convergence emits a warning and uses the last iteration, as requested.

---

## 🧩 Fortran Backend Modules (`wflop_core.f90`)

The mathematical heavy lifting is divided into highly modularized Fortran namespaces.

### 1. `MODULE types` & `MODULE precision`
Defines the 64-bit working precision (`wp`) and the core derived data types used throughout the program:
- `ConfigData`: Hyperparameters (population, generations, mutation rates) and farm constraints.
- `SiteData`: Spatial mesh boundaries, bathymetry (Z-depths), and hourly wind time-series.
- `TurbineSpec`: Aerodynamic properties (power curves, thrust curves, physical dimensions).
- `Individual` & `Population`: Chromosomes representing spatial layouts and their associated fitness scores.

### 2. `MODULE inputs`
Handles the safe, dynamic ingestion of user configurations. Features automatic scanning of Master Turbine text files to deduce exact unique hub-heights, preventing unnecessary 3D field calculations.

### 3. `MODULE costs`
Implements the comprehensive **Kikuchi Financial Model** to calculate total CAPEX.
- Evaluates dynamic support structure costs based on specific seabed depths at turbine nodes.
- Calculates cable array topographies (radial vs. ring topology) and associated substation requirements.
- Models realistic installation vessel logistics based on port distances, turbine MW class, and weather workability.

### 4. `MODULE physics` (Power / Wake Modeling)
Evaluates Annual Energy Production (AEP) and structural fatigue lifetime.
- Implements the **Niayifar & Porté-Agel (2016) dynamic wake framework** on top of the Bastankhah Gaussian wake shape.
- **Dynamic wake growth rate** (Eq. 15): `k* = 0.3837·I + 0.003678` — the wake expansion rate is computed per-turbine from local inflow turbulence intensity, not a hardcoded constant.
- **Linear velocity deficit superposition** (Eq. 16): `Uj = U∞ − Σ(deficits)` — wake deficits are summed arithmetically, replacing the old Root-Sum-Square model.
- **Maximum turbulence selection**: when multiple wakes overlap, the dominant turbulence source governs rather than accumulating additively.
- **Iterative TI propagation**: local turbulence intensity `ti_new(:)` is tracked per turbine and fed back into each iteration of the All-to-All solver so wake growth rate converges alongside wind speed.
- **Yang (2025) fatigue model**: normalized fatigue life `N_i,OPT / N_i,ORI` is computed as a second optimization objective alongside AEP.
- Contains a **Dense Matrix Solver** (static `k_star = 0.0324`, visualization only) for post-processing full 3D wind fields for MP4 animations.

> **Reference:** Niayifar, A. & Porté-Agel, F. (2016). *Analytical Modeling of Wind Farms: A New Approach for Power Prediction*. Energies, 9(9), 741.

### 5. `MODULE NSGA_II`
The core engine for Multi-Objective optimization (Cost vs. AEP trade-off).
- Employs Deb's fast non-dominated sorting and crowding distance calculations.
- Houses the foundational genetic operators: **Tournament Selection**, **Uniform Crossover**, and **Fisher-Yates Poisson Mutation**.

### 6. `MODULE SOGA`
The engine for Single-Objective optimization.
- Re-uses genetic operators from the NSGA-II module.
- Features **Lazy Evaluation**: dynamically evaluates only the physics required for the user's targeted objective (e.g., skips wake modeling if optimizing purely for Cost).
- Uses scalar fitness sorting instead of Pareto ranks.

### 7. `MODULE outputs`
Safely writes data to CSV formats. Dynamically builds headers based on grid sizes and restores normalized/negated values back to real-world units (GBP, GWh) for the visualization engine.

---

## 🎨 Python Frontend & Visualization Modules

### `main.py`
The control center. Organized into chronological workflow tabs:
1. **Pre-Processing:** Integrates KML boundaries, GEBCO bathymetry, and ERA5 NetCDF wind data.
2. **Farm Setup:** Manages the Master Turbine Specification file and physical turbine limits.
3. **SOGA (Single-Obj):** Configures algorithms targeting absolute best Cost or AEP. Includes integrated Fortran compilation (Fast/Debug).
4. **MOGA (Multi-Obj):** Configures the NSGA-II solver for Pareto trade-off analysis. Includes integrated Fortran compilation (Fast/Debug).

All compilations and optimizations run in background daemon threads, keeping the GUI responsive and allowing hard-aborts via the UI.

### `visualizer.py`
The post-processing engine. Triggered automatically by the GUI upon successful optimization.
- **Pareto / Convergence Tracking (`matplotlib`):** Generates `plot_evolution.png` (MOGA) and `plot_soga_convergence.png` (SOGA), dynamically flipping negated internal objectives back to positive readable labels.
- **Interactive 3D Layouts (`pyvista`):** Renders farm topography, mapped seabed depths, and 3D cylinders representing heterogeneous turbine classes at their optimized nodes.
- **MP4 Flow Animations (`matplotlib.animation` + `ffmpeg`):** Renders `tricontourf` plots of the 3D wake field interacting with the champion layout over the simulated time-series.

---

## ⚙️ Wake Physics Model

The `MODULE physics` in `wflop_core.f90` implements the Niayifar & Porté-Agel (2016) dynamic wake framework. Three targeted changes were made relative to the static Bastankhah baseline. All optimization algorithms, cost models, fatigue models, and array-bound structures are left unchanged.

### What Changed vs. What Did Not

| Area | Changed | Unchanged |
|------|---------|-----------|
| Wake growth rate `k_star` | Hardcoded `0.0324` → dynamic formula | — |
| Velocity superposition | RSS → linear sum | Gaussian wake shape |
| Turbulence superposition | Squared-sum → MAX selection | TKE ambient combination |
| `analytical_wake_sparse` signature | Added `ti_new(:)` parameter | All other parameters |
| `evaluate_physics` | TI array allocated and propagated | Fatigue model, AEP formula |
| `bastankhah_wake_dense` | Not changed (visualization only) | Static `k_star = 0.0324` |
| NSGA-II / SOGA | Not changed | Genetic operators, selection |
| Cost module | Not changed | Kikuchi financial model |

### Dynamic Wake Growth Rate (Eq. 15)

Wake expansion is no longer hardcoded. Each turbine's growth rate is computed from its local inflow turbulence intensity at every solver iteration:

```
k* = 0.3837 · I_local + 0.003678          (Niayifar 2016, Eq. 15)
```

| Local TI | k* (static, old) | k* (dynamic, new) |
|----------|-----------------|-------------------|
| 0.00     | 0.0324          | 0.003678          |
| 0.08 (ambient) | 0.0324  | 0.034374          |
| 0.10     | 0.0324          | 0.042048          |
| 0.30     | 0.0324          | 0.118788          |

### Linear Velocity Deficit Superposition (Eq. 16)

Multiple overlapping wakes are combined by arithmetic sum rather than root-sum-square:

```
Uj = U∞ · (1 − Σ ΔUij/U∞)               (Niayifar 2016, Eq. 16)
```

For two wakes with deficits `[0.2, 0.3]`: RSS gives `0.361`, linear gives `0.500`. Linear superposition conserves momentum and produces physically correct multi-turbine wake predictions.

### Maximum Turbulence Superposition

When wakes from multiple upstream turbines overlap, the dominant turbulence source governs:

```
ΔI_combined = MAX(ΔI₁, ΔI₂, ..., ΔIₙ)
```

The updated TI feeds back into the next solver iteration via TKE superposition:

```
ti_new(m) = √(I_ambient² + ΔI_combined(m))
```

For two equal wakes with added TI `[0.05, 0.05]`: the old squared-sum yields `0.071`, MAX yields `0.050`.

### Subroutine Signature Change

`analytical_wake_sparse` gained one new `INTENT(IN)` parameter. All existing parameters and array bounds are unchanged:

```fortran
! Before
SUBROUTINE analytical_wake_sparse(..., t_step, deficit_u, added_i)

! After
SUBROUTINE analytical_wake_sparse(..., t_step, ti_new, deficit_u, added_i)
```

A new `REAL(wp), ALLOCATABLE :: ti_new(:)` array is allocated and deallocated inside `evaluate_physics` (same dimension as `ws_new`), adding `8 bytes × n_turb` per evaluation call.

### Key Numerical Invariants

These must hold after any future modification to the physics module:

```
1. k_star ∈ (0.003678, 0.118788)  for TI ∈ [0.0, 0.3]
2. k_star is monotonically increasing in TI
3. k_star(m) depends only on ti_new(m), not on ti_new(j≠m)
4. wake_deficit_u = Σ single_deficit_u   (not √Σdeficit²)
5. wake_added_i   = MAX(single_added_i)  (not Σ added_i)
6. ti_new(m) = I_ambient when wake_added_i(m) = 0.0
7. Fortran source contains exact tokens: "0.3837_wp" and "0.003678_wp"
8. Solver terminates at or before k_iter = config%max_iter
```

### Limitations

- `bastankhah_wake_dense` (used by `calculate_3d_wind_field` for animations) retains the old static `k_star = 0.0324`. It does not participate in the optimization loop and is out of scope for this refactoring. A future task may align it with `analytical_wake_sparse` for visual fidelity.
- The added-turbulence formula inside `analytical_wake_sparse` (`0.73 × (1−√(1−Ct))^0.8325 × I_ambient^0.0325 × (x/D)^−0.32`) is an empirical stand-in for the Ishihara model and is unchanged; only the superposition rule was changed.

---

## 🧪 Test Suite

All physics changes are covered by a property-based and integration test suite in `tests/`. Tests are pure-Python reimplementations of the Fortran formulas — no compiled binary is required.

```bash
# Run the full test suite
uv run pytest tests/

# Run a specific property test
uv run pytest tests/test_wake_growth_rate.py -v
```

### Test Inventory

| File | Type | Property | Requirements |
|------|------|----------|--------------|
| `test_wake_growth_rate.py` | PBT + unit | P1: k* formula correctness | 1.1, 11.1 |
| `test_wake_growth_rate_independence.py` | PBT | P2: k*(m) independence | 1.2, 1.5, 4.4 |
| `test_linear_velocity_superposition.py` | PBT + unit | P3: Linear deficit sum | 2.1, 2.2, 11.2 |
| `test_maximum_turbulence_selection.py` | PBT + unit | P4: MAX turbulence selection | 3.1, 11.3 |
| `test_turbulence_preservation.py` | PBT + unit | P5: No-wake TI preservation | 3.5 |
| `test_iteration_bound_enforcement.py` | PBT + unit | P6: Iteration bound | 8.4 |
| `test_coefficient_precision.py` | Source scan + PBT | P7: Fortran coefficient tokens | 11.5 |
| `test_edge_cases.py` | Unit | Task 9.4 edge cases | 1.1, 2.1, 3.1, 3.5 |
| `test_integration_single_turbine.py` | Integration | Task 10.1: Single turbine | 10.3, 10.4 |
| `test_integration_two_turbine.py` | Integration | Task 10.2: Aligned pair | 8.1, 8.2 |
| `test_integration_three_turbine.py` | Integration | Task 10.3: Three-turbine overlap | 2.1, 3.1 |

### Property-Based Test Strategy

Each Hypothesis property runs 100 generated examples over the physically meaningful input domain.

| Property | Input Domain | Tolerance |
|----------|--------------|-----------|
| P1: k* formula | TI ∈ [0.0, 0.3] | 1×10⁻¹⁰ |
| P2: k* independence | TI ∈ [0.0, 0.3], N ∈ [2, 10] | 1×10⁻¹⁰ |
| P3: Linear superposition | deficit ∈ [0.0, 0.5], U∞ ∈ [5, 25] m/s | 1×10⁻¹⁰ |
| P4: MAX turbulence | TI ∈ [0.0, 0.1] | 1×10⁻¹⁰ |
| P5: TI preservation | I_amb ∈ [0.01, 0.2], N ∈ [1, 20] | 1×10⁻¹⁰ |
| P6: Iteration bound | max_iter ∈ [1, 50], N ∈ [1, 20] | exact |
| P7: Coefficient precision | exact token match in Fortran source | 1×10⁻¹⁵ |

### Integration Test Scenarios

**Task 10.1 — Single Turbine (No Wake):** One turbine, no upstream wakes. Verifies `ti_new = I_ambient`, `k_star = 0.034374`, solver converges on iteration 1.

**Task 10.2 — Aligned Two-Turbine Pair (5D spacing):** T1 at `(0, 0)`, T2 at `(5D, 0)`. Verifies `deficit_T2 > 0`, `ws_T2 < v_ambient`, `ti_T2 > I_ambient`, `k_star_T2 > k_star_ambient`. T1 is unaffected.

**Task 10.3 — Three-Turbine Wake Overlap:** T1 at `(0, +D/2)`, T2 at `(0, −D/2)`, T3 at `(5D, 0)`. Verifies `deficit_T3 = d₁ + d₂` (linear, not RSS) and `added_i_T3 = MAX(added₁, added₂)` (not summed).

For the full technical specification see [`NIAYIFAR_WAKE_MODEL_REPORT.md`](NIAYIFAR_WAKE_MODEL_REPORT.md).

---

## 📁 Modified Files

| File | Nature of Change |
|------|-----------------|
| `source/wflop_core.f90` | Primary implementation: all three physics changes |
| `tests/test_wake_growth_rate.py` | New — Property 1 + unit tests |
| `tests/test_wake_growth_rate_independence.py` | New — Property 2 |
| `tests/test_linear_velocity_superposition.py` | New — Property 3 + unit tests |
| `tests/test_maximum_turbulence_selection.py` | New — Property 4 + unit tests |
| `tests/test_turbulence_preservation.py` | New — Property 5 + unit tests |
| `tests/test_iteration_bound_enforcement.py` | New — Property 6 + unit tests |
| `tests/test_coefficient_precision.py` | New — Property 7, scans Fortran source |
| `tests/test_edge_cases.py` | New — Task 9.4 edge cases |
| `tests/test_integration_single_turbine.py` | New — Task 10.1 |
| `tests/test_integration_two_turbine.py` | New — Task 10.2 |
| `tests/test_integration_three_turbine.py` | New — Task 10.3 |
| `tests/__init__.py` | New — package marker |

---

## 🚀 Installation & Setup

### Prerequisites
1. **Python 3.10+** (Anaconda/Miniconda recommended)
2. **Fortran Compiler**: `gfortran` (included in MinGW for Windows)
3. **FFmpeg**: required for MP4 animation rendering.

### Environment Setup

```bash
conda create -n owflo_env python=3.10
conda activate owflo_env

# Runtime dependencies
pip install customtkinter pandas numpy matplotlib pyvista netCDF4

# Test dependencies (property-based tests)
pip install pytest hypothesis

# FFmpeg (required for animations)
conda install -c conda-forge ffmpeg
```

---

## 🎮 Usage Guide

1. **Launch the GUI:**
   ```bash
   python main.py
   ```

2. **Prepare Inputs:** Use the Pre-Processing tab to generate your spatial mesh and extract wind/depth data.

3. **Configure Farm:** In the Farm Setup tab, link your `turbine_spec.txt` master file.

4. **Compile the backend:** Navigate to either the SOGA or MOGA tab and click Compile (Fast). The GUI will invoke `gfortran` to build the core library and the specific driver script.

5. **Optimize:** Click Run Optimization. Watch the Fortran console stream live to the right panel.

6. **Visualize:** Once finished, use the glowing action buttons at the bottom of the screen to launch 3D layouts, convergence plots, and flow animations.
