import os
import json
import numpy as np
import xarray as xr
from pyproj import Transformer
from scipy.stats import weibull_min

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


def safe_interp(ds, method='cubic', **indexers):
    """Perform xarray interpolation with fallback when cubic is unsupported."""
    if method == 'cubic':
        needs_fallback = any(ds.sizes.get(dim, 0) < 4 for dim in indexers)
        if needs_fallback:
            return ds.interp(method='linear', **indexers)
    return ds.interp(method=method, **indexers)


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

    if filters.get('mode') == "Wind Rose Binning":
        output_callback("Executing Probabilistic Wind Rose Binning Core...")

        # 1. Compute Geometric Center Coordinates
        center_lon = float(np.mean(lons))
        center_lat = float(np.mean(lats))
        output_callback(f"   Wind Farm Geographic Center: Lon={center_lon:.4f}, Lat={center_lat:.4f}")

        # 2. Execute High-Order Bicubic Interpolation for Target Coordinate Point
        output_callback("   Performing 2D Bicubic Spline space-time interpolation...")
        ds_center = safe_interp(ds, latitude=center_lat, longitude=center_lon, method='cubic').load()

        u10 = ds_center['u10'].values
        v10 = ds_center['v10'].values

        # 3. Derive Vector Magnitudes and Meteorological Angles
        ws = np.sqrt(u10**2 + v10**2)
        # Correct Meteorological Wind Direction (direction FROM which wind blows: 0°=N, 90°=E, 180°=S, 270°=W)
        # Using (-u10, -v10) reverses the flow vector to point toward the wind source.
        wd_deg = np.degrees(np.arctan2(-u10, -v10)) % 360.0

        # 4. Resolve True North Wrap-Around Boundary Conditions
        n_sectors = int(filters.get('dir_bins', 12))
        delta_dir = 360.0 / n_sectors
        shifted_wd = (wd_deg + (delta_dir / 2.0)) % 360.0

        # Define contiguous structural bins for direction and velocity
        vel_step = float(filters.get('vel_step', 1.0))
        max_ws = np.max(ws)
        speed_bins = np.arange(0, max_ws + vel_step * 2, vel_step)
        dir_bins = np.arange(0, 360.0 + delta_dir, delta_dir)

        # 5. Generate Empirical Joint Probability Mass Grid
        counts, _, _ = np.histogram2d(shifted_wd, ws, bins=[dir_bins, speed_bins])
        prob_matrix = counts / len(ws)

        # 6. Fit continuous parametric profile via Maximum Likelihood Estimation
        output_callback("   Fitting continuous 2-parameter Weibull distribution profiles...")
        shape_k, _, scale_c = weibull_min.fit(ws, floc=0)
        output_callback(f"   MLE Results -> Shape (k): {shape_k:.4f}, Scale (c): {scale_c:.4f} m/s")

        # 7. Serialize Structural Analytics Output for visualizer.py
        # High-resolution frequency tally optimized to match Weibull curve overlays cleanly
        hist_counts, hist_edges = np.histogram(ws, bins='auto', density=True)

        analytics_payload = {
            "weibull_k": float(shape_k),
            "weibull_c": float(scale_c),
            "sector_width": float(delta_dir),
            "dir_centers": [float(i * delta_dir) for i in range(n_sectors)],
            "speed_centers": [float(v) for v in (speed_bins[:-1] + vel_step / 2.0)],
            "joint_probabilities": prob_matrix.tolist(),
            "hist_density": hist_counts.tolist(),
            "hist_edges": hist_edges.tolist()
        }

        analytics_path = os.path.join(os.path.dirname(output_file), 'wind_analytics.json')
        with open(analytics_path, 'w', encoding='utf-8') as jf:
            json.dump(analytics_payload, jf, indent=4)

        # 8. Export Discrete State Matrix Document tailored for Modern Fortran Core
        # File contains: Total active bins on line 1, followed by: midpoint_wd, midpoint_ws, probability
        active_bins = []
        for i in range(n_sectors):
            wd_mid = float(i * delta_dir)
            for j in range(len(speed_bins) - 1):
                ws_mid = float(speed_bins[j] + vel_step / 2.0)
                p_val = float(prob_matrix[i, j])
                if p_val > 1e-6: # Memory compression: drop zero-probability environmental states
                    active_bins.append((wd_mid, ws_mid, p_val))

        rose_output_path = os.path.join(os.path.dirname(output_file), 'wind_rose_matrix.dat')
        with open(rose_output_path, 'w', newline='\n') as rf:
            rf.write(f"{len(active_bins):12d}\n")
            for item in active_bins:
                rf.write(f"{item[0]:10.2f}{item[1]:10.2f}{item[2]:12.6f}\n")

        output_callback(f"SUCCESS: Statistical profiles generated. Matrix saved to '{os.path.basename(rose_output_path)}'.")

        # Explicit resource termination to clear RAM buffers under Linux/WSL runtime environments
        ds.close()
        for d in datasets:
            d.close()
        return True

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
