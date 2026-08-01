🏛️ Project Plan — Clouds, Surfaces, Radiance, Renderer Shadows, UsdVol, and the Physics-Validation Moat

Goal (Phases 1–7, DONE): Build an OpenUSD scene and practice pipeline for a bounded 3D atmospheric digital twin: a 50 x 50 x 25 cloud domain above a half-ocean, half-land surface, with movable clouds and two sun illumination cases (slant + zenith). Mature it into a research-grade visualization with realistic lighting, cloud structure, surface albedo context, camera composition, renderer-computed cloud shadows, and a true `UsdVol`/OpenVDB cloud. Each week produced a concrete artifact previewable in `usdview` and renderable on CURC GPU nodes.

Goal (Phase 8+, IN PROGRESS — the thesis): Pivot from "make it visual" to the project's actual point per `openusd-cloud-physics-project.md` — **bridge OpenUSD to real atmospheric radiative transfer**. Ingest a real 3D LES cloud field, author it as a USD volume driven by physically-derived optical properties, render it, and **validate the rendered light transport against the EaR3T 3D-RT benchmark with a quantitative agreement metric**. Everything in Phase 8+ serves the "USD ↔ real physics" bridge; if a feature doesn't strengthen that bridge, it's out of scope.

---

## Week 1 — Environment & Static Scene
Goal: Produce a baseline 50 x 50 horizontal scene with a 25-unit vertical atmosphere/cloud domain, a half-ocean/half-land surface, and placeholder clouds.

Concepts
- USD composition, sublayers and `Kind`/model organization.
- Basic `UsdShade` materials for ocean and land.
- Clear scene units and domain bounds for x=50, y=50, z=25.

Tasks
- Create two surface prims: ocean covering half of the x-y domain and land covering the other half.
- Add a simple atmosphere/domain box or thin volume placeholder with bounds x=50, y=50, z=25.
- Add a low-res static cloud placeholder inside the 50 x 50 x 25 domain using a mesh, point cloud, or voxel-like point grid.
- Add `VariantSets` or `Kinds` so ocean/land surface layers, atmosphere bounds, and cloud visibility can be toggled.

API focus
- `pxr.Sdf`, `pxr.Usd`, `pxr.UsdShade`

Deliverable
- `assets/week1/environment.usda` (sublayers: surface_half_ocean_land, atmosphere_domain, cloud_placeholder)

---

## Week 2 — Movable Clouds & Animation
Goal: Make clouds transformable and support motion through the 50 x 50 x 25 domain.

Concepts
- `Usd.TimeCode` and `TimeSamples` for animated transforms.
- Approaches for cloud motion: baked transforms vs VDB advection.

Tasks
- Replace placeholder with a transformable cloud prim (e.g., `UsdGeom.Xform` parent for cloud `UsdGeom.Points` or a referenced VDB).
- Implement movement via either:
	- Baking transform timeSamples on the cloud Xform (fast, simple), or
	- Generating advected per-frame VDBs (higher-fidelity; export sequence of VDBs and reference per-frame).
- Keep cloud motion within or visibly passing through the x=50, y=50, z=25 domain.
- Add a `VariantSet` to switch between static cloud, manual transform animation, and velocity-field advection.

API focus
- `pxr.UsdGeom`, `Usd.TimeCode`, `pxr.Sdf` (layer/frame referencing)

Deliverable
- `assets/week2/clouds_move.usda` + a short demo sequence (5–20 frames) of cloud motion

Notes
- For long sequences prefer per-frame VDB references rather than embedding large binary data into layers.

---

## Week 3 — Cloud Voxels & Radiance Simulation
Goal: Represent clouds as volumetric data (`UsdVol`/VDB or a structured placeholder) and compare two sun illumination directions.

Concepts
- `UsdVol` integration with OpenVDB (density, scatter, absorption grids).
- Radiative-transfer (EaR3T or equivalent): computing inscattered radiance per voxel, storing results as VDB grids or textures.
- Shading: feeding radiance/scattering outputs into `UsdShade` for visualization.
- Sun-angle configuration using `UsdLux`: slant-angle sun vs zenith/overhead sun.

