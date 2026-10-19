#!/usr/bin/env python3
"""
🏔️ Mountain DEM → 3D Print Pipeline
Converts topographic data (GEBCO/SRTM) to printable STL for Prusa MK4S
"""

import os
import sys
import numpy as np
import trimesh
from scipy import ndimage
import subprocess
from pathlib import Path

# Mountain presets (name -> lat, lon, region_size_degrees)
MOUNTAINS = {
    "belchen": {
        "name": "Belchen (Schwarzwald)",
        "lat": 47.91,
        "lon": 7.83,
        "size": 0.2,
        "description": "1414m peak in Black Forest, Germany"
    },
    "mont_blanc": {
        "name": "Mont Blanc (Alps)",
        "lat": 45.83,
        "lon": 6.86,
        "size": 0.3,
        "description": "4808m highest in Alps"
    },
    "matterhorn": {
        "name": "Matterhorn (Alps)",
        "lat": 45.98,
        "lon": 7.66,
        "size": 0.15,
        "description": "4478m iconic pyramidal peak"
    },
    "zugspitze": {
        "name": "Zugspitze (Bavaria)",
        "lat": 47.42,
        "lon": 10.99,
        "size": 0.2,
        "description": "2962m highest in Germany"
    },
}

def print_banner():
    """Display welcome banner"""
    print("""
╔════════════════════════════════════════════════════════════════════╗
║                 🏔️  MOUNTAIN TO 3D PRINT PIPELINE                 ║
║                  Convert DEM → STL → Prusa MK4S                    ║
╚════════════════════════════════════════════════════════════════════╝
    """)

def select_mountain():
    """Interactive mountain selection"""
    print("\n📍 SELECT MOUNTAIN:\n")

    mountains_list = list(MOUNTAINS.items())
    for i, (key, data) in enumerate(mountains_list, 1):
        print(f"  {i}. {data['name']:30} - {data['description']}")

    print(f"  {len(mountains_list)+1}. Custom coordinates")

    while True:
        try:
            choice = int(input(f"\nChoice (1-{len(mountains_list)+1}): "))
            if 1 <= choice <= len(mountains_list):
                key, data = mountains_list[choice-1]
                return data
            elif choice == len(mountains_list) + 1:
                return get_custom_coords()
        except ValueError:
            print("Invalid input")

def get_custom_coords():
    """Get custom lat/lon input"""
    print("\n📍 CUSTOM MOUNTAIN:\n")
    lat = float(input("  Latitude (e.g., 47.91): "))
    lon = float(input("  Longitude (e.g., 7.83): "))
    size = float(input("  Region size in degrees (e.g., 0.2): "))
    name = input("  Mountain name: ")

    return {
        "name": name,
        "lat": lat,
        "lon": lon,
        "size": size,
        "description": "Custom mountain"
    }

def load_dem_data(mountain):
    """Load DEM data (looks for local GEBCO file or prompts download)"""
    print(f"\n📂 LOADING DEM DATA for {mountain['name']}...\n")

    gebco_file = Path("/tmp/gebco_2023.tif")

    if not gebco_file.exists():
        print("⚠️  GEBCO file not found locally")
        print("\nOptions:")
        print("  1. Download manually from: ftp://ftp.soest.hawaii.edu/gdata/gebco/2023/")
        print("  2. Provide path to existing GEBCO/SRTM .tif file")
        print("  3. Use synthetic terrain (no real data)")

        choice = input("\nChoice (1-3): ").strip()

        if choice == "1":
            print("\n⏳ Attempting wget download (may take 5-10 min for 1.5GB)...")
            subprocess.run([
                "wget", "-O", str(gebco_file),
                "ftp://ftp.soest.hawaii.edu/gdata/gebco/2023/gebco_2023.tif"
            ], timeout=600)
        elif choice == "2":
            gebco_file = Path(input("Path to DEM file: "))
            if not gebco_file.exists():
                print(f"❌ File not found: {gebco_file}")
                return None
        else:
            print("ℹ️  Using synthetic terrain (realistic but not real)")
            return "synthetic"

    try:
        import rasterio
        with rasterio.open(gebco_file) as src:
            print(f"✓ Opened {gebco_file.name}")
            print(f"  Dimensions: {src.shape}")
            print(f"  Bounds: {src.bounds}")
            return str(gebco_file)
    except ImportError:
        print("❌ rasterio not installed")
        return None

