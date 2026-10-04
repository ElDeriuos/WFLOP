import os
import sys
import re
import subprocess
import shutil
import threading

# =====================================================================
# WORKING DIRECTORY
# =====================================================================
# All paths in the app (./inputs, ./outputs, ./source) are relative to the
# project folder. Anchor the working directory there so the app works when
# launched from anywhere, including as a PyInstaller bundle where the folder
# is the one containing the executable.
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP_DIR)

# Apps launched from the macOS Finder do not inherit the shell PATH, so
# Homebrew tools (gfortran, ffmpeg) would not be found.
if sys.platform == "darwin":
    for brew_bin in ("/opt/homebrew/bin", "/usr/local/bin"):
        if brew_bin not in os.environ.get("PATH", "").split(os.pathsep):
            os.environ["PATH"] = brew_bin + os.pathsep + os.environ.get("PATH", "")
os.makedirs("inputs", exist_ok=True)
os.makedirs("outputs", exist_ok=True)

# `--self-test` runs before the GUI and plotting imports below, so an install whose
# libraries fail to load still writes a report (selftest.log) instead of dying silently.
if __name__ == "__main__" and "--self-test" in sys.argv:
    from source import selftest
    sys.exit(selftest.run())

import customtkinter as ctk
import tkinter.filedialog as filedialog
from source import mesh_generator
from source import bathymetry_generator
from source import wind_generator
from source import distance_calculator
from source import visualizer

# =====================================================================
# DESIGN: GLOBAL THEME CONFIGURATION
# =====================================================================
# appearance_mode options: "System" (follows OS), "Dark", "Light"
ctk.set_appearance_mode("Light")
# color_theme options: "blue" (standard), "green", "dark-blue"
ctk.set_default_color_theme("dark-blue")

# Monospace font for the live console, per platform
MONO_FONT = {"win32": "Consolas", "darwin": "Menlo"}.get(sys.platform, "DejaVu Sans Mono")

# config.inp is positional: one value per line, in the exact order read_gui_config
# (source/wflop_core.f90) reads them. Fortran list-directed READ ignores the rest of
# each line, so the trailing "! name: description" comments are safe.
CONFIG_FIELDS = [
    ("it_max", "GA: max generations (SOGA, MOGA)"),
    ("n_pop", "GA: population size (SOGA, MOGA)"),
    ("p_cross", "GA: crossover probability (SOGA, MOGA)"),
    ("p_mut", "GA: mutation probability (SOGA, MOGA)"),
    ("mu", "GA: mutation step (SOGA, MOGA)"),
    ("max_turbs", "Farm: max turbines, hard limit (SOGA, MOGA)"),
    ("min_turbs", "Farm: min turbines, hard limit (SOGA, MOGA)"),
    ("soga_stall", "GA: generations without improvement before early stop, 0 = off (SOGA)"),
    ("workability", "Farm: installation workability factor, affects CAPEX (all modes, simulator)"),
    ("opt_mode", "Mode: 1 = SOGA, 2 = MOGA (NSGA-II)"),
    ("obj_1", "Objective 1: 1 = min LCOE, 2 = min CAPEX, 3 = max AEP, 4 = max fatigue life"),
    ("obj_2", "Objective 2, same codes; 0 when SOGA (MOGA only)"),
    ("wind_mode", "Wind: 1 = time-series (wind1 file), 2 = wind rose (wind2 file); simulator forces 1"),
    ("use_soft_constraints", "Soft constraints: 1 = on, 0 = off (SOGA, MOGA)"),
    ("aep_min_soft", "Soft constraint: min AEP, 0 = off (SOGA, MOGA)"),
    ("capex_max_soft", "Soft constraint: max CAPEX, 0 = off (SOGA, MOGA)"),
    ("w_aep_soft", "Soft constraint: AEP penalty weight (SOGA, MOGA)"),
    ("w_capex_soft", "Soft constraint: CAPEX penalty weight (SOGA, MOGA)"),
    ("soft_penalty_power", "Soft constraint: penalty exponent (SOGA, MOGA)"),
    ("f_turb", "File: turbine specification (all modes)"),
    ("f_mesh", "File: mesh node coordinates (all modes)"),
    ("f_wind1", "File: wind time series, filtered_wind.txt (wind_mode 1, simulator)"),
    ("f_wind2", "File: wind rose matrix (wind_mode 2)"),
    ("f_bathy", "File: farm bathymetry (all modes)"),
    ("f_dist", "File: site distances to shore/grid/port (all modes)"),
    ("out_dir", "Directory: outputs, must end with / (all modes)"),
]
CONFIG_PATH_FIELDS = {"f_turb", "f_mesh", "f_wind1", "f_wind2", "f_bathy", "f_dist", "out_dir"}


def format_config(values):
    """Renders config.inp text from a dict keyed by CONFIG_FIELDS names."""
    lines = []
    for key, comment in CONFIG_FIELDS:
        value = values[key]
        if key in CONFIG_PATH_FIELDS:
            value = '"' + str(value).replace("\\", "/") + '"'
        lines.append(f"{str(value):<40} ! {key}: {comment}")
    return "\n".join(lines) + "\n"


def simulator_config_values(turb, mesh, wind1, bathy, dist, out_dir, workability):
    """Config values for a simulator-only run. The simulator ignores the GA, objective
    and soft-constraint fields, so they get neutral placeholders."""
    out_dir = out_dir.replace("\\", "/")
    return {
        "it_max": 1, "n_pop": 2, "p_cross": 0.5, "p_mut": 0.5, "mu": 0.08,
        "max_turbs": 1, "min_turbs": 1, "soga_stall": 0, "workability": workability,
        "opt_mode": 1, "obj_1": 1, "obj_2": 0, "wind_mode": 1,
        "use_soft_constraints": 0, "aep_min_soft": 0.0, "capex_max_soft": 0.0,
        "w_aep_soft": 0.0, "w_capex_soft": 0.0, "soft_penalty_power": 2.0,
        "f_turb": turb, "f_mesh": mesh, "f_wind1": wind1, "f_wind2": "./inputs/wind_rose_matrix.dat",
        "f_bathy": bathy, "f_dist": dist, "out_dir": out_dir if out_dir.endswith("/") else out_dir + "/",
    }


# GUI target -> program name in build/
PROGRAMS = {"soga": "soga_optimizer", "moga": "moga_optimizer", "simulator": "simulator"}


def fortran_exe(name):
    """Path of a compiled Fortran program; every build path (GUI, Makefile) puts them in ./build."""
    return os.path.join(os.getcwd(), "build", name + (".exe" if sys.platform == "win32" else ""))


def build_simulator_command(exe_path, config_path, csv_path, rows):
    """Builds the simulator argv. rows is 'all', blank, or 1-based rows like '1,4,7'."""
    rows = rows.replace(" ", "")
    if rows in ("", "all"):
        return [exe_path, config_path, csv_path, "all"]
    tokens = rows.split(",")
    if not all(t.isdigit() and int(t) >= 1 for t in tokens):
        raise ValueError(f"Invalid row selector: '{rows}'. Use 'all' or e.g. 1,4,7")
    return [exe_path, config_path, csv_path, ",".join(tokens)]


OBJ_MAPPING = {
    "Minimize LCOE": 1,
    "Minimize CAPEX": 2,
    "Maximize AEP": 3,
    "Maximize Fatigue Life": 4
}

