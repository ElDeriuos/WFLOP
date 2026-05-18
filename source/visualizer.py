import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.tri import Triangulation
import pyvista as pv
import ffmpeg

# =====================================================================
# CONFIGURATION & METADATA
# =====================================================================
TURBINE_META = {
    2: {'name': 'IEA 10MW',  'height': 119.0, 'color': 'blue',   'radius': 15.0, 'marker': 'o'},
    3: {'name': 'IEA 15MW',  'height': 150.0, 'color': 'red',    'radius': 16.0, 'marker': '^'},
    4: {'name': 'NREL 5MW',  'height': 90.0,  'color': 'green',  'radius': 14.0, 'marker': 's'},
    5: {'name': 'DTU 10MW',  'height': 119.0, 'color': 'orange', 'radius': 15.0, 'marker': 'D'},
    6: {'name': 'LEANWIND',  'height': 110.0, 'color': 'purple', 'radius': 14.5, 'marker': 'v'}
}



# =====================================================================
# MODULE 1: PARETO FRONT PLOTTING (Static Images)
# =====================================================================
def _get_moga_objectives():
    """Reads config.inp to dynamically determine the selected objectives."""
    # Maps the Fortran integer ID to: (CSV Column Name, Optimization Direction, Axis Label)
    mapping = {
        1: ('LCOE', 'Minimize', 'Levelized Cost of Energy'), 
        2: ('raw_cost', 'Minimize', 'Total CAPEX (£)'),
        3: ('raw_aep', 'Maximize', 'Annual Energy Production (MWh)'), 
        4: ('raw_fatigue', 'Minimize', 'Total Fatigue Damage')
    }
    try:
        with open('./inputs/config.inp', 'r') as f:
            lines = f.readlines()
            obj1_id = int(lines[9].strip())
            obj2_id = int(lines[10].strip())
            return mapping[obj1_id], mapping[obj2_id]
    except Exception:
        return mapping[2], mapping[3] # Fallback

def save_pareto_plots(output_dir='./outputs'):
    """Reads optimization history and saves Pareto front plots to the dynamic output directory."""
    
    # Construct paths dynamically
    gen_file = os.path.join(output_dir, 'generational_fronts.csv')
    final_file = os.path.join(output_dir, 'final_pareto_front.csv')
    out_evolution = os.path.join(output_dir, 'plot_evolution.png')
    out_final = os.path.join(output_dir, 'plot_final_pareto.png')
    
    if not os.path.exists(gen_file) or not os.path.exists(final_file):
        print("Error: Pareto files not found. Run optimizer first.")
        return False

    print("Generating Pareto Front plots...")
    
    try:
        gen_df = pd.read_csv(gen_file, encoding='utf-8')
        final_df = pd.read_csv(final_file, encoding='utf-8')
    except UnicodeDecodeError:
        print("Warning: UTF-8 decode failed, falling back to default encoding.")
        gen_df = pd.read_csv(gen_file)
        final_df = pd.read_csv(final_file)
    
    # Note: _get_moga_objectives() internally accesses './inputs/config.inp', 
    # so the input directory logic remains structurally intact and separate.
    obj1_info, obj2_info = _get_moga_objectives()
    col1, dir1, _ = obj1_info
    col2, dir2, _ = obj2_info

    def get_axis_label(col_name, direction):
        unit_map = {
            'LCOE': 'Levelized Cost of Energy (£/MWh)',
            'raw_cost': 'Total CAPEX (£)',
            'raw_aep': 'Annual Energy Production (GWh/Year)',
            'raw_fatigue': 'Fatigue Damage Index [-]'
        }
        base_name = unit_map.get(col_name, col_name)
        dir_text = "Lower" if direction == "Minimize" else "Higher"
        return f"{base_name}\n({dir_text} is Better)"

    label1 = get_axis_label(col1, dir1)
    label2 = get_axis_label(col2, dir2)
    short_title = f"{col1.replace('raw_', '').upper()} vs {col2.replace('raw_', '').upper()}"

    # =========================================================
    # PLOT 1: Evolution over generations
    # =========================================================
    # DESIGN: Adjust layout size
    plt.figure(figsize=(10, 6))
    
    # DESIGN: 
    # - cmap: Colormap for the generations. Try 'viridis', 'plasma', 'inferno', 'coolwarm'.
    # - s: Marker size. Increase for larger scatter points.
    # - alpha: Transparency of the points.
    scatter = plt.scatter(gen_df[col1], gen_df[col2], 
                          c=gen_df['generation'], cmap='cividis', alpha=0.7, s=15)
    
    plt.colorbar(scatter, label='Generation Set')
    plt.xlabel(label1)
    plt.ylabel(label2)
    plt.title(f'Evolution of the Pareto Front: {short_title}')
    
    plt.grid(True, linestyle='--', alpha=0.6)
    
    # DESIGN: Adjust dpi to 300+ for high resolution
    plt.savefig(out_evolution, dpi=300, bbox_inches='tight', format='png')
    plt.close()

    # =========================================================
    # PLOT 2: Final Pareto Front
    # =========================================================
    # DESIGN: Adjust layout size
    plt.figure(figsize=(10, 6))
    
    # DESIGN: 
    # - c: Color of the final Pareto optimal points. Accepts names ('blue') or hex codes.
    # - edgecolor: Color of the border around each scatter point (e.g., 'black', 'none').
    # - s: Marker size. Made slightly larger (40) here to emphasize the final front.
    plt.scatter(final_df[col1], final_df[col2], c="#eb4325", label='Optimal Layouts', s=40, edgecolor='black')
    
    plt.title(f'Final Non-Dominated Pareto Front: {short_title}')
    plt.xlabel(label1)
    plt.ylabel(label2)
    plt.grid(True, linestyle='--', alpha=0.6)
    
    # DESIGN: Change legend location using loc='upper right', 'lower left', etc.
    plt.legend()
    
    # DESIGN: Adjust dpi to 300+ for high resolution
    plt.savefig(out_final, dpi=300, bbox_inches='tight', format='png')
    plt.close()
    
    print("✅ Saved evolution and final Pareto plots.")
    return True
