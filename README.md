# OWFLO: Offshore Wind Farm Layout Optimizer

![OWFLO](https://img.shields.io/badge/Status-Active-success) ![Fortran](https://img.shields.io/badge/Backend-Fortran90-734f96) ![Python](https://img.shields.io/badge/Frontend-Python_3-3776ab) 

OWFLO is an end-to-end, high-performance software suite for the layout optimization of offshore wind farms. It couples a modern, highly interactive Python Graphical User Interface (GUI) with a blazing-fast Fortran backend to evaluate deep arrays of wind turbines using genetic algorithms.

By balancing aerodynamic wake losses against complex financial capital expenditures (CAPEX), OWFLO allows engineers to discover both the absolute best single-objective layouts (SOGA) and the optimal multi-objective trade-offs (MOGA/NSGA-II).

---

## 🏗️ System Architecture

The OWFLO ecosystem uses a **"Library + Driver"** architecture to maintain high execution speeds while offering a seamless user experience.

1. **The Python Frontend (`gui_modern.py`)**: A CustomTkinter-based interface that handles pre-processing (mesh generation, wind data, bathymetry), user parameter staging, automated Fortran compilation, and background job threading.
2. **The Fortran Core (`wflop_core.f90`)**: A monolithic, highly optimized mathematical library containing all physics, cost models, and evolutionary mechanics.
3. **The Fortran Drivers (`main_soga.f90` & `main_moga.f90`)**: Lightweight execution scripts that load the core library and run specific optimization pipelines.
4. **The Python Visualizer (`visualizer.py`)**: A post-processing suite that intercepts Fortran outputs to generate Pareto plots, PyVista 3D interactive layouts, and FFmpeg-powered MP4 wind flow animations.

---

## 🧩 Fortran Backend Modules (`wflop_core.f90`)

The mathematical heavy lifting is divided into highly modularized Fortran namespaces.

### 1. `MODULE types` & `MODULE precision`
Defines the 64-bit working precision (`wp`) and the core derived data types used throughout the program:
* `ConfigData`: Hyperparameters (population, generations, mutation rates) and farm constraints.
* `SiteData`: Spatial mesh boundaries, bathymetry (Z-depths), and hourly wind time-series.
* `TurbineSpec`: Aerodynamic properties (power curves, thrust curves, physical dimensions).
* `Individual` & `Population`: Chromosomes representing spatial layouts and their associated fitness scores.

### 2. `MODULE inputs`
Handles the safe, dynamic ingestion of user configurations. Features automatic scanning of Master Turbine text files to deduce exact unique hub-heights, preventing unnecessary 3D field calculations.

### 3. `MODULE costs`
Implements the comprehensive **Kikuchi Financial Model** to calculate total CAPEX.
* Evaluates dynamic support structure costs based on specific seabed depths at turbine nodes.
* Calculates cable array topographies (radial vs. ring topology) and associated substation requirements.
* Models realistic installation vessel logistics based on port distances, turbine MW class, and weather workability.

### 4. `MODULE physics` (Power / Wake Modeling)
Evaluates Annual Energy Production (AEP).
* Implements the **Bastankhah Analytical Wake Model**.
* Utilizes an All-to-All Iterative Solver to resolve intersecting wakes across complex topographies.
* Features a highly optimized **Sparse Matrix Approach**: only active turbine nodes calculate wake deficits, accelerating the genetic algorithm evaluation loop.
* Contains a **Dense Matrix Solver** specifically for post-processing full 3D wind fields for MP4 animations.

### 5. `MODULE NSGA_II`
The core engine for Multi-Objective optimization (Trade-off between Cost vs. AEP).
* Employs Deb's fast non-dominated sorting and crowding distance calculations.
* Houses the foundational genetic operators: **Tournament Selection**, **Uniform Crossover**, and **Fisher-Yates Poisson Mutation**.

### 6. `MODULE SOGA`
The engine for Single-Objective optimization.
* Re-uses genetic operators from the NSGA-II module.
* Features **Lazy Evaluation**: dynamically evaluates *only* the physics required for the user's targeted objective (e.g., skips wake modeling if optimizing purely for Cost), vastly accelerating runtimes.
* Uses scalar fitness sorting instead of Pareto ranks.

### 7. `MODULE outputs`
Safely writes data to CSV formats. Dynamically builds headers based on grid sizes and seamlessly restores normalized/negated values back to real-world units (e.g., GBP and GWh) for the visualization engine.

---

## 🎨 Python Frontend & Visualization Modules

### `main.py`
The control center. Organized into chronological workflow tabs:
1. **Pre-Processing:** Integrates KML boundaries, GEBCO bathymetry, and ERA5 NetCDF wind data.
2. **Farm Setup:** Manages the Master Turbine Specification file and physical turbine limits.
3. **SOGA (Single-Obj):** Configures algorithms targeting absolute best Cost or AEP. Includes integrated Fortran compilation (Fast/Debug).
4. **MOGA (Multi-Obj):** Configures the NSGA-II solver for Pareto trade-off analysis. Includes integrated Fortran compilation (Fast/Debug).

*Note: All compilations and optimizations are launched in background daemon threads, keeping the GUI responsive and allowing for hard-aborts (`.kill()`) via the UI.*

### `visualizer.py`
The post-processing engine. Triggered automatically by the GUI upon successful optimization.
* **Pareto / Convergence Tracking (`matplotlib`):** Generates `plot_evolution.png` (MOGA) and `plot_soga_convergence.png` (SOGA), dynamically flipping negated internal objectives back to positive readable labels.
* **Interactive 3D Layouts (`pyvista`):** Renders the farm topography, mapped seabed depths, and highly accurate 3D cylinders representing heterogeneous turbine classes placed at their optimized nodes.
* **MP4 Flow Animations (`matplotlib.animation` + `ffmpeg`):** Renders fluid dynamic `tricontourf` plots of the 3D wake field interacting with the champion layout over the simulated time-series.

---

## 🚀 Installation & Setup

### Prerequisites
1. **Python 3.8+** (Anaconda/Miniconda recommended)
2. **Fortran Compiler**: `gfortran` (Included in MinGW for Windows)
3. **FFmpeg**: Required for MP4 animation rendering.

### Environment Setup
Open an Anaconda Prompt and set up the environment:
```bash
conda create -n owflo_env python=3.10
conda activate owflo_env

# Install Python dependencies
pip install customtkinter pandas numpy matplotlib pyvista netCDF4

# Install FFmpeg (CRITICAL for animations)
conda install -c conda-forge ffmpeg
```
## 🎮 Usage Guide

1. **Launch the GUI:**
   ```bash
   python main.py

2. **Prepare Inputs:** Use the Pre-Processing tab to generate your spatial mesh and extract wind/depth data.

3. ** Configure Farm:** In the Farm Setup tab, link your turbine_spec.txt master file.

4. **Compile the backend:** Navigate to either the SOGA or MOGA tab and click Compile (Fast). The GUI will invoke gfortran to build the core library and the specific driver script.

5. **Optimize:** Click Run Optimization. Watch the Fortran console stream live to the right panel.

6. **Visualize:** Once finished, use the glowing action buttons at the bottom of the screen to launch 3D layouts, convergence plots, and flow animations.
