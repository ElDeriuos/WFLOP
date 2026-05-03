import os
import json
import numpy as np
import xarray as xr
from datetime import datetime
from pyproj import Transformer

def read_rocol_mesh(filepath):
    """Reads the relative coordinates from the mesh file."""
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
        n_rows = int(lines[2].split()[0])
        current_line = 3 + n_rows
        n_cols = int(lines[current_line].split()[0])
        current_line += 1 + n_cols
        n_nodes = int(lines[current_line].split()[0])
        current_line += 1
        
        rel_x, rel_y = np.zeros(n_nodes), np.zeros(n_nodes)
        for i in range(n_nodes):
            parts = lines[current_line + i].split()
            rel_x[i], rel_y[i] = float(parts[0]), float(parts[1])
        return rel_x, rel_y, n_nodes
    except Exception as e:
        return None, None, None

def apply_cyclic_filter(ds, time_component, start_val, end_val):
    """Applies a time filter that can handle wrap-around loops (e.g. Hour 18 to 4)."""
    if start_val == "All" or end_val == "All" or not start_val or not end_val:
        return ds
        
    s, e = int(start_val), int(end_val)
    
    if time_component == 'hour':
        attr = ds.valid_time.dt.hour
    elif time_component == 'day':
        attr = ds.valid_time.dt.day
    elif time_component == 'month':
        attr = ds.valid_time.dt.month
    elif time_component == 'year':
        attr = ds.valid_time.dt.year
    else:
        return ds

    if s <= e:
        return ds.where((attr >= s) & (attr <= e), drop=True)
    else:
        # Wrap-around logic (e.g., >= 18 OR <= 4)
        return ds.where((attr >= s) | (attr <= e), drop=True)