Tasks
- Produce OpenVDB density (and optional scattering coefficient) fields for clouds.
- Run two illumination cases:
	- Slant-angle sun: one directional light from an oblique solar angle.
	- Zenith sun: one directional light from overhead.
- Run radiative-transfer (EaR3T or your RT tool) on those VDBs to compute radiance grids OR implement an approximation shader that simulates radiance for both sun cases.
- Reference the resulting VDB grids in a `UsdVol` prim and link radiance attribute(s) into material inputs for visualization.
- Add a `VariantSet` to switch between `sun_slant` and `sun_zenith`.

API & tools
- `pxr.UsdVol`, `pxr.UsdShade`, `pxr.UsdLux`; OpenVDB tooling and EaR3T (or Python RT bindings).

Deliverable
- `assets/week3/clouds_vol.usda` + `assets/week3/vdbs/*.vdb` and two short RTX preview renders showing slant-angle vs zenith illumination.

Notes
- If the RT tool writes radiance as VDB grids (e.g., radiance_r/g/b), reference those grids directly in `UsdVol` or map to textures via `UsdShade`.

---

## Week 4 — Pipeline, Optimization & Validation
Goal: Harden the pipeline, validate the 50 x 50 x 25 scene, optimize performance, and produce final comparison renders/documentation.

Concepts
- Asset resolution (`Ar`), `usdchecker`, instancing (`PointInstancer` / prototypes), scene streaming.

Tasks
- Validate scenes with `usdchecker` and `Usd.ModelAPI` checks.
- Optimize heavy content: use instancing for repeatable cloud clusters and tiled surface patches.
- Create final RTX renders on CURC for:
	- Cloud motion over half-ocean/half-land surface.
	- Slant-angle sun illumination.
	- Zenith/overhead sun illumination.
- Write `README.md` documenting the pipeline and the radiative-transfer approach used.

Deliverable
- `renders/final.mp4`, `renders/sun_slant.png`, `renders/sun_zenith.png`, `README.md`, `repro/env.yml` (Conda env), and minimal scripts to reproduce a small demo.

---

## Week 5 — Realistic Atmospheric Rendering Pass
Goal: Upgrade `assets/week4/cloud_motion_scene.usda` from a practice-looking animation into a research-grade atmospheric visualization with better lighting, cloud appearance, surface context, and composition.

Concepts
- Sun-sky lighting with believable ambient fill instead of a black void background.
- Volumetric-style cloud structure: denser core, softer edges, irregular layered particles or VDB density.
- Arctic/ocean/ice material design using albedo values as scientific inputs, not arbitrary colors.
- Cloud-shadow footprint as a radiative cue over sea ice/ocean.
- Camera framing for either satellite-style orthographic visualization or low-oblique cinematic inspection.

Tasks
- Add a sky or atmospheric backdrop so rendered frames no longer sit in a black empty scene.
- Replace the uniform cotton-ball cloud cluster with multi-scale, randomized cloud elements:
	- broad translucent base layer,
	- denser interior core,
	- smaller wispy edge particles or low-density volume shells.
- Upgrade ground materials from flat blue/green panels to a simple Arctic surface:
	- ocean: dark blue, low albedo, slightly reflective,
	- sea ice: high albedo in the 0.5 to 0.9 research range,
	- optional melt ponds or snow bands with intermediate albedo.
- Make cloud shadow a first-class animated data layer:
	- time-sampled cloud motion,
	- moving shadow footprint,
	- optional surface warming/cooling overlay tied to shadow/albedo.
- Improve lighting with at least two variants:
	- `polar_low_sun` for long shadows and Arctic atmosphere,
	- `midday_sun` for clean scientific comparison.
- Reframe the camera so the scene reads as an atmospheric domain, not a floating sandbox.
- Render a 20-frame preview with `usdrecord` and compare it against the Week 4 output.

API & tools
- `pxr.UsdLux`, `pxr.UsdShade`, `pxr.UsdGeom`, `Usd.TimeCode`; optional `UsdVol`/OpenVDB if replacing particles with density grids.

