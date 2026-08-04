# Task Tracking Note — Phase 8 rendering on CURC

> Handoff note for agents/sessions picking this up while Slurm jobs are queued.
> Written 2026-08-01. Full environment details: `repro/curc/README.md`.
> Project plan and checkboxes: `plan.md` (Phase 8 section).

## Where things stand (2026-08-02, after the stripe hunt)

**Stripe saga CLOSED** (docs/rendering_artifacts.md #6): the wavy scanline
stripes in the hero frames were the DENOISER (OpenImageDenoise, on by
default) streaking noisy 512-sample input — confirmed by A/B on frame 81
(`--no-denoise` = grain only; 2048 samples + denoise = clean). Two earlier
theories (negative-scale mirror instances, HALF-precision NanoVDB) were
refuted by renders; their fixes were kept anyway (baked-mirror VDB,
precision=FULL + clipping=0). **Hero frames now render at 2048 samples.**

Also DONE 2026-08-02:
- Hero mirror VDB REBUILT with min_beta 2e-3 (was 5e-4): kills the blue
  veil slabs / hard-edged shadow polygons (#4) that clipping=0 had made
  more visible, and removes the denoiser's main variance source. Now
  36,468 active voxels; worst-column tau lost 0.67 (cloud tau_max ~53 —
  cosmetically nil). HERO ONLY — the validation VDB
  (`cloud_density.vdb`) keeps 5e-4. Revert:
  `conda run -n vdbtools python src/grid_to_vdb.py data/processed/cloud_ext_64x64x32.f32 assets/week7/vdbs/cloud_density_mirror3x3.vdb 5e-4 --mirror3x3`
- Master output dir cleared; striped-era frames archived to
  `renders/les_cloud_arctic_scene_cycles_MainCamera_512denoise_old`.
- Driver gained `--no-denoise` (A/B tool) and camera-hint prefix matching
  (pass e.g. `MainCameraNoDN` to give a test run its own output dir while
  still selecting MainCamera).

UPDATE 2026-08-02 (second session): the 2048-sample masters came out bad.
Diagnosis + fixes:
- 1080p master (`_MainCamera`, Blanca 27307793) rendered on **CUDA** — the
  driver's `auto` silently fell back when OptiX init failed on that node.
  Violent scanline banding (row-stripe power 0.0119 vs 0.0030 striped-era
  reference). Dir is dead — archive it. FIXED in driver: `auto` is now
  OPTIX-or-CPU-with-warning; CUDA only via explicit `--device cuda`;
  explicitly requested unavailable device aborts the job.
- 720p master (`_MainCamera720p`, OPTIX) is stripe-clean (0.0014) but shows
  the artifact-#4 hard-edged veil slabs + black shadow polygons — the 2e-3
  cut did NOT remove them (slab beta is 2e-3..5e-3). Hero mirror VDB
  REBUILT at **min_beta 5e-3**: 26,595 active voxels, worst-column tau
  lost 2.56 (cloud tau_max ~53). Also de-fragments NanoVDB leaves (attacks
  OptiX artifact #3's topology) and removes the denoiser's variance source.
- `_MainCameraNoDN` / `_MainCameraHS` were the frame-81 denoiser A/B on the
  OLD (pre-rebuild) VDB — superseded, archive.

IN FLIGHT (check before launching anything):
- Alpine 30732625: CPU spot check frames 1+81, 720p/2048, on the 2e-3 VDB
  (loaded before the rebuild) -> `_MainCameraCPU`. Device-isolation
  reference + CPU min/frame timing.
- Blanca 27317411: OPTIX spot check frames 1-100 step 10, 1080p/2048, on
  the NEW 5e-3 VDB -> `_MainCameraOptix5e3`. Gate for the full master:
  squares gone + no scanlines + no exact-zero leaf-box pixels.
- ~~Alpine 30732949 -> 30732950: clipping=0 validation rerun~~ DONE
  2026-08-02 10:29: **r = 0.9880, rel RMSE 13.93%** — statistically
  identical to the original 0.9880/13.90%. The silent beta drop in
  [5e-4,1e-3) did NOT matter; the r=0.988 headline stands, now with clean
  provenance. Results: `validation/usd_vs_ear3t_clip0_*`; old render
  archived as `..._NadirCamera_preclip0_old`. compare_ear3t*.sbatch (both
  clusters) gained optional 4th arg = cached h5 path (skips the MC run).
- Blanca 27317176 (user-submitted): CPU spot frames 1+81 on the 2e-3 VDB
  (imported pre-rebuild) -> `_MainCameraCPUblanca`. Same role as Alpine
  30732625.
- NOTE: user prefers Blanca-first for all submissions (memory updated).

FINDING 2026-08-02 ~11:50 — the "square volumes" are an OPTIX ARTIFACT,
not data: same frame 1, same region — OPTIX (2e-3 AND 5e-3 VDB) renders
the thin fringe as bright hard-edged slab boxes with diagonal hatch;
CPU (2e-3) renders it as soft faithful haze, zero squares. Over-bright
sibling of artifact #3 (zero-radiance leaf boxes), same fragmented-NanoVDB
root. "GPU fine for hero frames" is REFUTED for this scene. Surface-only
render (`_MainCameraSurfOnly`) proved the albedo texture is clean.
Stripes ARE fixed everywhere except CUDA (driver now blocks silent CUDA).
A/B results (both landed ~12:05): CPU + 5e-3 VDB = CLEAN (stripe 0.00027,
no squares — rebuilt VDB is good). OPTIX + `--volume-step-rate 0.25` =
slabs pixel-identical (GPU route dead for this volume). Catalog entry
#11 written; standing rule updated to CPU-for-all-frames.

MASTER LAUNCHED 2026-08-02 ~12:15 — Blanca CPU jobs 27321648-27321652:
5 chunks x 20 frames, 1080p, 2048 samples, `--time=12:00:00`,
`--skip-existing` -> shared dir
`renders/les_cloud_arctic_scene_cycles_MainCameraCPUmaster`.
STATUS 2026-08-03 morning: chunks 3-5 COMPLETED (frames 41-100); chunks
1-2 TIMEOUT at 12 h with frames 1-12 + 21-32 done. Cause: per-frame cost
varies 15-60 min — EARLY frames (low camera, volume-filled view) run
~58-60 min, late frames ~15 min. Recovery submitted: Blanca 27361389-92,
4 frames each (13-16, 17-20, 33-36, 37-40), ~4 h worst case each.
QUALITY VERIFIED on frames 1/50/81/100 at 1080p: stripe 0.00014-0.00022
(below the 0.0004 clean floor), zero-pixels 0, no slabs — master is
artifact-free. Rule of thumb for future CPU chunking: budget 60 min/frame
for frames 1-40, 20 min/frame for 41-100.

MASTER DONE 2026-08-03 ~11:54 — all 100 frames verified (contiguous
1-100, no 0-byte, recovered frames 15/35 spot-checked: stripe 0.00018-
0.00022, zero-pixels 0). Final `preview.mp4` assembled (12.5 s @ 8 fps,
1080p, `module load ffmpeg` needed on login nodes) in
`renders/les_cloud_arctic_scene_cycles_MainCameraCPUmaster/`.
The HERO VIDEO DELIVERABLE IS COMPLETE.

EXTENSION 2026-08-03: camera path extended to 200 frames in
`author_arctic_hero.py` (segment-2 smoothstep, same NE drift; frames
1-100 verified bit-identical to the rendered master; usdchecker clean;
albedo texture NOT regenerated). Spot frames 101/134/167/200 clean
(seam 100->101 diff 0.17/255 = seamless). COMPOSITION: by frame ~134
the view is 93-95% uniform ice sheet (clouds exited). User chose the
FULL 200-frame plan (calm ice-sheet ending kept): frames 101-150 on
Blanca 27369671-75 (5x10 chunks, ~19 min/frame with clouds in view),
frames 151-200 on Blanca 27369694 (single job, ~1 min/frame on ice).
EXTENSION DONE 2026-08-03 22:10 — all 200 frames rendered and verified
(no gaps, no 0-byte, recovered frames 119/120/122 clean at stripe
0.00011); final `preview.mp4` = 25.0 s @ 8 fps 1080p in
`renders/les_cloud_arctic_scene_cycles_MainCameraCPUmaster/`.
Preemption lesson fixed in tooling: both render_cycles_cpu*.sbatch now
delete stale 0-byte placeholders at startup (the GPU script already
did) — a requeued chunk had skipped frame 122 over its own dead
placeholder. THE 200-FRAME HERO VIDEO IS COMPLETE.

NEXT (deliverables only — all rendering is done):
1. Copy the validation figure into docs/
   (`renders/validation/usd_vs_ear3t_clip0_figure.png` is the final one).
2. One-pager leading with r=0.988 / rel RMSE 13.9%.
3. Postmortem from docs/rendering_artifacts.md (11 artifacts).

FUTURE (explicitly deferred 2026-08-03, only if GPU speed is needed for
multi-timestep animation batches): GPU-rescue experiments — connectivity
filter and/or upsample+smooth in grid_to_vdb.py, then re-A/B OptiX.
Global cutoff is already ruled out (2e-2 kills all slabs but loses 34%
of total tau; flat beta histogram means no safe threshold).
2. Deliverables: copy the validation figure into docs/, one-pager,
   postmortem (artifact catalog is the source), final mp4 at 8 fps.
   (Validation rerun is done — headline r=0.988 / 13.9% confirmed under
   clipping=0; quote `usd_vs_ear3t_clip0_*` as the final artifacts.)

### Hero video pipeline (for the personal website)
- Scene: `assets/phase8/les_cloud_arctic_scene.usda` from
  `src/author_arctic_hero.py` (19.2 km 3x3-tiled LES clouds, SZA 55 sun,
  camera timeSamples frames 1-100 @ 8 fps = 12.5 s clip).
- Surface: procedural albedo TEXTURE (`src/gen_arctic_albedo.py` ->
  `data/processed/arctic_albedo_texture.png`, 3072^2 over the 64-km quad,
  ~21 m/px). REGENERATE it if scratch purged it, or the surface renders
  textureless. Flat polygons were rejected (read as paper cutouts).
- Submit (GPU hero route; dual clusters). 2048 samples MINIMUM — at 512
  the denoiser streaks scanlines across veil-shadow regions (artifacts #6).
  Spot-check first (scene/VDB changed), then full; spot frames land in the
  master dir and Blanca's `--skip-existing` reuses them:
  `sbatch repro/curc/render_week7_cycles.sbatch assets/phase8/les_cloud_arctic_scene.usda 1 100 2048 MainCamera 1920 1080 "--frame-step 10"`
  then the same line without the `"--frame-step 10"` arg.
  (Blanca: `module load slurm/blanca; sbatch repro/curc/render_week7_cycles_blanca.sbatch <same args>`)
  Timing: ~1 min/frame at 2048/720p on Blanca OPTIX -> expect ~2-3
  min/frame at 1080p, ~4-5 h for 100 frames (Blanca 12 h limit is the
  safer home; Alpine's 6 h works but is tight).
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
3. ~~Validation render~~ DONE (CPU route, scene-linear EXR, sun-only,
   flat albedo 0.05). To RE-RUN with the clipping=0 driver (NEXT item 2
   above — use the CPU sbatch and the periodic 3x3 scene):
   `sbatch repro/curc/render_cycles_cpu.sbatch assets/phase8/les_cloud_scene_periodic.usda 1 1 4096 NadirCamera 128 128 "--exr --world-strength 0 --flat-albedo 0.05 --volume-bounces 64"`
4. ~~First USD-vs-EaR3T comparison~~ DONE 2026-08-01, FINAL headline:
   **r = 0.988, rel RMSE 13.9%** (periodic 3x3 CPU render, azimuth-aligned,
   vs 1e9-photon EaR3T on the identical field). Figure + metrics at
   `$OPENUSD_CLD_DATAROOT/renders/validation/usd_vs_ear3t_*`.
   KEY FINDING: OptiX GPU renders have a zero-radiance leaf-box artifact on
   this fragmented volume (6% of nadir pixels black in open sun) — ALWAYS
   render validation frames with the CPU route (`render_cycles_cpu*.sbatch`);
   GPU is fine for hero/animation frames. 1e8 vs 1e9 photons changed r by
   0.001 — EaR3T noise is not the bottleneck.
   The EaR3T h5 is cached there (`ear3t_rad_3d.h5`) — re-compare without
   re-running MC via `--ear3t-h5`. sbatch wrappers: `repro/curc/compare_ear3t*.sbatch`.
5. ~~Close the physics gap~~ RESOLVED to the extent planned: azimuth
   convention fixed (compass SAA -> USD Rz = 180-SAA), cyclic-BC 3x3
   tiling, 64 volume bounces. Remaining ~14% decomposed as Rayleigh
   skylight in shadows (sun-only Cycles scene) + MC noise — documented as
   postmortem material, not chased further.
6. Hero fly-through + deliverables: see NEXT list at the top of this note.

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
