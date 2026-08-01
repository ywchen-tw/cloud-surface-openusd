# CURC (Alpine) Rendering Environment — Setup Plan

How to render the USD cloud pipeline on CURC, replacing the Mac-local
Homebrew/Cycles setup. Everything here was verified against the live cluster
(2026-07-31): partitions, QOS, quotas, conda-forge package availability.

## Findings that shaped this plan

- **`/projects/yuch8913` is 92% full (~21 GB free).** Persistent software goes
  there; all data/renders go to scratch via **`$OPENUSD_CLD_DATAROOT`**
  (default `/scratch/alpine/$USER/cloud_sfc_openusd_data`, 10 TB, purged ~90 days).
- **The 7SEAS LES `.nc` is no longer on CURC** — the Nov 2024 copies under
  `/scratch/alpine/yuch8913/les/7SEAS/` were purged. It must be re-transferred
  from the Mac (or just the small processed artifacts; see below).
- **`er3t` conda env already exists and imports** (`/projects/.../envs/er3t`)
  — usable as-is for `src/cloud_field.py` and the EaR3T validation.
- **conda-forge now ships `openusd` 26.05** (full build: `pxr`, `UsdVol`,
  `usdview`, `usdrecord`) **and `openvdb` 13 with Python bindings** — no
  Homebrew, no C++ tool, no source build needed on CURC.
- **No blender/apptainer modules**, but apptainer exists at `/usr/bin` and
  compute nodes have outbound internet → portable Blender 4.5 LTS tarball
  works (glibc 2.28 requirement matches Rocky 8.10).
- **GPU partitions require `--qos=gpu-normal`** (24 h max; `gpu-long` for 7 d).
  Account `ucb744_asc1` has access. For Cycles/OptiX prefer RT-core GPUs:
  `al40` (L40) or `artxpro6000` (RTX Pro 6000); `aa100` (A100) works but has
  no RT cores.

## Storage layout

| Location | Contents | Why |
|---|---|---|
| `/projects/$USER/software/blender` | Blender 4.5 LTS portable | persistent, ~1.4 GB |
| `/projects/.../anaconda/envs/openusd` | OpenUSD 26.05 + OpenVDB 13 env | persistent (via `~/.condarc` envs_dirs) |
| `$OPENUSD_CLD_DATAROOT/data` | LES `.nc`, `data/processed/*` | big, regenerable → scratch |
| `$OPENUSD_CLD_DATAROOT/renders` | all render output | big → scratch |
| `$OPENUSD_CLD_DATAROOT/vdbs`, `build` | VDB sequences, compiled tools | scratch |

`setup_curc_env.sh` symlinks `data -> $OPENUSD_CLD_DATAROOT/data` and
`renders/curc -> $OPENUSD_CLD_DATAROOT/renders` inside the repo (excluded from
git via `.git/info/exclude`), so existing scripts keep working unchanged.
Override the root by exporting `OPENUSD_CLD_DATAROOT` before sourcing
`repro/curc/env.sh`.

## One-time setup

```bash
cd /projects/yuch8913/cloud-surface-openusd
bash repro/curc/setup_curc_env.sh
```

Creates the scratch layout, the `openusd` conda env, downloads Blender, and
prints a verification report (pxr/openvdb imports + whether the conda build
includes `hioOpenVDB`, which Storm needs to display `.vdb` fields).

## Data transfer from the Mac

DONE (2026-07-31): the full 7SEAS `.nc` (1.3 GB) and all `data/processed/*`
artifacts are uploaded and verified under `$OPENUSD_CLD_DATAROOT/data/`.
Since scratch purges after ~90 days, keep the `.nc` archived off-cluster
(Mac / PetaLibrary) and re-upload if it ages out:

```bash
# from the Mac, inside the repo:
scp data/7SEAS_*.nc data/processed/cloud_ext_64x64x32.{f32,json} \
    data/processed/cloud_field_64x64x{64,32}.npz \
    yuch8913@login.rc.colorado.edu:/scratch/alpine/yuch8913/cloud_sfc_openusd_data/data/
```

## Render routes

1. **Blender-Cycles on GPU node (primary, the physics render).**
   Real volumetric path tracing + volume→surface shadows — this is the route
   that answers plan.md's open "render route" decision on CURC.
   ```bash
   sbatch repro/curc/render_week7_cycles.sbatch                # week 7 scene, frames 1-20
   sbatch repro/curc/render_week7_cycles.sbatch assets/week7/usdvol_cloud_scene.usda 1 20 512
   ```
   Driver: `blender_render_usd.py` (USD import → Principled Volume with
   `density` grid, HG g=0.85 → OptiX/CUDA → PNG frames + preview.mp4).

2. **usdview on Core Desktop (interactive inspection).**
   Launch a Core Desktop OnDemand session, then:
   ```bash
   source repro/curc/env.sh && conda activate openusd
   usdview assets/week7/usdvol_cloud_scene.usda
   ```
   If `hioOpenVDB` is missing from the conda build, Storm shows bounds only —
   use the `points_preview` variant for inspection.

3. **usdrecord/Storm batch preview (experimental).**
   `sbatch repro/curc/render_usdrecord_storm.sbatch` — geometry/animation
   check only; Storm cannot render volume scattering.

## Phase 8 on CURC (end-to-end)

```bash
# 1. ingest LES (er3t env)         -> data/processed/*
conda run -n er3t python src/cloud_field.py
# 2. extinction grid -> VDB (pure Python now, replaces the C++ tool)
#    NOTE: use the vdbtools env (OpenVDB 11, writes file format 224), NOT the
#    openusd env — its OpenVDB 13 writes format 225, which Blender 4.5's
#    bundled OpenVDB cannot read (volume gets silently skipped in renders).
conda run -n vdbtools python src/grid_to_vdb.py \
    data/processed/cloud_ext_64x64x32.f32 assets/week7/vdbs/cloud_density.vdb
# 3. author the Phase 8 real-data stage (meters-true, nadir + oblique cameras)
conda run -n openusd python src/author_cloud_usd.py
# 4. GPU render (hero view; use --camera NadirCamera route for validation)
sbatch repro/curc/render_week7_cycles.sbatch assets/phase8/les_cloud_scene.usda 1 1 256
# 5. EaR3T benchmark + comparison (er3t env; validation/compare_ear3t.py, TBD)
```

## Slurm cheat sheet

| Need | Header |
|---|---|
| GPU render (default) | `--partition=al40 --gres=gpu:1 --qos=gpu-normal` |
| Fastest RT | `--partition=artxpro6000 --gres=gpu:1 --qos=gpu-normal` |
| A100 (e.g. for EaR3T/ML too) | `--partition=aa100 --gres=gpu:1 --qos=gpu-normal` |
| >24 h | `--qos=gpu-long` (7 d max) |
| CPU (cloud_field, EaR3T MC) | `--partition=amilan --qos=normal` |
