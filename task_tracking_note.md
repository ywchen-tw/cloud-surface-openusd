# Task Tracking Note — Phase 8 rendering on CURC

> Handoff note for agents/sessions picking this up while Slurm jobs are queued.
> Written 2026-08-01. Full environment details: `repro/curc/README.md`.
> Project plan and checkboxes: `plan.md` (Phase 8 section).

## Where things stand (2026-08-01 evening)

**IN FLIGHT: Blanca GPU job `27298324`** (`usd-cloud-cycles-blanca`) — Arctic
hero fly-through, frames 1..100 @ 512 samples, ~65 s/frame (~2 h total),
output `$OPENUSD_CLD_DATAROOT/renders/les_cloud_arctic_scene_cycles_MainCamera720/`.

**KNOWN PROBLEM with that job:** it was submitted while the scene's camera
animation still ended at frame 20 (`FRAMES = 20`), so frames 21-100 render
as identical static copies of frame 20. The scene has since been re-authored
with `FRAMES = 100` (endTimeCode 100), but the running job loaded the OLD
scene at startup. RECOVERY: cancel it (`module load slurm/blanca; scancel
27298324`), delete the stale frames (`rm .../les_cloud_arctic_scene_cycles_MainCamera720/frame_*.png`
— they follow the old 20-frame path and would be kept by --skip-existing,
glitching the animation), then resubmit 1..100 (see Hero video below).
If it instead ran to completion, only frames 1-20 are usable.

### Hero video pipeline (for the personal website)
- Scene: `assets/phase8/les_cloud_arctic_scene.usda` from
  `src/author_arctic_hero.py` (19.2 km 3x3-tiled LES clouds, SZA 55 sun,
  camera timeSamples frames 1-100 @ 8 fps = 12.5 s clip).
- Surface: procedural albedo TEXTURE (`src/gen_arctic_albedo.py` ->
  `data/processed/arctic_albedo_texture.png`, 2048^2). REGENERATE it if
  scratch purged it, or the surface renders textureless. Flat polygons were
  rejected (read as paper cutouts).
- Submit (GPU hero route; dual clusters):
  `sbatch repro/curc/render_week7_cycles.sbatch assets/phase8/les_cloud_arctic_scene.usda 1 100 512`
  (Blanca: `module load slurm/blanca; sbatch repro/curc/render_week7_cycles_blanca.sbatch <same args>`)
  1080p final: append `MainCamera 1920 1080`.
- The sbatch auto-assembles `preview.mp4` (ffmpeg, 8 fps) when frames
  finish. If a job dies after frames are done, assemble manually:
  `ffmpeg -framerate 8 -i frame_%04d.png -pix_fmt yuv420p preview.mp4`.
- Blanca preemption: multi-frame runs pass --skip-existing and resume at
  the first unfinished frame (0-byte placeholders are auto-deleted).


Phase 8 validation loop is CLOSED: hero render, nadir sensor render, EaR3T
run, and quantitative comparison all work. FINAL headline: **r = 0.988, rel RMSE 13.9%**
(periodic 3x3 scene + 64 volume bounces + azimuth-aligned CPU render vs
1e9-photon EaR3T). Improvement ladder: 0.756 (first try) -> 0.802 (CPU,
no OptiX artifact) -> 0.943 (azimuth convention) -> 0.988 (cyclic-BC
tiling + bounces). Remaining ~14%: Rayleigh-skylight deficit in shadows
(sun-only Cycles scene) + MC/render noise — postmortem material.

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

0. **Read `docs/rendering_artifacts.md` first** — the full catalog of every
   rendering artifact hit so far (VDB format, OptiX zero-boxes, CUDA
   banding on negative-scale volumes, tile-seam cut walls, fringe veils,
   stale-frame traps) with root causes and the standing rules
   (validation = CPU only; never mirror volumes by transform).

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
   **r = 0.943, rel RMSE 22.2%** (CPU-rendered USD frame, azimuth-aligned,
   vs 1e9-photon EaR3T on the identical field). Figure + metrics at
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