Deliverable
- `src/week5_realistic_arctic_cloud_scene.py`
- `assets/week5/realistic_arctic_cloud_scene.usda`
- `renders/week5/cloud_realistic_###.png`
- `renders/week5/preview.mp4`
- before/after notes in `README.md` explaining what changed from the Week 4 practice render.

Success criteria
- Render has no black void background.
- Cloud edges are soft, irregular, and semi-transparent instead of uniformly circular.
- Surface materials clearly communicate ocean, sea ice, snow, and albedo contrast.
- Cloud motion and shadow are time-sampled.
- The sequence looks like a prototype atmospheric digital twin rather than a toy scene.

---

## Week 6 — Renderer-Based Cloud Shadows
Goal: Replace fake dark shadow patches with real renderer-computed shadows from cloud geometry and sun lighting, so clouds darken ocean, floes, sea ice, and snow consistently without white cutout boundaries.

Problem learned from Week 5
- Week 5 used opaque dark USD geometry as a fake cloud shadow.
- That means the surface was not physically darkened; a dark patch was pasted on top.
- Bright floe or ice polygons around the dark patch created unnatural white boundaries.
- Storm/`usdrecord` also treated point-sprite shadows too much like cloud particles, so they sometimes rendered white or cloud-like.

Concepts
- Real occluder geometry vs preview point sprites.
- `UsdLux.DistantLight` sun direction, intensity, and camera-light behavior.
- Shadow-casting mesh clouds as an intermediate step before true `UsdVol`/OpenVDB shadows.
- Renderer capability testing: Storm preview renderer vs RTX/path tracing/volume-capable renderers.
- Fallback strategy: bake a shadow mask into the surface albedo field if renderer shadows are not robust.

Tasks
- Create a Week 6 scene variant with cloud particles represented as real mesh occluders:
	- mesh spheres or ellipsoids for each cloud lobe,
	- grouped under a moving cloud Xform with timeSamples,
	- same cloud motion path as Week 5 for direct comparison.
- Add a physically meaningful sun setup:
	- `UsdLux.DistantLight` as the only main sun,
	- low polar sun angle for visible long shadows,
	- optional zenith comparison light.
- Render with camera light disabled when possible:
	- `usdrecord --disableCameraLight ...`
	- compare against default camera-light output.
- Test whether Storm produces real surface shadows from mesh cloud occluders.
- If Storm succeeds:
	- remove fake shadow patch geometry from the primary Week 6 scene,
	- keep a debug variant showing the shadow footprint proxy for comparison.
- If Storm fails:
	- document renderer limitation,
	- test RTX/path tracing on CURC,
	- implement a baked shadow-mask surface layer as the stable fallback.
- Add `VariantSet`s:
	- `cloud_representation = points_preview | mesh_occluders | future_vdb`
	- `shadow_mode = renderer_shadow | baked_shadow_mask | debug_shadow_proxy`
	- `sun_case = polar_low_sun | zenith_sun`
- Compare frame 1 and frame 20 against Week 5:
	- no white boundary around shadows,
	- shadow follows cloud motion,
	- shadow darkens all surface types consistently.

API & tools
- `pxr.UsdGeom`, `pxr.UsdLux`, `pxr.UsdShade`, `Usd.TimeCode`; optional `UsdVol`/OpenVDB and RTX renderer testing on CURC.

Deliverable
- `src/week6_renderer_shadows.py`
- `assets/week6/renderer_shadow_scene.usda`
- `renders/week6/renderer_shadow_###.png`
- `renders/week6/preview.mp4`
- `renders/week6/shadow_comparison.md` comparing:
	- Week 5 fake shadow geometry,
	- Week 6 mesh-occluder renderer shadows,
	- baked shadow-mask fallback if needed.

Success criteria
- Cloud shadow is generated by renderer lighting when using `shadow_mode = renderer_shadow`.
- No white cutout boundary appears around the shadow.
- Shadow can fall over ocean, floes, sea ice, and snow without needing separate pasted geometry.
- Cloud motion and shadow motion remain time-sampled.
- If Storm cannot support the required shadow quality, the limitation is documented and the baked-mask fallback is implemented.

---

