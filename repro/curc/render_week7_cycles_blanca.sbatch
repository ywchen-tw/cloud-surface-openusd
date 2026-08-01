#!/bin/bash

#SBATCH --account=blanca-airs
#SBATCH --nodes=1
#SBATCH --ntasks=8
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=Yu-Wen.Chen@colorado.edu
#SBATCH --output=sbatch-output_%x_%j.txt
#SBATCH --job-name=usd-cloud-cycles-blanca
#SBATCH --qos=preemptable
#SBATCH --gres=gpu:1
#SBATCH --requeue
###SBATCH --partition=blanca-airs
###SBATCH --qos=blanca-airs

# Blanca variant of render_week7_cycles.sbatch (Blender-Cycles volumetric
# path-trace, plan.md Phase 8). Default runs preemptable on any Blanca GPU
# node (RTX 8000 on blanca-airs — RT cores, good OptiX); --requeue resubmits
# after preemption and --skip-existing resumes at the first unfinished frame.
# For owned-node priority without preemption, swap to the commented
# partition/qos=blanca-airs pair above.
#
# Submit from a login node with the Blanca slurm instance loaded:
#   module load slurm/blanca
#   sbatch repro/curc/render_week7_cycles_blanca.sbatch [usd_scene] [start] [end] [samples] [camera] [res_x] [res_y]

set -euo pipefail

REPO_ROOT="/projects/yuch8913/cloud-surface-openusd"
cd "$REPO_ROOT"
source repro/curc/env.sh

# Alpine scratch is mounted on Blanca nodes (the old sim-rad-7SEAS Blanca jobs
# wrote there), but guard anyway in case a node lacks the mount.
if [ ! -d "$OPENUSD_CLD_DATAROOT" ]; then
    echo "ERROR: OPENUSD_CLD_DATAROOT not reachable on $(hostname): $OPENUSD_CLD_DATAROOT" >&2
    exit 1
fi

USD_SCENE="${1:-assets/week7/usdvol_cloud_scene.usda}"
FRAME_START="${2:-1}"
FRAME_END="${3:-20}"
SAMPLES="${4:-256}"
CAMERA_ARG="${5:-}"                 # e.g. NadirCamera; default MainCamera
CAMERA="${CAMERA_ARG:-MainCamera}"
RES_X="${6:-1280}"
RES_Y="${7:-720}"

RUN_NAME="$(basename "${USD_SCENE%.*}")_cycles${CAMERA_ARG:+_${CAMERA_ARG}}"
OUT_DIR="$OPENUSD_CLD_DATAROOT/renders/$RUN_NAME"
mkdir -p "$OUT_DIR"

# Drop 0-byte placeholders left by a preempted run so those frames re-render.
find "$OUT_DIR" -name 'frame_*.png' -size 0 -delete

echo "GPU:"; nvidia-smi -L
echo "Scene: $USD_SCENE  frames $FRAME_START..$FRAME_END  samples $SAMPLES"
echo "Out:   $OUT_DIR"

"$BLENDER_BIN" -b --factory-startup -noaudio \
    -P repro/curc/blender_render_usd.py -- \
    --usd "$USD_SCENE" \
    --vdb assets/week7/vdbs/cloud_density.vdb \
    --out "$OUT_DIR/frame_" \
    --frame-start "$FRAME_START" --frame-end "$FRAME_END" \
    --samples "$SAMPLES" --res "$RES_X" "$RES_Y" \
    --camera "$CAMERA" --anisotropy 0.85 \
    $( [ "$FRAME_END" -gt "$FRAME_START" ] && echo --skip-existing )
# --skip-existing only for multi-frame runs: it resumes after preemption, but
# on a single-frame rerun it silently skips the stale frame from a previous
# submission (this bit us on 2026-08-01, jobs 27294045/27294083).

# Assemble a preview mp4 if ffmpeg is available (module or system).
module load ffmpeg 2>/dev/null || true
if command -v ffmpeg >/dev/null; then
    ffmpeg -y -framerate 8 -start_number "$FRAME_START" \
        -i "$OUT_DIR/frame_%04d.png" -pix_fmt yuv420p "$OUT_DIR/preview.mp4"
    echo "Wrote $OUT_DIR/preview.mp4"
fi