def generate_mountain_mesh(mountain, dem_file=None):
    """Generate STL mesh from DEM or synthetic terrain"""
    print(f"\n🏔️  GENERATING MESH for {mountain['name']}...\n")

    lat, lon = mountain['lat'], mountain['lon']
    size = mountain['size']

    if dem_file and dem_file != "synthetic":
        # Real DEM data
        try:
            import rasterio
            with rasterio.open(dem_file) as src:
                # Read window for region of interest
                from rasterio.windows import from_bounds
                window = from_bounds(
                    lon - size/2, lat - size/2,
                    lon + size/2, lat + size/2,
                    src.transform
                )
                heights_raw = src.read(1, window=window)
                print(f"✓ Extracted region: {heights_raw.shape}")
        except Exception as e:
            print(f"⚠️  Error loading DEM: {e}, falling back to synthetic")
            dem_file = "synthetic"

    if dem_file == "synthetic":
        # Generate synthetic terrain with REALISTIC Schwarzwald/Alpine features
        resolution = 200  # Higher resolution for detail
        heights_raw = np.ones((resolution, resolution)) * 950

        # REAL Schwarzwald peaks (Belchen region)
        peaks = [
            # (rel_y, rel_x, height_m, sigma_px, prominence)
            (0.50, 0.50, 1414, 35, 350),      # Belchen Hauptgipfel
            (0.55, 0.60, 1347, 25, 180),      # Wiedenköpfle
            (0.40, 0.45, 1380, 28, 200),      # Schwarzwald-Kamm
            (0.65, 0.35, 1165, 22, 150),      # Hochblauen
            (0.30, 0.65, 1290, 20, 140),      # Rotenbüchig
            (0.70, 0.70, 1100, 15, 100),      # Minor peak
            (0.25, 0.35, 1150, 18, 120),      # Ridge
        ]

        for rel_y, rel_x, h, sigma, _ in peaks:
            cy, cx = int(rel_y * resolution), int(rel_x * resolution)
            y, x = np.ogrid[:resolution, :resolution]
            dist = np.sqrt((x-cx)**2 + (y-cy)**2)
            # Realistic Gaussian falloff
            heights_raw += np.exp(-(dist**2)/(2*sigma**2)) * (h - 950)

        # Add REALISTIC multi-scale fractal terrain (Perlin-like)
        np.random.seed(42)
        # Large-scale valleys and ridges
        for scale_factor in [4.0, 2.0, 1.0, 0.5]:
            scale = max(2, int(resolution / scale_factor))
            noise = np.random.randn(scale, scale)
            # Upsample to full resolution
            from scipy.interpolate import RectBivariateSpline
            y_orig = np.linspace(0, 1, scale)
            x_orig = np.linspace(0, 1, scale)
            f = RectBivariateSpline(y_orig, x_orig, noise, kx=1, ky=1)
            y_new = np.linspace(0, 1, resolution)
            x_new = np.linspace(0, 1, resolution)
            noise_upsampled = f(y_new, x_new)
            noise_upsampled = ndimage.gaussian_filter(noise_upsampled, sigma=scale_factor)
            # Amplitude decreases with scale
            heights_raw += noise_upsampled * (120 / scale_factor)

        # Add ridge lines and valleys for natural look
        ridge_y = np.linspace(0, resolution-1, resolution)
        ridge_x = resolution * (0.3 + 0.4 * np.sin(ridge_y / 50))
        for i, (ry, rx) in enumerate(zip(ridge_y, ridge_x)):
            dist_to_ridge = np.abs(np.arange(resolution) - rx)
            if i < len(heights_raw):
                heights_raw[i, :] += (100 / (1 + (dist_to_ridge/15)**2)) - 50

        # Deepen valleys (realistic relief)
        valley_mask = 1 / (1 + np.exp((np.sqrt((np.arange(resolution)[None,:] - resolution/2)**2 +
                                              (np.arange(resolution)[:,None] - resolution/2)**2) - 60)/10))
        heights_raw -= valley_mask * 150

        print(f"  Synthetic: 7 peaks, multi-scale noise, valleys (res={resolution}x{resolution})")

    # Normalize heights
    heights = np.clip(heights_raw, np.nanmin(heights_raw), np.nanmax(heights_raw))
    h_min, h_max = np.nanmin(heights), np.nanmax(heights)
    print(f"  Height range: {h_min:.0f}m - {h_max:.0f}m")

    # Convert to printable 3D coordinates
    resolution = heights.shape[0]
    vertices = []

    # Scale: 100mm print bed, 50mm height
    scale_xy = 100 / size / 111  # mm per degree per km
    scale_z = 50 / (h_max - h_min)  # mm per meter

    for i in range(resolution):
        for j in range(resolution):
            x_mm = (j / resolution) * 100
            y_mm = (i / resolution) * 100
            z_mm = (heights[i, j] - h_min) * scale_z
            vertices.append([x_mm, y_mm, z_mm])

    # Create mesh triangles
    faces = []
    for i in range(resolution - 1):
        for j in range(resolution - 1):
            v00 = i * resolution + j
            v01 = i * resolution + (j + 1)
            v10 = (i + 1) * resolution + j
            v11 = (i + 1) * resolution + (j + 1)
            faces.append([v00, v01, v10])
            faces.append([v01, v11, v10])

    # Create heightfield mesh
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)

    # Solidify: add bottom and sides to close the mesh
    z_min = np.min(heights) - h_min
    vertices_solid = list(vertices)

    # Bottom platform at z=-1mm (base)
    bottom_vertices = []
    for i in range(resolution):
        for j in range(resolution):
            x_mm = (j / resolution) * 100
            y_mm = (i / resolution) * 100
            bottom_vertices.append([x_mm, y_mm, -1.0])

    vertices_solid.extend(bottom_vertices)

    # Add bottom faces (reverse winding for outward normals)
    bottom_offset = len(vertices)
    for i in range(resolution - 1):
        for j in range(resolution - 1):
            v00 = bottom_offset + i * resolution + j
            v01 = bottom_offset + i * resolution + (j + 1)
            v10 = bottom_offset + (i + 1) * resolution + j
            v11 = bottom_offset + (i + 1) * resolution + (j + 1)
            faces.append([v00, v10, v01])
            faces.append([v01, v10, v11])

    # Add side walls (perimeter edges)
    for i in range(resolution - 1):
        # Top edge
        v_top_0 = i * resolution + (resolution - 1)
        v_top_1 = (i + 1) * resolution + (resolution - 1)
        v_bot_0 = bottom_offset + i * resolution + (resolution - 1)
        v_bot_1 = bottom_offset + (i + 1) * resolution + (resolution - 1)
        faces.append([v_top_0, v_bot_0, v_top_1])
        faces.append([v_top_1, v_bot_0, v_bot_1])

        # Left edge
        v_top_0 = i * resolution
        v_top_1 = (i + 1) * resolution
        v_bot_0 = bottom_offset + i * resolution
        v_bot_1 = bottom_offset + (i + 1) * resolution
        faces.append([v_top_0, v_top_1, v_bot_0])
        faces.append([v_top_1, v_bot_1, v_bot_0])

    # Right and bottom edges of grid
    for j in range(resolution - 1):
        # Right edge
        v_top_0 = (resolution - 1) * resolution + j
        v_top_1 = (resolution - 1) * resolution + (j + 1)
        v_bot_0 = bottom_offset + (resolution - 1) * resolution + j
        v_bot_1 = bottom_offset + (resolution - 1) * resolution + (j + 1)
        faces.append([v_top_0, v_top_1, v_bot_0])
        faces.append([v_top_1, v_bot_1, v_bot_0])

        # Bottom edge
        v_top_0 = j
        v_top_1 = j + 1
        v_bot_0 = bottom_offset + j
        v_bot_1 = bottom_offset + (j + 1)
        faces.append([v_top_0, v_bot_0, v_top_1])
        faces.append([v_top_1, v_bot_0, v_bot_1])

    mesh = trimesh.Trimesh(vertices=vertices_solid, faces=faces)

    # Add solid base platform for extra support
    base = trimesh.creation.box(
        extents=[104, 104, 2],
        center=[50, 50, -1]
    )
    mesh = trimesh.util.concatenate([mesh, base])

    print(f"  Mesh: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces (solidifiziert)")
    return mesh

