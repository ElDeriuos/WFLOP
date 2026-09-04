import os
import re
import numpy as np
import subprocess
from pyproj import Transformer
import json
import stat
import sys

def calculate_polygon_area(x, y):
    """Calculates polygon area using the Shoelace formula."""
    return 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))

def get_utm_zone_and_epsg(lons, lats):
    """Dynamically calculates the UTM zone based on average longitude."""
    avg_lon = np.mean(lons)
    avg_lat = np.mean(lats)
    utm_zone = int((avg_lon + 180) / 6) + 1
    # 32600 for Northern Hemisphere, 32700 for Southern
    epsg_code = 32600 + utm_zone if avg_lat >= 0 else 32700 + utm_zone
    return utm_zone, f"EPSG:{epsg_code}"

def process_kmls_and_mesh(kml_files, dx, dy, output_callback=print):
    """
    Reads KMLs, converts to UTM, applies offsets, writes Fortran inputs, 
    runs polygon3, and cleans up.
    """
    output_callback("--- Starting Mesh Generation Pipeline ---")
    
    raw_polygons = []
    all_lons = []
    all_lats = []

    # 1. Parse KMLs
    for file in kml_files:
        output_callback(f"Reading: {os.path.basename(file)}")
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
            # Extract text between <coordinates> tags
            match = re.search(r'<coordinates>\s*(.*?)\s*</coordinates>', content, re.DOTALL)
            if not match:
                output_callback(f"  WARNING: No coordinates found in {file}. Skipping.")
                continue
            
            coord_str = match.group(1).strip()
            pts = [pt.split(',') for pt in coord_str.split()]
            
            # Ensure polygon is closed (Google Earth usually closes it, but just in case)
            if pts[0] == pts[-1]:
                pts = pts[:-1] # Remove duplicate closing point for cleaner connectivity
            
            lons = [float(p[0]) for p in pts]
            lats = [float(p[1]) for p in pts]
            
            raw_polygons.append((lons, lats))
            all_lons.extend(lons)
            all_lats.extend(lats)

    if not raw_polygons:
        output_callback("ERROR: No valid polygons extracted. Aborting.")
        return None

    # 2. Determine UTM Zone and Transform
    utm_zone, target_epsg = get_utm_zone_and_epsg(all_lons, all_lats)
    output_callback(f"Calculated Target CRS: {target_epsg} (UTM Zone {utm_zone})")
    
    transformer = Transformer.from_crs("EPSG:4326", target_epsg, always_xy=True)
    
    transformed_polygons = []
    for lons, lats in raw_polygons:
        x_vals, y_vals = transformer.transform(lons, lats)
        transformed_polygons.append({'x': np.array(x_vals), 'y': np.array(y_vals)})

    # 3. Sort by Area to find Macro-Boundary
    for p in transformed_polygons:
        p['area'] = calculate_polygon_area(p['x'], p['y'])
    
    # Sort descending by area: index 0 becomes the macro-boundary
    transformed_polygons.sort(key=lambda p: p['area'], reverse=True)
    output_callback(f"Identified Macro-Boundary (Area: {transformed_polygons[0]['area']:,.0f} m²)")

    # 4. Find Min X / Min Y and apply Offset
    all_x = np.concatenate([p['x'] for p in transformed_polygons])
    all_y = np.concatenate([p['y'] for p in transformed_polygons])
    
    min_x = np.min(all_x)
    min_y = np.min(all_y)
    output_callback(f"Applying Offsets -> Min X: {min_x:.2f}, Min Y: {min_y:.2f}")

    for p in transformed_polygons:
        p['x'] -= min_x
        p['y'] -= min_y

    # 5. Write Fortran Inputs
    mesh_input_file = "xycoordinates.txt"
    
    output_callback("Writing geometry to xycoordinates.txt...")
    total_nodes = sum(len(p['x']) for p in transformed_polygons)
    
    with open(mesh_input_file, 'w', newline='\n') as f:
        f.write(f"{dx} {dy}\n")
        f.write(f"{total_nodes}\n")
        
        # Write all coordinates
        for p in transformed_polygons:
            for x, y in zip(p['x'], p['y']):
                f.write(f"{x:.4f} {y:.4f}\n")
                
        f.write(f"{total_nodes}\n") # Total edges equals total nodes
        
        # Write connectivity
        node_offset = 0
        for p in transformed_polygons:
            n = len(p['x'])
            for i in range(n - 1):
                f.write(f"{node_offset + i + 1} {node_offset + i + 2} 1\n")
            f.write(f"{node_offset + n} {node_offset + 1} 1\n") # Close the loop
            node_offset += n

    # Write BOTH cases and pad them to exactly 80 characters to satisfy Fortran's (80a) read
    for proj_name in ["Polygon_project.txt", "polygon_project.txt"]:
        with open(proj_name, 'w', newline='\n') as f:
            f.write(f"{mesh_input_file:<80}\n")
            f.write(f"{'./inputs/windfarm_rocol.txt':<80}\n")
            f.write(f"{'./outputs/windfarm_1.plt':<80}\n")
            f.write(f"{'windfarm_2.plt':<80}\n")


    if sys.platform == "win32":
        binary_path = './source/polygon3.exe'
        output_callback("Executing polygon3 mesh generator natively in Windows...")
    else:
        binary_path = './source/polygon3'
        output_callback("Executing polygon3 mesh generator natively in Linux/WSL...")
    
    # Give the file executable permissions for the user (Handled gracefully by OS)
    if os.path.exists(binary_path):
        st = os.stat(binary_path)
        os.chmod(binary_path, st.st_mode | stat.S_IEXEC)

    # 6. Execute polygon3 and Cleanup
    try:
        process = subprocess.run(
            [binary_path], 
            check=True, 
            capture_output=True, 
            text=True
        )
        
        output_callback("Mesh generation successful. Temporary files are being preserved.")

        # Temporarily disabled to preserve mesh-generator inputs and outputs for inspection.
        # files_to_remove = [mesh_input_file, 'windfarm_2.plt', 'polygon_project.txt', 't', 't2.dat', 'geom3.dat']
        # for file in files_to_remove:
        #     if os.path.exists(file):
        #         os.remove(file)

        output_callback("--- Mesh Pipeline Complete ---")
        
        
        # Save metadata to a physical file for future modules
        metadata = {
            'utm_zone': int(utm_zone),
            'min_x': float(min_x),
            'min_y': float(min_y)
        }
        with open('./inputs/mesh_metadata.json', 'w') as f:
            json.dump(metadata, f)
            
        return metadata
        
    except FileNotFoundError:
        output_callback("🔴 ERROR: Compiled './source/polygon3' executable not found in this directory.")
        return None
    except subprocess.CalledProcessError as e:
        # EXPOSING THE REAL FORTRAN ERROR TO THE GUI
        output_callback(f"🔴 ERROR: polygon3 failed with exit code {e.returncode}.")
        if e.stdout:
            output_callback(f"Output: {e.stdout.strip()}")
        if e.stderr:
            output_callback(f"Fortran Error Log: {e.stderr.strip()}")
        return None