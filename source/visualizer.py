import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.tri import Triangulation
import pyvista as pv

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
def save_pareto_plots(gen_file='./outputs/generational_fronts.csv', 
                      final_file='./outputs/final_pareto_front.csv'):
    """Reads optimization history and saves convergence plots as PNG images."""
    if not os.path.exists(gen_file) or not os.path.exists(final_file):
        print("Error: Pareto files not found. Run optimizer first.")
        return False

    print("Generating Pareto Front plots...")
    gen_df = pd.read_csv(gen_file)
    final_df = pd.read_csv(final_file)

    # Plot 1: Evolution over generations
    plt.figure(figsize=(10, 6))
    scatter = plt.scatter(gen_df['cost_obj1'], gen_df['aep_obj2'], 
                          c=gen_df['generation'], cmap='cividis', alpha=0.7, s=20)
    plt.colorbar(scatter, label='Generation')
    plt.xlabel('Financial Cost (Great British Pound)')
    plt.ylabel('Annual Energy Production (MWh)')
    plt.title('Evolution of the Pareto Front')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.savefig('./outputs/plot_evolution.png', dpi=150, bbox_inches='tight')
    plt.close()

    # Plot 2: Final Pareto Front
    plt.figure(figsize=(10, 6))
    plt.scatter(final_df['cost_obj1'], final_df['aep_obj2'], c='blue', label='Optimal Solutions')
    plt.title('Final Pareto Front: Cost vs. AEP')
    plt.xlabel('Normalized Financial Cost (Lower is Better)')
    plt.ylabel('Annual Energy Production (MWh, Higher is Better)')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend()
    plt.savefig('./outputs/plot_final_pareto.png', dpi=150, bbox_inches='tight')
    plt.close()
    
    print("Saved 'plot_evolution.png' and 'plot_final_pareto.png'.")
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

def _plot_farm_solution(plotter, subplot_index, title, nodes_xyz, genes):
    """Helper: Renders a single farm layout in a PyVista subplot."""
    plotter.subplot(0, subplot_index)
    plotter.add_text(title, font_size=12, color='black', shadow=False)
    
    cloud = pv.PolyData(nodes_xyz)
    sea_floor = cloud.delaunay_2d()
    plotter.add_mesh(sea_floor, cmap='ocean', scalars=nodes_xyz[:, 2], 
                     show_scalar_bar=True, scalar_bar_args={'title': 'Depth (m)'}, opacity=0.85)

    legend_entries = []
    added_types = set()

    for node_idx, t_type in enumerate(genes):
        if t_type > 1 and t_type in TURBINE_META:
            x, y, z = nodes_xyz[node_idx]
            meta = TURBINE_META[t_type]
            center_z = z + (meta['height'] / 2.0)
            
            tower_mesh = pv.Cylinder(center=(x, y, center_z), direction=(0, 0, 1), 
                                     radius=meta['radius'], height=meta['height'], resolution=40)
            
            plotter.add_mesh(tower_mesh, color=meta['color'], smooth_shading=True)

            if t_type not in added_types:
                legend_entries.append([meta['name'], meta['color']])
                added_types.add(t_type)

    if legend_entries:
        plotter.add_legend(legend_entries, bcolor='white', border=True, size=(0.25, 0.25), loc='upper right')

    plotter.show_axes()
    plotter.show_bounds(grid='front', location='outer', all_edges=True,
                        xtitle='Easting (X)', ytitle='Northing (Y)', ztitle='Elevation (Z)',
                        font_size=10, color='black')

    plotter.add_light(pv.Light(position=(0, 0, 5000), light_type='scene light'))
    plotter.camera_position = 'iso'
    plotter.set_scale(zscale=10.0)