def save_stl(mesh, mountain):
    """Save mesh to STL file"""
    filename = f"{mountain['name'].lower().replace(' ', '_')}_topo.stl"
    filepath = Path("/home/md/git/rc-park/modelle") / filename

    mesh.export(str(filepath))
    size_kb = filepath.stat().st_size / 1024
    print(f"✓ Saved: {filename} ({size_kb:.0f} KB)")
    return filepath

def slice_model(stl_file):
    """Slice STL with PrusaSlicer"""
    print(f"\n🔪 SLICING {stl_file.name}...\n")

    slicer = Path("/home/md/.local/share/PrusaSlicer/squashfs-root/usr/bin/bin/prusa-slicer")
    config = Path("/home/md/.config/PrusaSlicer/mk4s_pla_tag_hohl.ini")
    gcode_file = stl_file.with_suffix(".gcode")

    cmd = [
        str(slicer),
        "--gcode",
        "-o", str(gcode_file),
        "--load", str(config),
        str(stl_file)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

    if result.returncode == 0 and gcode_file.exists():
        size_kb = gcode_file.stat().st_size / 1024
        print(f"✓ G-Code generated: {gcode_file.name} ({size_kb:.0f} KB)")
        return gcode_file
    else:
        print(f"❌ Slicing failed: {result.stderr[:200]}")
        return None

def upload_to_printer(gcode_file):
    """Upload G-Code to Prusa MK4S"""
    print(f"\n📤 UPLOADING TO PRUSA...\n")

    prusa_ip = "192.168.178.55"
    user = "maker"
    passwd = "eNU6xZJ95V9tJxQ"

    cmd = [
        "curl",
        "--digest", "-u", f"{user}:{passwd}",
        "-X", "PUT",
        "-T", str(gcode_file),
        f"http://{prusa_ip}/api/v1/files"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    if "201" in result.stdout or result.returncode == 0:
        print(f"✓ Uploaded to Prusa")
        return True
    else:
        print(f"⚠️  Upload may have failed (HTTP issue)")
        print(f"   File ready at: {gcode_file}")
        return False

def main():
    """Main pipeline"""
    print_banner()

    # Step 1: Select mountain
    mountain = select_mountain()
    print(f"\n✓ Selected: {mountain['name']}")

    # Step 2: Load DEM
    dem_file = load_dem_data(mountain)
    if dem_file is None:
        print("❌ Cannot proceed without DEM data")
        return

    # Step 3: Generate mesh
    mesh = generate_mountain_mesh(mountain, dem_file)

    # Step 4: Save STL
    stl_file = save_stl(mesh, mountain)

    # Step 5: Slice
    gcode_file = slice_model(stl_file)
    if not gcode_file:
        return

    # Step 6: Upload (optional)
    print(f"\n🎯 Upload to Prusa? (y/n): ", end="")
    if input().lower() == "y":
        upload_to_printer(gcode_file)

    print(f"""
╔════════════════════════════════════════════════════════════════════╗
║                        ✅ READY TO PRINT!                          ║
║  {mountain['name']:50}  ║
║  File: {gcode_file.name:50}  ║
║  Size: {gcode_file.stat().st_size/1024:>49.0f} KB  ║
╚════════════════════════════════════════════════════════════════════╝
    """)

if __name__ == "__main__":
    main()
