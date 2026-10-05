"""Static audit of a Linux release bundle (run in CI after PyInstaller).

Fails if any file in the bundle
  * needs a newer glibc or libstdc++ than the oldest supported system has
    (Ubuntu 22.04: GLIBC 2.35, GLIBCXX 3.4.30), or
  * is a library that must come from the user's system (C++ runtime, OpenGL,
    X11, fonts, ...), see SYSTEM_LIBS in wflop.spec.

Usage: python tests/audit_linux_bundle.py dist/WFLOP
"""
import fnmatch
import os
import re
import subprocess
import sys

MAX_VERSIONS = {"GLIBC": (2, 35), "GLIBCXX": (3, 4, 30)}

# Libraries that must come from the user's system; wflop.spec imports this list
SYSTEM_LIBS = [
    "ld-linux*", "libc.so*", "libm.so*", "libdl.so*", "libpthread.so*", "librt.so*",
    "libresolv.so*", "libutil.so*", "libmvec.so*",
    "libstdc++.so*", "libgcc_s.so*", "libobjc.so*",
    "libGL.so*", "libGLX*", "libGLdispatch*", "libOpenGL*", "libEGL*", "libGLES*",
    "libdrm*", "libgbm*", "libglapi*",
    "libX11*", "libxcb.so*", "libxcb-*.so*", "libXau.so*", "libXdmcp*", "libbsd.so*", "libmd.so*", "libXext*",
    "libXrender*", "libXss*", "libXi.*", "libXfixes*", "libXrandr*", "libXcursor*",
    "libXinerama*", "libXcomposite*", "libXdamage*", "libxkbcommon*",
    "libfontconfig*", "libfreetype*", "libharfbuzz*", "libgraphite2*", "libpng16*",
    "libbrotli*", "libexpat*", "libxml2*", "libglib-2.0*", "libpcre2*", "libz.so*", "libuuid*",
]

# auditwheel renames the libraries it vendors into a wheel: libxcb-ad31f5a3.so.1.1.0
WHEEL_COPY_RE = re.compile(r"-[0-9a-f]{8}\.so")

VERSION_RE = re.compile(r"\b(GLIBC|GLIBCXX)_(\d+(?:\.\d+)+)\b")


def is_elf(path):
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"\x7fELF"
    except OSError:
        return False


def required_versions(path):
    out = subprocess.run(["objdump", "-T", path], capture_output=True, text=True).stdout
    found = {}
    for name, ver in VERSION_RE.findall(out):
        v = tuple(int(x) for x in ver.split("."))
        found[name] = max(found.get(name, v), v)
    return found


def audit(bundle):
    problems = []
    for root, _, files in os.walk(bundle):
        for name in files:
            path = os.path.join(root, name)
            rel = os.path.relpath(path, bundle)
            if os.path.islink(path) or not is_elf(path):
                continue
            # Wheel-vendored copies carry a hash (libXau-154567c4.so.6) and are safe
            if not WHEEL_COPY_RE.search(name) and any(fnmatch.fnmatch(name, p) for p in SYSTEM_LIBS):
                problems.append(f"{rel}: system library bundled (must come from the user's system)")
            for lib, ver in required_versions(path).items():
                if ver > MAX_VERSIONS[lib]:
                    need = ".".join(map(str, ver))
                    have = ".".join(map(str, MAX_VERSIONS[lib]))
                    problems.append(f"{rel}: needs {lib} {need} (oldest supported system has {have})")
    return problems


if __name__ == "__main__":
    bundle = sys.argv[1] if len(sys.argv) > 1 else "dist/WFLOP"
    problems = audit(bundle)
    for p in problems:
        print("FAIL", p)
    print(f"{len(problems)} problem(s) in {bundle}")
    sys.exit(1 if problems else 0)