def generate_3d_comparison(user_idx=0):
    """Generates a 1x3 interactive 3D PyVista window."""
    if not os.path.exists('./outputs/final_pareto_front.csv'):
        print("Error: final_pareto_front.csv not found.")
        return

    print("Rendering 3D Scene...")
    nodes_xyz = _read_mesh_and_bathymetry()
    df_pareto = pd.read_csv('./outputs/final_pareto_front.csv')
    
    best_cost_idx = df_pareto['cost_obj1'].idxmin()
    best_aep_idx = df_pareto['aep_obj2'].idxmax() 
    
    gene_cols = [c for c in df_pareto.columns if 'gene' in c.lower()]
    genes_cost = df_pareto.iloc[best_cost_idx][gene_cols].astype(int).values
    genes_aep = df_pareto.iloc[best_aep_idx][gene_cols].astype(int).values
    genes_user = df_pareto.iloc[user_idx][gene_cols].astype(int).values

    plotter = pv.Plotter(shape=(1, 3), window_size=[1800, 600]) # Resized for standard monitors
    plotter.set_background('grey')

    _plot_farm_solution(plotter, 0, f"Lowest Cost (ID: {best_cost_idx})", nodes_xyz, genes_cost)
    _plot_farm_solution(plotter, 1, f"Highest AEP (ID: {best_aep_idx})", nodes_xyz, genes_aep)
    _plot_farm_solution(plotter, 2, f"User Selection (ID: {user_idx})", nodes_xyz, genes_user)

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

def generate_html_animation(file_path, level_idx=1, fast_mode=False):
    """Generates an interactive HTML animation file for a specific height level."""
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return None

    print(f"Reading animation data from {os.path.basename(file_path)} for Level {level_idx}...")
    df_anim = pd.read_csv(file_path)
    times = sorted(df_anim['time'].unique())
    
    if fast_mode:
        times = times[:3]
        df_anim = df_anim[df_anim['time'].isin(times)]
        print(f"Fast Mode ON: Rendering only {len(times)} frames.")

    # Extract layout
    df_pareto = pd.read_csv('./outputs/final_pareto_front.csv')
    
    # Extract the objective number from the filename (e.g. "animation_data_obj_1.csv" -> "1")
    obj_num_str = os.path.basename(file_path).replace('.csv', '').split('_')[-1]
    try:
        obj_idx = int(obj_num_str) - 1 # Python uses 0-based indexing for columns
    except ValueError:
        obj_idx = 0 # Default fallback
        
    # THE FIX: Cost is Minimized (idxmin), but positive AEP is Maximized (idxmax)
    if obj_idx == 0:
        best_layout_idx = df_pareto.iloc[:, 0].idxmin() # Lowest Cost
    elif obj_idx == 1:
        best_layout_idx = df_pareto.iloc[:, 1].idxmax() # Highest AEP
    else:
        # Fallback for any future objectives (assuming minimization)
        best_layout_idx = df_pareto.iloc[:, obj_idx].idxmin() 
        
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
    
    print(f"Building Animation Figure ({height_val}m)...")
    plt.close('all')
    fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
    ax.set_aspect('equal')
    
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

    ax.legend(handles=legend_elements, loc='center left', bbox_to_anchor=(1.05, 0.5))
    plt.subplots_adjust(right=0.75)
    
    cbar = fig.colorbar(plt.cm.ScalarMappable(cmap='viridis', norm=plt.Normalize(vmin, vmax)), ax=ax)
    cbar.set_label('Wind Speed Magnitude [m/s]')
    
    title_text = ax.text(0.5, 1.05, '', transform=ax.transAxes, ha='center', fontsize=14, fontweight='bold')
    
    contour_coll = None
    quiver_coll = None
    skip = max(1, len(t0_data) // 300)

    def update(frame_time):
        nonlocal contour_coll, quiver_coll
        frame_data = df_anim[df_anim['time'] == frame_time]
        
        if contour_coll: contour_coll.remove()
        if quiver_coll: quiver_coll.remove()
            
        contour_coll = ax.tricontourf(triang, frame_data[mag_col], levels=20, 
                                      cmap='viridis', vmin=vmin, vmax=vmax, zorder=1)
        
        quiver_coll = ax.quiver(frame_data['x'][::skip], frame_data['y'][::skip], 
                                frame_data[u_col][::skip], frame_data[v_col][::skip], 
                                color='white', alpha=0.8, scale_units='xy', zorder=5)
        
        title_text.set_text(f'Wind Field at Height: {height_val}m | Time Step: {int(frame_time)}')
        return ax.collections + [title_text]

    print("Compiling video frames...")
    ani = animation.FuncAnimation(fig, update, frames=times, interval=300, blit=False)
    
    # Save with a dynamic filename so objectives don't overwrite each other
    output_filename = f'./outputs/Animation_Obj_{obj_num_str}_Level_{level_idx}.html'
    with open(output_filename, 'w') as f:
        f.write(ani.to_jshtml())
        
    print(f"Saved: {output_filename}")
    return output_filename