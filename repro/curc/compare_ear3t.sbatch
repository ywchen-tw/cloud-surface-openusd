#!/bin/bash

#SBATCH --account=ucb744_asc1
#SBATCH --nodes=1
#SBATCH --ntasks=16
#SBATCH --time=04:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=Yu-Wen.Chen@colorado.edu
#SBATCH --output=sbatch-output_%x_%j.txt
#SBATCH --job-name=usd-ear3t-compare
#SBATCH --partition=amilan
#SBATCH --qos=normal

# Phase 8 validation: run EaR3T/MCARaTS 3D-RT on the LES extinction field and
# compare against the USD/Cycles nadir radiance (.npy from the --exr render).
# CPU-only. Module set mirrors the working er3t job (arcsix curc_shell_test.sh).
#
# Usage:
#   sbatch repro/curc/compare_ear3t.sbatch [usd_npy] [out_prefix]

set -euo pipefail

REPO_ROOT="/projects/yuch8913/cloud-surface-openusd"
cd "$REPO_ROOT"
source repro/curc/env.sh

module load intel/2022.1.2 hdf5/1.10.1 zlib/1.2.11 netcdf/4.8.1 swig/4.1.1 gsl/2.7 2>/dev/null || true
conda activate er3t

USD_NPY="${1:-$OPENUSD_CLD_DATAROOT/renders/les_cloud_scene_cycles_NadirCamera/frame_0001.npy}"
OUT_PREFIX="${2:-$OPENUSD_CLD_DATAROOT/renders/validation/usd_vs_ear3t}"

if [ ! -f "$USD_NPY" ]; then
    echo "ERROR: USD radiance npy not found: $USD_NPY" >&2
    echo "Run the --exr NadirCamera render first (see task_tracking_note.md)." >&2
    exit 1
fi

echo "USD npy : $USD_NPY"
echo "Out     : $OUT_PREFIX  (ncpu ${SLURM_NTASKS:-16})"

python validation/compare_ear3t.py \
    --run-ear3t \
    --ncpu "${SLURM_NTASKS:-16}" \
    --usd-npy "$USD_NPY" \
    --out-prefix "$OUT_PREFIX"

echo "Figure : ${OUT_PREFIX}_figure.png"
echo "Metrics: ${OUT_PREFIX}_metrics.json"
