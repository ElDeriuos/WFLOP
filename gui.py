import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import subprocess
import threading
import webbrowser
import os
import sys
import platform
import glob
from tkinter import filedialog
from source import visualizer
from source import mesh_generator
from source import bathymetry_generator
from source import wind_generator
from source import distance_calculator

class WindFarmGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Wind Farm Layout Optimizer (NSGA-II)")
        self.root.geometry("1300x800")
        
        # --- Variables for config.inp ---
        self.it_max = tk.StringVar(value="50")
        self.n_pop = tk.StringVar(value="100")
        self.p_cross = tk.StringVar(value="0.5")
        self.p_mut = tk.StringVar(value="0.5")
        self.mu = tk.StringVar(value="0.11")
        self.max_turbs = tk.StringVar(value="50")
        self.min_turbs = tk.StringVar(value="1")
        self.num_threads = tk.StringVar(value="0")
        self.workability = tk.StringVar(value="0.65")

        # --- Variables for Pre-Processing ---
        self.dx = tk.StringVar(value="10000.0")
        self.dy = tk.StringVar(value="10000.0")
        self.kml_files_list = [] 
        self.mesh_metadata = {} 
        self.asc_file = None
        self.nc_folder = None
        
        # --- Variables for Wind Filters ---
        self.f_h_start, self.f_h_end = tk.StringVar(value="All"), tk.StringVar(value="All")
        self.f_d_start, self.f_d_end = tk.StringVar(value="All"), tk.StringVar(value="All")
        self.f_m_start, self.f_m_end = tk.StringVar(value="All"), tk.StringVar(value="All")
        self.f_y_start, self.f_y_end = tk.StringVar(value="All"), tk.StringVar(value="All")

        self.shoreline_kml = None
        self.grid_kml = None
        self.port_kml = None

        # --- Variables for Visualization ---
        self.viz_user_idx = tk.StringVar(value="0")
        self.viz_level_idx = tk.StringVar(value="1")

        self.build_main_layout()
        self.build_scrollable_container()
        self.build_ui()

    def build_main_layout(self):
        """Creates a split-screen PanedWindow for the left (controls) and right (console)."""
        self.paned_window = ttk.Panedwindow(self.root, orient="horizontal")
        self.paned_window.pack(fill="both", expand=True, padx=5, pady=5)

        # Create the two main containers
        self.left_container = ttk.Frame(self.paned_window)
        self.right_container = ttk.Frame(self.paned_window)

        # Add them to the PanedWindow (weight=1 makes them share space equally)
        self.paned_window.add(self.left_container, weight=1)
        self.paned_window.add(self.right_container, weight=1)

    def build_scrollable_container(self):
        """Creates a Canvas and Scrollbar to allow vertical scrolling on the LEFT panel."""
        # Create a Canvas inside the left container
        self.canvas = tk.Canvas(self.left_container, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        # Add a Scrollbar to the Canvas
        self.scrollbar = ttk.Scrollbar(self.left_container, orient="vertical", command=self.canvas.yview)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Create the actual frame that will hold all our UI widgets
        self.main_frame = ttk.Frame(self.canvas)

        # Add that frame to a window in the canvas
        self.canvas_window = self.canvas.create_window((0, 0), window=self.main_frame, anchor="nw")

        # Bind events to update the scroll region dynamically
        self.main_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width)
        )

        # Bind Mouse Wheel (Windows/Linux)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel) 
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        """Handles mouse wheel scrolling."""
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")

    def build_ui(self):
        
        # --- 0. Mesh Generation Frame ---
        mesh_frame = ttk.Labelframe(self.main_frame, text="Mesh Generation (KML to Grid)", padding=10)
        mesh_frame.pack(fill="x", padx=10, pady=5)
        
        self.create_input_row(mesh_frame, "Grid dx (m):", self.dx, 0)
        self.create_input_row(mesh_frame, "Grid dy (m):", self.dy, 1)
        
        # Staging Area for KML Files
        list_frame = ttk.Frame(mesh_frame)
        list_frame.grid(row=2, column=0, columnspan=2, pady=10, sticky="we")
        
        self.kml_listbox = tk.Listbox(list_frame, height=4)
        self.kml_listbox.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        btn_box = ttk.Frame(list_frame)
        btn_box.pack(side="right")
        
        ttk.Button(btn_box, text="Add KML(s)", command=self.add_kmls).pack(fill="x", pady=2)
        ttk.Button(btn_box, text="Clear List", command=self.clear_kmls).pack(fill="x", pady=2)
        
        # The Run Button
        self.btn_mesh = ttk.Button(mesh_frame, text="Generate Mesh", command=self.start_mesh_generation)
        self.btn_mesh.grid(row=3, column=0, columnspan=2, pady=5, sticky="we")

        # --- 0.25 Site Logistics Frame ---
        logistics_frame = ttk.Labelframe(self.main_frame, text="Site Logistics (Distances)", padding=10)
        logistics_frame.pack(fill="x", padx=10, pady=5)
        
        # Shoreline File Selector
        shore_box = ttk.Frame(logistics_frame)
        shore_box.pack(fill="x", pady=2)
        self.lbl_shore = ttk.Label(shore_box, text="No Shoreline KML selected", foreground="red")
        self.lbl_shore.pack(side="left", padx=5)
        ttk.Button(shore_box, text="Browse Shoreline KML", command=self.select_shoreline).pack(side="right")
        
        # Grid Point File Selector
        grid_box = ttk.Frame(logistics_frame)
        grid_box.pack(fill="x", pady=2)
        self.lbl_grid = ttk.Label(grid_box, text="No Grid Point KML selected", foreground="red")
        self.lbl_grid.pack(side="left", padx=5)
        ttk.Button(grid_box, text="Browse Grid Point KML", command=self.select_grid).pack(side="right")

        # Port File Selector
        port_box = ttk.Frame(logistics_frame)
        port_box.pack(fill="x", pady=2)
        self.lbl_port = ttk.Label(port_box, text="No Port KML selected", foreground="red")
        self.lbl_port.pack(side="left", padx=5)
        ttk.Button(port_box, text="Browse Port KML", command=self.select_port).pack(side="right")
        
        self.btn_dist = ttk.Button(logistics_frame, text="Calculate Distances", command=self.start_distances)
        self.btn_dist.pack(fill="x", pady=(5, 0))

        # --- 0.5 Bathymetry Generation Frame ---
        bathy_frame = ttk.Labelframe(self.main_frame, text="Bathymetry Extraction (.asc to Grid)", padding=10)
        bathy_frame.pack(fill="x", padx=10, pady=5)
        
        # File selector sub-frame
        asc_box = ttk.Frame(bathy_frame)
        asc_box.pack(fill="x", pady=5)
        
        self.lbl_asc = ttk.Label(asc_box, text="No GEBCO .asc file selected", foreground="red")
        self.lbl_asc.pack(side="left", padx=5)
        
        ttk.Button(asc_box, text="Browse GEBCO .asc", command=self.select_asc).pack(side="right")
        
        self.btn_bathy = ttk.Button(bathy_frame, text="Generate farm_bathymetry.dat", command=self.start_bathymetry)
        self.btn_bathy.pack(fill="x", pady=5)

        # --- 0.75 Wind Data Generation Frame ---
        wind_frame = ttk.Labelframe(self.main_frame, text="Wind Field Generation (.nc to Grid)", padding=10)
        wind_frame.pack(fill="x", padx=10, pady=5)
        
        # Folder selector
        nc_box = ttk.Frame(wind_frame)
        nc_box.pack(fill="x", pady=(0, 10))
        self.lbl_nc = ttk.Label(nc_box, text="No .nc folder selected", foreground="red")
        self.lbl_nc.pack(side="left", padx=5)
        ttk.Button(nc_box, text="Browse .nc Folder", command=self.select_nc_folder).pack(side="right")
        
        # Time Filters (Grid Layout for compactness)
        filter_box = ttk.Frame(wind_frame)
        filter_box.pack(fill="x")
        
        ttk.Label(filter_box, text="Hours (0-23):").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        self.create_filter_pair(filter_box, self.f_h_start, self.f_h_end, [str(i) for i in range(24)], 0, 1)
        
        ttk.Label(filter_box, text="Days (1-31):").grid(row=1, column=0, sticky="w", padx=2, pady=2)
        self.create_filter_pair(filter_box, self.f_d_start, self.f_d_end, [str(i) for i in range(1, 32)], 1, 1)
        
        ttk.Label(filter_box, text="Months (1-12):").grid(row=2, column=0, sticky="w", padx=2, pady=2)
        self.create_filter_pair(filter_box, self.f_m_start, self.f_m_end, [str(i) for i in range(1, 13)], 2, 1)
        
        ttk.Label(filter_box, text="Years:").grid(row=3, column=0, sticky="w", padx=2, pady=2)
        self.create_filter_pair(filter_box, self.f_y_start, self.f_y_end, [str(i) for i in range(1980, 2040)], 3, 1)
        
        ttk.Label(filter_box, text="(Leave as 'All' to ignore filter. Wrap-around supported, e.g. Hr 18 to 4)", font=("Arial", 8, "italic")).grid(row=4, column=0, columnspan=4, pady=2)

        self.btn_wind = ttk.Button(wind_frame, text="Generate filtered_wind.txt", command=self.start_wind_generation)
        self.btn_wind.pack(fill="x", pady=(10, 0))

        # --- 1. Parameters Frame ---
        param_frame = ttk.Labelframe(self.main_frame, text="Optimization Parameters", padding=10)
        param_frame.pack(fill="x", padx=10, pady=10)
        
        self.create_input_row(param_frame, "Max Generations (it_max):", self.it_max, 0)
        self.create_input_row(param_frame, "Population Size (n_pop):", self.n_pop, 1)
        self.create_input_row(param_frame, "Crossover Probability:", self.p_cross, 2)
        self.create_input_row(param_frame, "Mutation Probability:", self.p_mut, 3)
        self.create_input_row(param_frame, "Mutation Rate (mu):", self.mu, 4)
        self.create_input_row(param_frame, "Max Turbines:", self.max_turbs, 5)
        self.create_input_row(param_frame, "Min Turbines:", self.min_turbs, 6)
        self.create_input_row(param_frame, "CPU Threads (0 = Auto):", self.num_threads, 7)
        self.create_input_row(param_frame, "Workability Probability:", self.workability, 8)
        # --- 1.5 Compilation Frame ---
        compile_frame = ttk.Labelframe(self.main_frame, text="Fortran Compiler", padding=10)
        compile_frame.pack(fill="x", padx=10, pady=5)
        
        self.btn_compile_fast = ttk.Button(compile_frame, text="Compile (Fast & Optimized)", bootstyle="success", command=self.compile_fast)
        self.btn_compile_fast.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.btn_compile_debug = ttk.Button(compile_frame, text="Compile (Debug Mode)", bootstyle="warning", command=self.compile_debug)
        self.btn_compile_debug.pack(side="right", fill="x", expand=True, padx=(5, 0))

        # --- 2. Action Buttons ---
        action_frame = ttk.Frame(self.root, padding=10)
        action_frame.pack(fill="x")
        
        self.btn_run = ttk.Button(action_frame, text="Run Fortran Optimizer", command=self.start_optimization)
        self.btn_run.pack(fill="x", pady=5)
        
        # --- 3. Console Output (Moved to the Right Container) ---
        console_frame = ttk.Labelframe(self.right_container, text="Fortran Engine Output", padding=10)
        console_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Changed bg to a dark charcoal hex color instead of "grey" for better contrast with lime text
        self.console = tk.Text(console_frame, bg="#1e1e1e", fg="lime", font=("Consolas", 11), wrap="word")
        
        # Create the scrollbar and link it to the text widget
        self.console_scroll = ttk.Scrollbar(console_frame, orient="vertical", command=self.console.yview)
        self.console.configure(yscrollcommand=self.console_scroll.set)
        
        # Pack the scrollbar on the right, and the console on the left
        self.console_scroll.pack(side="right", fill="y")
        self.console.pack(side="left", fill="both", expand=True)

        # --- 4. Visualization Options Frame ---
        viz_frame = ttk.Labelframe(self.main_frame, text="Visualization Options", padding=10)
        viz_frame.pack(fill="x", padx=10, pady=5)
        
        self.btn_pareto = ttk.Button(viz_frame, text="1. Plot 2D Pareto Front", command=self.view_pareto, state="disabled")
        self.btn_pareto.pack(fill="x", pady=2)
        
        # 3D Button with Index Selector side-by-side
        frame_3d = ttk.Frame(viz_frame)
        frame_3d.pack(fill="x", pady=2)

        self.btn_3d = ttk.Button(frame_3d, text="2. Generate 3D Comparison", command=self.view_3d, state="disabled")
        self.btn_3d.pack(side="left", expand=True, fill="x", padx=(0, 5))
        
        ttk.Label(frame_3d, text="Custom Solution ID:").pack(side="left")
        ttk.Spinbox(frame_3d, from_=0, to=9999, textvariable=self.viz_user_idx, width=5).pack(side="left", padx=2)
        
        # Animation Button with Height Level Selector side-by-side
        frame_anim = ttk.Frame(viz_frame)
        frame_anim.pack(fill="x", pady=2)
        
        self.btn_anim = ttk.Button(frame_anim, text="3. Generate HTML Animation", command=self.view_animation, state="disabled")
        self.btn_anim.pack(side="left", expand=True, fill="x", padx=(0, 5))
        
        ttk.Label(frame_anim, text="Height Level:").pack(side="left")
        ttk.Spinbox(frame_anim, from_=1, to=10, textvariable=self.viz_level_idx, width=5).pack(side="left", padx=2)

        # Enable visualization buttons immediately if output files already exist
        if os.path.exists("./outputs/final_pareto_front.csv"):
            self.enable_viz_buttons()

    def create_input_row(self, parent, label_text, var, row_idx):
        ttk.Label(parent, text=label_text).grid(row=row_idx, column=0, sticky="w", pady=2)
        ttk.Entry(parent, textvariable=var, width=15).grid(row=row_idx, column=1, sticky="e", pady=2)

    def log(self, message):
        """Prints text to the GUI console."""
        self.console.insert(tk.END, message + "\n")
        self.console.see(tk.END) # Auto-scroll to bottom

    def write_config(self):
        """Writes the GUI parameters to the file Fortran will read."""
        with open("./inputs/config.inp", "w") as f:
            f.write(f"{self.it_max.get()}       ! it_max\n")
            f.write(f"{self.n_pop.get()}       ! n_pop\n")
            f.write(f"{self.p_cross.get()}       ! p_cross\n")
            f.write(f"{self.p_mut.get()}       ! p_mutation\n")
            f.write(f"{self.mu.get()}       ! mu\n")
            f.write(f"{self.max_turbs.get()}       ! max_turbs\n")
            f.write(f"{self.min_turbs.get()}       ! min_turbs\n")
            f.write(f"{self.workability.get()}     ! workability probability")

    def start_optimization(self):
        """Starts the Fortran engine in a background thread."""
        self.btn_run.config(state="disabled")
        self.console.delete(1.0, tk.END)
        self.write_config()
        self.log("Configuration saved. Triggering WSL Bridge...")
        
        # Start thread so GUI doesn't freeze
        thread = threading.Thread(target=self.run_fortran_process)
        thread.start()

    def run_fortran_process(self):
        """Executes the compiled binary natively based on the OS and captures output."""
        try:
            threads = self.num_threads.get()
            is_windows = sys.platform == "win32"
            
            exe_name = "wfo.exe" if is_windows else "./wfo"
            
            # Format the OpenMP command based on the operating system
            if threads == "0" or not threads.isdigit():
                run_cmd = exe_name 
            else:
                if is_windows:
                    run_cmd = f"set OMP_NUM_THREADS={threads} & {exe_name}"
                else:
                    run_cmd = f"export OMP_NUM_THREADS={threads} && {exe_name}"

            # Execute the command natively
            process = subprocess.Popen(
                run_cmd, 
                shell=True,
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True,
                bufsize=1, # Line buffered
                cwd="./source"
            )
            
            for line in process.stdout:
                # Update the GUI safely from the background thread
                self.root.after(0, self.log, line.strip())
                
            process.wait()
            self.root.after(0, self.log, "\n=== OPTIMIZATION COMPLETE ===")
            self.root.after(0, self.enable_viz_buttons)
            
        except Exception as e:
            self.root.after(0, self.log, f"ERROR: {str(e)}")
        finally:
            self.root.after(0, lambda: self.btn_run.config(state="normal"))


    def enable_viz_buttons(self):
        self.btn_pareto.config(state="normal")
        self.btn_3d.config(state="normal")
        self.btn_anim.config(state="normal")

    # --- Visualization Triggers ---
    def view_pareto(self):
        self.log("Generating 2D Pareto PNGs...")
        from source import visualizer
        visualizer.save_pareto_plots()
        self.log("Plots saved. Opening folder...")
        
        # Open the current directory (.) so you can see the generated images
        self.open_file_externally("./outputs")

    def view_3d(self):
        try:
            # Read the index from the Spinbox
            idx = int(self.viz_user_idx.get())
        except ValueError:
            self.log("ERROR: Custom Solution ID must be an integer. Defaulting to 0.")
            idx = 0
            
        self.log(f"Opening PyVista 3D Engine for Solution ID {idx}...")
        
        # Pass the user's chosen index to the visualizer module
        from source import visualizer # Ensure it's pointing to your source folder
        visualizer.generate_3d_comparison(user_idx=idx)

    def view_animation(self):
        try:
            lvl = int(self.viz_level_idx.get())
        except ValueError:
            self.log("ERROR: Height Level must be an integer. Defaulting to 1.")
            lvl = 1
            
        self.log(f"Scanning for animation files for Height Level {lvl}... Please wait.")
        
        from source import visualizer
        
        # Use glob to find all files matching the new objective pattern
        anim_files = glob.glob("./outputs/animation_data_obj_*.csv")
        
        if not anim_files:
            self.log("ERROR: No animation data files found in ./outputs/")
            return
            
        for file_path in anim_files:
            self.log(f"Processing: {os.path.basename(file_path)}")
            
            # NOTE: You will need to slightly update visualizer.generate_html_animation 
            # to accept the file_path as a parameter, so it knows which CSV to read!
            output_file = visualizer.generate_html_animation(file_path=file_path, level_idx=lvl, fast_mode=False)
            
            if output_file:
                self.log(f"Animation saved: {os.path.basename(output_file)}")
                self.open_file_externally(output_file)

    def add_kmls(self):
        """Allows user to pick files and adds them to the visual list."""
        files = filedialog.askopenfilenames(
            title="Select Polygon KML Files",
            filetypes=[("KML Files", "*.kml")]
        )
        for f in files:
            if f not in self.kml_files_list:
                self.kml_files_list.append(f)
                self.kml_listbox.insert(tk.END, os.path.basename(f))
                self.log(f"Added to queue: {os.path.basename(f)}")

    def clear_kmls(self):
        """Clears the KML queue."""
        self.kml_files_list.clear()
        self.kml_listbox.delete(0, tk.END)
        self.log("KML queue cleared.")

    def start_mesh_generation(self):
        """Triggers the mesh generation thread using the queued files."""
        if not self.kml_files_list:
            self.log("ERROR: Please add at least one KML file first.")
            return

        self.btn_mesh.config(state="disabled")
        
        try:
            dx_val = float(self.dx.get())
            dy_val = float(self.dy.get())
        except ValueError:
            self.log("ERROR: dx and dy must be valid numbers.")
            self.btn_mesh.config(state="normal")
            return
            
        # Run in background thread
        threading.Thread(
            target=self._run_mesh_pipeline, 
            args=(self.kml_files_list, dx_val, dy_val), 
            daemon=True
        ).start()

    def _run_mesh_pipeline(self, kml_files, dx, dy):
        """Background thread worker for mesh generation."""
        def safe_log(msg):
            self.root.after(0, self.log, msg)

        metadata = mesh_generator.process_kmls_and_mesh(kml_files, dx, dy, output_callback=safe_log)
        
        if metadata:
            self.mesh_metadata = metadata
            safe_log(f"Saved to Memory -> UTM Zone: {metadata['utm_zone']}, Min X: {metadata['min_x']:.2f}, Min Y: {metadata['min_y']:.2f}")
            safe_log("Mesh files (windfarm_rocol.txt, windfarm_1.plt) are ready for optimization.")
            
        self.root.after(0, lambda: self.btn_mesh.config(state="normal"))

    def select_asc(self):
        """Opens file dialog for GEBCO .asc file."""
        file_path = filedialog.askopenfilename(
            title="Select GEBCO Bathymetry File",
            filetypes=[("ASCII Grid", "*.asc"), ("All Files", "*.*")]
        )
        if file_path:
            self.asc_file = file_path
            # Just show the filename, not the huge path
            self.lbl_asc.config(text=os.path.basename(file_path), foreground="green")
            self.log(f"Selected GEBCO file: {os.path.basename(file_path)}")

    def start_bathymetry(self):
        """Triggers the bathymetry extraction in a background thread."""
        if not self.asc_file:
            self.log("ERROR: Please select a GEBCO .asc file first.")
            return

        self.btn_bathy.config(state="disabled")
        
        # Run in background thread so NumPy doesn't freeze the GUI
        threading.Thread(
            target=self._run_bathy_pipeline, 
            daemon=True
        ).start()

    def _run_bathy_pipeline(self):
        """Background thread worker for bathymetry extraction."""
        def safe_log(msg):
            self.root.after(0, self.log, msg)

        try:
            # Notice we only pass the asc_file and the callback now
            success = bathymetry_generator.process_bathymetry(
                self.asc_file, 
                output_callback=safe_log
            )
        except Exception as e:
            # THIS will catch silent crashes and print them to the GUI!
            import traceback
            safe_log(f"🔴 PYTHON CRASH: {str(e)}")
            safe_log(traceback.format_exc())
        finally:
            self.root.after(0, lambda: self.btn_bathy.config(state="normal"))

    def create_filter_pair(self, parent, var_start, var_end, values, row, col_start):
        """Helper to create two comboboxes for Start and End ranges."""
        vals = ["All"] + values
        cb1 = ttk.Combobox(parent, textvariable=var_start, values=vals, width=5, state="readonly")
        cb1.grid(row=row, column=col_start, padx=2)
        ttk.Label(parent, text=" to ").grid(row=row, column=col_start+1)
        cb2 = ttk.Combobox(parent, textvariable=var_end, values=vals, width=5, state="readonly")
        cb2.grid(row=row, column=col_start+2, padx=2)

    def select_nc_folder(self):
        """Opens folder dialog for NetCDF files."""
        folder_path = filedialog.askdirectory(title="Select Folder containing .nc files")
        if folder_path:
            self.nc_folder = folder_path
            self.lbl_nc.config(text=os.path.basename(folder_path), foreground="green")
            self.log(f"Selected NetCDF folder: {folder_path}")

    def start_wind_generation(self):
        if not self.nc_folder:
            self.log("ERROR: Please select the folder containing your .nc files first.")
            return

        self.btn_wind.config(state="disabled")
        
        # Package the GUI filters into a dictionary
        filters = {
            'h_start': self.f_h_start.get(), 'h_end': self.f_h_end.get(),
            'd_start': self.f_d_start.get(), 'd_end': self.f_d_end.get(),
            'm_start': self.f_m_start.get(), 'm_end': self.f_m_end.get(),
            'y_start': self.f_y_start.get(), 'y_end': self.f_y_end.get()
        }
        
        threading.Thread(
            target=self._run_wind_pipeline, 
            args=(filters,),
            daemon=True
        ).start()

    def _run_wind_pipeline(self, filters):
        def safe_log(msg):
            self.root.after(0, self.log, msg)

        wind_generator.process_wind_data(self.nc_folder, filters, output_callback=safe_log)
        
        self.root.after(0, lambda: self.btn_wind.config(state="normal"))

    def open_file_externally(self, filepath):
        """Safely opens a file or folder in the host OS (handles WSL, Windows, Linux, Mac)."""
        abs_path = os.path.abspath(filepath)
        try:
            # Check if we are running inside WSL
            if 'microsoft' in platform.uname().release.lower() or 'wsl' in platform.uname().release.lower():
                # Translate the Linux path to a Windows path (e.g., /mnt/d/ -> D:\)
                wsl_path_proc = subprocess.run(['wslpath', '-w', abs_path], capture_output=True, text=True)
                
                if wsl_path_proc.returncode == 0:
                    win_path = wsl_path_proc.stdout.strip()
                    subprocess.run(['explorer.exe', win_path])
                else:
                    self.log(f"WARNING: wslpath translation failed for {abs_path}")
            
            # Standard Windows
            elif sys.platform == "win32":
                os.startfile(abs_path)
            
            # Standard Mac
            elif sys.platform == "darwin":
                subprocess.call(["open", abs_path])
            
            # Standard Linux (Ubuntu/Debian UI)
            else:
                subprocess.call(["xdg-open", abs_path])
                
        except Exception as e:
            self.log(f"WARNING: Could not automatically open file/folder. {e}")

    def compile_fast(self):
        """Compiles the Fortran code with maximum optimization (-O3)."""
        self.log("Compiling Fortran (Fast Mode)... please wait.")
        
        # Determine the correct executable name based on the OS
        exe_name = "wfo.exe" if sys.platform == "win32" else "wfo"
        
        cmd = (f"gfortran -O3 -march=native -ffast-math -flto -fopenmp "
               f"WFLOP.f90 -o {exe_name}")
        
        threading.Thread(target=self._run_compiler, args=(cmd,), daemon=True).start()

    def compile_debug(self):
        """Compiles the Fortran code with full bounds checking and backtraces (-g)."""
        self.log("Compiling Fortran (Debug Mode)... please wait.")
        
        exe_name = "wfo.exe" if sys.platform == "win32" else "wfo"
        
        cmd = (f"gfortran -g -fbacktrace -fcheck=all -Wall -Wextra -Og -fopenmp "
               f"WFLOP.f90 -o {exe_name}")
               
        threading.Thread(target=self._run_compiler, args=(cmd,), daemon=True).start()

    def _run_compiler(self, cmd):
        """Background thread worker for compilation."""
        try:
            # shell=True allows us to pass the string directly without WSL wrappers
            process = subprocess.Popen(
                cmd, 
                shell=True,
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True,
                cwd="./source"
            )
            for line in process.stdout:
                self.root.after(0, self.log, f"Compiler: {line.strip()}")
            process.wait()
            
            if process.returncode == 0:
                self.root.after(0, self.log, "Compilation Successful! Ready to Run.")
            else:
                self.root.after(0, self.log, "Compilation FAILED. Check errors above.")
                
        except Exception as e:
            self.root.after(0, self.log, f"ERROR: {str(e)}")

    def select_shoreline(self):
        file_path = filedialog.askopenfilename(title="Select Shoreline KML", filetypes=[("KML Files", "*.kml")])
        if file_path:
            self.shoreline_kml = file_path
            self.lbl_shore.config(text=os.path.basename(file_path), foreground="green")
            self.log(f"Selected Shoreline: {os.path.basename(file_path)}")

    def select_grid(self):
        file_path = filedialog.askopenfilename(title="Select Grid Connection KML", filetypes=[("KML Files", "*.kml")])
        if file_path:
            self.grid_kml = file_path
            self.lbl_grid.config(text=os.path.basename(file_path), foreground="green")
            self.log(f"Selected Grid Point: {os.path.basename(file_path)}")

    def select_port(self):
        file_path = filedialog.askopenfilename(title="Select Port KML", filetypes=[("KML Files", "*.kml")])
        if file_path:
            self.port_kml = file_path
            self.lbl_port.config(text=os.path.basename(file_path), foreground="green")
            self.log(f"Selected Port: {os.path.basename(file_path)}")

    def start_distances(self):
        if not self.shoreline_kml and not self.grid_kml and not self.port_kml:
            self.log("ERROR: Please select at least one KML file to calculate.")
            return
            
        self.btn_dist.config(state="disabled")
        
        def safe_log(msg):
            self.root.after(0, self.log, msg)
            
        def run_calc():
            # Pass all THREE variables to the calculator
            distance_calculator.calculate_site_distances(self.shoreline_kml, self.grid_kml, self.port_kml, output_callback=safe_log)
            self.root.after(0, lambda: self.btn_dist.config(state="normal"))
            
        threading.Thread(target=run_calc, daemon=True).start()

if __name__ == "__main__":
    # Choose your theme here! 'darkly' and 'superhero' are great dark modes. 
    # 'flatly' or 'lumen' are great light modes.
    root = ttk.Window(themename="lumen") 
    
    app = WindFarmGUI(root)
    root.mainloop()