## Week 7 — True UsdVol/OpenVDB Cloud
Goal: Replace the Week 6 point/mesh cloud placeholders with a real `UsdVol.Volume` backed by an OpenVDB fog-volume density grid named `density`, so the cloud can eventually render as a volume and cast physically meaningful volume shadows in a capable renderer.

Problem learned from Week 6
- Mesh cloud occluders are better than point sprites, but they are still not actual cloud density.
- Storm/`usdrecord` may not compute useful shadows from the mesh occluder setup.
- A scientifically meaningful atmospheric cloud should be represented as density, not just visible spheres or pasted shadow masks.

Implementation update
- Homebrew OpenVDB is available locally as C++ libraries and CLI tools.
- The `openusd` conda Python environment still does not expose `openvdb` or `pyopenvdb`.
- Therefore Week 7 uses Python for USD authoring and a small C++ OpenVDB generator for `cloud_density.vdb`.
- Generate the VDB with `repro/generate_week7_vdb.sh`; render the USD scene with `repro/render_week7.sh`.

Concepts
- `UsdVol.Volume` and `UsdVol.OpenVDBAsset`.
- Volume field relationships such as `field:density`.
- OpenVDB grid naming, grid class, and data type.
- Parent-Xform motion for one static density grid vs per-frame VDB advection.
- Volume-capable renderer testing on CURC.

Tasks
- Author a `UsdVol.Volume` at `/World/CloudVolume/Volume`.
- Author a `UsdVol.OpenVDBAsset` at `/World/CloudVolume/Fields/Density`.
- Connect the volume to the field with `field:density`.
- Expect a VDB file:
	- path: `assets/week7/vdbs/cloud_density.vdb`
	- grid name: `density`
	- grid class: `fogVolume`
	- data type: float
- Generate the VDB locally from C++ OpenVDB tooling:
	- compile `tools/generate_week7_vdb.cpp`
	- write a synthetic lumpy fog-volume density field
	- verify it with `vdb_print`
- Animate the cloud parent Xform with timeSamples, using the same motion path as Week 6.
- Add a points-preview variant for local inspection before the VDB file exists.
- Render/test with a volume-capable Hydra delegate or RTX/path tracing on CURC.

API & tools
- `pxr.UsdVol`, `pxr.UsdGeom`, `pxr.UsdLux`, `pxr.UsdShade`, `Usd.TimeCode`; Homebrew OpenVDB C++ tooling locally, then volume-capable rendering on CURC.

Deliverable
- `src/week7_usdvol_cloud.py`
- `tools/generate_week7_vdb.cpp`
- `repro/generate_week7_vdb.sh`
- `assets/week7/usdvol_cloud_scene.usda`
- `assets/week7/vdbs/README.md`
- `assets/week7/vdbs/cloud_density.vdb`
- `renders/week7/usdvol_cloud_###.png`
- `renders/week7/preview.mp4`

Success criteria
- USD stage contains a valid `UsdVol.Volume`.
- Volume has a `field:density` relationship targeting a `UsdVol.OpenVDBAsset`.
- OpenVDB asset expects `vdbs/cloud_density.vdb` and grid name `density`.
- `vdb_print` confirms a float fog-volume grid named `density`.
- Cloud parent Xform motion is time-sampled.
- A points-preview variant exists for inspection without the VDB.
- Local OpenUSD build includes `hioOpenVDB`; otherwise Storm cannot load `.vdb` field textures.
- On CURC, a volume-capable renderer can read the VDB and render the cloud as a volume.

---

## Phase 8 — Real LES Physics & EaR3T Validation (the moat)
Goal: Replace the synthetic VDB with a real LES cloud field, drive the USD volume from physically-derived optical properties, and validate the rendered radiance against EaR3T 3D radiative transfer. This is the centerpiece of the demo and every interview conversation.

Data in hand
- `data/7SEAS_480x480x150_dx100m_dz40m_dt2sec_480_0000081000_mod.nc` — SAM-LES 7SEAS shallow-cumulus field, 480 x 480 x 125, dx=dy=100 m, dz=40 m, single timestep. Variables: `QC` (cloud water), `REL` (effective radius), `NC`, `QV`, `QR`, `TABS`, `p`, winds, `QRAD`, aerosol. Cloud layer 580–2460 m, ~1% 3D cloud fraction, column τ up to ~50.

