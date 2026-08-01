#!/bin/bash

#SBATCH --account=ucb744_asc1
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --time=00:30:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=Yu-Wen.Chen@colorado.edu
#SBATCH --output=sbatch-output_%x_%j.txt
#SBATCH --job-name=usd-cloud-usdrecord
#SBATCH --partition=al40
#SBATCH --gres=gpu:1
#SBATCH --qos=gpu-normal

# EXPERIMENTAL: Storm/usdrecord preview render on a GPU node, mirroring the
# local repro/render_week7.sh. Storm cannot do volumetric path tracing or
# volume->surface shadows (plan.md), so this is only a geometry/preview check;
# the physics render route is render_week7_cycles.sbatch.
#
# Headless GL: recent OpenUSD builds fall back to EGL when $DISPLAY is unset.
# If this fails with a GL context error, preview interactively instead with
# usdview in a CURC Core Desktop session (conda activate openusd).
#
# Usage: sbatch repro/curc/render_usdrecord_storm.sbatch [usd_scene]

set -euo pipefail

REPO_ROOT="/projects/yuch8913/cloud-surface-openusd"
cd "$REPO_ROOT"
source repro/curc/env.sh
conda activate openusd

USD_SCENE="${1:-assets/week7/usdvol_cloud_scene.usda}"
RUN_NAME="$(basename "${USD_SCENE%.*}")_storm"
OUT_DIR="$OPENUSD_CLD_DATAROOT/renders/$RUN_NAME"
mkdir -p "$OUT_DIR"

nvidia-smi -L
usdrecord \
    --disableCameraLight \
    --camera /World/Camera/MainCamera \
    --frames 1:20 \
    --imageWidth 1280 \
    --colorCorrectionMode disabled \
    "$USD_SCENE" \
    "$OUT_DIR/frame_####.png"
echo "Wrote frames to $OUT_DIR"