# =====================================================================
# MODULE 2: PYVISTA 3D VISUALIZATION
# =====================================================================
def _read_mesh_and_bathymetry():
    """Helper: Parses Fortran mesh and bathymetry files."""
    with open('./inputs/windfarm_rocol.txt', 'r') as f:
        lines = f.readlines()
        
    dx, dy = map(float, lines[0].split()[:2])
    n_rows = int(lines[2].split()[0])
    current_line = 3 + n_rows
    n_cols = int(lines[current_line].split()[0])
    current_line += 1 + n_cols
    n_nodes, n_cells = map(int, lines[current_line].split()[:2])
    current_line += 1
    
    x_coords, y_coords = [], []
    for i in range(n_nodes):
        parts = lines[current_line + i].split()
        x_coords.append(float(parts[0]))
        y_coords.append(float(parts[1]))
        
    with open('./inputs/farm_bathymetry.dat', 'r') as f:
        lines = f.readlines()
    
    z_coords = []
    for i in range(n_nodes):
        parts = lines[9 + i].split()
        z_coords.append(float(parts[2]))
        
    return np.column_stack((x_coords, y_coords, z_coords))

def _get_turbine_dimensions(t_type, turb_path):
    """Helper: Attempts to extract dimensions from file, falls back to defaults."""
    meta = TURBINE_META.get(t_type, {'name': 'Generic', 'height': 120.0, 'color': 'gray'})
    hub_height = meta.get('height', 120.0)
    
    # Mathematical assumption: Rotor diameter is typically ~1.5x to 1.8x the hub height.
    # If we have a specific radius stored, use it. Otherwise approximate based on height.
    rotor_radius = meta.get('radius', hub_height * 0.75) 
    
    # If the user passed a valid file, we could parse it here using pandas.
    # For now, we apply realistic proportionality based on meta data.
    return hub_height, rotor_radius, meta['color'], meta['name']