def process_wind_data(nc_dir, filters, output_callback=print):
    """Main pipeline: Aggregates, filters, interpolates, and writes Fortran wind data."""
    rocol_file = './inputs/windfarm_rocol.txt'
    metadata_file = './inputs/mesh_metadata.json'
    
    # FIX 1: Match the exact filename Fortran expects
    output_file = './inputs/filtered_wind.txt' 
    
    # FIX 2: Lower chunk size to prevent SciPy from hoarding RAM during interpolation
    chunk_size = 1000
    
    if not os.path.exists(rocol_file) or not os.path.exists(metadata_file):
        output_callback("🔴 ERROR: Mesh files missing. Generate the mesh first.")
        return False
        
    output_callback("--- Starting Wind Data Generation ---")
    
    # 1. Load Metadata and Mesh
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
        
    rel_x, rel_y, n_nodes = read_rocol_mesh(rocol_file)
    if n_nodes is None:
        output_callback("🔴 ERROR: Could not parse windfarm_rocol.txt")
        return False

    # 2. Project Coordinates to Lat/Lon for NetCDF Slicing
    output_callback("1. Preparing spatial boundaries...")
    source_epsg = f"EPSG:{32600 + metadata['utm_zone']}"
    transformer = Transformer.from_crs(source_epsg, "EPSG:4326", always_xy=True)
    
    abs_x = [x + metadata['min_x'] for x in rel_x]
    abs_y = [y + metadata['min_y'] for y in rel_y]
    lons, lats = transformer.transform(abs_x, abs_y)
    
    min_lon, max_lon = np.min(lons), np.max(lons)
    min_lat, max_lat = np.min(lats), np.max(lats)

    # 3. Load NetCDF Files (MEMORY OPTIMIZED)
    output_callback(f"2. Scanning directory '{os.path.basename(nc_dir)}' for .nc files...")
    nc_files = sorted([os.path.join(nc_dir, f) for f in os.listdir(nc_dir) if f.endswith('.nc')])
    if not nc_files:
        output_callback("🔴 ERROR: No .nc files found in the selected folder.")
        return False
        
    try:
        datasets = []
        for f in nc_files:
            # FIX 3: Open the dataset and IMMEDIATELY drop everything except u10 and v10.
            # This prevents Sea Surface Temp, Pressure, etc. from eating your RAM.
            d = xr.open_dataset(f, engine='netcdf4')
            if 'u10' in d.data_vars and 'v10' in d.data_vars:
                datasets.append(d[['u10', 'v10']])
            else:
                datasets.append(d) # Fallback just in case
                
        ds = xr.concat(datasets, dim="valid_time")
    except Exception as e:
        output_callback(f"🔴 ERROR: Failed to combine NetCDF files: {e}")
        return False

    # 4. Apply Spatial and Temporal Filters
    output_callback("3. Applying spatial and time-window filters...")
    offset = 0.3
    lat_slice = slice(max_lat + offset, min_lat - offset)
    lon_slice = slice(min_lon - offset, max_lon + offset)
    ds = ds.sel(latitude=lat_slice, longitude=lon_slice)
    
    original_steps = ds.sizes['valid_time']
    
    # Apply Cyclic Filters from GUI
    ds = apply_cyclic_filter(ds, 'hour', filters['h_start'], filters['h_end'])
    ds = apply_cyclic_filter(ds, 'day', filters['d_start'], filters['d_end'])
    ds = apply_cyclic_filter(ds, 'month', filters['m_start'], filters['m_end'])
    ds = apply_cyclic_filter(ds, 'year', filters['y_start'], filters['y_end'])
    
    n_steps = ds.sizes['valid_time']
    if n_steps == 0:
        output_callback("🔴 ERROR: Time filters resulted in 0 valid time steps.")
        return False
        
    output_callback(f"   Filtered from {original_steps} to {n_steps} target time steps.")

    # 5. Interpolate and Write Directly to Fortran Format
    output_callback(f"4. Interpolating and writing {output_file} (Chunk Size: {chunk_size})...")
    
    node_dim = 'node'
    lat_da = xr.DataArray(lats, dims=node_dim, name='latitude')
    lon_da = xr.DataArray(lons, dims=node_dim, name='longitude')

    try:
        with open(output_file, 'w', newline='\n') as f:
            # --- FORTRAN HEADER ---
            f.write("\n\n")
            f.write(f"{n_nodes:12d}{n_steps:12d}\n")
            
            # Write relative coordinates
            for i in range(n_nodes):
                f.write(f"{i+1:12d}{rel_x[i]:16.1f}{rel_y[i]:16.1f}\n")
                
            # --- CHUNKED DATA PROCESSING ---
            num_chunks = int(np.ceil(n_steps / chunk_size))
            global_step = 1
            
            for i in range(num_chunks):
                start_idx = i * chunk_size
                end_idx = min((i + 1) * chunk_size, n_steps)
                
                # Interpolate just this tiny chunk to save RAM
                chunk = ds.isel(valid_time=slice(start_idx, end_idx))
                interp_chunk = chunk.interp(latitude=lat_da, longitude=lon_da, method='linear').load()
                
                # Write time steps for this chunk
                for t_idx in range(len(interp_chunk.valid_time)):
                    f.write(f"{global_step:6d}\n")
                    u10_vals = interp_chunk['u10'].values[t_idx, :]
                    v10_vals = interp_chunk['v10'].values[t_idx, :]
                    
                    for n in range(n_nodes):
                        # Ensure no NaNs crash the Fortran format
                        u = 0.0 if np.isnan(u10_vals[n]) else u10_vals[n]
                        v = 0.0 if np.isnan(v10_vals[n]) else v10_vals[n]
                        f.write(f"{u:8.3f}{v:8.3f}\n")
                        
                    global_step += 1
                    
                output_callback(f"  > Wrote chunk {i+1}/{num_chunks}")
                
        output_callback("✅ SUCCESS: filtered_wind.txt is ready for the optimizer!")
        
        # FIX 4: Explicitly close the datasets to free up Linux RAM
        ds.close()
        for d in datasets:
            d.close()
            
        return True
        
    except Exception as e:
        output_callback(f"🔴 ERROR writing final text file: {e}")
        return False