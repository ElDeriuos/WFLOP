import os
import numpy as np
from pyproj import Transformer
import json

def read_rocol_mesh(file_path, output_callback=print):
    """Parses windfarm_rocol.txt to extract the relative X, Y coordinates of the nodes."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        # Follow the structure of windfarm_rocol.txt to reach the node list
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
            
        return x_coords, y_coords, n_nodes
    except Exception as e:
        output_callback(f"🔴 ERROR reading {file_path}: {e}")
        return None, None, None

def read_asc_header(file_path):
    """Reads the 6-line header of an ESRI ASCII grid file."""
    header = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        for _ in range(6):
            line = f.readline().split()
            header[line[0].lower()] = float(line[1])
    return header

def process_bathymetry(asc_file, output_callback=print):
    """Main pipeline: Reverse projects nodes, queries GEBCO data, and writes the output."""
    rocol_file = './inputs/windfarm_rocol.txt'
    output_file = './inputs/farm_bathymetry.dat'
    metadata_file = './inputs/mesh_metadata.json'
    
    if not os.path.exists(rocol_file):
        output_callback("🔴 ERROR: 'windfarm_rocol.txt' not found. Generate the mesh first.")
        return False
        
    if not os.path.exists(metadata_file):
        output_callback("🔴 ERROR: 'mesh_metadata.json' missing. Generate the mesh first.")
        return False

    output_callback("--- Starting Bathymetry Extraction ---")
    
    # Load the metadata from the file
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)

    # 1. Read relative coordinates from mesh
    output_callback("1. Reading mesh nodes from windfarm_rocol.txt...")
    rel_x, rel_y, n_nodes = read_rocol_mesh(rocol_file, output_callback)
    if not n_nodes:
        return False

    # 2. Reverse Project from UTM back to Lat/Lon (WGS 84)
    output_callback("2. Reverse projecting coordinates to Lat/Lon...")
    # Persian gulf is northern hemisphere, so EPSG base is 32600
    source_epsg = f"EPSG:{32600 + metadata['utm_zone']}" 
    target_epsg = "EPSG:4326" # WGS 84
    
    transformer = Transformer.from_crs(source_epsg, target_epsg, always_xy=True)
    
    abs_x = [x + metadata['min_x'] for x in rel_x]
    abs_y = [y + metadata['min_y'] for y in rel_y]
    lons, lats = transformer.transform(abs_x, abs_y)

    # 3. Load GEBCO ASCII Data
    output_callback(f"3. Reading GEBCO header from {os.path.basename(asc_file)}...")
    header = read_asc_header(asc_file)
    output_callback(f"   Grid Size: {int(header['ncols'])} cols x {int(header['nrows'])} rows")
    
    output_callback("4. Loading massive GEBCO data matrix (This may take 10-30 seconds)...")
    try:
        data_matrix = np.loadtxt(asc_file, skiprows=6)
    except Exception as e:
        output_callback(f"🔴 ERROR loading ASCII matrix: {e}")
        return False

    # 4. Extract Depths
    output_callback("5. Extracting depths for mesh nodes...")
    ncols = int(header['ncols'])
    nrows = int(header['nrows'])
    xll = header['xllcorner']
    yll = header['yllcorner']
    cs = header['cellsize']
    nodata = header['nodata_value']
    y_upper_left = yll + (nrows * cs)

    depths = []
    land_count = 0
    
    for i in range(n_nodes):
        lon = lons[i]
        lat = lats[i]
        
        col_idx = int((lon - xll) / cs)
        row_idx = int((y_upper_left - lat) / cs)
        
        # Check bounds
        if 0 <= col_idx < ncols and 0 <= row_idx < nrows:
            val = data_matrix[row_idx, col_idx]
            # Convert nodata or positive (land) to 0.0
            if val == nodata or val >= 0:
                depths.append(0.0)
                land_count += 1
            else:
                depths.append(val) # Keep negative underwater values
        else:
            # Out of bounds
            depths.append(0.0)
            land_count += 1

    output_callback(f"   Extraction complete. {n_nodes - land_count} underwater nodes, {land_count} land/nodata nodes set to 0.0.")

    # 5. Write to farm_bathymetry.dat
    output_callback(f"6. Writing data to {output_file}...")
    try:
        # Force linux line endings for WSL
        with open(output_file, 'w', newline='\n') as f:
            
            # --- STRICT TECPLOT 9-LINE HEADER ---
            f.write('TITLE="Farm Bathymetry"\n')
            f.write('VARIABLES="X"\n')
            f.write('"Y"\n')
            f.write('"Z"\n')
            f.write('ZONE T="Bathymetry_Data"\n')
            f.write(f'I={n_nodes}\n')
            f.write('J=1\n')
            f.write('K=1\n')
            f.write('F=POINT\n')
            
            # Write Node Data (Relative X, Relative Y, Depth)
            for i in range(n_nodes):
                f.write(f"{rel_x[i]:.4f} {rel_y[i]:.4f} {depths[i]:.4f}\n")
                
        output_callback("✅ SUCCESS: farm_bathymetry.dat is ready for the optimizer and Tecplot!")
        return True
    except Exception as e:
        output_callback(f"🔴 ERROR writing file: {e}")
        return False