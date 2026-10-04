# PyInstaller spec for the standalone WFLOP GUI.
#
# Build (from the repository root, after `make all`):
#     uv run pyinstaller wflop.spec --noconfirm
#
# Result: dist/WFLOP/ containing the WFLOP executable plus the inputs/,
# outputs/, source/ and build/ folders the app reads and writes at runtime.

import os
import re
import shutil
import sys

from PyInstaller.utils.hooks import collect_all, collect_data_files

datas = collect_data_files("customtkinter")
binaries = []
hiddenimports = ["netCDF4", "cftime", "scipy.interpolate", "scipy.stats"]

for pkg in ("pyproj", "xarray"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["main.py"],
    pathex=[SPECPATH],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "hypothesis", "fortls"],
)

# VTK: the wheel ships ~630 MB of libraries, but the 3D viewer only loads the
# modules below (recorded from /proc/<pid>/maps while the viewers ran onscreen
# and offscreen). Everything else in vtkmodules is dropped. `WFLOP --self-test`
# renders with the real viewer code, so a missing module fails the release build.
VTK_KEEP = {
    "vtkChartsCore", "vtkCommonColor", "vtkCommonComputationalGeometry", "vtkCommonCore",
    "vtkCommonDataModel", "vtkCommonExecutionModel", "vtkCommonMath", "vtkCommonMisc",
    "vtkCommonSystem", "vtkCommonTransforms", "vtkDICOMParser", "vtkFiltersCellGrid",
    "vtkFiltersCore", "vtkFiltersExtraction", "vtkFiltersGeneral", "vtkFiltersGeometry",
    "vtkFiltersHybrid", "vtkFiltersHyperTree", "vtkFiltersModeling", "vtkFiltersPython",
    "vtkFiltersReduction", "vtkFiltersSources", "vtkFiltersStatistics", "vtkFiltersTexture",
    "vtkFiltersVerdict", "vtkIOCellGrid", "vtkIOCore", "vtkIOImage", "vtkIOLegacy",
    "vtkIOXML", "vtkIOXMLParser", "vtkImagingColor", "vtkImagingCore", "vtkImagingGeneral",
    "vtkImagingHybrid", "vtkImagingMath", "vtkImagingSources", "vtkInfovisCore",
    "vtkInteractionStyle", "vtkInteractionWidgets", "vtkParallelCore", "vtkParallelDIY",
    "vtkPythonContext2D", "vtkRenderingAnnotation", "vtkRenderingContext2D",
    "vtkRenderingCore", "vtkRenderingFreeType", "vtkRenderingHyperTreeGrid",
    "vtkRenderingMatplotlib", "vtkRenderingOpenGL2", "vtkRenderingUI", "vtkRenderingVolume",
    "vtkRenderingVolumeOpenGL2", "vtkViewsContext2D", "vtkViewsCore",
    "vtkWrappingPythonCore", "vtkexpat", "vtkfmt", "vtkfreetype", "vtkglad", "vtkjpeg",
    "vtkkissfft", "vtkloguru", "vtklz4", "vtklzma", "vtkmetaio", "vtkpng", "vtkpugixml",
    "vtkscn", "vtksys", "vtktiff", "vtktoken", "vtkverdict", "vtkx11", "vtkzlib",
}
_VTK_STEM = re.compile(r"^(?:lib)?([A-Za-z][A-Za-z0-9_]*?)(?:\d\.\d+)?(?:-[\d.]+)?\.(?:cpython|cp\d|so|dll|pyd|dylib)")


def _keep_binary(dest):
    parts = dest.replace("\\", "/").split("/")
    if "vtkmodules" not in parts:
        return True
    m = _VTK_STEM.match(parts[-1])
    return m is None or m.group(1) in VTK_KEEP


a.binaries = [b for b in a.binaries if _keep_binary(b[0])]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WFLOP",
    console=False,
)

# Linux libraries ship with debug symbols (libvtkCommonCore: 150 MB -> 87 MB stripped).
# Not on macOS (would invalidate code signatures) or Windows (no symbols in DLLs).
coll = COLLECT(exe, a.binaries, a.datas, strip=sys.platform.startswith("linux"), name="WFLOP")

# ---------------------------------------------------------------------------
# Runtime folders: the app works relative to its own folder (see main.py).
# ---------------------------------------------------------------------------
app_dir = os.path.join(DISTPATH, "WFLOP")
root = SPECPATH
win = sys.platform == "win32"
ext = ".exe" if win else ""

# inputs/: turbine catalogue, sample KMLs and bathymetry (not generated files)
inputs_dst = os.path.join(app_dir, "inputs")
for sub in ("Turbines", "kmlfiles", "raw_bathymetry"):
    shutil.copytree(os.path.join(root, "inputs", sub), os.path.join(inputs_dst, sub), dirs_exist_ok=True)
shutil.copy2(os.path.join(root, "inputs", "turbine_spec.txt"), inputs_dst)

os.makedirs(os.path.join(app_dir, "outputs"), exist_ok=True)

# source/: Fortran sources, for the GUI's Compile buttons
src_dst = os.path.join(app_dir, "source")
os.makedirs(src_dst, exist_ok=True)
for name in ("wflop_core.f90", "main_soga.f90", "main_moga.f90",
             "simulation.f90", "main_simulator.f90", "polygon3.for"):
    shutil.copy2(os.path.join(root, "source", name), src_dst)

# build/: prebuilt programs, where the GUI runs them from
build_dst = os.path.join(app_dir, "build")
os.makedirs(build_dst, exist_ok=True)
for name in ("soga_optimizer", "moga_optimizer", "simulator", "polygon3"):
    src = os.path.join(root, "build", name + ext)
    if os.path.exists(src):
        shutil.copy2(src, build_dst)
    else:
        print(f"WARNING: {src} not found; run `make all` first. "
              f"The app will ask the user to compile it.")

for doc in ("README.md", "LICENSE"):
    shutil.copy2(os.path.join(root, doc), app_dir)
