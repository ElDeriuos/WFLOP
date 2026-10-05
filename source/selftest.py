"""`WFLOP --self-test`: checks that a (bundled) install works without any
prerequisites. Used by the release workflow on every platform; exits non-zero
on the first failure and writes the report to selftest.log."""
import os
import subprocess
import sys
import tempfile
import traceback

import numpy as np


def _check_fortran(exe_for):
    # A program that cannot load its runtime libraries dies before printing its own messages
    expected = {"soga_optimizer": "configuration file", "moga_optimizer": "configuration file",
                "simulator": "Usage", "polygon3": "Polygon_project"}
    with tempfile.TemporaryDirectory() as empty:
        for name, text in expected.items():
            exe = exe_for(name)
            if not os.path.exists(exe):
                raise RuntimeError(f"{exe} is missing")
            out = subprocess.run([exe], cwd=empty, capture_output=True, text=True, timeout=60)
            if text not in out.stdout + out.stderr:
                raise RuntimeError(f"{name} did not start (exit {out.returncode}): {(out.stdout + out.stderr)[-300:]}")


def _check_ffmpeg():
    # Same setup as visualizer.py, without importing it (and with it VTK)
    import imageio_ffmpeg
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
    fig, ax = plt.subplots()
    line, = ax.plot([], [])
    ani = FuncAnimation(fig, lambda i: line.set_data(range(i + 1), range(i + 1)) or [line], frames=3)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "check.mp4")
        ani.save(path, writer="ffmpeg", fps=2)
        plt.close(fig)
        with open(path, "rb") as f:
            if f.read(12)[4:8] != b"ftyp":
                raise RuntimeError("ffmpeg wrote an invalid MP4")


def _check_vtk():
    import pyvista as pv
    from source import visualizer
    xs, ys = np.meshgrid(np.linspace(0, 4000, 6), np.linspace(0, 3000, 5))
    nodes = np.column_stack([xs.ravel(), ys.ravel(), -30 - 5 * np.sin(xs.ravel() / 900)])
    genes = np.ones(len(nodes), dtype=int)
    genes[::4] = 2
    plotter = pv.Plotter(shape=(1, 1), off_screen=True, window_size=[400, 300])
    visualizer._plot_farm_solution(plotter, 0, "self-test", nodes, genes, turb_path="./inputs/turbine_spec.txt")
    image = plotter.screenshot(return_img=True)
    plotter.close()
    if image is None or image.std() == 0:
        raise RuntimeError("VTK rendered an empty image")


def _exe_for(name):
    return os.path.join(os.getcwd(), "build", name + (".exe" if sys.platform == "win32" else ""))


def _check_gui():
    # Opens and closes the real GUI toolkit window: catches broken Tk, X11 or font libraries
    import customtkinter as ctk
    window = ctk.CTk()
    ctk.CTkLabel(window, text="self-test").pack()
    window.update()
    window.destroy()


def run():
    """Runs every check. Each result is appended to selftest.log as soon as it is
    known, with the full traceback on failure, so even a crash leaves a report."""
    checks = [("Fortran programs", lambda: _check_fortran(_exe_for)), ("ffmpeg (MP4 export)", _check_ffmpeg),
              ("GUI (Tk window)", _check_gui), ("VTK (3D viewer)", _check_vtk)]
    # GUI before VTK, as in the app: on macOS, Tk must create the NSApplication
    # (its TKApplication subclass); one created first by VTK crashes Tk.
    ok = True
    with open("selftest.log", "w") as log:
        def report(text):
            log.write(text + "\n")
            log.flush()
            if sys.stdout:
                print(text, flush=True)
        for name, check in checks:
            # Logged first, so a native crash inside a check still shows which one
            report(f"RUN   {name}")
            try:
                check()
                report(f"PASS  {name}")
            except BaseException as e:
                ok = False
                report(f"FAIL  {name}: {e!r}\n" + traceback.format_exc())
    return 0 if ok else 1
