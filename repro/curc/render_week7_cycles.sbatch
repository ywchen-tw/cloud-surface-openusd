#!/bin/bash

#SBATCH --account=ucb744_asc1
#SBATCH --nodes=1
#SBATCH --ntasks=8
#SBATCH --time=02:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=Yu-Wen.Chen@colorado.edu
#SBATCH --output=sbatch-output_%x_%j.txt
#SBATCH --job-name=usd-cloud-cycles
#SBATCH --partition=al40
###SBATCH --partition=artxpro6000
#SBATCH --gres=gpu:1
#SBATCH --qos=gpu-normal

# Blender-Cycles volumetric path-trace of a USD cloud scene on an Alpine GPU
# node. This is the primary physics-render route (plan.md Phase 8): Cycles
# gives real volume scattering + volume->surface shadows that Storm cannot.
#
# Partition guide (all need --qos=gpu-normal; gpu-long for >24 h):
#   al40        L40, has RT cores -> fast OptiX (default)
#   artxpro6000 RTX Pro 6000, fastest RT if available
#   aa100       A100, no RT cores — works, but slower for Cycles
#
# Usage:
#   sbatch repro/curc/render_week7_cycles.sbatch [usd_scene] [start] [end] [samples]

set -euo pipefail

REPO_ROOT="/projects/yuch8913/cloud-surface-openusd"
cd "$REPO_ROOT"
source repro/curc/env.sh

USD_SCENE="${1:-assets/week7/usdvol_cloud_scene.usda}"
FRAME_START="${2:-1}"
FRAME_END="${3:-20}"
SAMPLES="${4:-256}"

RUN_NAME="$(basename "${USD_SCENE%.*}")_cycles"
OUT_DIR="$OPENUSD_CLD_DATAROOT/renders/$RUN_NAME"
mkdir -p "$OUT_DIR"

echo "GPU:"; nvidia-smi -L
echo "Scene: $USD_SCENE  frames $FRAME_START..$FRAME_END  samples $SAMPLES"
echo "Out:   $OUT_DIR"

"$BLENDER_BIN" -b --factory-startup -noaudio \
    -P repro/curc/blender_render_usd.py -- \
    --usd "$USD_SCENE" \
    --vdb assets/week7/vdbs/cloud_density.vdb \
    --out "$OUT_DIR/frame_" \
    --frame-start "$FRAME_START" --frame-end "$FRAME_END" \
    --samples "$SAMPLES" --res 1280 720 \
    --camera MainCamera --anisotropy 0.85

# Assemble a preview mp4 if ffmpeg is available (module or system).
module load ffmpeg 2>/dev/null || true
if command -v ffmpeg >/dev/null; then
    ffmpeg -y -framerate 8 -start_number "$FRAME_START" \
        -i "$OUT_DIR/frame_%04d.png" -pix_fmt yuv420p "$OUT_DIR/preview.mp4"
    echo "Wrote $OUT_DIR/preview.mp4"
fi
