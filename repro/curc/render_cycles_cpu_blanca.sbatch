#!/bin/bash

#SBATCH --account=blanca-airs
#SBATCH --nodes=1
#SBATCH --ntasks=32
#SBATCH --time=02:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=Yu-Wen.Chen@colorado.edu
#SBATCH --output=sbatch-output_%x_%j.txt
#SBATCH --job-name=usd-cloud-cycles-cpu-blanca
#SBATCH --qos=preemptable
#SBATCH --requeue
#SBATCH --mem=32G

# CPU Cycles render, Blanca preemptable variant (module load slurm/blanca). Use for VALIDATION renders: OptiX shows a
# zero-radiance leaf-box artifact on this fragmented volume (diagnosed
# 2026-08-01: 252/4096 nadir pixels exactly 0 in open sun on GPU; 0 on CPU).
# 128x128 validation frames are cheap on 32 CPU cores.
#
#
# Usage:
#   sbatch repro/curc/render_cycles_cpu_blanca.sbatch [usd_scene] [start] [end] [samples] [camera] [res_x] [res_y] ["extra driver flags"]

set -euo pipefail

REPO_ROOT="/projects/yuch8913/cloud-surface-openusd"
cd "$REPO_ROOT"
source repro/curc/env.sh

USD_SCENE="${1:-assets/week7/usdvol_cloud_scene.usda}"
FRAME_START="${2:-1}"
FRAME_END="${3:-20}"
SAMPLES="${4:-256}"
CAMERA_ARG="${5:-}"                 # e.g. NadirCamera; default MainCamera
CAMERA="${CAMERA_ARG:-MainCamera}"
RES_X="${6:-1280}"
RES_Y="${7:-720}"
EXTRA="${8:-}"                      # extra driver flags, e.g. "--exr --world-strength 0"

RUN_NAME="$(basename "${USD_SCENE%.*}")_cycles${CAMERA_ARG:+_${CAMERA_ARG}}"
OUT_DIR="$OPENUSD_CLD_DATAROOT/renders/$RUN_NAME"
mkdir -p "$OUT_DIR"

echo "Scene: $USD_SCENE  frames $FRAME_START..$FRAME_END  samples $SAMPLES"
echo "Out:   $OUT_DIR"

"$BLENDER_BIN" -b --factory-startup -noaudio \
    -P repro/curc/blender_render_usd.py -- \
    --usd "$USD_SCENE" \
    --vdb assets/week7/vdbs/cloud_density.vdb \
    --out "$OUT_DIR/frame_" \
    --frame-start "$FRAME_START" --frame-end "$FRAME_END" \
    --samples "$SAMPLES" --res "$RES_X" "$RES_Y" \
    --camera "$CAMERA" --anisotropy 0.85 --device cpu $EXTRA

# Assemble a preview mp4 if ffmpeg is available (module or system).
module load ffmpeg 2>/dev/null || true
if command -v ffmpeg >/dev/null && ls "$OUT_DIR"/frame_*.png >/dev/null 2>&1; then
    ffmpeg -y -framerate 8 -start_number "$FRAME_START" \
        -i "$OUT_DIR/frame_%04d.png" -pix_fmt yuv420p "$OUT_DIR/preview.mp4"
    echo "Wrote $OUT_DIR/preview.mp4"
fi
