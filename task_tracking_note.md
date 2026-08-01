# Task Tracking Note — Phase 8 rendering on CURC

> Handoff note for agents/sessions picking this up while Slurm jobs are queued.
> Written 2026-08-01. Full environment details: `repro/curc/README.md`.
> Project plan and checkboxes: `plan.md` (Phase 8 section).

## Where things stand (2026-08-01 end of day)

Phase 8 validation loop is CLOSED: hero render, nadir sensor render, EaR3T
run, and quantitative comparison all work. Current headline: **r = 0.802,
rel RMSE 36.8%** (see Next steps item 4). Remaining work is physics-gap
closing (item 5) and deliverables (item 6).

## Done so far (do NOT redo)

- CURC env fully set up: `openusd` conda env (conda-forge openusd 26.05 +
  openvdb 13), `vdbtools` env (openvdb 11 — see gotcha #1), Blender 4.5.12 LTS
  at `/projects/yuch8913/software/blender`, `er3t` env pre-existing and working.
- Data on scratch and verified: 7SEAS `.nc` (1.3 GB) + `data/processed/*` at
  `$OPENUSD_CLD_DATAROOT/data` (= `/scratch/alpine/yuch8913/cloud_sfc_openusd_data/data`,
  symlinked as repo `data/`).
- Real-data VDB: `assets/week7/vdbs/cloud_density.vdb` (8,525 active voxels,
  β_max 0.086 m⁻¹, voxels 100×100×80 m, **file format 224**) via
  `src/grid_to_vdb.py` run in the `vdbtools` env.
- Phase 8 stage: `assets/phase8/les_cloud_scene.usda` from
  `src/author_cloud_usd.py` — meters-true (`metersPerUnit=1`, Z-up), dark
  ocean, sun SZA 30°/az 40°, oblique `MainCamera` + orthographic
  `NadirCamera` (EaR3T sensor geometry). `usdchecker` clean; Blender import
  pre-flighted headless (volume/grids/cameras/sun all verified).
- GPU smoke tests on al40 (jobs 30690221, 30690329) proved the render chain;
  both frames show only the old toy-domain view — expected, superseded by the
  phase8 scene.

## Gotchas (will bite you if forgotten)

1. **VDB file-format**: Blender 4.5 reads OpenVDB file format ≤224. The
   `openusd` env's OpenVDB 13 writes 225 → Blender silently drops the volume
   (warning only in the log). ALWAYS write Blender-bound VDBs with the
   `vdbtools` env (OpenVDB 11): `conda run -n vdbtools python src/grid_to_vdb.py ...`
2. **`python` shadowing**: run scripts with `conda run -n <env> python ...` or
   the env's absolute path (`/projects/yuch8913/software/anaconda/envs/<env>/bin/python`);
   a bare `python` after `conda activate` has resolved wrongly before.
3. **GPU QOS**: GPU partitions reject `--qos=normal`; use `gpu-normal`
   (`gpu-long` >24 h). Blanca variant: `render_week7_cycles_blanca.sbatch`
   (submit after `module load slurm/blanca`; preemptable + `--skip-existing` resume).
4. **Storage**: `/projects/yuch8913` has only ~20 GB free — never write big
   artifacts there; use `$OPENUSD_CLD_DATAROOT` (scratch purges ~90 days; the
   Mac holds the `.nc` archive).
5. **conda-forge openusd has no `hioOpenVDB`** → usdview/Storm shows volume
   bounds only. That's fine; Cycles is the render route.
6. `pip list` showing `usd-core 26.5` in the openusd env is a conda stub, not
   a real pip install. Never `pip install usd-core`/`pyopenvdb` here.

## Next steps (in order)

1. ~~First real-LES render~~ DONE 2026-08-01: white multiple-scattering
   cumulus + ocean shadows confirmed (`les_cloud_scene_cycles/frame_0001.png`).
   Appearance fixes that made it work: Principled Volume color = SSA (~1),
   `cycles.volume_bounces=16` (defaults rendered black smoke). Beware stale
   frames when re-rendering with new settings — delete old PNGs first.
2. ~~Nadir geometry~~ DONE: 128x128 ortho sensor verified (tile edge-to-edge,
   pattern matches the quicklook tau map). Blocky translucent veils over the
   ocean = real optically thin cloud fringe (beta 5e-4..5e-3), NOT a bug —
   isolation renders proved the ocean surface itself is clean.
3. **Validation render** (scene-linear, sun-only, flat albedo — arg 8 passes
   extra driver flags):
   `sbatch repro/curc/render_week7_cycles.sbatch assets/phase8/les_cloud_scene.usda 1 1 4096 NadirCamera 128 128 "--exr --world-strength 0 --flat-albedo 0.05"`
   -> writes frame_0001.exr + frame_0001.npy (radiance array).
4. ~~First USD-vs-EaR3T comparison~~ DONE 2026-08-01, current headline:
   **r = 0.802, rel RMSE 36.8%** (CPU-rendered USD frame vs 1e9-photon EaR3T
   on the identical field). Figure + metrics at
   `$OPENUSD_CLD_DATAROOT/renders/validation/usd_vs_ear3t_*`.
   KEY FINDING: OptiX GPU renders have a zero-radiance leaf-box artifact on
   this fragmented volume (6% of nadir pixels black in open sun) — ALWAYS
   render validation frames with the CPU route (`render_cycles_cpu*.sbatch`);
   GPU is fine for hero/animation frames. 1e8 vs 1e9 photons changed r by
   0.001 — EaR3T noise is not the bottleneck.
   The EaR3T h5 is cached there (`ear3t_rad_3d.h5`) — re-compare without
   re-running MC via `--ear3t-h5`. sbatch wrappers: `repro/curc/compare_ear3t*.sbatch`.
5. **Close the physics gap** (largest first):
   - USD shadows are true zero (sun-only scene, no molecular atmosphere);
     EaR3T fills shadows with Rayleigh skylight (~0.02). Options: calibrated
     uniform world strength in Cycles, or quantify-and-document as a known
     renderer limitation (postmortem angle).
   - Check shadow-displacement dipoles in the diff panel for a residual
     sun-azimuth convention mismatch (USD az-from-+x vs MCARaTS saa).
   - More photons (1e8 -> 1e9) + higher render samples to shrink MC noise.
6. Then: 20-frame fly-through + one-pager leading with the validation figure.

## Conventions

- **Always give the user BOTH submission variants** — Alpine and Blanca —
  for any render/compute job (Alpine GPU queues can have long waits):
  ```bash
  # Alpine (fast L40s, may queue):
  sbatch repro/curc/render_week7_cycles.sbatch <scene> <start> <end> <samples>
  # Blanca (preemptable, usually starts fast; slower RTX 8000):
  module load slurm/blanca
  sbatch repro/curc/render_week7_cycles_blanca.sbatch <scene> <start> <end> <samples>
  module load slurm/alpine   # switch back for Alpine submissions
  ```

- Sun geometry lives in `src/author_cloud_usd.py` (`SUN_SZA_DEG = 30`,
  `SUN_AZ_DEG = 40`) — EaR3T runs MUST use the same values for the comparison
  to be legitimate.
- β_ext is stored per meter and the stage is meters-true, so Cycles optical
  depth is physically correct with density scale 1.0 — do not "tune" density.
- Render outputs: `$OPENUSD_CLD_DATAROOT/renders/<scene>_cycles/frame_####.png`.
- Slurm logs: `sbatch-output_<jobname>_<jobid>.txt` in the repo root.
