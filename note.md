# Project Notes

## Phase 8 Lessons: the Rendering-Artifact Saga (Cycles + UsdVol)

Full catalog with root causes and evidence: `docs/rendering_artifacts.md`
(10 artifacts). These are the transferable lessons, not the individual bugs.

### What happened, in one paragraph

Getting the real-LES cloud field from USD/VDB to validated pixels hit ten
distinct artifacts. Most were caught quickly (VDB file-format silently too
new for Blender, clouds rendering as dark smoke because Cycles defaults to
zero volume bounces, OptiX zero-radiance boxes, a compass-vs-math sun-azimuth
convention mismatch, non-cyclic tiling slicing clouds into flat walls). The
expensive one was the stripe hunt: wavy scanline stripes over the surface in
GPU hero frames survived THREE confident fixes — (1) replacing negative-scale
mirrored volume instances with a voxel-baked mirror VDB, (2) forcing the GPU
NanoVDB texture from HALF to FULL precision, (3) setting volume clipping
0.001 -> 0. The actual cause was none of them: Blender's denoiser
(OpenImageDenoise, ON by default) was streaking its own noisy 512-sample
input. Proven by a two-job A/B on the worst frame: `--no-denoise` left pure
grain and no stripes; 2048 samples with denoise left a clean smooth image.

### Lessons learned

1. **Distrust "GPU-only" (or any single-variable) framing until the A/B is
   truly controlled.** "CPU clean, GPU striped" was a confound: every CPU
   render was a 4096-sample nadir validation frame, every GPU render a
   256-512-sample oblique hero frame. The device was never the variable —
   sample count was. Three rounds of fixes targeted the wrong axis because
   the two comparison sets differed in camera, samples, AND device at once.
2. **Classify an artifact in image space vs world space before theorizing.**
   Zooming in settled it in minutes: the stripes were strictly image-space
   horizontal scanlines (1-3 px period), which no data/precision/step-size
   mechanism can produce — those band along world-space iso-tau contours.
   Post-process (denoiser) was the only remaining suspect class.
3. **Renderer DEFAULTS are part of the physics.** Four defaults silently
   changed results: volume bounces 0 (black clouds), volume clipping 1e-3
   (discarded real beta on every device — corrupted the validation field,
   not just the look), NanoVDB HALF precision, denoising ON. For any
   quantitative pipeline, print/pin every relevant setting in the driver
   rather than trusting factory values.
4. **A refuted theory can still leave a good fix.** The baked-mirror VDB and
   FULL-precision/clipping=0 changes didn't cure the stripes, but all are
   kept: they remove real (latent) hazards and made the scene simpler.
5. **Make A/Bs cheap and decisive.** Single-frame Slurm jobs (~1 min GPU)
   with one flag changed (`--no-denoise`, `--device cpu`, `--hide-volumes`,
   `--frame-step 10`) answered questions that hours of full-sequence renders
   could not. The driver accumulating these isolation flags is itself a
   diagnostic toolkit now.
6. **Denoisers need clean input, not just any input.** Denoising is not a
   substitute for samples in high-variance regions (dark surface behind a
   scattering veil). Hero standard is now 2048 samples + denoise; the
   optically-thin veil (the variance source) is cut from the hero VDB at
   beta < 2e-3.
7. **Output-dir hygiene is a correctness issue.** Stale frames from an old
   scene/settings repeatedly masqueraded as "the fix didn't work" (or
   vice versa). Rule: when the scene changes, archive the output dir
   (`*_old`-suffix convention) before re-rendering; check job start time
   against commit time before believing a render tested your fix.

## Week 5 Rendering Mistake: Shadow Point Sprites

Week 5 initially drifted away from the Week 2/Week 4 shadow approach.

Week 2 used a simple, explicit dark projected shadow:

```python
shadow.CreateDisplayColorAttr([Gf.Vec3f(0.004, 0.006, 0.004)])
shadow.CreateDisplayOpacityAttr([0.72])
```

That worked because the shadow was clearly authored as a dark surface cue.

In Week 5, I changed the shadow/cooling overlay into `UsdGeom.Points` sprites with lighter blue-gray colors. In Storm/`usdrecord`, those point sprites were rendered too much like cloud particles, so the intended shadow appeared white or cloud-like instead of dark. That was the mistake.

Rule going forward:

- Use dark projected surface geometry for cloud shadows.
- Prefer flat mesh ellipses or polygons on the surface for renderer-stable shadows.
- Avoid using bright or semi-transparent `UsdGeom.Points` as shadows in Storm/`usdrecord`.
- Keep any cooling or radiative proxy visually separate from the shadow, and do not let it hide the physical shadow cue.

