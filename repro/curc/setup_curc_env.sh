#!/usr/bin/env bash
set -euo pipefail

# One-time CURC (Alpine) setup for rendering the USD cloud pipeline.
# Idempotent — safe to re-run. Run from the repo root on a login node or in a
# code-server/Core Desktop session (needs outbound internet):
#   bash repro/curc/setup_curc_env.sh
#
# Steps:
#   1. Create $OPENUSD_CLD_DATAROOT on scratch, link it into the repo
#   2. Create the `openusd` conda env: conda-forge OpenUSD 26.05 (usdview,
#      usdrecord, UsdVol) + OpenVDB 13 (C++ libs, vdb_print, Python bindings)
#   3. Download Blender 4.5 LTS portable (Cycles GPU renderer) to /projects
#   4. Verify pxr / openvdb imports and check for the hioOpenVDB Storm plugin

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
source repro/curc/env.sh

echo "== 1/4 Data root on scratch: $OPENUSD_CLD_DATAROOT"
mkdir -p "$OPENUSD_CLD_DATAROOT"/{data/processed,renders,build,vdbs}

# data/ does not exist in the CURC checkout (gitignored) -> symlink to scratch.
if [ ! -e data ]; then
    ln -s "$OPENUSD_CLD_DATAROOT/data" data
    echo "  linked data -> $OPENUSD_CLD_DATAROOT/data"
fi
# renders/ holds a tracked .gitkeep, so keep the dir and add a scratch link inside.
if [ ! -e renders/curc ]; then
    ln -s "$OPENUSD_CLD_DATAROOT/renders" renders/curc
    echo "  linked renders/curc -> $OPENUSD_CLD_DATAROOT/renders"
fi
# Keep the symlinks out of git status without touching the shared .gitignore.
for pat in /data /renders/curc; do
    grep -qxF "$pat" .git/info/exclude 2>/dev/null || echo "$pat" >> .git/info/exclude
done

echo "== 2/4 Conda env 'openusd' (goes to ~/.condarc envs_dirs on /projects)"
if conda env list | grep -qE '^openusd\s|/openusd$'; then
    echo "  env already exists — skipping create"
else
    conda create -y -n openusd -c conda-forge --override-channels \
        python=3.13 "openusd=26.05" "openvdb=13" numpy pyside6 pyopengl
    conda clean -y --tarballs   # keep the /projects pkgs cache small
fi

echo "== 3/4 Blender 4.5 LTS portable"
if [ -x "$BLENDER_BIN" ]; then
    echo "  already installed: $("$BLENDER_BIN" --version | head -1)"
else
    TARBALL="$(curl -fsSL https://download.blender.org/release/Blender4.5/ \
        | grep -oE 'blender-4\.5\.[0-9]+-linux-x64\.tar\.xz' | sort -uV | tail -1)"
    [ -n "$TARBALL" ] || { echo "ERROR: could not find a Blender 4.5 linux-x64 tarball"; exit 1; }
    echo "  downloading $TARBALL to $OPENUSD_CLD_SOFTROOT"
    mkdir -p "$OPENUSD_CLD_SOFTROOT"
    curl -fL --progress-bar -o "$OPENUSD_CLD_SOFTROOT/$TARBALL" \
        "https://download.blender.org/release/Blender4.5/$TARBALL"
    tar -xJf "$OPENUSD_CLD_SOFTROOT/$TARBALL" -C "$OPENUSD_CLD_SOFTROOT"
    ln -sfn "$OPENUSD_CLD_SOFTROOT/${TARBALL%.tar.xz}" "$OPENUSD_CLD_SOFTROOT/blender"
    rm -f "$OPENUSD_CLD_SOFTROOT/$TARBALL"
    echo "  installed: $("$BLENDER_BIN" --version | head -1)"
fi

echo "== 4/4 Verification"
conda run -n openusd python - <<'PY'
from pxr import Usd, UsdVol, Plug
import openvdb
print(f"  pxr OK       : USD {Usd.GetVersion()}")
print(f"  openvdb OK   : {openvdb.LIBRARY_VERSION_STRING if hasattr(openvdb,'LIBRARY_VERSION_STRING') else 'imported'}")
hio = Plug.Registry().GetPluginWithName("hioOpenVDB")
print(f"  hioOpenVDB   : {'FOUND — Storm/usdview can load .vdb fields' if hio else 'MISSING — usdview will show the volume bounds only; use Cycles for real volume renders'}")
PY
"$BLENDER_BIN" --version | head -1 | sed 's/^/  /'
echo
echo "Setup complete. Next:"
echo "  - copy LES artifacts from the Mac into $OPENUSD_CLD_DATAROOT/data/ (see repro/curc/README.md)"
echo "  - sbatch repro/curc/render_week7_cycles.sbatch"
