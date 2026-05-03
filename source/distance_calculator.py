import os
import re
import json
import numpy as np
from pyproj import Transformer

def extract_kml_blocks(file_path):
    """Extracts blocks of coordinates from a KML file."""
    blocks = []
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        matches = re.findall(r'<coordinates>\s*(.*?)\s*</coordinates>', content, re.DOTALL)
        for match in matches:
            coord_str = match.strip()
            pts = [pt.split(',') for pt in coord_str.split()]
            # Extract Lon, Lat
            block = [(float(p[0]), float(p[1])) for p in pts if len(p) >= 2]
            if block:
                blocks.append(np.array(block))
    return blocks

def point_to_segment_distances(p, line_points):
    """Calculates the minimum distance from a single point to a polyline."""
    if len(line_points) == 1:
        return np.linalg.norm(p - line_points[0])
        
    a = line_points[:-1]
    b = line_points[1:]
    
    ab = b - a
    ap = p - a
    
    ab_squared = np.sum(ab**2, axis=1)
    ab_squared[ab_squared == 0] = 1e-8 # Prevent division by zero
    
    # Project point onto the segment and clamp to endpoints [0.0, 1.0]
    t = np.sum(ap * ab, axis=1) / ab_squared
    t = np.clip(t, 0.0, 1.0)
    
    closest = a + t[:, np.newaxis] * ab
    dists = np.linalg.norm(p - closest, axis=1)
    return np.min(dists)

def calculate_site_distances(shoreline_kml, grid_kml, port_kml, output_callback=print):
    """Main pipeline to calculate distance from farm center to shoreline, grid, and port."""
    rocol_file = './inputs/windfarm_rocol.txt'
    metadata_file = './inputs/mesh_metadata.json'
    output_file = './inputs/site_distances.txt' 
    
    if not os.path.exists(rocol_file) or not os.path.exists(metadata_file):
        output_callback("🔴 ERROR: Mesh files missing. Generate the mesh first.")
        return False
        
    output_callback("--- Starting Site Distance Calculations ---")
    
    # 1. Load Metadata
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
        
    # 2. Calculate the Geometric Center of the Wind Farm
    try:
        with open(rocol_file, 'r') as f:
            lines = f.readlines()
            
        n_rows = int(lines[2].split()[0])
        current_line = 3 + n_rows
        n_cols = int(lines[current_line].split()[0])
        current_line += 1 + n_cols
        n_nodes = int(lines[current_line].split()[0])
        current_line += 1
        
        x_coords, y_coords = [], []
        for i in range(n_nodes):
            parts = lines[current_line + i].split()
            x_coords.append(float(parts[0]) + metadata['min_x'])
            y_coords.append(float(parts[1]) + metadata['min_y'])
            
        center_x = np.mean(x_coords)
        center_y = np.mean(y_coords)
        center_point = np.array([center_x, center_y])
        output_callback(f"1. Farm Center (UTM): X={center_x:.1f}, Y={center_y:.1f}")
        
    except Exception as e:
        output_callback(f"🔴 ERROR reading mesh nodes: {e}")
        return False

    # Target CRS Transformer
    source_epsg = "EPSG:4326"
    target_epsg = f"EPSG:{32600 + metadata['utm_zone']}"
    transformer = Transformer.from_crs(source_epsg, target_epsg, always_xy=True)

    # Variables to hold final km values (default to 0.0 if missing)
    shore_km = 0.0
    grid_km = 0.0
    port_km = 0.0 # NEW

    # 3. Calculate Distance to Shoreline
    if shoreline_kml and os.path.exists(shoreline_kml):
        output_callback(f"2. Processing Shoreline: {os.path.basename(shoreline_kml)}")
        blocks = extract_kml_blocks(shoreline_kml)
        if blocks:
            min_shore_dist = float('inf')
            for block in blocks:
                utmx, utmy = transformer.transform(block[:, 0], block[:, 1])
                utm_pts = np.column_stack((utmx, utmy))
                dist = point_to_segment_distances(center_point, utm_pts)
                if dist < min_shore_dist:
                    min_shore_dist = dist
            shore_km = min_shore_dist / 1000.0
            output_callback(f"   => Minimum Shoreline Distance: {shore_km:.2f} km")

    # 4. Calculate Distance to Grid Connection
    if grid_kml and os.path.exists(grid_kml):
        output_callback(f"3. Processing Grid Point: {os.path.basename(grid_kml)}")
        blocks = extract_kml_blocks(grid_kml)
        if blocks:
            min_grid_dist = float('inf')
            for block in blocks:
                utmx, utmy = transformer.transform(block[:, 0], block[:, 1])
                utm_pts = np.column_stack((utmx, utmy))
                dist = point_to_segment_distances(center_point, utm_pts)
                if dist < min_grid_dist:
                    min_grid_dist = dist
            grid_km = min_grid_dist / 1000.0
            output_callback(f"   => Distance to Grid Connection: {grid_km:.2f} km")

    # 5. Calculate Distance to Nearest Port (NEW)
    if port_kml and os.path.exists(port_kml):
        output_callback(f"4. Processing Port Point: {os.path.basename(port_kml)}")
        blocks = extract_kml_blocks(port_kml)
        if blocks:
            min_port_dist = float('inf')
            for block in blocks:
                utmx, utmy = transformer.transform(block[:, 0], block[:, 1])
                utm_pts = np.column_stack((utmx, utmy))
                dist = point_to_segment_distances(center_point, utm_pts)
                if dist < min_port_dist:
                    min_port_dist = dist
            port_km = min_port_dist / 1000.0
            output_callback(f"   => Distance to Nearest Port: {port_km:.2f} km")

    # 6. Write data to file for Fortran
    try:
        with open(output_file, 'w', newline='\n') as f:
            # Write shoreline, grid, and port distances (space separated)
            f.write(f"{shore_km:.3f} {grid_km:.3f} {port_km:.3f}\n")
        output_callback(f"✅ Saved distances to {output_file} for the optimizer.")
    except Exception as e:
        output_callback(f"🔴 ERROR writing distances file: {e}")
        return False

    output_callback("--- Distance Calculations Complete ---")
    return True