def _plot_farm_solution(plotter, subplot_index, title, nodes_xyz, genes, z_scale=5.0, turb_path=None):
    """Renders a farm layout with customizable UI elements, Ghost Box framing, and decoupled Z-scaling."""
    plotter.subplot(0, subplot_index)
    
    # ====================================================================
    # DESIGN: HEADER / TITLE
    # ====================================================================
    # - position: 'upper_left', 'upper_right', 'lower_left', 'lower_right', 'upper_edge', 'lower_edge'
    # - font_family: 'arial', 'courier', 'times'
    plotter.add_text(title, 
                     position='upper_edge', 
                     font_size=12, 
                     font='arial', 
                     color='black', 
                     shadow=False)
    
    # Setup Z-Scales
    terrain_z_scale = z_scale * 8.0  
    turbine_z_scale = z_scale        
    
    scaled_nodes = nodes_xyz.copy()
    scaled_nodes[:, 2] = scaled_nodes[:, 2] * terrain_z_scale
    
    cloud = pv.PolyData(scaled_nodes)
    sea_floor = cloud.delaunay_2d()
    
    # ====================================================================
    # DESIGN: BATHYMETRY COLOR BAR (Scalar Bar)
    # ====================================================================
    # Controls the depth legend. Uses fractions of the window (0.0 to 1.0).
    sbar_args = {
        'title': f'True Depth (m) [Exag: {terrain_z_scale}x]',
        'title_font_size': 11,
        'label_font_size': 7,
        'font_family': 'arial',
        'color': 'black',
        'width': 0.3,        # Width of the color bar (8% of screen)
        'height': 0.10,       # Height of the color bar (40% of screen)
        'position_x': 0.65,   # Pushes it to the far right edge
        'position_y': 0.10    # Centers it vertically
    }
    
    plotter.add_mesh(sea_floor, cmap='viridis', scalars=nodes_xyz[:, 2], 
                     show_scalar_bar=True, scalar_bar_args=sbar_args, opacity=0.9)

    legend_entries = []
    added_types = set()

    visual_radius_multiplier = 4.0 

    # Draw Turbines
    for node_idx, t_type in enumerate(genes):
        if t_type > 1 and t_type in TURBINE_META:
            x, y, true_z = nodes_xyz[node_idx]
            hub_height, true_rotor_radius, color, name = _get_turbine_dimensions(t_type, turb_path)
            
            visual_rotor_radius = true_rotor_radius * visual_radius_multiplier
            tower_radius = visual_rotor_radius * 0.10 
            
            base_z = true_z * terrain_z_scale
            scaled_hub_height = hub_height * turbine_z_scale
            
            center_tower_z = base_z + (scaled_hub_height / 2.0)
            hub_z = base_z + scaled_hub_height
            
            tower = pv.Cylinder(center=(x, y, center_tower_z), direction=(0, 0, 1), 
                                radius=tower_radius, height=scaled_hub_height, resolution=20)
            
            rotor = pv.Cylinder(center=(x, y, hub_z), direction=(1, 0, 0), 
                                radius=visual_rotor_radius, height=4.0 * visual_radius_multiplier, resolution=30)
            
            turbine_mesh = tower + rotor
            plotter.add_mesh(turbine_mesh, color=color, smooth_shading=True)

            if t_type not in added_types:
                legend_entries.append([name, color])
                added_types.add(t_type)

    # ====================================================================
    # DESIGN: TURBINE TYPE LEGEND
    # ====================================================================
    if legend_entries:
        # - loc: 'upper right', 'upper left', 'lower left', 'lower right', 'center left', 'center right'
        # - size: (width, height) as a fraction of the window.
        # - bcolor: Background color. Set to None for transparent.
        plotter.add_legend(legend_entries, 
                           loc='upper left', 
                           size=(0.15, 0.12), 
                           bcolor='white', 
                           border=True)

    # ====================================================================
    # DESIGN: 3D AXES AND BOUNDING BOX
    # ====================================================================
    plotter.show_axes() # Shows the small red/green/blue XYZ directional arrows
    
    # - grid: 'front', 'back', 'both'
    # - location: 'outer', 'origin', 'front'
    # - font_family: 'arial', 'courier', 'times'
    plotter.show_bounds(grid='back', 
                        location='outer', 
                        all_edges=True,
                        xtitle='Easting (X)', 
                        ytitle='Northing (Y)', 
                        ztitle='Elevation (Z)',
                        font_size=8, 
                        font_family='arial',
                        color='black')

    plotter.add_light(pv.Light(position=(0, 0, 5000), light_type='scene light'))
    plotter.camera_position = 'iso'
    
    # ====================================================================
    # THE GHOST BOX FIX: Prevent canvas cropping during mouse rotation
    # ====================================================================
    x_min, x_max = nodes_xyz[:, 0].min(), nodes_xyz[:, 0].max()
    y_min, y_max = nodes_xyz[:, 1].min(), nodes_xyz[:, 1].max()
    z_min, z_max = (nodes_xyz[:, 2] * terrain_z_scale).min(), (nodes_xyz[:, 2] * terrain_z_scale).max()
    
    center_x = (x_max + x_min) / 2.0
    center_y = (y_max + y_min) / 2.0
    center_z = (z_max + z_min) / 2.0
    
    max_range = max(x_max - x_min, y_max - y_min, z_max - z_min) / 2.0
    max_range = max_range * 1.10 
    
    ghost_box = pv.Box(bounds=(
        center_x - max_range, center_x + max_range,
        center_y - max_range, center_y + max_range,
        center_z - max_range, center_z + max_range
    ))
    
    plotter.add_mesh(ghost_box, opacity=0.0)
    plotter.reset_camera()

