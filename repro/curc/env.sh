# Shared CURC (Alpine) environment for the cloud-surface-openusd pipeline.
# Source from login shells and sbatch scripts:
#   source repro/curc/env.sh
#
# /projects/$USER is small (250 GB quota, mostly full), so all bulky and
# regenerable artifacts (LES data, processed grids, VDBs, renders) live under
# OPENUSD_CLD_DATAROOT on scratch. NOTE: /scratch/alpine is purged after
# ~90 days — keep the source .nc backed up elsewhere (PetaLibrary / Mac).

export OPENUSD_CLD_DATAROOT="${OPENUSD_CLD_DATAROOT:-/scratch/alpine/${USER}/cloud_sfc_openusd_data}"

# Persistent software (Blender, conda envs) stays on /projects.
export OPENUSD_CLD_SOFTROOT="${OPENUSD_CLD_SOFTROOT:-/projects/${USER}/software}"
export BLENDER_BIN="${BLENDER_BIN:-${OPENUSD_CLD_SOFTROOT}/blender/blender}"

# Conda: prefer the user's own install (has er3t/ml/data envs and the
# ~/.condarc envs_dirs pointing at /projects); fall back to the CURC module.
if [ -f "${OPENUSD_CLD_SOFTROOT}/anaconda/etc/profile.d/conda.sh" ]; then
    source "${OPENUSD_CLD_SOFTROOT}/anaconda/etc/profile.d/conda.sh"
else
    module load miniforge 2>/dev/null || module load anaconda
fi