class OWFLOGui(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.running_process = None

        # --- Main Window Configuration ---
        self.title("OWFLO: Offshore Wind Farm Layout Optimizer")
        self.geometry("1400x850")

        # uniform keeps the split fixed, so the console has the same width on every tab
        self.grid_columnconfigure(0, weight=1, uniform="panels")
        self.grid_columnconfigure(1, weight=1, uniform="panels")
        self.grid_rowconfigure(0, weight=1)

        # =========================================================
        # LEFT PANEL: THE CONTROL CENTER (TABBED)
        # =========================================================
        self.tabview = ctk.CTkTabview(self, corner_radius=10, command=self.on_tab_change)
        self.tabview.grid(row=0, column=0, padx=10, pady=(10, 10), sticky="nsew")

        self.tab_pre = self.tabview.add("Pre-Processing")
        self.tab_farm = self.tabview.add("Farm Setup")
        # Pre-Processing and Farm Setup build their own scrollable frames
        self.tab_soga = self._scrollable_tab("SOGA (Single-Obj)")
        self.tab_moga = self._scrollable_tab("NSGA-II (Multi-Obj)")
        self.tab_sim = self._scrollable_tab("Simulator")
        self.compile_buttons = {}

        # ---------------------------------------------------------
        # SHARED VARIABLES
        # ---------------------------------------------------------
        self.opt_mode_var = ctk.StringVar(value="SOGA")
        self.obj1_var = ctk.StringVar(value="Minimize LCOE")
        self.obj2_var = ctk.StringVar(value="Maximize Fatigue Life")

        self.path_turb = ctk.StringVar(value="./inputs/turbine_spec.txt")
        self.path_mesh = ctk.StringVar(value="./inputs/windfarm_rocol.txt")
        self.path_wind1 = ctk.StringVar(value="./inputs/filtered_wind.txt")
        self.path_wind2 = ctk.StringVar(value="./inputs/wind_rose_matrix.dat")
        self.path_bathy = ctk.StringVar(value="./inputs/farm_bathymetry.dat")
        self.path_dist = ctk.StringVar(value="./inputs/site_distances.txt")
        self.path_out = ctk.StringVar(value="./outputs/")
        self.wind_calc_mode = ctk.StringVar(value="Time-Series")
        # Soft-constraint GUI state
        self.use_soft_constraints_var = ctk.BooleanVar(value=False)


        # =========================================================
        # RIGHT PANEL: THE OUTPUT CENTER
        # =========================================================
        self.output_frame = ctk.CTkFrame(self, corner_radius=10)
        self.output_frame.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="nsew")
        self.output_frame.grid_rowconfigure(1, weight=1)
        self.output_frame.grid_columnconfigure(0, weight=1)

        # 1. Output Header
        self.lbl_console = ctk.CTkLabel(self.output_frame, text="Live Optimization Console", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_console.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")

        # 2. Live Console Textbox (Read-only)
        self.console = ctk.CTkTextbox(self.output_frame, font=ctk.CTkFont(family=MONO_FONT, size=12))
        self.console.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.console.insert("0.0", "OWFLO System Initialized. Awaiting commands...\n")
        self.console.configure(state="disabled") # Prevent user typing

        # 3. Global Console Action Buttons (Bottom row)
        self.console_action_frame = ctk.CTkFrame(self.output_frame, fg_color="transparent")
        self.console_action_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")

        # Keep the Global Abort Button here
        self.btn_abort = ctk.CTkButton(self.console_action_frame, text="Abort Execution", fg_color="#b22222", hover_color="#8b1a1a", state="disabled", command=self.abort_process)
        self.btn_abort.pack(side="right")

        # =========================================================
        # INITIALIZATION EXECUTION
        # =========================================================
        # Build the Tabs
        self.build_pre_processing_tab()
        self.build_farm_setup_tab()
        self.build_soga_tab()
        self.build_moga_tab()
        self.build_simulator_tab()

        # Run the validation once at startup so the MOGA dropdowns don't overlap
        self.enforce_unique_objectives(1)
        self._apply_objective_rules(1)

        # Compile needs gfortran; Run needs the compiled program in build/
        self.run_buttons = {"soga": self.btn_run_soga, "moga": self.btn_run_moga, "simulator": self.btn_run_sim}
        self.compiling = set()
        self.refresh_program_buttons(report=True)

    def _scrollable_tab(self, name):
        """Adds a tab whose content scrolls when it is taller than the window."""
        scroll = ctk.CTkScrollableFrame(self.tabview.add(name), fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        return scroll

    def on_tab_change(self):
        is_sim = self.tabview.get() == "Simulator"
        self.lbl_console.configure(text="Live Simulation Console" if is_sim else "Live Optimization Console")
        self.refresh_program_buttons()

    def refresh_program_buttons(self, report=False):
        """Disables Compile without gfortran and Run without the compiled program.
        Called at startup, on tab change, and after each compile."""
        has_gfortran = shutil.which("gfortran") is not None
        if report and not has_gfortran:
            self.log("gfortran not found: Compile buttons are disabled. The prebuilt programs in build/ are used.")
        for target, run_btn in self.run_buttons.items():
            compile_btn = self.compile_buttons[target]
            if target not in self.compiling:
                compile_btn.configure(state="normal" if has_gfortran else "disabled",
                                      text=compile_btn.base_text + ("" if has_gfortran else " (gfortran not found)"))
            exe = fortran_exe(PROGRAMS[target])
            built = os.path.exists(exe)
            if report and not built:
                self.log(f"{os.path.relpath(exe)} not found: its Run button is disabled until it is compiled.")
            run_btn.configure(text=run_btn.base_text + ("" if built else " (program not built)"))
            if not built:
                run_btn.configure(state="disabled")
            elif self.running_process is None and target not in self.compiling:
                run_btn.configure(state="normal")

    def _add_compile_button(self, parent, target, label):
        """One compile button per tab; run_compiler disables it while gfortran runs."""
        btn = ctk.CTkButton(parent, text=label, fg_color="#e0b000", hover_color="#b38c00", text_color="#1a1a1a",
                            command=lambda: self.run_compiler(target))
        btn.base_text = label
        btn.pack(fill="x", padx=10, pady=(15, 0), side="bottom")
        self.compile_buttons[target] = btn

    # ---------------------------------------------------------
    # TAB BUILDERS
    # ---------------------------------------------------------
    def build_soga_tab(self):
        """Constructs the Single-Objective inputs."""

        soga_frame = ctk.CTkFrame(self.tab_soga, corner_radius=10)
        soga_frame.pack(fill="x", padx=10, pady=(10, 20))

        ctk.CTkLabel(soga_frame, text="SOGA Hyperparameters", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))

        ga_grid = ctk.CTkFrame(soga_frame, fg_color="transparent")
        ga_grid.pack(fill="x", padx=15, pady=5)

        # Generational Setup
        ctk.CTkLabel(ga_grid, text="Max Generations:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.soga_gen = ctk.CTkEntry(ga_grid, width=100)
        self.soga_gen.insert(0, "100")
        self.soga_gen.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(ga_grid, text="Population Size:").grid(row=0, column=2, sticky="e", padx=(20, 5), pady=5)
        self.soga_pop = ctk.CTkEntry(ga_grid, width=100)
        self.soga_pop.insert(0, "50")
        self.soga_pop.grid(row=0, column=3, padx=5, pady=5)

        # GA Probabilities
        ctk.CTkLabel(ga_grid, text="Crossover Prob:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.soga_cross = ctk.CTkEntry(ga_grid, width=100)
        self.soga_cross.insert(0, "0.50")
        self.soga_cross.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(ga_grid, text="Mutation Prob:").grid(row=1, column=2, sticky="e", padx=(20, 5), pady=5)
        self.soga_mut = ctk.CTkEntry(ga_grid, width=100)
        self.soga_mut.insert(0, "0.50")
        self.soga_mut.grid(row=1, column=3, padx=5, pady=5)

        ctk.CTkLabel(ga_grid, text="Mutation Step (\u03BC):").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.soga_mu = ctk.CTkEntry(ga_grid, width=100)
        self.soga_mu.insert(0, "0.08") # Adjust this default value to whatever fits your SOGA logic
        self.soga_mu.grid(row=2, column=1, padx=5, pady=5)

        # SOGA Specifics
        ctk.CTkLabel(soga_frame, text="Target Objective:", font=ctk.CTkFont(weight="bold")).pack(pady=(10, 5), anchor="w", padx=15)

        # Link this directly to the shared obj1_var
        self.soga_target = ctk.CTkOptionMenu(
            soga_frame,
            values=list(OBJ_MAPPING.keys()),
            variable=self.obj1_var
        )
        self.soga_target.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(soga_frame, text="Stall Tolerance (Generations before early stop):").pack(pady=(10, 0), anchor="w", padx=15)
        self.soga_stall = ctk.CTkEntry(soga_frame, placeholder_text="e.g., 50")
        self.soga_stall.insert(0, "50")
        self.soga_stall.pack(fill="x", padx=15, pady=(5, 15))

        self.btn_run_soga = ctk.CTkButton(self.tab_soga, text="Run SOGA Optimization", height=40, font=ctk.CTkFont(weight="bold"),
                                            command=self.run_soga_pipeline, fg_color="#2c824c", hover_color="#1d5c34")
        self.btn_run_soga.base_text = self.btn_run_soga.cget("text")
        self.btn_run_soga.pack(pady=10, fill="x", padx=10, side="bottom")

        self._add_compile_button(self.tab_soga, "soga", "Compile SOGA")

        # --- NEW: SOGA Visualizer Buttons ---
        viz_frame_soga = ctk.CTkFrame(self.tab_soga, fg_color="transparent")
        viz_frame_soga.pack(fill="x", padx=10, pady=(0, 10), side="bottom")

        # Row 1: Static Plots
        plot_row = ctk.CTkFrame(viz_frame_soga, fg_color="transparent")
        plot_row.pack(fill="x", pady=(0, 5))

        self.btn_soga_plot = ctk.CTkButton(plot_row, text="Plot Convergence History", state="normal", command=self.plot_soga_convergence)
        self.btn_soga_plot.pack(side="left", padx=(0, 10), expand=True, fill="x")

        # --- NEW: Z-Scale Entry ---
        ctk.CTkLabel(plot_row, text="Z-Scale:").pack(side="left", padx=(5, 2))
        self.soga_z_scale = ctk.CTkEntry(plot_row, width=45)
        self.soga_z_scale.insert(0, "5.0")
        self.soga_z_scale.pack(side="left", padx=(0, 5))

        self.btn_soga_3d = ctk.CTkButton(plot_row, text="View Best 3D Layout", state="normal", command=self.plot_soga_3d)
        self.btn_soga_3d.pack(side="left", expand=True, fill="x")

        # Row 2: Animation & Dynamic Height Selection
        anim_row = ctk.CTkFrame(viz_frame_soga, fg_color="transparent")
        anim_row.pack(fill="x", pady=5)

        ctk.CTkLabel(anim_row, text="Height:").pack(side="left", padx=(0, 2))
        self.soga_anim_height_dropdown = ctk.CTkOptionMenu(anim_row, values=["Run optimization first"], state="disabled", width=90)
        self.soga_anim_height_dropdown.pack(side="left", padx=(0, 10))

        # --- NEW: Frame Step Entry ---
        ctk.CTkLabel(anim_row, text="Step:").pack(side="left", padx=(0, 2))
        self.soga_anim_step = ctk.CTkEntry(anim_row, width=40)
        self.soga_anim_step.insert(0, "1")
        self.soga_anim_step.pack(side="left", padx=(0, 10))

        # --- NEW: FPS Entry ---
        ctk.CTkLabel(anim_row, text="FPS:").pack(side="left", padx=(0, 2))
        self.soga_anim_fps = ctk.CTkEntry(anim_row, width=40)
        self.soga_anim_fps.insert(0, "10")
        self.soga_anim_fps.pack(side="left", padx=(0, 10))

        self.btn_soga_anim = ctk.CTkButton(anim_row, text="Generate MP4 Flow", state="normal", command=self.generate_soga_animation)
        self.btn_soga_anim.pack(side="left", expand=True, fill="x")

    def build_moga_tab(self):
        """Constructs the Multi-Objective (NSGA-II) inputs."""

        ga_frame = ctk.CTkFrame(self.tab_moga, corner_radius=10)
        ga_frame.pack(fill="x", padx=10, pady=(10, 10))

        ctk.CTkLabel(ga_frame, text="NSGA-II Hyperparameters", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))

        ga_grid = ctk.CTkFrame(ga_frame, fg_color="transparent")
        ga_grid.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(ga_grid, text="Max Generations:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.moga_gen = ctk.CTkEntry(ga_grid, width=100)
        self.moga_gen.insert(0, "200")
        self.moga_gen.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(ga_grid, text="Population Size:").grid(row=0, column=2, sticky="e", padx=(20, 5), pady=5)
        self.moga_pop = ctk.CTkEntry(ga_grid, width=100)
        self.moga_pop.insert(0, "100")
        self.moga_pop.grid(row=0, column=3, padx=5, pady=5)

        ctk.CTkLabel(ga_grid, text="Crossover Prob:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.moga_cross = ctk.CTkEntry(ga_grid, width=100)
        self.moga_cross.insert(0, "0.50")
        self.moga_cross.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(ga_grid, text="Mutation Prob:").grid(row=1, column=2, sticky="e", padx=(20, 5), pady=5)
        self.moga_mut = ctk.CTkEntry(ga_grid, width=100)
        self.moga_mut.insert(0, "0.50")
        self.moga_mut.grid(row=1, column=3, padx=5, pady=5)

        ctk.CTkLabel(ga_grid, text="Mutation Step (\u03BC):").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.moga_mu = ctk.CTkEntry(ga_grid, width=100)
        self.moga_mu.insert(0, "0.08")
        self.moga_mu.grid(row=2, column=1, padx=5, pady=5)

        # MOGA Objectives
        obj_frame = ctk.CTkFrame(self.tab_moga, fg_color="transparent")
        obj_frame.pack(fill="x", padx=10, pady=(5, 10))

        ctk.CTkLabel(obj_frame, text="Objective 1:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.dropdown_obj1 = ctk.CTkOptionMenu(
            obj_frame, values=list(OBJ_MAPPING.keys()), variable=self.obj1_var,
            command=lambda choice: self.enforce_unique_objectives(3)
        )
        self.dropdown_obj1.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(obj_frame, text="Objective 2:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.dropdown_obj2 = ctk.CTkOptionMenu(
            obj_frame, values=list(OBJ_MAPPING.keys()), variable=self.obj2_var,
            command=lambda choice: self.enforce_unique_objectives(4)
        )
        self.dropdown_obj2.grid(row=0, column=3, padx=5, pady=5)

        self.btn_run_moga = ctk.CTkButton(self.tab_moga, text="Run NSGA-II Optimization", height=40, font=ctk.CTkFont(weight="bold"),
                                           command=self.run_moga_pipeline, fg_color="#2c824c", hover_color="#1d5c34")
        self.btn_run_moga.base_text = self.btn_run_moga.cget("text")
        self.btn_run_moga.pack(pady=10, fill="x", padx=10, side="bottom")

        self._add_compile_button(self.tab_moga, "moga", "Compile NSGA-II")

        # --- MOGA Visualizer Buttons ---
        viz_frame_moga = ctk.CTkFrame(self.tab_moga, fg_color="transparent")
        viz_frame_moga.pack(fill="x", padx=10, pady=(0, 10), side="bottom")


        # Row 1: Static Plots
        plot_row = ctk.CTkFrame(viz_frame_moga, fg_color="transparent")
        plot_row.pack(fill="x", pady=(0, 5))

        self.btn_moga_pareto = ctk.CTkButton(plot_row, text="Plot Pareto Front", state="normal", command=self.plot_moga_pareto)
        self.btn_moga_pareto.pack(side="left", padx=(0, 10), expand=True, fill="x")

        # --- NEW: Z-Scale Entry ---
        ctk.CTkLabel(plot_row, text="Z-Scale:").pack(side="left", padx=(5, 2))
        self.moga_z_scale = ctk.CTkEntry(plot_row, width=45)
        self.moga_z_scale.insert(0, "5.0")
        self.moga_z_scale.pack(side="left", padx=(0, 5))

        self.btn_moga_3d = ctk.CTkButton(plot_row, text="View Extreme 3D Layouts", state="normal", command=self.plot_moga_3d)
        self.btn_moga_3d.pack(side="left", expand=True, fill="x")

        # Row 2: Animation Settings & Button (All on one line)
        anim_row = ctk.CTkFrame(viz_frame_moga, fg_color="transparent")
        anim_row.pack(fill="x", pady=5)

        ctk.CTkLabel(anim_row, text="Height:").pack(side="left", padx=(0, 2))
        self.anim_height_dropdown = ctk.CTkOptionMenu(anim_row, values=["Run optimization first"], state="normal", width=110, dynamic_resizing=False)
        self.anim_height_dropdown.pack(side="left", padx=(0, 5))

        ctk.CTkLabel(anim_row, text="Layout:").pack(side="left", padx=(0, 2))
        self.moga_anim_layout = ctk.CTkOptionMenu(anim_row, values=["Best Obj 1", "Best Obj 2"], width=100)
        self.moga_anim_layout.pack(side="left", padx=(0, 5))

        ctk.CTkLabel(anim_row, text="Step:").pack(side="left", padx=(0, 2))
        self.moga_anim_step = ctk.CTkEntry(anim_row, width=40)
        self.moga_anim_step.insert(0, "1")
        self.moga_anim_step.pack(side="left", padx=(0, 5))

        ctk.CTkLabel(anim_row, text="FPS:").pack(side="left", padx=(0, 2))
        self.moga_anim_fps = ctk.CTkEntry(anim_row, width=40)
        self.moga_anim_fps.insert(0, "10")
        self.moga_anim_fps.pack(side="left", padx=(0, 10))

        self.btn_moga_anim = ctk.CTkButton(anim_row, text="Generate MP4 Flow", state="normal", command=self.generate_moga_animation)
        self.btn_moga_anim.pack(side="left", expand=True, fill="x")

    def build_simulator_tab(self):
        """Constructs the time-series re-simulation inputs."""
        self.sim_config = ctk.StringVar(value="./inputs/config.inp")
        self.sim_csv = ctk.StringVar(value="./outputs/final_pareto_front.csv")

        sim_frame = ctk.CTkFrame(self.tab_sim, corner_radius=10)
        sim_frame.pack(fill="x", padx=10, pady=(10, 20))

        ctk.CTkLabel(sim_frame, text="Time-Series Simulator", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))
        ctk.CTkLabel(sim_frame, text="Re-simulates optimizer layouts on filtered_wind.txt. Results go to the output folder set in the config file.",
                     text_color="gray", font=ctk.CTkFont(size=11, slant="italic"), wraplength=480, justify="left").pack(anchor="w", padx=15, pady=(0, 10))

        # Config source: an existing config.inp, or parameters typed in below
        self.sim_config_source = ctk.StringVar(value="Config File")
        ctk.CTkSegmentedButton(sim_frame, values=["Config File", "Manual Parameters"], variable=self.sim_config_source,
                               command=self.toggle_sim_config_source).pack(anchor="w", padx=15, pady=(0, 10))

        def add_path_row(grid, row, label_text, string_var, filetypes=None, is_dir=False):
            ctk.CTkLabel(grid, text=label_text).grid(row=row, column=0, sticky="e", padx=5, pady=5)
            ctk.CTkEntry(grid, textvariable=string_var, width=350).grid(row=row, column=1, padx=5, pady=5, sticky="w")
            ctk.CTkButton(grid, text="Folder" if is_dir else "Browse", width=80, fg_color="#4a4a4a", hover_color="#333333",
                          command=lambda: self.select_path(string_var, f"Select {label_text}", is_dir, filetypes)).grid(row=row, column=2, padx=5, pady=5)

        # Config-file mode
        self.sim_file_grid = ctk.CTkFrame(sim_frame, fg_color="transparent")
        self.sim_file_grid.pack(fill="x", padx=15, pady=5)
        add_path_row(self.sim_file_grid, 0, "Config File:", self.sim_config, [("Config", "*.inp"), ("All Files", "*.*")])

        # Manual mode: only the fields the simulator reads (see CONFIG_FIELDS)
        self.sim_manual_grid = ctk.CTkFrame(sim_frame, fg_color="transparent")
        self.sim_turb = ctk.StringVar(value="./inputs/turbine_spec.txt")
        self.sim_mesh = ctk.StringVar(value="./inputs/windfarm_rocol.txt")
        self.sim_wind1 = ctk.StringVar(value="./inputs/filtered_wind.txt")
        self.sim_bathy = ctk.StringVar(value="./inputs/farm_bathymetry.dat")
        self.sim_dist = ctk.StringVar(value="./inputs/site_distances.txt")
        self.sim_out = ctk.StringVar(value="./outputs/")
        add_path_row(self.sim_manual_grid, 0, "Turbine Master:", self.sim_turb, [("Text/CSV", "*.txt *.csv *.dat")])
        add_path_row(self.sim_manual_grid, 1, "Mesh Coordinates:", self.sim_mesh, [("Text", "*.txt")])
        add_path_row(self.sim_manual_grid, 2, "Wind Time-Series:", self.sim_wind1, [("Text", "*.txt")])
        add_path_row(self.sim_manual_grid, 3, "Bathymetry Data:", self.sim_bathy, [("Data", "*.dat")])
        add_path_row(self.sim_manual_grid, 4, "Site Distances:", self.sim_dist, [("Text", "*.txt")])
        add_path_row(self.sim_manual_grid, 5, "Output Directory:", self.sim_out, is_dir=True)
        ctk.CTkLabel(self.sim_manual_grid, text="Workability:").grid(row=6, column=0, sticky="e", padx=5, pady=5)
        self.sim_work = ctk.CTkEntry(self.sim_manual_grid, width=100)
        self.sim_work.insert(0, "0.7")
        self.sim_work.grid(row=6, column=1, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(self.sim_manual_grid, text="Written to ./inputs/simulation_config.inp; ./inputs/config.inp is not changed.",
                     text_color="gray", font=ctk.CTkFont(size=11, slant="italic")).grid(row=7, column=0, columnspan=3, sticky="w", padx=5, pady=(0, 5))

        # Shared by both modes
        sim_grid = ctk.CTkFrame(sim_frame, fg_color="transparent")
        sim_grid.pack(fill="x", padx=15, pady=5)
        self.sim_shared_grid = sim_grid
        add_path_row(sim_grid, 0, "Solutions CSV:", self.sim_csv, [("CSV", "*.csv"), ("All Files", "*.*")])

        ctk.CTkLabel(sim_grid, text="Rows:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.sim_rows = ctk.CTkEntry(sim_grid, width=350, placeholder_text="all  or  1,4,7")
        self.sim_rows.insert(0, "all")
        self.sim_rows.grid(row=1, column=1, padx=5, pady=(5, 15), sticky="w")

        self.btn_run_sim = ctk.CTkButton(self.tab_sim, text="Run Simulation", height=40, font=ctk.CTkFont(weight="bold"),
                                         command=self.run_simulator_pipeline, fg_color="#2c824c", hover_color="#1d5c34")
        self.btn_run_sim.base_text = self.btn_run_sim.cget("text")
        self.btn_run_sim.pack(pady=10, fill="x", padx=10, side="bottom")

        self._add_compile_button(self.tab_sim, "simulator", "Compile Simulator")

    def toggle_sim_config_source(self, choice):
        """Swaps the config-file row for the manual parameter fields."""
        if choice == "Manual Parameters":
            self.sim_file_grid.pack_forget()
            self.sim_manual_grid.pack(fill="x", padx=15, pady=5, before=self.sim_shared_grid)
        else:
            self.sim_manual_grid.pack_forget()
            self.sim_file_grid.pack(fill="x", padx=15, pady=5, before=self.sim_shared_grid)

    def build_farm_setup_tab(self):
        """Constructs the shared physical constraints and turbine selection."""

        self.scroll_farm = ctk.CTkScrollableFrame(self.tab_farm, fg_color="transparent")
        self.scroll_farm.pack(fill="both", expand=True)

        # 1. Global I/O Paths
        io_frame = ctk.CTkFrame(self.scroll_farm, corner_radius=10)
        io_frame.pack(fill="x", padx=10, pady=(10, 20))

        ctk.CTkLabel(io_frame, text="1. Target Simulation Files & Output Directory", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))
        ctk.CTkLabel(io_frame, text="Defaults point to the ./inputs/ and ./outputs/ folders. Change these if bypassing preprocessing.", text_color="gray", font=ctk.CTkFont(size=11, slant="italic")).pack(anchor="w", padx=15, pady=(0, 10))

        io_grid = ctk.CTkFrame(io_frame, fg_color="transparent")
        io_grid.pack(fill="x", padx=15, pady=5)

        # Helper UI Builder
        def add_path_row(row, label_text, string_var, btn_text, is_dir=False, filetypes=[("All Files", "*.*")]):
            ctk.CTkLabel(io_grid, text=label_text).grid(row=row, column=0, sticky="e", padx=5, pady=5)
            entry = ctk.CTkEntry(io_grid, textvariable=string_var, width=350)
            entry.grid(row=row, column=1, padx=5, pady=5, sticky="w")
            ctk.CTkButton(io_grid, text=btn_text, width=80, fg_color="#4a4a4a", hover_color="#333333",
                          command=lambda: self.select_path(string_var, f"Select {label_text}", is_dir, filetypes)).grid(row=row, column=2, padx=5, pady=5)

        add_path_row(0, "Turbine Master:", self.path_turb, "Browse", filetypes=[("Text/CSV", "*.txt *.csv *.dat")])
        add_path_row(1, "Mesh Coordinates:", self.path_mesh, "Browse", filetypes=[("Text", "*.txt")])
        add_path_row(2, "Wind Time-Series:", self.path_wind1, "Browse", filetypes=[("Text", "*.txt")])
        add_path_row(3, "Wind Rose Data:", self.path_wind2, "Browse", filetypes=[("Text", "*.dat")])
        add_path_row(4, "Bathymetry Data:", self.path_bathy, "Browse", filetypes=[("Data", "*.dat")])
        add_path_row(5, "Site Distances:", self.path_dist, "Browse", filetypes=[("Text", "*.txt")])
        add_path_row(6, "Output Directory:", self.path_out, "Folder", is_dir=True)
        # 2. Farm Constraints (Shared)
        const_frame = ctk.CTkFrame(self.scroll_farm, corner_radius=10)
        const_frame.pack(fill="x", padx=10, pady=0)

        ctk.CTkLabel(const_frame, text="2. Farm Design Constraints", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))

        const_grid = ctk.CTkFrame(const_frame, fg_color="transparent")
        const_grid.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(const_grid, text="Min Turbines:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.farm_min_turb = ctk.CTkEntry(const_grid, width=100)
        self.farm_min_turb.insert(0, "10")
        self.farm_min_turb.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(const_grid, text="Max Turbines:").grid(row=0, column=2, sticky="e", padx=(20, 5), pady=5)
        self.farm_max_turb = ctk.CTkEntry(const_grid, width=100)
        self.farm_max_turb.insert(0, "50")
        self.farm_max_turb.grid(row=0, column=3, padx=5, pady=5)

        ctk.CTkLabel(const_grid, text="Workability:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.farm_work = ctk.CTkEntry(const_grid, width=100)
        self.farm_work.insert(0, "0.65")
        self.farm_work.grid(row=1, column=1, padx=5, pady=5)

        # 3. Soft Objective Constraints
        soft_frame = ctk.CTkFrame(self.scroll_farm, corner_radius=10)
        soft_frame.pack(fill="x", padx=10, pady=(10, 10))

        ctk.CTkLabel(soft_frame, text="3. Soft Objective Constraints", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))
        soft_grid = ctk.CTkFrame(soft_frame, fg_color="transparent")
        soft_grid.pack(fill="x", padx=15, pady=5)

        # Enable checkbox
        self.chk_soft_enable = ctk.CTkCheckBox(soft_grid, text="Enable Soft Constraints", variable=self.use_soft_constraints_var)
        self.chk_soft_enable.grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=5)

        ctk.CTkLabel(soft_grid, text="Minimum AEP:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.soft_aep_min = ctk.CTkEntry(soft_grid, width=150)
        self.soft_aep_min.insert(0, "0.0")
        self.soft_aep_min.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(soft_grid, text="Maximum CAPEX:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.soft_capex_max = ctk.CTkEntry(soft_grid, width=150)
        self.soft_capex_max.insert(0, "0.0")
        self.soft_capex_max.grid(row=2, column=1, padx=5, pady=5)

        ctk.CTkLabel(soft_grid, text="AEP Penalty Weight:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        self.soft_aep_weight = ctk.CTkEntry(soft_grid, width=150)
        self.soft_aep_weight.insert(0, "10.0")
        self.soft_aep_weight.grid(row=3, column=1, padx=5, pady=5)

        ctk.CTkLabel(soft_grid, text="CAPEX Penalty Weight:").grid(row=4, column=0, sticky="e", padx=5, pady=5)
        self.soft_capex_weight = ctk.CTkEntry(soft_grid, width=150)
        self.soft_capex_weight.insert(0, "10.0")
        self.soft_capex_weight.grid(row=4, column=1, padx=5, pady=5)

        ctk.CTkLabel(soft_grid, text="Penalty Power:").grid(row=5, column=0, sticky="e", padx=5, pady=5)
        self.soft_penalty_power = ctk.CTkEntry(soft_grid, width=150)
        self.soft_penalty_power.insert(0, "2.0")
        self.soft_penalty_power.grid(row=5, column=1, padx=5, pady=5)

        ctk.CTkLabel(soft_frame, text="""Note: Threshold value 0 disables that specific soft constraint.
        Enter values using the same units as the raw AEP and CAPEX outputs.""", text_color="gray", font=ctk.CTkFont(size=11, slant="italic")).pack(anchor="w", padx=15, pady=(5,10))

    # ---------------------------------------------------------
    # UTILITY FUNCTIONS
    # ---------------------------------------------------------
    def log(self, message):
        """Safely prints to the live console from any thread."""
        self.console.configure(state="normal")
        self.console.insert("end", message + "\n")
        self.console.see("end")  # Auto-scroll
        self.console.configure(state="disabled")

    def build_pre_processing_tab(self):
        """Constructs the Mesh, Bathymetry, and Upgraded Wind Data preparation tools."""

        self.scroll_pre = ctk.CTkScrollableFrame(self.tab_pre, fg_color="transparent")
        self.scroll_pre.pack(fill="both", expand=True)

        # ==========================================
        # 1. MESH GENERATION FRAME
        # ==========================================
        mesh_frame = ctk.CTkFrame(self.scroll_pre, corner_radius=10)
        mesh_frame.pack(fill="x", padx=10, pady=(10, 20))

        ctk.CTkLabel(mesh_frame, text="1. Spatial Mesh Generation",
                        font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))

        # Grid Resolution Inputs (dx, dy)
        res_frame = ctk.CTkFrame(mesh_frame, fg_color="transparent")
        res_frame.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(res_frame, text="Grid X (dx):").pack(side="left", padx=(0, 5))
        self.entry_dx = ctk.CTkEntry(res_frame, width=80)
        self.entry_dx.insert(0, "500.0")
        self.entry_dx.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(res_frame, text="Grid Y (dy):").pack(side="left", padx=(0, 5))
        self.entry_dy = ctk.CTkEntry(res_frame, width=80)
        self.entry_dy.insert(0, "500.0")
        self.entry_dy.pack(side="left")

        # KML File Selection
        self.kml_files_list = []
        self.lbl_kml_status = ctk.CTkLabel(mesh_frame, text="No KML boundaries selected.",
                                            text_color="gray")
        self.lbl_kml_status.pack(anchor="w", padx=15, pady=(5, 0))

        btn_row_1 = ctk.CTkFrame(mesh_frame, fg_color="transparent")
        btn_row_1.pack(fill="x", padx=15, pady=(5, 15))

        ctk.CTkButton(btn_row_1, text="Select KML Files", width=120, fg_color="#4a4a4a", hover_color="#333333",
                      command=self.select_kmls).pack(side="left", padx=(0, 10))
        self.btn_run_mesh = ctk.CTkButton(btn_row_1, text="Generate Mesh (Polygon3)", command=self.run_mesh_pipeline)
        self.btn_run_mesh.pack(side="left")

        # ==========================================
        # 2. BATHYMETRY FRAME
        # ==========================================
        bathy_frame = ctk.CTkFrame(self.scroll_pre, corner_radius=10)
        bathy_frame.pack(fill="x", padx=10, pady=(0, 20))

        ctk.CTkLabel(bathy_frame, text="2. Bathymetry Extraction",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))

        self.gebco_file = None
        self.lbl_bathy_status = ctk.CTkLabel(bathy_frame, text="No GEBCO .asc file selected.", text_color="gray")
        self.lbl_bathy_status.pack(anchor="w", padx=15, pady=(5, 0))

        btn_row_2 = ctk.CTkFrame(bathy_frame, fg_color="transparent")
        btn_row_2.pack(fill="x", padx=15, pady=(5, 15))

        ctk.CTkButton(btn_row_2, text="Select GEBCO (.asc)", width=120, fg_color="#4a4a4a",
                      hover_color="#333333", command=self.select_gebco).pack(side="left", padx=(0, 10))
        self.btn_run_bathy = ctk.CTkButton(btn_row_2, text="Extract Depths", command=self.run_bathy_pipeline)
        self.btn_run_bathy.pack(side="left")

        # ==========================================
        # 3. WIND DATA & RESOURCE ANALYTICS FRAME
        # ==========================================
        wind_frame = ctk.CTkFrame(self.scroll_pre, corner_radius=10)
        wind_frame.pack(fill="x", padx=10, pady=(0, 20))

        ctk.CTkLabel(wind_frame, text="3. Wind Resource Assessment",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))

        self.era5_dir = None
        self.lbl_wind_status = ctk.CTkLabel(wind_frame, text="No ERA5 directory selected.", text_color="gray")
        self.lbl_wind_status.pack(anchor="w", padx=15, pady=(0, 5))

        # --- A. MODE SELECTION ---
        # DESIGN: We use a segmented button for a modern, clean toggle aesthetic.
        # Colors: selected_color sets the active state background, unselected_color is the idle background.
        mode_frame = ctk.CTkFrame(wind_frame, fg_color="transparent")
        mode_frame.pack(fill="x", padx=15, pady=(5, 10))

        ctk.CTkLabel(mode_frame, text="Calculation Mode:").pack(side="left", padx=(0, 10))
        self.seg_wind_mode = ctk.CTkSegmentedButton(
            mode_frame,
            values=["Time-Series", "Wind Rose Binning"],
            variable=self.wind_calc_mode,
            command=self.toggle_wind_mode,
            selected_color="#2c824c", # Distinctive green for active
            selected_hover_color="#1d5c34"
        )
        self.seg_wind_mode.pack(side="left")

        # --- B. TIME WINDOW FILTERS (Shared) ---
        tip_text = "Tip: Hours are 0 to 23. Wrap-around is supported (e.g., Start 22, End 4)."
        ctk.CTkLabel(wind_frame, text=tip_text, text_color="gray",
                     font=ctk.CTkFont(size=11, slant="italic")).pack(anchor="w", padx=15, pady=(0, 5))

        # --- Time Window Filters Grid ---
        filter_frame = ctk.CTkFrame(wind_frame, fg_color="transparent")
        filter_frame.pack(fill="x", padx=15, pady=5)

        # Headers
        ctk.CTkLabel(filter_frame, text="Start", font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, padx=5)
        ctk.CTkLabel(filter_frame, text="End", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, padx=5)

        # Hour Row
        ctk.CTkLabel(filter_frame, text="Hour:").grid(row=1, column=0, sticky="e", padx=5, pady=2)
        self.ent_h_start = ctk.CTkEntry(filter_frame, width=60, placeholder_text="All")
        self.ent_h_start.grid(row=1, column=1, padx=5, pady=2)
        self.ent_h_end = ctk.CTkEntry(filter_frame, width=60, placeholder_text="All")
        self.ent_h_end.grid(row=1, column=2, padx=5, pady=2)

        # Day Row
        ctk.CTkLabel(filter_frame, text="Day:").grid(row=2, column=0, sticky="e", padx=5, pady=2)
        self.ent_d_start = ctk.CTkEntry(filter_frame, width=60, placeholder_text="All")
        self.ent_d_start.grid(row=2, column=1, padx=5, pady=2)
        self.ent_d_end = ctk.CTkEntry(filter_frame, width=60, placeholder_text="All")
        self.ent_d_end.grid(row=2, column=2, padx=5, pady=2)

        # Month Row
        ctk.CTkLabel(filter_frame, text="Month:").grid(row=3, column=0, sticky="e", padx=5, pady=2)
        self.ent_m_start = ctk.CTkEntry(filter_frame, width=60, placeholder_text="All")
        self.ent_m_start.grid(row=3, column=1, padx=5, pady=2)
        self.ent_m_end = ctk.CTkEntry(filter_frame, width=60, placeholder_text="All")
        self.ent_m_end.grid(row=3, column=2, padx=5, pady=2)

        # Year Row
        ctk.CTkLabel(filter_frame, text="Year:").grid(row=4, column=0, sticky="e", padx=5, pady=2)
        self.ent_y_start = ctk.CTkEntry(filter_frame, width=60, placeholder_text="All")
        self.ent_y_start.grid(row=4, column=1, padx=5, pady=2)
        self.ent_y_end = ctk.CTkEntry(filter_frame, width=60, placeholder_text="All")
        self.ent_y_end.grid(row=4, column=2, padx=5, pady=2)

        # --- C. WIND ROSE BINNING CONFIGURATION ---
        # DESIGN: Frame for binning inputs. Padded slightly on top to separate from time windows.
        self.bin_frame = ctk.CTkFrame(wind_frame, fg_color="transparent")
        self.bin_frame.pack(fill="x", padx=15, pady=(10, 5))

        # DESIGN: Fonts for labels can be customized using font=ctk.CTkFont(...)
        ctk.CTkLabel(self.bin_frame, text="Directional Sectors (N):").pack(side="left", padx=(0, 5))
        self.ent_dir_bins = ctk.CTkEntry(self.bin_frame, width=60)
        self.ent_dir_bins.insert(0, "12") # Default to 30-degree sectors
        self.ent_dir_bins.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(self.bin_frame, text="Velocity Step (m/s):").pack(side="left", padx=(0, 5))
        self.ent_vel_step = ctk.CTkEntry(self.bin_frame, width=60)
        self.ent_vel_step.insert(0, "1.0") # Default to 1 m/s intervals
        self.ent_vel_step.pack(side="left")

        # Set initial UI state based on default toggle (Time-Series)
        self.toggle_wind_mode(self.wind_calc_mode.get())

        # --- D. ACTION & VISUALIZATION BUTTONS ---
        btn_row_3 = ctk.CTkFrame(wind_frame, fg_color="transparent")
        btn_row_3.pack(fill="x", padx=15, pady=(10, 5))

        # DESIGN: Main processing buttons. Primary action gets standard theme color, secondary gets gray (#4a4a4a).
        ctk.CTkButton(btn_row_3, text="Select ERA5 Directory", width=150, fg_color="#4a4a4a", hover_color="#333333", command=self.select_era5).pack(side="left", padx=(0, 10))
        self.btn_run_wind = ctk.CTkButton(btn_row_3, text="Process Wind Data", command=self.run_wind_pipeline)
        self.btn_run_wind.pack(side="left")

        # DESIGN: Analytics buttons. Grouped in a separate frame below the main execution row.
        # Container frame grouping the visual resource assessment triggers
        viz_btn_row = ctk.CTkFrame(wind_frame, fg_color="transparent")
        viz_btn_row.pack(fill="x", padx=15, pady=(5, 15))

        # Button 1: Directional Polar Distribution (Wind Rose)
        # CONFIGURATION HINT: Adjust 'fg_color' (hex string) and text padding here
        self.btn_plot_rose = ctk.CTkButton(
            viz_btn_row,
            text=" Plot Wind Rose",
            fg_color="#3a5a80",        # Base widget fill tone
            hover_color="#2b4360",     # Dynamic cursor interaction color
            command=self.plot_wind_rose
        )
        # expand=True ensures both elements scale identically across horizontal space
        self.btn_plot_rose.pack(side="left", expand=True, fill="x", padx=(0, 5))

        # Button 2: Integrated Velocity Analytics (Histogram + Weibull Fit Overlay)
        # CONFIGURATION HINT: Modify text parameters to customize font style or context scaling
        self.btn_plot_speed = ctk.CTkButton(
            viz_btn_row,
            text=" Plot Weilbull Fit",
            fg_color="#3a806c",        # Base widget fill tone matching the analytics theme
            hover_color="#2b6051",     # Dynamic cursor interaction color
            command=self.plot_wind_speed_diagnostics
        )
        self.btn_plot_speed.pack(side="left", expand=True, fill="x", padx=(5, 0))

        # ==========================================
        # 4. DISTANCE CALCULATOR FRAME
        # ==========================================
        dist_frame = ctk.CTkFrame(self.scroll_pre, corner_radius=10)
        dist_frame.pack(fill="x", padx=10, pady=(0, 20))

        ctk.CTkLabel(dist_frame, text="4. Logistics & Site Distances",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))

        self.shoreline_kml = None
        self.grid_kml = None
        self.port_kml = None

        # Grid system for the 3 distance files to keep it compact
        dist_grid = ctk.CTkFrame(dist_frame, fg_color="transparent")
        dist_grid.pack(fill="x", padx=15, pady=5)

        # Row 1: Shoreline
        ctk.CTkButton(dist_grid, text="Shoreline KML", width=120,
                      fg_color="#4a4a4a", hover_color="#333333",
                      command=self.select_shoreline).grid(row=0, column=0, pady=2, sticky="w")
        self.lbl_shore_status = ctk.CTkLabel(dist_grid, text="Pending...", text_color="gray")
        self.lbl_shore_status.grid(row=0, column=1, padx=10, sticky="w")

        # Row 2: Grid Connection
        ctk.CTkButton(dist_grid, text="Grid Conn. KML", width=120,
                      fg_color="#4a4a4a", hover_color="#333333",
                      command=self.select_grid).grid(row=1, column=0, pady=2, sticky="w")
        self.lbl_grid_status = ctk.CTkLabel(dist_grid, text="Pending...", text_color="gray")
        self.lbl_grid_status.grid(row=1, column=1, padx=10, sticky="w")

        # Row 3: Port
        ctk.CTkButton(dist_grid, text="Port KML", width=120,
                      fg_color="#4a4a4a", hover_color="#333333",
                      command=self.select_port).grid(row=2, column=0, pady=2, sticky="w")
        self.lbl_port_status = ctk.CTkLabel(dist_grid, text="Pending...", text_color="gray")
        self.lbl_port_status.grid(row=2, column=1, padx=10, sticky="w")

        self.btn_run_dist = ctk.CTkButton(dist_frame, text="Calculate Distances",
                                          command=self.run_distances_pipeline)
        self.btn_run_dist.pack(anchor="w", padx=15, pady=(10, 15))

    # ---------------------------------------------------------
    # CALLBACKS & WORKER THREADS
    # ---------------------------------------------------------
    def toggle_wind_mode(self, current_mode):
        """Grays out or enables the binning input fields based on the selected mode."""
        if current_mode == "Time-Series":
            self.ent_dir_bins.configure(state="disabled", fg_color="#e0e0e0", text_color="gray")
            self.ent_vel_step.configure(state="disabled", fg_color="#e0e0e0", text_color="gray")
            self.log("Wind Mode switched to Time-Series. Chronological evaluation active.")
        else:
            self.ent_dir_bins.configure(state="normal", fg_color=["#F9F9FA", "#343638"],
                                        text_color=["#000000", "#FFFFFF"])
            self.ent_vel_step.configure(state="normal", fg_color=["#F9F9FA", "#343638"],
                                        text_color=["#000000", "#FFFFFF"])
            self.log("Wind Mode switched to Wind Rose Binning. Empirical probability evaluation active.")

    def abort_process(self):
        """Force-kills the currently running Fortran subprocess."""
        if self.running_process is not None and self.running_process.poll() is None:
            self.log("\nABORT SIGNAL SENT: Terminating Fortran process...")

            try:
                self.running_process.kill()  # Hard kill at the OS level
            except Exception as e:
                self.log(f"Failed to kill process: {e}")

    def select_path(self, var_name, title, is_dir=False, filetypes=None):
        if is_dir:
            path = filedialog.askdirectory(title=title)
            # Ensure output directories always end with a slash for Fortran string concatenation
            if path:
                var_name.set(path + "/" if not path.endswith("/") else path)
        else:
            path = filedialog.askopenfilename(title=title, filetypes=filetypes)
            if path:
                var_name.set(path)

    def select_kmls(self):
        files = filedialog.askopenfilenames(title="Select Boundary KMLs", filetypes=[("KML Files", "*.kml")])
        if files:
            self.kml_files_list = list(files)
            self.lbl_kml_status.configure(text=f"{len(files)} KML(s) selected.", text_color="green")
            self.log(f"Loaded {len(files)} boundary KML files.")

    def select_gebco(self):
        file_path = filedialog.askopenfilename(title="Select GEBCO Data", filetypes=[("ASCII Grid", "*.asc")])
        if file_path:
            self.gebco_file = file_path
            self.lbl_bathy_status.configure(text=os.path.basename(file_path), text_color="green")
            self.log(f"Loaded bathymetry data: {os.path.basename(file_path)}")

    def select_turbine(self):
        file_path = filedialog.askopenfilename(title="Select Turbine Data", filetypes=[("Data Files", "*.dat *.csv *.txt"), ("All Files", "*.*")])
        if file_path:
            self.turbine_file = file_path
            self.lbl_turb_status.configure(text=os.path.basename(file_path), text_color="green")
            self.log(f"Loaded Turbine Profile: {os.path.basename(file_path)}")

    def run_mesh_pipeline(self):
        if not self.kml_files_list:
            self.log("ERROR: Please select KML boundary files first.")
            return

        # Disable button to prevent double-clicks
        self.btn_run_mesh.configure(state="disabled")
        dx = float(self.entry_dx.get())
        dy = float(self.entry_dy.get())

        def worker():
            self.log("--- Starting Mesh Generation Pipeline ---")
            # --- Uncomment when integrating the backend ---
            metadata = mesh_generator.process_kmls_and_mesh(
                self.kml_files_list, dx, dy, output_callback=self.log
            )
            if metadata:
                self.mesh_metadata = metadata
            self.log("Mesh Worker finished. ")

            # Re-enable button safely
            self.after(0, lambda: self.btn_run_mesh.configure(state="normal"))

        # Run Fortran/Python intensive task in background thread
        threading.Thread(target=worker, daemon=True).start()

    def run_bathy_pipeline(self):
        if not self.gebco_file:
            self.log("ERROR: Please select a GEBCO .asc file first.")
            return

        self.btn_run_bathy.configure(state="disabled")

        def worker():
            self.log("--- Starting Bathymetry Extraction ---")
            # --- Uncomment when integrating the backend ---
            bathymetry_generator.process_bathymetry(
                self.gebco_file,
                output_callback=self.log
            )
            self.log("Bathymetry Worker finished. ")
            self.after(0, lambda: self.btn_run_bathy.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    # --- Wind Data Callbacks ---
    def select_era5(self):
        dir_path = filedialog.askdirectory(title="Select Directory Containing ERA5 .nc Files")
        if dir_path:
            self.era5_dir = dir_path

            import glob
            nc_files = glob.glob(os.path.join(dir_path, "*.nc"))

            # --- NEW: Dynamically parse years from filenames ---
            years = []
            for f in nc_files:
                filename = os.path.basename(f)     # gets "2005.nc"
                year_str = filename.replace('.nc', '') # gets "2005"
                if year_str.isdigit():
                    years.append(int(year_str))

            # Build the dynamic status message
            if years:
                min_y, max_y = min(years), max(years)
                year_info = f" | Available Years: {min_y} to {max_y}"
            else:
                year_info = " | Warning: No valid YYYY.nc files found."

            # Update the UI Label
            self.lbl_wind_status.configure(
                text=f"Folder: {os.path.basename(dir_path)} ({len(nc_files)} files){year_info}",
                text_color="green"
            )
            self.log(f"Selected ERA5 directory. {year_info}")

    def run_wind_pipeline(self):
        if not self.era5_dir:
            self.log("ERROR: Please select a directory containing ERA5 .nc files first.")
            return

        self.btn_run_wind.configure(state="disabled")

        # Harvest the filters from the GUI inputs
        # (If the user left it blank, it defaults to an empty string, which your backend handles as "All")
        filters = {
            'h_start': self.ent_h_start.get().strip(),
            'h_end': self.ent_h_end.get().strip(),
            'd_start': self.ent_d_start.get().strip(),
            'd_end': self.ent_d_end.get().strip(),
            'm_start': self.ent_m_start.get().strip(),
            'm_end': self.ent_m_end.get().strip(),
            'y_start': self.ent_y_start.get().strip(),
            'y_end': self.ent_y_end.get().strip()
        }

        def worker():
            self.log("--- Starting Wind Data Interpolation ---")

            # Pass BOTH the directory and the filters to your backend
            wind_generator.process_wind_data(
                self.era5_dir,
                filters,
                output_callback=self.log
            )

            self.log("--- Wind Pipeline Complete ---")
            self.after(0, lambda: self.btn_run_wind.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    # --- Distance Callbacks ---
    def select_shoreline(self):
        file_path = filedialog.askopenfilename(title="Select Shoreline KML", filetypes=[("KML", "*.kml")])
        if file_path:
            self.shoreline_kml = file_path
            self.lbl_shore_status.configure(text=os.path.basename(file_path), text_color="green")
            self.log("Shoreline boundary loaded.")

    def select_grid(self):
        file_path = filedialog.askopenfilename(title="Select Grid KML", filetypes=[("KML", "*.kml")])
        if file_path:
            self.grid_kml = file_path
            self.lbl_grid_status.configure(text=os.path.basename(file_path), text_color="green")
            self.log("Grid connection point loaded.")

    def select_port(self):
        file_path = filedialog.askopenfilename(title="Select Port KML", filetypes=[("KML", "*.kml")])
        if file_path:
            self.port_kml = file_path
            self.lbl_port_status.configure(text=os.path.basename(file_path), text_color="green")
            self.log("Port location loaded.")

    def run_distances_pipeline(self):
        if not any([self.shoreline_kml, self.grid_kml, self.port_kml]):
            self.log("ERROR: Please select at least one KML file for distance calculations.")
            return

        self.btn_run_dist.configure(state="disabled")

        def worker():
            self.log("--- Starting Distance Calculations ---")
            # --- Uncomment when integrating the backend ---
            distance_calculator.calculate_site_distances(
                self.shoreline_kml,
                self.grid_kml,
                self.port_kml,
                output_callback=self.log
            )
            self.log("Distance Worker finished.")
            self.after(0, lambda: self.btn_run_dist.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def run_soga_pipeline(self):
        self.btn_run_soga.configure(state="disabled")

        try:
            it_max = int(self.soga_gen.get())
            n_pop = int(self.soga_pop.get())
            p_cross = float(self.soga_cross.get())
            p_mut = float(self.soga_mut.get())
            mu = float(self.soga_mu.get())
            max_turbs = int(self.farm_max_turb.get())
            min_turbs = int(self.farm_min_turb.get())
            workability = float(self.farm_work.get())


        except ValueError:
            self.log("ERROR: Please ensure all SOGA parameters are valid numbers.")
            self.btn_run_soga.configure(state="normal")
            return

        def worker():
            self.log("--- Preparing SOGA Environment ---")
            os.makedirs('./inputs', exist_ok=True)

            # 2. Write the config.inp file using the unified method
            self.opt_mode_var.set("SOGA") # Force mode to SOGA
            try:
                # Pass the variables extracted at the top of run_soga_pipeline (include SOGA stall tolerance)
                soga_stall = int(self.soga_stall.get()) if self.soga_stall.get() else 0
                self.generate_config_file(it_max, n_pop, p_cross, p_mut, mu, max_turbs, min_turbs, workability, soga_stall)
            except Exception as e:
                self.log(f"ERROR writing config file: {e}")
                self.after(0, lambda: self.btn_run_soga.configure(state="normal"))
                return

            self.log("Launching SOGA Fortran Optimizer...")

            exe_path = fortran_exe("soga_optimizer")
            exe_name = os.path.basename(exe_path)

            if not os.path.exists(exe_path):
                self.log(f"ERROR: {exe_name} not found. Please click Compile SOGA first.")
                self.after(0, lambda: self.btn_run_soga.configure(state="normal"))
                return

            try:
                self.after(0, lambda: self.btn_abort.configure(state="normal"))
                self.running_process = subprocess.Popen(
                    [exe_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, universal_newlines=True, cwd=os.getcwd()
                )

                self.detected_height_levels = 0
                for line in self.running_process.stdout:
                    cleaned = line.strip()
                    self.log(cleaned)
                    if "unique hub height level(s)" in cleaned:
                        match = re.search(r'(\d+)\s*unique hub height', cleaned)
                        if match: self.detected_height_levels = int(match.group(1))

                self.running_process.wait()

                if self.running_process.returncode == 0:
                    self.log("SOGA Optimization Finished Successfully!")
                    self.after(0, lambda: self.btn_soga_plot.configure(state="normal"))
                    self.after(0, lambda: self.btn_soga_3d.configure(state="normal"))
                    self.after(0, lambda: self.btn_soga_anim.configure(state="normal"))

                    # Update SOGA dropdown safely
                    max_z = getattr(self, 'detected_height_levels', 0)
                    if max_z > 0:
                        valid_levels = [f"Level {i}" for i in range(1, max_z + 1)]
                        self.after(0, lambda: self.soga_anim_height_dropdown.configure(values=valid_levels, state="normal"))
                        self.after(0, lambda: self.soga_anim_height_dropdown.set(valid_levels[0]))
                else:
                    self.log(f"Process Terminated (Exit code {self.running_process.returncode})")

            except Exception as e:
                self.log(f"System Error executing Fortran: {e}")
            finally:
                self.running_process = None
                self.after(0, lambda: self.btn_abort.configure(state="disabled"))

            self.after(0, lambda: self.btn_run_soga.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    # --- SOGA Visualization Callbacks ---
    def plot_soga_convergence(self):
        target_obj = self.soga_target.get() # Grab the objective name
        out_dir = self.path_out.get()       # Grab the dynamic output path

        self.log(f"Generating SOGA Convergence Plot for {target_obj} in {out_dir}...")
        self.btn_soga_plot.configure(state="normal")

        def worker():
            # Pass BOTH the dynamic output directory and the target objective
            out_img = visualizer.save_soga_convergence_plot(output_dir=out_dir, target_obj=target_obj)
            if out_img:
                try:
                    self._open_visualization_file(out_img)
                except Exception: pass
            self.after(0, lambda: self.btn_soga_plot.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def plot_soga_3d(self):
        target_obj = self.soga_target.get()
        turb_file = self.path_turb.get() # Get the turbine data path
        try:
            z_scale = float(self.soga_z_scale.get())
        except ValueError:
            z_scale = 5.0 # Fallback default

        self.log(f"Launching SOGA 3D Viewer (Z-Scale: {z_scale}x)...")
        self.btn_soga_3d.configure(state="normal")

        def worker():
            try:
                # Pass the new parameters to visualizer
                visualizer.generate_soga_3d_layout(target_obj=target_obj, z_scale=z_scale, turb_path=turb_file)
            except Exception as e:
                self.log(f"Error in 3D viewer: {e}")
            self.after(0, lambda: self.btn_soga_3d.configure(state="normal"))
        self._start_3d_viewer(worker)

    def generate_soga_animation(self):
        selected = self.soga_anim_height_dropdown.get()
        if "Level" not in selected: return
        level_idx = int(selected.replace("Level ", ""))
        out_dir = self.path_out.get() # Dynamic output path

        try:
            user_step = int(self.soga_anim_step.get())
            user_fps = int(self.soga_anim_fps.get())
        except ValueError:
            user_step, user_fps = 1, 10 # Fallbacks

        self.log(f"Generating SOGA MP4 animation for {selected} (Step: {user_step}, FPS: {user_fps})...")
        self.btn_soga_anim.configure(state="normal")

        def worker():
            try:
                # Assuming visualizer.generate_soga_mp4_animation was updated similarly to accept these
                out_mp4 = visualizer.generate_soga_mp4_animation(
                    file_path=os.path.join(out_dir, 'animation_data_soga.csv'),
                    level_idx=level_idx,
                    frame_step=user_step,
                    fps=user_fps,
                    turb_path=self.path_turb.get()
                )
                if out_mp4:
                    self._open_visualization_file(out_mp4)
            except Exception as e:
                self.log(f"Error generating animation: {e}")
            self.after(0, lambda: self.btn_soga_anim.configure(state="normal"))
        threading.Thread(target=worker, daemon=True).start()

    def run_moga_pipeline(self):
        self.btn_run_moga.configure(state="disabled")

        # 1. Harvest inputs from the UI
        try:
            it_max = int(self.moga_gen.get())
            n_pop = int(self.moga_pop.get())
            p_cross = float(self.moga_cross.get())
            p_mut = float(self.moga_mut.get())
            mu = float(self.moga_mu.get())

            # Grabbing shared constraints from Tab 2!
            max_turbs = int(self.farm_max_turb.get())
            min_turbs = int(self.farm_min_turb.get())
            workability = float(self.farm_work.get())
        except ValueError:
            self.log("ERROR: Please ensure all MOGA parameters are valid numbers.")
            self.btn_run_moga.configure(state="normal")
            return

        def worker():
            self.log("--- Preparing NSGA-II Environment ---")
            os.makedirs('./inputs', exist_ok=True)

            # 2. Write the config.inp file using the unified method
            self.opt_mode_var.set("MOGA") # Force mode to MOGA
            try:
                # Pass the variables extracted at the top of run_moga_pipeline
                self.generate_config_file(it_max, n_pop, p_cross, p_mut, mu, max_turbs, min_turbs, workability)
            except Exception as e:
                self.log(f"ERROR writing config file: {e}")
                self.after(0, lambda: self.btn_run_moga.configure(state="normal"))
                return

            self.log("config.inp successfully updated.")
            self.log("Launching Fortran Optimizer...")

            # 3. Execute Fortran Executable and stream output LIVE
            import subprocess

            # Determine platform-specific binary name
            # Determine platform-specific binary name
            exe_path = fortran_exe("moga_optimizer")
            exe_name = os.path.basename(exe_path)

            if not os.path.exists(exe_path):
                self.log(f"ERROR: Compiled optimizer ({exe_name}) not found in /build folder.")
                self.after(0, lambda: self.btn_run_moga.configure(state="normal"))
                return

            try:
                # 1. Enable the Abort button
                self.after(0, lambda: self.btn_abort.configure(state="normal"))

                # 2. Assign the process to the class variable so abort_process() can see it
                self.running_process = subprocess.Popen(
                    [exe_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    cwd=os.getcwd()
                )

                self.detected_height_levels = 0  # Reset before running

                # 3. Stream the output and intercept metadata
                for line in self.running_process.stdout:
                    cleaned_line = line.strip()
                    self.log(cleaned_line)

                    # Intercept the height level count dynamically!
                    if "unique hub height level(s)" in cleaned_line:
                        match = re.search(r'(\d+)\s*unique hub height', cleaned_line)
                        if match:
                            self.detected_height_levels = int(match.group(1))

                self.running_process.wait()

                if self.running_process.returncode == 0:
                    self.log("NSGA-II Optimization Finished Successfully!")

                    # 1. Unlock the plot buttons
                    self.after(0, lambda: self.btn_moga_pareto.configure(state="normal"))
                    self.after(0, lambda: self.btn_moga_3d.configure(state="normal"))
                    self.after(0, lambda: self.btn_moga_anim.configure(state="normal"))

                    # 2. Dynamically find the max height level and update the dropdown
                    self.update_animation_dropdown()
                else:
                    self.log(f"Process Terminated (Exit code {self.running_process.returncode})")

            except Exception as e:
                self.log(f"System Error executing Fortran: {e}")

            finally:
                # 5. Cleanup: Disconnect the process and disable the abort button
                self.running_process = None
                self.after(0, lambda: self.btn_abort.configure(state="disabled"))

            # Re-enable the Run button when entirely finished
            self.after(0, lambda: self.btn_run_moga.configure(state="normal"))

        # Launch the worker thread
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def run_simulator_pipeline(self):
        exe_path = fortran_exe("simulator")
        config_path, csv_path = self.sim_config.get(), self.sim_csv.get()

        try:
            if self.sim_config_source.get() == "Manual Parameters":
                workability = float(self.sim_work.get())
                if workability <= 0:
                    raise ValueError("Workability must be greater than 0.")
                values = simulator_config_values(
                    turb=self.sim_turb.get(), mesh=self.sim_mesh.get(), wind1=self.sim_wind1.get(),
                    bathy=self.sim_bathy.get(), dist=self.sim_dist.get(), out_dir=self.sim_out.get(),
                    workability=workability,
                )
                for key in ("f_turb", "f_mesh", "f_wind1", "f_bathy", "f_dist"):
                    if not os.path.exists(values[key]):
                        raise ValueError(f"Input file not found: {values[key]}")
                config_path = "./inputs/simulation_config.inp"
                with open(config_path, "w") as f:
                    f.write(format_config(values))
                self.log(f"Simulation parameters written to {config_path}")
            cmd = build_simulator_command(exe_path, config_path, csv_path, self.sim_rows.get())
        except ValueError as e:
            self.log(f"ERROR: {e}")
            return
        for label, path in (("Simulator executable (compile it first)", exe_path), ("Config file", config_path), ("Solutions CSV", csv_path)):
            if not os.path.exists(path):
                self.log(f"ERROR: {label} not found: {path}")
                return

        self.btn_run_sim.configure(state="disabled")

        def worker():
            self.log("Launching Time-Series Simulator...")
            self.log(f"Executing: {' '.join(cmd)}")
            try:
                self.after(0, lambda: self.btn_abort.configure(state="normal"))
                self.running_process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, cwd=os.getcwd()
                )
                for line in self.running_process.stdout:
                    self.log(line.strip())
                self.running_process.wait()

                if self.running_process.returncode == 0:
                    self.log("Simulation Finished Successfully!")
                else:
                    self.log(f"Process Terminated (Exit code {self.running_process.returncode})")
            except Exception as e:
                self.log(f"System Error executing simulator: {e}")
            finally:
                self.running_process = None
                self.after(0, lambda: self.btn_abort.configure(state="disabled"))
                self.after(0, lambda: self.btn_run_sim.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def run_compiler(self, target):
        # Disable the button to prevent spawning multiple compile threads
        button = self.compile_buttons[target]
        button.configure(state="disabled")
        self.compiling.add(target)

        def worker():
            self.log(f"--- Starting Fortran Compilation ({target.upper()}) ---")

            # Automatically set the correct binary extension based on the OS
            out_path = fortran_exe(PROGRAMS[target])
            exe_name = os.path.basename(out_path)
            # Each target gets its own module folder, so compiles running at once don't collide
            mod_dir = os.path.join(os.path.dirname(out_path), f"mod_{target}")
            os.makedirs(mod_dir, exist_ok=True)

            # Define exact paths to the core library and the specific main script(s)
            core_path = os.path.join(".", "source", "wflop_core.f90")
            if target == "simulator":
                main_paths = [os.path.join(".", "source", "simulation.f90"), os.path.join(".", "source", "main_simulator.f90")]
            else:
                main_paths = [os.path.join(".", "source", f"main_{target}.f90")]

            # Optimized build for this machine: -march=native uses every CPU instruction set
            # available here, -flto optimizes across the core module and the driver.
            # -ffast-math is deliberately left out: it can change floating-point results.
            flags = ["-O3", "-march=native", "-funroll-loops", "-flto", "-fopenmp"]

            # Command now compiles BOTH the core module and the main program!
            # -J keeps the .mod files in build/ instead of the working directory
            cmd = ["gfortran"] + flags + ["-J", mod_dir, core_path, *main_paths, "-o", out_path]
            self.log(f"Executing: {' '.join(cmd)}")

            try:
                import subprocess
                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, universal_newlines=True, cwd=os.getcwd()
                )

                for line in process.stdout:
                    self.log(f"Compiler: {line.strip()}")

                process.wait()

                if process.returncode == 0:
                    self.log(f"Compilation Successful! Executable saved as: build/{exe_name}")
                else:
                    self.log(f"Compilation FAILED with exit code {process.returncode}")

            except FileNotFoundError:
                self.log("ERROR: 'gfortran' command not found. Ensure MinGW is in your system PATH.")
            except Exception as e:
                self.log(f"System Error during compilation: {e}")

            # Re-enable the button safely from the main thread
            self.compiling.discard(target)
            self.after(0, self.refresh_program_buttons)

        import threading
        threading.Thread(target=worker, daemon=True).start()

    # ==========================================
    # VISUALIZATION CALLBACKS
    # ==========================================

    def plot_moga_pareto(self):
        out_dir = self.path_out.get() # Grab the dynamic output path
        self.log(f"Generating Pareto Front plots in {out_dir}...")
        self.btn_moga_pareto.configure(state="normal")

        def worker():
            # Pass the dynamic output directory to the visualizer
            success = visualizer.save_pareto_plots(output_dir=out_dir)
            if success:
                self.log(f"Pareto plots saved to {out_dir}")

                # --- Auto-open BOTH images using dynamic paths ---
                img1_path = os.path.join(out_dir, "plot_final_pareto.png")
                img2_path = os.path.join(out_dir, "plot_evolution.png")

                try:
                    self._open_visualization_file(img1_path)
                    self._open_visualization_file(img2_path)
                except Exception:
                    pass

            self.after(0, lambda: self.btn_moga_pareto.configure(state="normal"))

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def plot_moga_3d(self):
        turb_file = self.path_turb.get()
        try:
            z_scale = float(self.moga_z_scale.get())
        except ValueError:
            z_scale = 5.0

        self.log(f"Launching 3D Viewer (Z-Scale: {z_scale}x)...")
        self.btn_moga_3d.configure(state="normal")

        def worker():
            try:
                visualizer.generate_3d_comparison(z_scale=z_scale, turb_path=turb_file)
            except Exception as e:
                self.log(f"Error in 3D viewer: {e}")
            self.after(0, lambda: self.btn_moga_3d.configure(state="normal"))

        self._start_3d_viewer(worker)

    def generate_moga_animation(self):
        selected_height = self.anim_height_dropdown.get()
        if "Level" not in selected_height: return
        level_idx = int(selected_height.replace("Level ", ""))
        out_dir = self.path_out.get() # Dynamic output path

        # Determine which file to read based on the dropdown
        selected_layout = self.moga_anim_layout.get()
        obj_num = "1" if "Obj 1" in selected_layout else "2"

        try:
            user_step = int(self.moga_anim_step.get())
            user_fps = int(self.moga_anim_fps.get())
        except ValueError:
            user_step, user_fps = 1, 10 # Fallbacks

        self.log(f"Generating MP4 animation for {selected_layout} at {selected_height} (Step: {user_step}, FPS: {user_fps})...")
        self.btn_moga_anim.configure(state="disabled")

        def worker():
            try:
                # Dynamically construct the file path based on objective choice
                data_path = os.path.join(out_dir, f'animation_data_obj_{obj_num}.csv')

                out_mp4 = visualizer.generate_mp4_animation(
                    file_path=data_path,
                    level_idx=level_idx,
                    fast_mode=False,
                    frame_step=user_step,
                    fps=user_fps,
                    turb_path=self.path_turb.get()
                )
                if out_mp4:
                    self.log(f"Animation saved to {out_mp4}")
                    self._open_visualization_file(out_mp4)
            except Exception as e:
                self.log(f"Error generating animation: {e}")
            self.after(0, lambda: self.btn_moga_anim.configure(state="normal"))

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def update_animation_dropdown(self):
        """Builds the dropdown based on what Fortran actually reported."""
        max_z_levels = getattr(self, 'detected_height_levels', 0)

        if max_z_levels > 0:
            valid_levels = [f"Level {i}" for i in range(1, max_z_levels + 1)]
            self.after(0, lambda: self.anim_height_dropdown.configure(values=valid_levels, state="normal"))
            self.after(0, lambda: self.anim_height_dropdown.set(valid_levels[0]))
        else:
            self.log("Could not detect height levels from Fortran output.")

    def enforce_unique_objectives(self, changed_dropdown):
        """Defers the update slightly to prevent CustomTkinter internal event clashing."""
        self.after(10, lambda: self._apply_objective_rules(changed_dropdown))

    def _apply_objective_rules(self, changed_dropdown):
        """Safely applies the mutually exclusive dropdown logic."""
        val1 = self.obj1_var.get()
        val2 = self.obj2_var.get()
        all_opts = list(OBJ_MAPPING.keys())

        # 1. Resolve collision if they somehow match
        if val1 == val2:
            if changed_dropdown == 1:
                # Find the first available option that isn't val1
                val2 = next(opt for opt in all_opts if opt != val1)
                self.obj2_var.set(val2)
            else:
                # Find the first available option that isn't val2
                val1 = next(opt for opt in all_opts if opt != val2)
                self.obj1_var.set(val1)

        # 2. Rebuild lists safely
        opts1 = [opt for opt in all_opts if opt != val2]
        opts2 = [opt for opt in all_opts if opt != val1]

        self.dropdown_obj1.configure(values=opts1)
        self.dropdown_obj2.configure(values=opts2)

    def generate_config_file(self, it_max, n_pop, p_cross, p_mut, mu, max_turbs, min_turbs, workability, soga_stall=0):
        """Writes the config.inp file before launching Fortran."""

        # Determine Opt Mode
        opt_mode_int = 1 if self.opt_mode_var.get() == "SOGA" else 2

        # Get mapped integer values
        obj1_int = OBJ_MAPPING[self.obj1_var.get()]

        # If SOGA, obj2 doesn't matter, we write 0. If MOGA, get the real value.
        obj2_int = 0 if opt_mode_int == 1 else OBJ_MAPPING[self.obj2_var.get()]
        wind_mode_int = 1 if self.wind_calc_mode.get() == "Time-Series" else 2

        # Safely parse soft-constraint inputs before writing config
        use_soft_int = 1 if self.use_soft_constraints_var.get() else 0
        try:
            aep_min_soft = float(self.soft_aep_min.get())
            capex_max_soft = float(self.soft_capex_max.get())
            w_aep_soft = float(self.soft_aep_weight.get())
            w_capex_soft = float(self.soft_capex_weight.get())
            soft_penalty_power = float(self.soft_penalty_power.get())
        except Exception as e:
            self.log(f"ERROR: Invalid soft-constraint numeric value: {e}")
            try:
                self.btn_run_soga.configure(state="normal")
            except Exception:
                pass
            try:
                self.btn_run_moga.configure(state="normal")
            except Exception:
                pass
            return

        values = {
            "it_max": it_max, "n_pop": n_pop, "p_cross": p_cross, "p_mut": p_mut, "mu": mu,
            "max_turbs": max_turbs, "min_turbs": min_turbs, "soga_stall": soga_stall,
            "workability": workability, "opt_mode": opt_mode_int, "obj_1": obj1_int,
            "obj_2": obj2_int, "wind_mode": wind_mode_int, "use_soft_constraints": use_soft_int,
            "aep_min_soft": aep_min_soft, "capex_max_soft": capex_max_soft,
            "w_aep_soft": w_aep_soft, "w_capex_soft": w_capex_soft,
            "soft_penalty_power": soft_penalty_power,
            "f_turb": self.path_turb.get(), "f_mesh": self.path_mesh.get(),
            "f_wind1": self.path_wind1.get(), "f_wind2": self.path_wind2.get(),
            "f_bathy": self.path_bathy.get(), "f_dist": self.path_dist.get(),
            "out_dir": self.path_out.get(),
        }
        with open('./inputs/config.inp', 'w') as f:
            f.write(format_config(values))

    # =====================================================================
    # WIND RESOURCE VISUALIZATION CALLBACK CONNECTIONS
    # =====================================================================
    def _start_3d_viewer(self, worker):
        """Run a PyVista viewer. macOS only allows windows on the main thread,
        so there the viewer blocks the GUI until it is closed; elsewhere it
        runs in a background thread."""
        if sys.platform == "darwin":
            self.after(0, worker)
        else:
            threading.Thread(target=worker, daemon=True).start()

    def _open_visualization_file(self, file_path):
        """Open a saved plot without requiring Matplotlib GUI support."""
        try:
            if sys.platform == "win32":
                os.startfile(os.path.normpath(file_path))
            elif sys.platform == "darwin":
                subprocess.run(["open", file_path], check=False)
            else:
                subprocess.run(["xdg-open", file_path], check=False)
        except Exception as exc:
            self.log(f"Plot saved, but could not open it automatically: {exc}")

    def plot_wind_rose(self):
        """Triggers the directional polar frequency mesh engine."""
        self.log("Extracting joint probability matrix distributions...")
        # Invokes interactive backend context parsing from visualizer_15.py
        success = visualizer.plot_wind_rose(json_path="./inputs/wind_analytics.json")
        if success:
            self.log(f"Wind rose saved to {success}")
            self._open_visualization_file(success)
        else:
            self.log("ERROR: Unable to load or parse path destination structural matrices.")

    def plot_wind_speed_diagnostics(self):
        """Triggers the unified speed diagnostics profile canvas (Histogram + Weibull)."""
        self.log("Compiling empirical frequency bars and analytical parametric curve fields...")
        # Invokes the unified graphics plot context mapping both data parameters
        success = visualizer.plot_wind_speed_diagnostics(json_path="./inputs/wind_analytics.json")
        if success:
            self.log(f"Wind speed histogram saved to {success}")
            self._open_visualization_file(success)
        else:
            self.log("ERROR: Failed to decode target distribution profile parameters.")
    # =====================================================================

    def run_wind_pipeline(self):
        if not self.era5_dir:
            self.log("ERROR: Please select a directory containing ERA5 .nc files first.")
            return
        self.btn_run_wind.configure(state="disabled")

        filters = {
            'h_start': self.ent_h_start.get().strip(),
            'h_end': self.ent_h_end.get().strip(),
            'd_start': self.ent_d_start.get().strip(),
            'd_end': self.ent_d_end.get().strip(),
            'm_start': self.ent_m_start.get().strip(),
            'm_end': self.ent_m_end.get().strip(),
            'y_start': self.ent_y_start.get().strip(),
            'y_end': self.ent_y_end.get().strip(),
            'mode': self.wind_calc_mode.get(),
            'dir_bins': self.ent_dir_bins.get() if self.wind_calc_mode.get() == "Wind Rose Binning" else None,
            'vel_step': self.ent_vel_step.get() if self.wind_calc_mode.get() == "Wind Rose Binning" else None
        }
        def worker():
            self.log(f"--- Starting Wind Data Generation ({filters['mode']}) ---")

            # Pass BOTH the directory and the extended filters to your backend
            wind_generator.process_wind_data(
                self.era5_dir,
                filters,
                output_callback=self.log
            )

            self.log("--- Wind Pipeline Complete ---")
            self.after(0, lambda: self.btn_run_wind.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()
if __name__ == "__main__":
    # Adjust UI scaling for Linux HiDPI displays
    if sys.platform.startswith("linux"):
        ctk.set_widget_scaling(1.0)  # Try 1.2, 1.25, or 1.5 depending on your monitor
        ctk.set_window_scaling(1.0)  # Scales the base window dimensions proportionally
    app = OWFLOGui()
    app.mainloop()