## CURC Renderer Upgrade Notes: OpenUSD, RTX, HdPrman, Omniverse

Problem from Week 7:

- Local `HdStormRendererPlugin` can display the `UsdVol`/OpenVDB cloud after `hioOpenVDB` is enabled.
- Storm is still a preview renderer and may not produce reliable VDB volume-to-surface shadows.
- For physically meaningful cloud shadows, test a stronger renderer path on CURC instead of continuing to tune fake geometry in Storm.

Recommended investigation order:

1. **CURC Core Desktop for interactive GPU visualization**
   - Use Open OnDemand -> Interactive Apps -> Core Desktop.
   - CURC says Core Desktop runs on the visualization cluster and can provide NVIDIA Tesla K80 or NVIDIA Quadro RTX 8000 GPUs.
   - This is the best first place to launch GUI tools like `usdview`, Omniverse Kit/USD Composer if available, or renderer test viewers.
   - Note: CURC warns these visualization GPUs are shared and not meant for heavy computation.
   - Source: https://curc.readthedocs.io/en/latest/open_ondemand/core_desktop.html

2. **CURC Alpine GPU jobs for batch rendering experiments**
   - Start from Alpine Quick Start: load `slurm/alpine`, then request GPU resources through Slurm.
   - Use this path for repeatable render tests once the renderer command is known.
   - Source: https://curc.readthedocs.io/en/latest/clusters/alpine/quick-start.html

3. **HdPrman / RenderMan path**
   - OpenUSD supports a Hydra plugin named `hdPrman`.
   - It is not built by default.
   - Building it requires RenderMan 25.0 or newer.
   - `build_usd.py` supports `--prman` and `--prman-location PRMAN_LOCATION`.
   - Manual CMake variables include `PXR_BUILD_PRMAN_PLUGIN=ON` and `RENDERMAN_LOCATION=$RMANTREE`.
   - This is likely the cleanest Hydra-renderer route for physically based offline testing if RenderMan licensing/install is available on CURC.
   - Source: https://openusd.org/dev/plugins_renderman.html

4. **NVIDIA Omniverse / RTX path**
   - NVIDIA Omniverse is OpenUSD-based and includes the RTX Renderer.
   - NVIDIA describes Omniverse RTX Renderer as a physically based renderer for Windows and Linux, with RTX Real-Time and RTX Interactive Path Tracing modes.
   - This is the promising route for checking whether a path-traced RTX renderer gives true volume shadows for the Week 7 VDB cloud.
   - Omniverse Launcher was deprecated on October 1, 2025; current developer entry points are Omniverse Kit, GitHub templates, NGC packages, APIs, and SDKs.
   - Sources:
     - https://docs-prod.omniverse.nvidia.com/materials-and-rendering/latest/rtx-renderer.html
     - https://docs.omniverse.nvidia.com/kit/docs/kit-manual/107.0.3/guide/kit_overview.html
     - https://developer.nvidia.com/omniverse/legacy-tools

5. **Omniverse Kit application route**
   - Kit is the SDK behind Omniverse applications like USD Composer and USD Explorer.
   - Kit combines USD/Hydra, Omniverse RTX Renderer, Omniverse Client Library, Carbonite, Python scripting, and GPU UI tooling.
   - For CURC, test this first in Core Desktop because it needs an RTX-capable host for interactive viewport rendering.
   - Source: https://docs.omniverse.nvidia.com/kit/docs/kit-manual/107.0.3/guide/kit_overview.html

6. **Streaming / headless route if GUI is hard**
   - NVIDIA Kit App Streaming keeps RTX rendering on an RTX host and streams the app to a browser.
   - This may fit CURC better than direct GUI rendering if Core Desktop is unstable or access-controlled.
   - Source: https://docs.omniverse.nvidia.com/kit/docs/kit-app-template/108.0/docs/streaming.html

Practical next action:

- On CURC, open a Core Desktop RTX 8000 session.
- Check available modules/software:
  - `module avail usd`
  - `module avail renderman`
  - `module avail omniverse`
  - `module avail cuda`
  - `module avail nvidia`
- If no module exists, ask CURC whether RenderMan, Omniverse Kit/USD Composer, or a Hydra renderer delegate is supported on the visualization nodes.
- If RenderMan exists, try rebuilding OpenUSD with `hdPrman`.
- If Omniverse/Kit exists, load the Week 7 USD and test RTX/path tracing volume shadows.
- If neither is practical, keep `UsdVol` for real cloud representation but compute cloud-shadow/radiative forcing externally and author it as a scientific albedo/irradiance mask layer.