def generate_3d_comparison(user_idx=0, z_scale=5.0, turb_path=None):
    if not os.path.exists('./outputs/final_pareto_front.csv'): return
    nodes_xyz = _read_mesh_and_bathymetry()
    df_pareto = pd.read_csv('./outputs/final_pareto_front.csv')
    obj1_info, obj2_info = _get_moga_objectives()
    col1, dir1, name1 = obj1_info
    col2, dir2, name2 = obj2_info
    best1_idx = df_pareto[col1].idxmin() if dir1 == 'Minimize' else df_pareto[col1].idxmax()
    best2_idx = df_pareto[col2].idxmin() if dir2 == 'Minimize' else df_pareto[col2].idxmax()
    gene_cols = [c for c in df_pareto.columns if 'gene' in c.lower()]
    genes_1 = df_pareto.iloc[best1_idx][gene_cols].astype(int).values
    genes_2 = df_pareto.iloc[best2_idx][gene_cols].astype(int).values

    plotter = pv.Plotter(shape=(1, 2), window_size=[1400, 600]) 
    plotter.set_background('white')
    _plot_farm_solution(plotter, 0, f"Best {name1} (ID: {best1_idx})", nodes_xyz, genes_1, z_scale, turb_path)
    _plot_farm_solution(plotter, 1, f"Best {name2} (ID: {best2_idx})", nodes_xyz, genes_2, z_scale, turb_path)
    plotter.link_views()
    plotter.show()
# =====================================================================
# MODULE 3: MATPLOTLIB ANIMATION
# =====================================================================
def _get_height_mapping():
    """Helper: Maps height level index to physical height."""
    heights_seen = []
    for t_type in sorted(TURBINE_META.keys()):
        h = TURBINE_META[t_type]['height']
        if h not in heights_seen: heights_seen.append(h)
    return {i+1: h for i, h in enumerate(heights_seen)}

