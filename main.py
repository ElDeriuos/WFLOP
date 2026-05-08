import customtkinter as ctk
import tkinter.filedialog as filedialog
import threading
from source import mesh_generator
from source import bathymetry_generator
from source import wind_generator
from source import distance_calculator
from source import visualizer
import os
import sys
import shutil
import re
import subprocess

# Set the global appearance and color theme
ctk.set_appearance_mode("Light")  # Options: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("dark-blue")  # Options: "blue" (standard), "green", "dark-blue"

class OWFLOGui(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Track the active Fortran subprocess so we can kill it if needed
        self.running_process = None

        # --- Main Window Configuration ---
        self.title("OWFLO: Offshore Wind Farm Layout Optimizer")
        self.geometry("1400x800")
        
        # Configure a 1x2 Grid (1 Row, 2 Columns)
        # Column 0 (Left) = Controls (Weight 1)
        # Column 1 (Right) = Console/Visuals (Weight 2, takes up more space)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # =========================================================
        # LEFT PANEL: THE CONTROL CENTER (TABBED)
        # =========================================================
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.grid(row=0, column=0, padx=10, pady=(10, 10), sticky="nsew")

        # Create the Tabs in chronological workflow order
        self.tab_pre = self.tabview.add("Pre-Processing")
        self.tab_farm = self.tabview.add("Farm Setup")
        self.tab_soga = self.tabview.add("SOGA (Single-Obj)")
        self.tab_moga = self.tabview.add("MOGA (NSGA-II)")

        # Build the Tabs
        self.build_pre_processing_tab()
        self.build_farm_setup_tab()
        self.build_soga_tab()
        self.build_moga_tab()

        # =========================================================
        # RIGHT PANEL: THE OUTPUT CENTER
        # =========================================================
        self.output_frame = ctk.CTkFrame(self, corner_radius=10)
        self.output_frame.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="nsew")
        self.output_frame.grid_rowconfigure(1, weight=1) # Let the console expand
        self.output_frame.grid_columnconfigure(0, weight=1)

        # 1. Output Header
        self.lbl_console = ctk.CTkLabel(self.output_frame, text="Live Optimization Console", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_console.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")

        # 2. Live Console Textbox (Read-only)
        self.console = ctk.CTkTextbox(self.output_frame, font=ctk.CTkFont(family="Consolas", size=12))
        self.console.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.console.insert("0.0", "OWFLO System Initialized. Awaiting commands...\n")
        self.console.configure(state="disabled") # Prevent user typing

        # 3. Global Console Action Buttons (Bottom row)
        self.console_action_frame = ctk.CTkFrame(self.output_frame, fg_color="transparent")
        self.console_action_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")

        # Keep the Global Abort Button here
        self.btn_abort = ctk.CTkButton(self.console_action_frame, text="⏹ Abort Execution", fg_color="#b22222", hover_color="#8b1a1a", state="disabled", command=self.abort_process)
        self.btn_abort.pack(side="right")

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
        self.soga_cross.insert(0, "0.80")
        self.soga_cross.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(ga_grid, text="Mutation Prob:").grid(row=1, column=2, sticky="e", padx=(20, 5), pady=5)
        self.soga_mut = ctk.CTkEntry(ga_grid, width=100)
        self.soga_mut.insert(0, "0.10")
        self.soga_mut.grid(row=1, column=3, padx=5, pady=5)

        ctk.CTkLabel(ga_grid, text="Mutation Step (\u03BC):").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.soga_mu = ctk.CTkEntry(ga_grid, width=100)
        self.soga_mu.insert(0, "0.08") # Adjust this default value to whatever fits your SOGA logic
        self.soga_mu.grid(row=2, column=1, padx=5, pady=5)

        # SOGA Specifics
        ctk.CTkLabel(soga_frame, text="Target Objective:", font=ctk.CTkFont(weight="bold")).pack(pady=(10, 5), anchor="w", padx=15)
        self.soga_target = ctk.CTkOptionMenu(soga_frame, values=["Maximize AEP", "Minimize Cost"])
        self.soga_target.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(soga_frame, text="Stall Tolerance (Generations before early stop):").pack(pady=(10, 0), anchor="w", padx=15)
        self.soga_stall = ctk.CTkEntry(soga_frame, placeholder_text="e.g., 50")
        self.soga_stall.insert(0, "50")
        self.soga_stall.pack(fill="x", padx=15, pady=(5, 15))
        
        self.btn_run_soga = ctk.CTkButton(self.tab_soga, text="Run SOGA Optimization", height=40, font=ctk.CTkFont(weight="bold"),
                                            command=self.run_soga_pipeline, fg_color="#2c824c", hover_color="#1d5c34") 
        self.btn_run_soga.pack(pady=10, fill="x", padx=10, side="bottom")

        # --- NEW: Compilation Action Buttons ---
        comp_frame = ctk.CTkFrame(self.tab_soga, fg_color="transparent")
        comp_frame.pack(fill="x", padx=10, pady=(15, 0), side="bottom")

        self.btn_compile_soga_debug = ctk.CTkButton(
            comp_frame, text="⚙️ Compile SOGA (Debug)", fg_color="#b8860b", hover_color="#8a6508", 
            command=lambda: self.run_compiler("debug", "soga")
        )
        self.btn_compile_soga_debug.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self.btn_compile_soga_fast = ctk.CTkButton(
            comp_frame, text="🚀 Compile SOGA (Fast)", fg_color="#b22222", hover_color="#8b1a1a", 
            command=lambda: self.run_compiler("fast", "soga")
        )
        self.btn_compile_soga_fast.pack(side="left", expand=True, fill="x", padx=(5, 0))

        # --- NEW: SOGA Visualizer Buttons ---
        viz_frame_soga = ctk.CTkFrame(self.tab_soga, fg_color="transparent")
        viz_frame_soga.pack(fill="x", padx=10, pady=(0, 10), side="bottom")

        # Row 1: Static Plots
        plot_row = ctk.CTkFrame(viz_frame_soga, fg_color="transparent")
        plot_row.pack(fill="x", pady=(0, 5))

        self.btn_soga_plot = ctk.CTkButton(plot_row, text="📈 Plot Convergence History", state="disabled", command=self.plot_soga_convergence)
        self.btn_soga_plot.pack(side="left", padx=(0, 10), expand=True, fill="x")

        self.btn_soga_3d = ctk.CTkButton(plot_row, text="🌐 View Best 3D Layout", state="disabled", command=self.plot_soga_3d)
        self.btn_soga_3d.pack(side="left", expand=True, fill="x")

        # Row 2: Animation & Dynamic Height Selection
        anim_row = ctk.CTkFrame(viz_frame_soga, fg_color="transparent")
        anim_row.pack(fill="x", pady=5)
        
        ctk.CTkLabel(anim_row, text="Height Level:").pack(side="left", padx=(0, 10))
        self.soga_anim_height_dropdown = ctk.CTkOptionMenu(anim_row, values=["Run optimization first"], state="disabled")
        self.soga_anim_height_dropdown.pack(side="left", padx=(0, 10))

        self.btn_soga_anim = ctk.CTkButton(anim_row, text="🎬 Generate MP4 Flow", state="disabled", command=self.generate_soga_animation)
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
        self.moga_cross.insert(0, "0.90")
        self.moga_cross.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(ga_grid, text="Mutation Prob:").grid(row=1, column=2, sticky="e", padx=(20, 5), pady=5)
        self.moga_mut = ctk.CTkEntry(ga_grid, width=100)
        self.moga_mut.insert(0, "0.15")
        self.moga_mut.grid(row=1, column=3, padx=5, pady=5)

        ctk.CTkLabel(ga_grid, text="Mutation Step (\u03BC):").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.moga_mu = ctk.CTkEntry(ga_grid, width=100)
        self.moga_mu.insert(0, "0.05")
        self.moga_mu.grid(row=2, column=1, padx=5, pady=5)

        self.btn_run_moga = ctk.CTkButton(self.tab_moga, text="Run NSGA-II Optimization", height=40, font=ctk.CTkFont(weight="bold"),
                                           command=self.run_moga_pipeline, fg_color="#2c824c", hover_color="#1d5c34")
        self.btn_run_moga.pack(pady=10, fill="x", padx=10, side="bottom")

        # --- MOGA Visualizer Buttons ---
        viz_frame_moga = ctk.CTkFrame(self.tab_moga, fg_color="transparent")
        viz_frame_moga.pack(fill="x", padx=10, pady=(0, 10), side="bottom")

        # --- NEW: Compilation Action Buttons ---
        comp_frame = ctk.CTkFrame(self.tab_moga, fg_color="transparent")
        comp_frame.pack(fill="x", padx=10, pady=(15, 0), side="bottom")

        self.btn_compile_moga_debug = ctk.CTkButton(
            comp_frame, text="⚙️ Compile MOGA (Debug)", fg_color="#b8860b", hover_color="#8a6508", 
            command=lambda: self.run_compiler("debug", "moga")
        )
        self.btn_compile_moga_debug.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self.btn_compile_moga_fast = ctk.CTkButton(
            comp_frame, text="🚀 Compile MOGA (Fast)", fg_color="#b22222", hover_color="#8b1a1a", 
            command=lambda: self.run_compiler("fast", "moga")
        )
        self.btn_compile_moga_fast.pack(side="left", expand=True, fill="x", padx=(5, 0))

        # Row 1: Static Plots
        plot_row = ctk.CTkFrame(viz_frame_moga, fg_color="transparent")
        plot_row.pack(fill="x", pady=(0, 5))
        
        self.btn_moga_pareto = ctk.CTkButton(plot_row, text="📊 Plot Pareto Front", state="disabled", command=self.plot_moga_pareto)
        self.btn_moga_pareto.pack(side="left", padx=(0, 10), expand=True, fill="x")

        self.btn_moga_3d = ctk.CTkButton(plot_row, text="🌐 View Extreme 3D Layouts", state="disabled", command=self.plot_moga_3d)
        self.btn_moga_3d.pack(side="left", expand=True, fill="x")

        # Row 2: Animation & Dynamic Height Selection
        anim_row = ctk.CTkFrame(viz_frame_moga, fg_color="transparent")
        anim_row.pack(fill="x", pady=5)
        
        ctk.CTkLabel(anim_row, text="Height Level:").pack(side="left", padx=(0, 10))
        
        # Starts with a placeholder. We will dynamically update this later!
        self.anim_height_dropdown = ctk.CTkOptionMenu(anim_row, values=["Run optimization first"], state="disabled")
        self.anim_height_dropdown.pack(side="left", padx=(0, 10))

        self.btn_moga_anim = ctk.CTkButton(anim_row, text="🎬 Generate Flow Animation", state="disabled", command=self.generate_moga_animation)
        self.btn_moga_anim.pack(side="left", expand=True, fill="x")

    def build_farm_setup_tab(self):
        """Constructs the shared physical constraints and turbine selection."""
        
        # 1. Turbine File Selection
        turb_frame = ctk.CTkFrame(self.tab_farm, corner_radius=10)
        turb_frame.pack(fill="x", padx=10, pady=(10, 20))
        
        ctk.CTkLabel(turb_frame, text="1. Turbine Specification Master File", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))
        
        # --- NEW: Helpful UI Tip and Template Box ---
        tip_text = "💡 Tip: This must be the Master Index file containing the paths to your individual turbine CSVs. Follow the exact spacing and alternating rows format below:"
        ctk.CTkLabel(turb_frame, text=tip_text, text_color="gray", font=ctk.CTkFont(size=11, slant="italic"), wraplength=600, justify="left").pack(anchor="w", padx=15, pady=(0, 5))

        template_box = ctk.CTkTextbox(turb_frame, height=120, fg_color="#1e1e1e", text_color="#a5d6ff", font=ctk.CTkFont(family="Consolas", size=11))
        template_box.pack(fill="x", padx=15, pady=(5, 10))
        template_str = (
            "Number of turbine types\n"
            "2\n"
            "=========================================================================\n"
            "diameter  rated power  cut in  cut off  Height  Turbine name\n"
            "198.0     10.          4.      25.      119.0   IEA_Reference_10MW_198\n"
            "./inputs/Turbines/IEA_Reference_10MW_198.csv\n"
            "240.0     15.          3.      25.      150.0   IEA_Reference_15MW_240\n"
            "./inputs/Turbines/IEA_Reference_15MW_240.csv\n"
            "========================================================================="
        )
        template_box.insert("0.0", template_str)
        template_box.configure(state="disabled") # Lock it so the user can't accidentally type in it
        # ----------------------------------------------

        self.turbine_file = None
        self.lbl_turb_status = ctk.CTkLabel(turb_frame, text="No Turbine Master file selected.", text_color="gray")
        self.lbl_turb_status.pack(anchor="w", padx=15, pady=(0, 5))
        
        ctk.CTkButton(turb_frame, text="Select Master File (.txt/.dat)", width=200, fg_color="#4a4a4a", hover_color="#333333", command=self.select_turbine).pack(anchor="w", padx=15, pady=(5, 15))

        # 2. Farm Constraints (Shared)
        const_frame = ctk.CTkFrame(self.tab_farm, corner_radius=10)
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
        """Constructs the Mesh, Bathymetry, and Wind Data preparation tools."""
        
        # We use a ScrollableFrame in case we add Wind and Distances here later
        self.scroll_pre = ctk.CTkScrollableFrame(self.tab_pre, fg_color="transparent")
        self.scroll_pre.pack(fill="both", expand=True)

        # ==========================================
        # 1. MESH GENERATION FRAME
        # ==========================================
        mesh_frame = ctk.CTkFrame(self.scroll_pre, corner_radius=10)
        mesh_frame.pack(fill="x", padx=10, pady=(10, 20))

        ctk.CTkLabel(mesh_frame, text="1. Spatial Mesh Generation", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))

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
        self.lbl_kml_status = ctk.CTkLabel(mesh_frame, text="No KML boundaries selected.", text_color="gray")
        self.lbl_kml_status.pack(anchor="w", padx=15, pady=(5, 0))

        btn_row_1 = ctk.CTkFrame(mesh_frame, fg_color="transparent")
        btn_row_1.pack(fill="x", padx=15, pady=(5, 15))
        
        ctk.CTkButton(btn_row_1, text="Select KML Files", width=120, fg_color="#4a4a4a", hover_color="#333333", command=self.select_kmls).pack(side="left", padx=(0, 10))
        self.btn_run_mesh = ctk.CTkButton(btn_row_1, text="Generate Mesh (Polygon3)", command=self.run_mesh_pipeline)
        self.btn_run_mesh.pack(side="left")

        # ==========================================
        # 2. BATHYMETRY FRAME
        # ==========================================
        bathy_frame = ctk.CTkFrame(self.scroll_pre, corner_radius=10)
        bathy_frame.pack(fill="x", padx=10, pady=(0, 20))

        ctk.CTkLabel(bathy_frame, text="2. Bathymetry Extraction", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))

        self.gebco_file = None
        self.lbl_bathy_status = ctk.CTkLabel(bathy_frame, text="No GEBCO .asc file selected.", text_color="gray")
        self.lbl_bathy_status.pack(anchor="w", padx=15, pady=(5, 0))

        btn_row_2 = ctk.CTkFrame(bathy_frame, fg_color="transparent")
        btn_row_2.pack(fill="x", padx=15, pady=(5, 15))

        ctk.CTkButton(btn_row_2, text="Select GEBCO (.asc)", width=120, fg_color="#4a4a4a", hover_color="#333333", command=self.select_gebco).pack(side="left", padx=(0, 10))
        self.btn_run_bathy = ctk.CTkButton(btn_row_2, text="Extract Depths", command=self.run_bathy_pipeline)
        self.btn_run_bathy.pack(side="left")

        # ==========================================
        # 3. WIND DATA FRAME
        # ==========================================
        wind_frame = ctk.CTkFrame(self.scroll_pre, corner_radius=10)
        wind_frame.pack(fill="x", padx=10, pady=(0, 20))

        ctk.CTkLabel(wind_frame, text="3. Wind Data Preparation", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))

        self.era5_dir = None
        self.lbl_wind_status = ctk.CTkLabel(wind_frame, text="No ERA5 directory selected.", text_color="gray")
        self.lbl_wind_status.pack(anchor="w", padx=15, pady=(0, 5))

        # --- NEW: Helpful UI Tip ---
        tip_text = "💡 Tip: Hours are 0 to 23 (0 = Midnight). Wrap-around is supported (e.g., Start 22, End 4)."
        ctk.CTkLabel(wind_frame, text=tip_text, text_color="gray", font=ctk.CTkFont(size=11, slant="italic")).pack(anchor="w", padx=15, pady=(0, 5))

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

        # Action Buttons
        btn_row_3 = ctk.CTkFrame(wind_frame, fg_color="transparent")
        btn_row_3.pack(fill="x", padx=15, pady=(10, 15))

        ctk.CTkButton(btn_row_3, text="Select ERA5 Directory", width=150, fg_color="#4a4a4a", hover_color="#333333", command=self.select_era5).pack(side="left", padx=(0, 10))
        self.btn_run_wind = ctk.CTkButton(btn_row_3, text="Interpolate to Mesh", command=self.run_wind_pipeline)
        self.btn_run_wind.pack(side="left")

        # ==========================================
        # 4. DISTANCE CALCULATOR FRAME
        # ==========================================
        dist_frame = ctk.CTkFrame(self.scroll_pre, corner_radius=10)
        dist_frame.pack(fill="x", padx=10, pady=(0, 20))

        ctk.CTkLabel(dist_frame, text="4. Logistics & Site Distances", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))

        self.shoreline_kml = None
        self.grid_kml = None
        self.port_kml = None

        # Grid system for the 3 distance files to keep it compact
        dist_grid = ctk.CTkFrame(dist_frame, fg_color="transparent")
        dist_grid.pack(fill="x", padx=15, pady=5)

        # Row 1: Shoreline
        ctk.CTkButton(dist_grid, text="Shoreline KML", width=120, fg_color="#4a4a4a", hover_color="#333333", command=self.select_shoreline).grid(row=0, column=0, pady=2, sticky="w")
        self.lbl_shore_status = ctk.CTkLabel(dist_grid, text="Pending...", text_color="gray")
        self.lbl_shore_status.grid(row=0, column=1, padx=10, sticky="w")

        # Row 2: Grid Connection
        ctk.CTkButton(dist_grid, text="Grid Conn. KML", width=120, fg_color="#4a4a4a", hover_color="#333333", command=self.select_grid).grid(row=1, column=0, pady=2, sticky="w")
        self.lbl_grid_status = ctk.CTkLabel(dist_grid, text="Pending...", text_color="gray")
        self.lbl_grid_status.grid(row=1, column=1, padx=10, sticky="w")

        # Row 3: Port
        ctk.CTkButton(dist_grid, text="Port KML", width=120, fg_color="#4a4a4a", hover_color="#333333", command=self.select_port).grid(row=2, column=0, pady=2, sticky="w")
        self.lbl_port_status = ctk.CTkLabel(dist_grid, text="Pending...", text_color="gray")
        self.lbl_port_status.grid(row=2, column=1, padx=10, sticky="w")

        self.btn_run_dist = ctk.CTkButton(dist_frame, text="Calculate Distances", command=self.run_distances_pipeline)
        self.btn_run_dist.pack(anchor="w", padx=15, pady=(10, 15))

    # ---------------------------------------------------------
    # CALLBACKS & WORKER THREADS
    # ---------------------------------------------------------
    def abort_process(self):
        """Force-kills the currently running Fortran subprocess."""
        if self.running_process is not None and self.running_process.poll() is None:
            self.log("\n⚠️ ABORT SIGNAL SENT: Terminating Fortran process...")
            
            try:
                self.running_process.kill()  # Hard kill at the OS level
            except Exception as e:
                self.log(f"🔴 Failed to kill process: {e}")

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
            
            # Map Objective Target ("Maximize AEP" = 1, "Minimize Cost" = 2)
            target_str = self.soga_target.get()
            obj_target = 1 if "AEP" in target_str else 2
            
        except ValueError:
            self.log("🔴 ERROR: Please ensure all SOGA parameters are valid numbers.")
            self.btn_run_soga.configure(state="normal")
            return

        def worker():
            self.log("--- Preparing SOGA Environment ---")
            os.makedirs('./inputs', exist_ok=True)
            
            # 1. Stage the Turbine Master File
            if not self.turbine_file:
                self.log("🔴 ERROR: Please select a Turbine Master File in the Farm Setup tab.")
                self.after(0, lambda: self.btn_run_soga.configure(state="normal"))
                return
            try:
                target_turbine_path = './inputs/turbine_spec.txt'
                if os.path.abspath(self.turbine_file) != os.path.abspath(target_turbine_path):
                    shutil.copy(self.turbine_file, target_turbine_path)
            except Exception as e:
                self.log(f"🔴 ERROR staging turbine file: {e}")
                self.after(0, lambda: self.btn_run_soga.configure(state="normal"))
                return
            
            # 2. Write the config.inp file
            config_path = './inputs/config.inp'
            try:
                with open(config_path, 'w') as f:
                    f.write(f"{it_max}\n{n_pop}\n{p_cross}\n{p_mut}\n{mu}\n{max_turbs}\n{min_turbs}\n{workability}\n")
                    f.write("1\n") # opt_mode: 1 = SOGA
                    f.write(f"{obj_target}\n") # SOGA obj_target
            except Exception as e:
                self.log(f"🔴 ERROR writing config file: {e}")
                self.after(0, lambda: self.btn_run_soga.configure(state="normal"))
                return

            self.log("🚀 Launching SOGA Fortran Optimizer...")

            exe_name = "soga_optimizer.exe" if sys.platform == "win32" else "./soga_optimizer"
            exe_path = os.path.join(os.getcwd(), 'source', exe_name)
            
            if not os.path.exists(exe_path):
                self.log(f"🔴 ERROR: {exe_name} not found. Please click Compile SOGA first.")
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
                    self.log("🎉 SOGA Optimization Finished Successfully!")
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
                    self.log(f"🛑 Process Terminated (Exit code {self.running_process.returncode})")
                    
            except Exception as e:
                self.log(f"🔴 System Error executing Fortran: {e}")
            finally:
                self.running_process = None
                self.after(0, lambda: self.btn_abort.configure(state="disabled"))

            self.after(0, lambda: self.btn_run_soga.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    # --- SOGA Visualization Callbacks ---
    def plot_soga_convergence(self):
        target_obj = self.soga_target.get() # Grab the objective name
        self.log(f"📈 Generating SOGA Convergence Plot for {target_obj}...")
        self.btn_soga_plot.configure(state="disabled")
        
        def worker():
            out_img = visualizer.save_soga_convergence_plot(target_obj=target_obj)
            if out_img:
                try:
                    if sys.platform == "win32": os.startfile(os.path.normpath(out_img))
                    else: subprocess.run(["xdg-open", out_img])
                except Exception: pass
            self.after(0, lambda: self.btn_soga_plot.configure(state="normal"))
        threading.Thread(target=worker, daemon=True).start()

    def plot_soga_3d(self):
        target_obj = self.soga_target.get() # Grab the objective name
        self.log(f"🌐 Launching SOGA 3D PyVista Viewer for {target_obj}...")
        self.btn_soga_3d.configure(state="disabled")
        
        def worker():
            try: visualizer.generate_soga_3d_layout(target_obj=target_obj)
            except Exception as e: self.log(f"🔴 Error in 3D viewer: {e}")
            self.after(0, lambda: self.btn_soga_3d.configure(state="normal"))
        threading.Thread(target=worker, daemon=True).start()

    def generate_soga_animation(self):
        selected = self.soga_anim_height_dropdown.get()
        if "Level" not in selected: return
        level_idx = int(selected.replace("Level ", ""))
        self.log(f"🎬 Generating SOGA MP4 animation for {selected}...")
        self.btn_soga_anim.configure(state="disabled")
        def worker():
            try:
                out_mp4 = visualizer.generate_soga_mp4_animation(level_idx=level_idx)
                if out_mp4:
                    if sys.platform == "win32": os.startfile(os.path.normpath(out_mp4))
                    else: subprocess.run(["xdg-open", out_mp4])
            except Exception as e:
                self.log(f"🔴 Error generating animation: {e}")
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
            self.log("🔴 ERROR: Please ensure all MOGA parameters are valid numbers.")
            self.btn_run_moga.configure(state="normal")
            return

        def worker():
            self.log("--- Preparing NSGA-II Environment ---")
            os.makedirs('./inputs', exist_ok=True)
            
            # --- NEW: Stage the Turbine Master File ---
            if not self.turbine_file:
                self.log("🔴 ERROR: Please select a Turbine Master File in the Farm Setup tab.")
                self.after(0, lambda: self.btn_run_moga.configure(state="normal"))
                return
                
            try:
                # Use the exact filename your Fortran expects
                target_turbine_path = './inputs/turbine_spec.txt'
                
                # Check if the selected file is already the target file
                if os.path.abspath(self.turbine_file) != os.path.abspath(target_turbine_path):
                    shutil.copy(self.turbine_file, target_turbine_path)
                    self.log("✅ Turbine Master File copied and staged for Fortran.")
                else:
                    self.log("✅ Turbine Master File is already in position.")
                    
            except Exception as e:
                self.log(f"🔴 ERROR staging turbine file: {e}")
                self.after(0, lambda: self.btn_run_moga.configure(state="normal"))
                return
            
            # 2. Write the config.inp file in the exact order Fortran expects
            config_path = './inputs/config.inp'
            try:
                with open(config_path, 'w') as f:
                    f.write(f"{it_max}\n")
                    f.write(f"{n_pop}\n")
                    f.write(f"{p_cross}\n")
                    f.write(f"{p_mut}\n")
                    f.write(f"{mu}\n")
                    f.write(f"{max_turbs}\n")
                    f.write(f"{min_turbs}\n")
                    f.write(f"{workability}\n")
                    f.write("2\n") # opt_mode: 2 = MOGA
                    f.write("1\n") # obj_target (Dummy value for MOGA)
            except Exception as e:
                self.log(f"🔴 ERROR writing config file: {e}")
                self.after(0, lambda: self.btn_run_moga.configure(state="normal"))
                return

            self.log("✅ config.inp successfully updated.")
            self.log("🚀 Launching Fortran Optimizer...")

            # 3. Execute Fortran Executable and stream output LIVE
            import subprocess
            
            # Determine platform-specific binary name
            # Determine platform-specific binary name
            exe_name = "moga_optimizer.exe" if sys.platform == "win32" else "./moga_optimizer"
            exe_path = os.path.join(os.getcwd(), 'source', exe_name)
            
            if not os.path.exists(exe_path):
                self.log(f"🔴 ERROR: Compiled optimizer ({exe_name}) not found in /source folder.")
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
                    self.log("🎉 NSGA-II Optimization Finished Successfully!")
                    
                    # 1. Unlock the plot buttons
                    self.after(0, lambda: self.btn_moga_pareto.configure(state="normal"))
                    self.after(0, lambda: self.btn_moga_3d.configure(state="normal"))
                    self.after(0, lambda: self.btn_moga_anim.configure(state="normal"))
                    
                    # 2. Dynamically find the max height level and update the dropdown
                    self.update_animation_dropdown()
                else:
                    self.log(f"🛑 Process Terminated (Exit code {self.running_process.returncode})")
                    
            except Exception as e:
                self.log(f"🔴 System Error executing Fortran: {e}")
                
            finally:
                # 5. Cleanup: Disconnect the process and disable the abort button
                self.running_process = None
                self.after(0, lambda: self.btn_abort.configure(state="disabled"))

            # Re-enable the Run button when entirely finished
            self.after(0, lambda: self.btn_run_moga.configure(state="normal"))

        # Launch the worker thread
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def run_compiler(self, mode, target="moga"):
        # Disable buttons to prevent spawning multiple compile threads
        if target == "moga":
            self.btn_compile_moga_debug.configure(state="disabled")
            self.btn_compile_moga_fast.configure(state="disabled")

        def worker():
            self.log(f"--- Starting Fortran Compilation ({mode.upper()} | {target.upper()}) ---")
            
            # Automatically set the correct binary extension based on the OS
            exe_name = f"{target}_optimizer.exe" if sys.platform == "win32" else f"{target}_optimizer"
            
            # Define exact paths to the core library and the specific main script
            out_path = os.path.join(".", "source", exe_name)
            core_path = os.path.join(".", "source", "wflop_core.f90") 
            main_path = os.path.join(".", "source", f"main_{target}.f90")
            
            # Define gfortran flags
            if mode == "debug":
                flags = ["-Wall", "-Wextra", "-g", "-O0", "-fcheck=all", "-fbacktrace", "-fopenmp"]
            else:
                flags = ["-O3", "-fopenmp"]

            # Command now compiles BOTH the core module and the main program!
            cmd = ["gfortran"] + flags + [core_path, main_path, "-o", out_path]
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
                    self.log(f"✅ Compilation Successful! Executable saved as: {exe_name}")
                else:
                    self.log(f"🔴 Compilation FAILED with exit code {process.returncode}")
                    
            except FileNotFoundError:
                self.log("🔴 ERROR: 'gfortran' command not found. Ensure MinGW is in your system PATH.")
            except Exception as e:
                self.log(f"🔴 System Error during compilation: {e}")

            # Re-enable buttons safely from the main thread
            if target == "moga":
                self.after(0, lambda: self.btn_compile_moga_debug.configure(state="normal"))
                self.after(0, lambda: self.btn_compile_moga_fast.configure(state="normal"))

        import threading
        threading.Thread(target=worker, daemon=True).start()

    # ==========================================
    # VISUALIZATION CALLBACKS
    # ==========================================

    def plot_moga_pareto(self):
        self.log("📊 Generating Pareto Front plots...")
        self.btn_moga_pareto.configure(state="disabled")
        
        def worker():
            success = visualizer.save_pareto_plots()
            if success:
                self.log("✅ Pareto plots saved to ./outputs/")
                # --- Auto-open BOTH images ---
                try:
                    if sys.platform == "win32":
                        os.startfile(os.path.normpath("./outputs/plot_final_pareto.png"))
                        os.startfile(os.path.normpath("./outputs/plot_evolution.png"))
                    else:
                        import subprocess
                        subprocess.run(["xdg-open", "./outputs/plot_final_pareto.png"])
                        subprocess.run(["xdg-open", "./outputs/plot_evolution.png"])
                except Exception:
                    pass
            self.after(0, lambda: self.btn_moga_pareto.configure(state="normal"))
            
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def plot_moga_3d(self):
        self.log("🌐 Launching 3D PyVista Viewer (this may take a moment)...")
        self.btn_moga_3d.configure(state="disabled")
        
        def worker():
            try:
                visualizer.generate_3d_comparison()
            except Exception as e:
                self.log(f"🔴 Error in 3D viewer: {e}")
            self.after(0, lambda: self.btn_moga_3d.configure(state="normal"))
            
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def generate_moga_animation(self):
        selected = self.anim_height_dropdown.get()
        if "Level" not in selected:
            return
            
        level_idx = int(selected.replace("Level ", ""))
        self.log(f"🎬 Generating MP4 animation for {selected} (Please wait)...")
        self.btn_moga_anim.configure(state="disabled")
        
        def worker():
            try:
                # Call the updated MP4 function
                out_mp4 = visualizer.generate_mp4_animation('./outputs/animation_data_obj_1.csv', level_idx=level_idx, fast_mode=False)
                if out_mp4:
                    self.log(f"✅ Animation saved to {out_mp4}")
                    # Auto-open the MP4 in the default media player
                    if sys.platform == "win32":
                        os.startfile(os.path.normpath(out_mp4))
                    else:
                        import subprocess
                        subprocess.run(["xdg-open", out_mp4])
            except Exception as e:
                self.log(f"🔴 Error generating animation: {e}")
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
            self.log("⚠️ Could not detect height levels from Fortran output.")

if __name__ == "__main__":
    app = OWFLOGui()
    app.mainloop()