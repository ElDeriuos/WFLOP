#!/bin/bash
# Runs `WFLOP --self-test` inside a clean Linux container (used by the release
# workflow for several distributions). Installs only what any desktop already
# has: an X server (Xvfb, headless), Mesa OpenGL, X11 and font libraries.
# Usage (from the repository root):
#   docker run --rm -v "$PWD/dist/WFLOP:/app" -v "$PWD/tests/ci:/ci" -w /app <image> bash /ci/selftest_in_container.sh
set -euo pipefail

if command -v apt-get >/dev/null; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq xvfb xauth libgl1 libgl1-mesa-dri libx11-6 libxext6 libxrender1 \
        libxss1 libfontconfig1 fonts-dejavu-core >/dev/null
elif command -v dnf >/dev/null; then
    dnf install -y -q xorg-x11-server-Xvfb xorg-x11-xauth mesa-libGL mesa-dri-drivers libX11 \
        libXext libXrender libXScrnSaver fontconfig dejavu-sans-fonts which >/dev/null
elif command -v pacman >/dev/null; then
    pacman -Syu --noconfirm --needed xorg-server-xvfb xorg-xauth mesa libx11 libxext libxrender \
        libxss fontconfig ttf-dejavu which >/dev/null
elif command -v zypper >/dev/null; then
    zypper -n -q install xvfb-run Mesa-libGL1 Mesa-dri libX11-6 libXext6 libXrender1 libXss1 \
        fontconfig dejavu-fonts which >/dev/null
else
    echo "No supported package manager in this image" >&2
    exit 1
fi

xvfb-run -a ./WFLOP --self-test
