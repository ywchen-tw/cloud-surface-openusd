# Rendering Artifact Diagnoses — Cycles + UsdVol/OpenVDB (Phase 8)

Every visual artifact met while rendering the real-LES cloud field, with root
cause, evidence, and resolution. Kept as a reference (and postmortem source):
several of these silently corrupt *quantitative* results, not just images.

| # | Artifact | Root cause | Device | Resolution |
|---|---|---|---|---|
| 1 | Volume silently missing from renders | Blender 4.5 bundles OpenVDB 11 (file format ≤224); conda-forge OpenVDB 13 writes format 225 | any | Write VDBs from the `vdbtools` env (OpenVDB 11). Warning appears only in the render log. |
| 2 | Clouds render as dark smoke | Principled Volume default color 0.5 (soot albedo) + Cycles default 0 volume bounces (single scattering, g=0.85 forward peak) | any | Driver sets color = SSA (~1) and `volume_bounces=16+`. Cloud whiteness *is* multiple scattering. |
| 3 | Zero-radiance leaf-box rectangles (6% of nadir pixels black in open sun — 77% had zero slant τ above them) | OptiX volume traversal on the fragmented NanoVDB leaf topology | OptiX only | CPU render for validation frames (`render_cycles_cpu*.sbatch`); CPU verified artifact-free. Would have poisoned the RMSE silently. |
| 4 | Blocky translucent veils over the ocean | Real optically thin cloud-base fringe (β 5e-4..5e-3 m⁻¹): slant paths through broad single-voxel slabs pick up τ 0.1–3; edges are cutoff iso-lines quantized to 100 m voxels | any (data) | Physically real — kept for validation (EaR3T sees the same). β<5e-4 cut (worst-column τ loss 0.17) applied identically on both sides. |
| 5 | Flat gray triangles/rectangles = cloud "cut walls" | The LES tile is NOT periodic; plain 3×3 tiling slices clouds into flat faces at every seam plane (dark when self-shadowed, bright when sunlit) | any (scene) | Mirror tiling (reflection padding) — continuous across every seam. Validation keeps plain wrap: MCARaTS cyclic BC wraps, it does not mirror. |
| 6 | Striped/hatched squares over the surface | Blender Volume render precision defaults to **HALF**: the GPU NanoVDB texture is FP16 (CPU samples full-float OpenVDB), and quantized β ~1e-4..1e-3 contours into stripes in surface-shadow transmittance. First blamed on negative-scale mirrored instances — stripes survived the baked-mirror single prim (L40 and P100), killing that theory; the baked VDB is kept anyway (cleaner). Also: Volume `clipping` defaults to 0.001, silently discarding β<1e-3 voxels on ALL devices. | GPU only | Driver now sets `precision=FULL` and `clipping=0`; `--volume-step-rate` exposed for residual step banding. |
| 7 | Camera-frame full of soft murk | Flying at 3–5 km puts 1–2 km voxel-soft cumuli right in front of a wide lens; shallow slant views integrate km of broken deck | any (framing) | Hero path at ~9 km altitude, ~45° down-look, 35 mm lens. |
| 8 | Surface reads as paper cutouts | Flat constant-color polygons have no multi-scale variation | any (authoring) | Procedural albedo *texture* (`gen_arctic_albedo.py`): fractal ice edge, floe field, feathered ponds. Also the physically meaningful quantity (albedo map). |
| 9 | Stale frames poisoning comparisons | Re-rendering after scene/settings changes while old PNGs exist: Blanca's `--skip-existing` keeps them; and a running job uses the scene it loaded at startup | workflow | Empty/rename the output dir when the scene changes (`*_oldscene` convention); frame ranges beyond the authored `endTimeCode` render as static copies of the last timeSample. |
| 10 | Validation-only geometry traps | Ortho aperture (Blender reads raw value as meters), AgX tone curve baked into PNGs, sun-azimuth conventions (er3t SAA is compass: 0=N, 90=E; USD Rz = 180−SAA) | — | `--exr` scene-linear + `.npy` dump; azimuth verified by cross-correlating shadow displacement against the τ map. |

## Standing rules distilled

- **Validation frames: CPU only.** Both GPU backends have shown volume
  artifacts (#3 OptiX, #6 CUDA); CPU has been clean in every A/B test.
- **Hero/animation frames: GPU is fine** once the scene contains no
  negative-scale volumes and no plain-tiled seams — spot-check with
  `--frame-step 10` before committing to a full sequence.
- **Never scale a volume negatively; bake mirroring into voxels instead.**
- **When the scene changes, clear the output dir before re-rendering.**
- Isolation tools that found these: `--hide-volumes` (surface-only pass),
  `--device cpu` A/B, single-frame `--frame-step` spot checks, and numpy
  ground truth (slant-τ shadow projection; cutoff coverage stats).