Decisions locked
- **Tile:** extract one cloudiest 64 x 64 horizontal tile, crop z[0:64] → native **64 x 64 x 64** (6.4 x 6.4 x 2.56 km). Regrid to a simple **64 x 64 x 32** (dz 40 m → 80 m, optical depth conserved).
- **Physics source:** real LES now (synthetic VDB retired). More LES timesteps later for animation.
- **Render route:** OPEN — Blender-Cycles (free, recommended default; Storm cannot do volume→surface shadows or volumetric path tracing) vs CURC RTX/HdPrman. Must be answered before the validation render.

Concepts
- Cloud water → extinction: β_ext = 1.5·LWC/(ρ_water·r_eff), with single-scattering albedo ω₀ ≈ 1 (liquid, VIS) and Henyey-Greenstein g ≈ 0.85 (or Mie from `REL`).
- The **same** β_ext field feeds both the USD volume and EaR3T — that identity is what makes the RMSE legitimate.
- Nadir radiance comparison on a shared sensor grid (e.g. 128 x 128).

Tasks
- [x] `src/cloud_field.py` — ingest `.nc` (run in `er3t` conda env), auto-pick cloudiest 64³ tile, clean `REL` (mask to cloud, cap 40 µm to drop rain contamination), compute β_ext/ω₀/g, regrid to 64 x 64 x 32, emit `.npz` (for EaR3T) + raw `.f32`/`.json` (for the VDB tool) + quicklook PNG. Verified: tile at (21.6, 41.2 km), β_max 0.086 m⁻¹, τ_max 52.6.
- [x] `src/grid_to_vdb.py` (pure Python, replaces extending the C++ tool — CURC's conda-forge `openusd` env ships OpenVDB Python bindings) reads `data/processed/cloud_ext_64x64x32.f32` + JSON and writes the `density` fog-volume VDB with anisotropic voxel transform (100 × 100 × 80 m). Verified on CURC: 8525 active voxels, cloud layer z-slabs 7–27, β_max 0.086 m⁻¹.
- [x] `src/author_cloud_usd.py` → `assets/phase8/les_cloud_scene.usda`: real-data VDB in a meters-true stage (`metersPerUnit=1`, Z-up, 6400 × 6400 × 2560 m domain, no extra volume transform — the VDB voxel transform carries the scale, so β in m⁻¹ gives physically correct τ in Cycles). Dark-ocean surface (7SEAS is marine), sun at SZA 30°/az 40°, oblique `MainCamera` + orthographic `NadirCamera` (the EaR3T sensor geometry). Passes `usdchecker`; Blender import verified (volume, grids, cameras, sun all correct).
- [x] First render of the real LES cloud (visual half of the thesis) — 2026-08-01, Blender-Cycles/OptiX on CURC (al40 L40 ~6 s/frame; Blanca A100 ~24 s at 512 samples). White multiply-scattered cumulus (SSA-driven volume color, 16 volume bounces) with renderer-computed cloud shadows on the ocean. Output: `$OPENUSD_CLD_DATAROOT/renders/les_cloud_scene_cycles/`.
- [ ] `validation/compare_ear3t.py` — run EaR3T 3D-RT on the same β_ext field, render the USD volume to the matching nadir sensor, compute RMSE / % agreement, produce the side-by-side headline figure.
- [ ] Decide and wire the render route (Cycles vs RTX/HdPrman).

API & tools
- `er3t` conda env (numpy, netCDF4, scipy, matplotlib, EaR3T); `pxr.UsdVol`; Homebrew OpenVDB C++ tooling; Blender-Cycles or CURC RTX/HdPrman.

Deliverables
- `src/cloud_field.py`, `data/processed/cloud_field_64x64x{64,32}.npz`
- real-data `cloud_density.vdb` + updated `usdvol_cloud_scene.usda`
- `validation/compare_ear3t.py` + the USD-vs-EaR3T agreement figure (RMSE / % match)
- one-pager + postmortem leading with the validation result

Success criteria
- USD volume density derives from real LES cloud water, not a procedural field.
- A single quantitative number (RMSE / % agreement) compares USD-rendered radiance to the EaR3T benchmark on the identical cloud field.
- The headline side-by-side figure is reproducible from `data/` + scripts.

Stretch (only after the above ships)
- PyTorch neural surrogate predicting cloud radiance at N× speedup, fixed accuracy.

---

## Artifacts & file layout (recommended)
- `assets/week1/environment.usda`
- `assets/week2/clouds_move.usda`
- `assets/week3/clouds_vol.usda`
- `assets/week3/vdbs/*.vdb`
- `assets/week4/cloud_motion_scene.usda`
- `assets/week5/realistic_arctic_cloud_scene.usda`
- `assets/week6/renderer_shadow_scene.usda`
- `assets/week7/usdvol_cloud_scene.usda`
- `assets/week7/vdbs/cloud_density.vdb`
- `renders/final.mp4`, `renders/sun_slant.png`, `renders/sun_zenith.png`
- `renders/week5/cloud_realistic_###.png`, `renders/week5/preview.mp4`
- `renders/week6/renderer_shadow_###.png`, `renders/week6/preview.mp4`
- `renders/week7/usdvol_cloud_###.png`, `renders/week7/preview.mp4`
- `data/7SEAS_*.nc` (real LES field), `data/processed/cloud_field_64x64x{64,32}.npz`, `data/processed/cloud_ext_64x64x32.{f32,json}`, `data/processed/cloud_field_quicklook.png`
- `src/cloud_field.py`, `validation/compare_ear3t.py` (the agreement metric + headline figure)
- `repro/env.yml`, `repro/run_demo.py`

## Risks & edge cases
- Storage & I/O: per-frame VDBs can be large — prefer referencing and streaming.
- Rendering performance: volumetric scattering is expensive. Use low-res previews and upres only for final renders.
- Tool compatibility: ensure EaR3T/OpenVDB outputs mesh with compatible grid names and types for `UsdVol`.
- Visual maturity: simple point clouds and flat planes read as practice assets. Use surface context, sky lighting, layered density, and thoughtful camera framing to make the scientific scene legible.
- Shadow realism: fake dark geometry can create white cutout boundaries on bright ice. Prefer renderer-computed shadows from mesh/volume occluders; use baked shadow masks only as a fallback.
- VDB generation: the local Python environment can author `UsdVol` but cannot import `openvdb`/`pyopenvdb`. Use the C++ generator with Homebrew OpenVDB locally, or use OpenVDB tooling on CURC for larger/advection-ready grids.
- Local rendering: `HdStormRendererPlugin` needs the `hioOpenVDB` plugin. If it reports `Unknown field data type 'vdb'`, rebuild OpenUSD with `PXR_ENABLE_OPENVDB_SUPPORT=ON`.

## Quick checklist
- [x] Week 1: 50 x 50 x 25 domain + half-ocean/half-land surface + static cloud placeholder (`assets/week1`)
- [x] Week 2: make clouds movable within the domain (baked transforms or advected VDB sequence)
- [x] Week 3: generate VDBs or structured cloud volume -> run/render slant and zenith sun cases -> connect radiance grids to `UsdVol`
- [x] Week 4: run validation, optimize/compose final scene, produce final comparison render targets and README
- [x] Week 5: improve realism with sky lighting, Arctic albedo materials, layered cloud density, animated shadows, and stronger camera framing
- [x] Week 6: replace fake shadow patches with renderer-computed shadows from mesh cloud occluders (`renders/week6/*.png`, `shadow_comparison.md`)
- [x] Week 7: author a true `UsdVol.Volume` with an OpenVDB density field; synthetic VDB + Storm preview renders done
- [~] Phase 8: real LES physics & EaR3T validation — `src/cloud_field.py` ingest DONE; VDB conversion, real-data render, and `compare_ear3t.py` remain

## Next steps I can do now
- Extend `tools/generate_week7_vdb.cpp` to read `data/processed/cloud_ext_64x64x32.f32` and write the real-data `density` VDB.
- Repoint `week7_usdvol_cloud.py` at the real-data VDB and render the first LES cloud.
- Scaffold `validation/compare_ear3t.py` against the 64³ field once the render route (Cycles vs RTX) is chosen.