def generate_mp4_animation(file_path, level_idx=1, fast_mode=False, frame_step=1, fps=10):
    """Generates an MP4 animation with user-defined frame skipping, FPS, and perfect centering."""
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return None

    import matplotlib as mpl
    import shutil
    
    # Ensure FFmpeg path is set correctly based on your previous fixes
    ffmpeg_exe = shutil.which("ffmpeg")
    if ffmpeg_exe:
        mpl.rcParams['animation.ffmpeg_path'] = ffmpeg_exe

    print(f"Reading animation data from {os.path.basename(file_path)} for Level {level_idx}...")
    df_anim = pd.read_csv(file_path)
    
    # ------------------------------------------------------------------
    # FIX 2: FRAME SKIPPING
    # Take every N-th time step based on the 'frame_step' argument
    # ------------------------------------------------------------------
    all_times = sorted(df_anim['time'].unique())
    times = all_times[::frame_step] 
    
    if fast_mode:
        times = times[:3]
        
    df_anim = df_anim[df_anim['time'].isin(times)]
    print(f"Rendering {len(times)} frames at {fps} FPS (Step: {frame_step})...")

    # Extract layout
    df_pareto = pd.read_csv('./outputs/final_pareto_front.csv')
    obj_num_str = os.path.basename(file_path).replace('.csv', '').split('_')[-1]
    try: obj_idx = int(obj_num_str) - 1
    except ValueError: obj_idx = 0
        
    obj1_info, obj2_info = _get_moga_objectives()
    col, direction, _ = obj1_info if obj_idx == 0 else obj2_info
    best_layout_idx = df_pareto[col].idxmin() if direction == 'Minimize' else df_pareto[col].idxmax()
    
    best_layout = df_pareto.iloc[best_layout_idx]
    genes = best_layout[[c for c in df_pareto.columns if 'gene' in c.lower()]].astype(int).values

    t0_data = df_anim[df_anim['time'] == times[0]].copy().reset_index(drop=True)
    turbines = []
    for node_idx, t_type in enumerate(genes):
        if t_type > 1 and t_type in TURBINE_META:
            turbines.append({
                'x': t0_data.loc[node_idx, 'x'],
                'y': t0_data.loc[node_idx, 'y'],
                'type': t_type,
                'height': TURBINE_META[t_type]['height']
            })
    df_turbines = pd.DataFrame(turbines)

    level_to_height = _get_height_mapping()
    height_val = level_to_height[level_idx]
    u_col, v_col, mag_col = f'u_{level_idx}', f'v_{level_idx}', f'mag_{level_idx}'
    
    # ====================================================================
    # DESIGN: FIGURE SIZE & RESOLUTION
    # ====================================================================
    plt.close('all')
    fig, ax = plt.subplots(figsize=(11, 7), dpi=100)
    ax.set_aspect('equal') # Ensures 1km in X equals 1km in Y visually
    
    # ------------------------------------------------------------------
    # FIX 1 & 5: PERFECT CENTERING AND PADDED BOUNDS (2D Ghost Box)
    # ------------------------------------------------------------------
    x_min, x_max = t0_data['x'].min(), t0_data['x'].max()
    y_min, y_max = t0_data['y'].min(), t0_data['y'].max()
    
    cx, cy = (x_max + x_min) / 2.0, (y_max + y_min) / 2.0
    max_range = max(x_max - x_min, y_max - y_min) / 2.0
    max_range = max_range * 1.15 # Add 15% padding so turbines don't touch the edge
    
    ax.set_xlim(cx - max_range, cx + max_range)
    ax.set_ylim(cy - max_range, cy + max_range)
    
    vmin, vmax = df_anim[mag_col].min(), df_anim[mag_col].max()
    triang = Triangulation(t0_data['x'], t0_data['y'])

    # Plot Static Turbines
    legend_elements = []
    for t_type, meta in TURBINE_META.items():
        subset = df_turbines[df_turbines['type'] == t_type]
        if subset.empty: continue
            
        colors = ['#ff0000' if h == height_val else '#ffffff' for h in subset['height']]
        scatter = ax.scatter(subset['x'], subset['y'], marker=meta['marker'], c=colors, 
                             s=120, edgecolors='#000000', zorder=10, 
                             label=f"{meta['name']} (H={meta['height']}m)")
        legend_elements.append(scatter)

    # ====================================================================
    # DESIGN: TURBINE LEGEND (Location, Size, Color)
    # ====================================================================
    # - loc: Anchors the legend ('upper left', 'upper right', 'center left', etc.)
    # - bbox_to_anchor: (X, Y) coordinates relative to the plot axes (1.0 is the right edge)
    #                   e.g., (1.05, 1.0) puts it strictly outside the top-right corner.
    # - fontsize: Size of the text.
    # - facecolor: Background color of the legend box.
    # - framealpha: Transparency of the background (0.0 to 1.0).
    ax.legend(handles=legend_elements, 
              loc='upper left', 
              bbox_to_anchor=(1.2, 1.0), 
              fontsize=9,
              facecolor='#f8f9fa', 
              edgecolor='black', 
              framealpha=0.9, 
              title="Turbine Types", 
              title_fontsize=11)
              
    # Adjust the main plot area so the legend has room to breathe outside the box
    plt.subplots_adjust(right=0.75, top=0.90)
    
    # ====================================================================
    # DESIGN: COLORBAR LEGEND (Location, Size)
    # ====================================================================
    # - fraction: The fraction of the original axes to use for the colorbar (default ~0.15)
    # - pad: The distance between the colorbar and the main plot.
    # - shrink: Scales the length of the colorbar (e.g., 0.8 makes it 80% as tall).
    # - location: 'right', 'left', 'top', 'bottom'
    sm = plt.cm.ScalarMappable(cmap='viridis', norm=plt.Normalize(vmin, vmax))
    cbar = fig.colorbar(sm, ax=ax, location='right', fraction=0.046, pad=0.04, shrink=0.75)
    
    cbar.set_label('Wind Speed Magnitude [m/s]', size=11, weight='bold', color='black')
    cbar.ax.tick_params(labelsize=10) # Size of the numbers on the bar
    
    title_text = ax.text(0.5, 1.05, '', transform=ax.transAxes, ha='center', fontsize=14, fontweight='bold')
    
    contour_coll = None
    quiver_coll = None
    skip = max(1, len(t0_data) // 300)

    def update(frame_time):
        nonlocal contour_coll, quiver_coll
        frame_data = df_anim[df_anim['time'] == frame_time]
        
        # --- MATPLOTLIB 3.8+ COMPATIBILITY FIX ---
        # Instead of looping through .collections, we remove the object directly.
        if contour_coll: 
            contour_coll.remove()
        if quiver_coll: 
            quiver_coll.remove()
            
        contour_coll = ax.tricontourf(triang, frame_data[mag_col], levels=20, 
                                      cmap='viridis', vmin=vmin, vmax=vmax, zorder=1)
        
        quiver_coll = ax.quiver(frame_data['x'][::skip], frame_data['y'][::skip], 
                                frame_data[u_col][::skip], frame_data[v_col][::skip], 
                                color='white', alpha=0.8, scale_units='xy', zorder=5)
        
        title_text.set_text(f'Wind Field at Height: {height_val}m | Time Step: {int(frame_time)}')
        
        # Since blit=False, the return list doesn't strictly need the contour collections
        return [quiver_coll, title_text]

    print("Compiling video frames (this may take a minute)...")
    ani = animation.FuncAnimation(fig, update, frames=times, interval=300, blit=False, cache_frame_data=False)
    
    # Extract the directory from the file_path we passed in, so it saves in the correct custom folder
    out_dir = os.path.dirname(file_path)
    output_filename = os.path.join(out_dir, f'Animation_Obj_{obj_num_str}_Level_{level_idx}.mp4')
    try:
        # ------------------------------------------------------------------
        # FIX 3: USER-DEFINED FPS
        # Passed via the fps argument down into the ffmpeg writer
        # ------------------------------------------------------------------
        ani.save(output_filename, writer='ffmpeg', fps=fps, dpi=150)
        print(f"✅ Saved: {output_filename}")
        return output_filename
    except Exception as e:
        print(f"🔴 Failed to save MP4: {e}")
        return None
        
# =====================================================================
# MODULE 4: SOGA VISUALIZERS (Single-Objective)
# =====================================================================

def save_soga_convergence_plot(output_dir='./outputs', target_obj="Cost"):
    """Reads SOGA history and saves the convergence plot with dynamic paths and units."""
    
    # Construct paths dynamically based on the user-selected output directory
    csv_file = os.path.join(output_dir, 'soga_convergence.csv')
    out_img = os.path.join(output_dir, 'plot_soga_convergence.png')
    
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found. Run SOGA optimizer first.")
        return False

    print("Generating SOGA Convergence plot...")
    
    try:
        df = pd.read_csv(csv_file, encoding='utf-8')
    except UnicodeDecodeError:
        print("Warning: UTF-8 decode failed, falling back to default encoding.")
        df = pd.read_csv(csv_file)

    target_upper = str(target_obj).upper()
    if "AEP" in target_upper:
        y_label = 'Best Annual Energy Production (GWh/Year)'
        title_obj = 'Maximize AEP'
        df['best_fitness'] = df['best_fitness'].abs() 
    elif "LCOE" in target_upper:
        y_label = 'Levelized Cost of Energy (£/MWh)'
        title_obj = 'Minimize LCOE'
    elif "FATIGUE" in target_upper:
        y_label = 'Total Fatigue Damage (Equivalent Load)'
        title_obj = 'Minimize Fatigue'
    elif "COST" in target_upper or "CAPEX" in target_upper:
        y_label = 'Total Capital Expenditure (£)'
        title_obj = 'Minimize CAPEX'
    else:
        y_label = f'Best Fitness Value ({target_obj})'
        title_obj = target_obj

    # ---------------------------------------------------------
    # DESIGN SETTINGS: Modify the parameters below to style your plot
    # ---------------------------------------------------------
    
    # DESIGN: figsize=(width, height) in inches. Adjust for different aspect ratios.
    plt.figure(figsize=(10, 6))
    
    # DESIGN: 
    # - color: Change the line color (e.g., 'indigo', '#FF5733', 'black').
    # - marker: Change the point shape ('o' for circle, 's' for square, '^' for triangle).
    # - markersize: Increase or decrease the size of the points.
    # - linestyle: Change to '--' for dashed, '-.' for dash-dot, or ':' for dotted.
    plt.plot(df['generation'], df['best_fitness'], marker='o', linestyle='-', color='indigo', markersize=4)
    
    plt.xlabel('Generation Set')
    plt.ylabel(y_label)
    plt.title(f'SOGA Convergence History: {title_obj}')
    
    # DESIGN: alpha controls transparency (0.0 to 1.0). Change linestyle for different grid looks.
    plt.grid(True, linestyle='--', alpha=0.6)
    
    # DESIGN: dpi (Dots Per Inch). 150 is good for screens. Use 300 for academic paper print quality.
    plt.savefig(out_img, dpi=300, bbox_inches='tight', format='png')
    plt.close()
    
    print(f"Saved '{out_img}' successfully.")
    return out_img


def generate_soga_3d_layout(target_obj="Cost", z_scale=5.0, turb_path=None):
    if not os.path.exists('./outputs/soga_best_layout.csv'): return
    nodes_xyz = _read_mesh_and_bathymetry()
    df_best = pd.read_csv('./outputs/soga_best_layout.csv')
    gene_cols = [c for c in df_best.columns if 'gene' in c.lower()]
    genes = df_best.iloc[0][gene_cols].astype(int).values
    fitness_val = abs(df_best.iloc[0]['fitness']) if "AEP" in target_obj else df_best.iloc[0]['fitness']
    
    plotter = pv.Plotter(shape=(1, 1), window_size=[900, 700]) 
    plotter.set_background('white') # Changed to white for better professional contrast
    _plot_farm_solution(plotter, 0, f"SOGA Champion ({target_obj}: {fitness_val:,.2f})", nodes_xyz, genes, z_scale, turb_path)
    plotter.show()

def generate_soga_mp4_animation(file_path='./outputs/animation_data_soga.csv', level_idx=1, frame_step=1, fps=10):
    """Generates an MP4 animation for the SOGA Champion with centering and frame skipping."""
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return None

    import matplotlib as mpl
    import shutil
    
    ffmpeg_exe = shutil.which("ffmpeg")
    if ffmpeg_exe:
        mpl.rcParams['animation.ffmpeg_path'] = ffmpeg_exe

    print(f"Reading SOGA animation data for Level {level_idx}...")
    df_anim = pd.read_csv(file_path)
    
    # Apply user-defined frame skipping
    all_times = sorted(df_anim['time'].unique())
    times = all_times[::frame_step] 
    
    df_anim = df_anim[df_anim['time'].isin(times)]
    print(f"Rendering {len(times)} frames at {fps} FPS (Step: {frame_step})...")

    # Extract layout from SOGA best layout file
    df_best = pd.read_csv('./outputs/soga_best_layout.csv')
    genes = df_best.iloc[0][[c for c in df_best.columns if 'gene' in c.lower()]].astype(int).values

    t0_data = df_anim[df_anim['time'] == times[0]].copy().reset_index(drop=True)
    turbines = []
    for node_idx, t_type in enumerate(genes):
        if t_type > 1 and t_type in TURBINE_META:
            turbines.append({
                'x': t0_data.loc[node_idx, 'x'],
                'y': t0_data.loc[node_idx, 'y'],
                'type': t_type,
                'height': TURBINE_META[t_type]['height']
            })
    df_turbines = pd.DataFrame(turbines)

    level_to_height = _get_height_mapping()
    height_val = level_to_height[level_idx]
    u_col, v_col, mag_col = f'u_{level_idx}', f'v_{level_idx}', f'mag_{level_idx}'
    
    plt.close('all')
    fig, ax = plt.subplots(figsize=(11, 7), dpi=100)
    ax.set_aspect('equal')
    
    # --- PERFECT CENTERING (2D Ghost Box) ---
    x_min, x_max = t0_data['x'].min(), t0_data['x'].max()
    y_min, y_max = t0_data['y'].min(), t0_data['y'].max()
    
    cx, cy = (x_max + x_min) / 2.0, (y_max + y_min) / 2.0
    max_range = max(x_max - x_min, y_max - y_min) / 2.0
    max_range = max_range * 1.15 # 15% padding
    
    ax.set_xlim(cx - max_range, cx + max_range)
    ax.set_ylim(cy - max_range, cy + max_range)
    
    vmin, vmax = df_anim[mag_col].min(), df_anim[mag_col].max()
    triang = Triangulation(t0_data['x'], t0_data['y'])

    legend_elements = []
    for t_type, meta in TURBINE_META.items():
        subset = df_turbines[df_turbines['type'] == t_type]
        if subset.empty: continue
            
        colors = ['#ff0000' if h == height_val else '#ffffff' for h in subset['height']]
        scatter = ax.scatter(subset['x'], subset['y'], marker=meta['marker'], c=colors, 
                             s=120, edgecolors='#000000', zorder=10, 
                             label=f"{meta['name']} (H={meta['height']}m)")
        legend_elements.append(scatter)

    # --- LEGEND FORMATTING ---
    ax.legend(handles=legend_elements, 
              loc='upper left', 
              bbox_to_anchor=(1.05, 1.0), 
              fontsize=10,
              facecolor='#f8f9fa', 
              edgecolor='black', 
              framealpha=0.9, 
              title="Turbine Types", 
              title_fontsize=11)
              
    plt.subplots_adjust(right=0.75, top=0.90)
    
    # --- COLORBAR FORMATTING ---
    sm = plt.cm.ScalarMappable(cmap='viridis', norm=plt.Normalize(vmin, vmax))
    cbar = fig.colorbar(sm, ax=ax, location='right', fraction=0.046, pad=0.04, shrink=0.75)
    cbar.set_label('Wind Speed Magnitude [m/s]', size=11, weight='bold', color='black')
    cbar.ax.tick_params(labelsize=10)
    
    title_text = ax.text(0.5, 1.05, '', transform=ax.transAxes, ha='center', fontsize=14, fontweight='bold')
    
    contour_coll = None
    quiver_coll = None
    skip = max(1, len(t0_data) // 300)

    def update(frame_time):
        nonlocal contour_coll, quiver_coll
        frame_data = df_anim[df_anim['time'] == frame_time]
        
        # --- MATPLOTLIB 3.8+ COMPATIBILITY FIX ---
        # Instead of looping through .collections, we remove the object directly.
        if contour_coll: 
            contour_coll.remove()
        if quiver_coll: 
            quiver_coll.remove()
            
        contour_coll = ax.tricontourf(triang, frame_data[mag_col], levels=20, 
                                      cmap='viridis', vmin=vmin, vmax=vmax, zorder=1)
        
        quiver_coll = ax.quiver(frame_data['x'][::skip], frame_data['y'][::skip], 
                                frame_data[u_col][::skip], frame_data[v_col][::skip], 
                                color='white', alpha=0.8, scale_units='xy', zorder=5)
        
        title_text.set_text(f'Wind Field at Height: {height_val}m | Time Step: {int(frame_time)}')
        
        # Since blit=False, the return list doesn't strictly need the contour collections
        return [quiver_coll, title_text]

    print("Compiling video frames...")
    ani = animation.FuncAnimation(fig, update, frames=times, interval=300, blit=False, cache_frame_data=False)
    
    out_dir = os.path.dirname(file_path)
    output_filename = os.path.join(out_dir, f'Animation_SOGA_Level_{level_idx}.mp4')
    try:
        # Pass the user-defined FPS here
        ani.save(output_filename, writer='ffmpeg', fps=fps, dpi=150)
        print(f"✅ Saved: {output_filename}")
        return output_filename
    except Exception as e:
        print(f"🔴 Failed to save MP4: {e}")
        return None