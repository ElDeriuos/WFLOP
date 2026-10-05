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
    # Only VTK's own modules are candidates; any other library shipped in the
    # folder (platform runtimes, third-party DLLs) is always kept
    m = _VTK_STEM.match(parts[-1])
    if m is None or not m.group(1).startswith(("vtk", "viskores")):
        return True
    return m.group(1) in VTK_KEEP


a.binaries = [b for b in a.binaries if _keep_binary(b[0])]

# Linux: which system libraries may be bundled. Libraries from wheels
# (site-packages) are built to run on any Linux and are always kept. Libraries
# PyInstaller takes from the build machine's own system (Ubuntu 22.04 in CI) are
# kept only if listed in BUNDLE_LIBS; those in SYSTEM_LIBS must come from the
# user's system instead, because they are tied to its GPU driver and desktop
# (e.g. bundling Ubuntu's old libstdc++ made Fedora's Mesa driver fail and the
# 3D viewer crash). Any other system library stops the build, so a new
# dependency needs a deliberate decision. tests/audit_linux_bundle.py checks the
# result in CI.
if sys.platform.startswith("linux"):
    import fnmatch
    sys.path.insert(0, os.path.join(SPECPATH, "tests"))
    from audit_linux_bundle import SYSTEM_LIBS, WHEEL_COPY_RE

    BUNDLE_LIBS = [
        # Python itself and its built-in modules
        "libpython3*", "*.cpython-3*-*.so",
        # Tk with Xft (anti-aliased GUI text)
        "libtcl*", "libtk*", "libtommath*", "libXft*",
        # Python's own dependencies, whose versions differ between distributions
        "libffi*", "libmpdec*", "libsqlite3*", "libssl*", "libcrypto*", "libreadline*",
        "libtinfo*", "libbz2*", "liblzma*", "libzstd*",
    ]

    def _matches(name, patterns):
        return any(fnmatch.fnmatch(name, p) for p in patterns)

    kept, unclassified = [], []
    for entry in a.binaries:
        name, src = os.path.basename(entry[0]), entry[1]
        if "site-packages" in src.split(os.sep) or WHEEL_COPY_RE.search(name):
            kept.append(entry)
        elif _matches(name, SYSTEM_LIBS):
            continue
        elif _matches(name, BUNDLE_LIBS):
            kept.append(entry)
        else:
            unclassified.append(src)
    if unclassified:
        raise SystemExit("Unclassified system libraries (add each to BUNDLE_LIBS in wflop.spec "
                         "or SYSTEM_LIBS in tests/audit_linux_bundle.py):\n  " + "\n  ".join(unclassified))
    a.binaries = kept

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WFLOP",
    console=False,
)

coll = COLLECT(exe, a.binaries, a.datas, name="WFLOP")

# Linux VTK libraries carry full symbol tables (libvtkCommonCore: 150 MB -> 87 MB
# stripped). Only vtkmodules is stripped: the libraries auditwheel vendored into
# numpy.libs/scipy.libs were rewritten by patchelf, and older binutils (Ubuntu
# 22.04) corrupt those when stripping ("ELF load command ... not page-aligned").
# Not on macOS (would invalidate code signatures) or Windows (no symbols in DLLs).
if sys.platform.startswith("linux"):
    import glob
    import subprocess
    vtk_dir = os.path.join(DISTPATH, "WFLOP", "_internal", "vtkmodules")
    for lib in glob.glob(os.path.join(vtk_dir, "*.so*")):
        subprocess.run(["strip", "--strip-unneeded", lib], check=True)

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
