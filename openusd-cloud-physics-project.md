# USD-RT Clouds — Physically-Grounded Volumetric Clouds in OpenUSD

> **Working title (rename freely):** `usd-rt-clouds` · `physicloud` · `cloud-twin-usd`

## Thesis (the whole point of this project)

**This project exists to prove one thing: that I can connect OpenUSD to *real* atmospheric physics — not just author pretty 3D scenes, and not just run radiative-transfer models in the dark, but bridge the two.**

A graphics engineer can make a volumetric cloud that *looks* right. An atmospheric scientist can compute how light *actually* travels through a cloud. **Almost nobody can do both.** This repo is the proof that I sit at that intersection: I take a physically real 3D cloud field, author it as an OpenUSD volume, render it, and then show that the rendered light transport agrees with a validated 3D radiative-transfer benchmark (EaR3T).

Every design decision below serves that thesis. If a feature doesn't strengthen the **"USD ↔ real physics"** bridge, it's out of scope.

---

## Why this matters for my target roles

This is the exact skill bridge that the most relevant roles in my search demand:

- **NVIDIA Earth-2 / SciML** — Earth-2 is climate/weather *digital twins rendered in Omniverse*, and Omniverse runs on OpenUSD. Atmospheric science + USD + real-time 3D *is* the Earth-2 skill set. (These were my highest-fit roles: 4.5–4.6.)
- **Omniverse / digital-twin / spatial-AI engineering** — physically-accurate simulation content authored in USD.
- **Remote sensing / Image Scientist roles** — demonstrates I can move fluidly between measured radiance, physical models, and 3D representation.

**Positioning rule:** this is never described as *"I learned OpenUSD."* It is always *"I built a physically-grounded cloud digital-twin pipeline that bridges atmospheric radiative transfer and real-time 3D."*

---

## What it demonstrates (skills surfaced)

| Capability | How this project shows it |
|---|---|
| OpenUSD authoring | Volume scene authored programmatically in Python (`pxr`) |
| **Physics integration (the moat)** | Cloud optical properties driven by real atmospheric values; output validated against EaR3T 3D-RT |
| Scientific Python | Real cloud-field ingestion, NetCDF/HDF5, NumPy/Xarray pipeline |
| Rendering / visualization | Hydra / Cycles volumetric path tracing, fly-through demo |
| ML bridge *(stretch)* | PyTorch neural surrogate for fast cloud radiance |

---

## Architecture

```
Real 3D cloud field            OpenUSD authoring            Render
(EaR3T / LES / satellite)  →   (Python pxr: Volume    →   (Hydra / Blender
 density + optical props)       + OpenVDB density)          Cycles path trace)
                                       │
                                       ▼
                          Physics validation (THE POINT)
                   USD-rendered radiance  vs  EaR3T 3D-RT benchmark
                          → agreement metric (RMSE / % match)
                                       │
                                       ▼
                      [Stretch] PyTorch neural surrogate
                   predicts cloud radiance at N× speedup, fixed accuracy
```

---

## Scope & milestones (tight on purpose — ship in ~2 weeks)

### Week 1 — MVP: make it visual
- Author a volumetric cloud scene in OpenUSD **programmatically in Python** (`pxr` / usd-core), using the USD `Volume` + OpenVDB density schema.
- Render it (see tech stack for the free Blender-Cycles route).
- **Deliverable:** public GitHub repo + a rendered fly-through video / stills on `yuwenchen.tw`.
- *This alone is portfolio-worthy — but it is not yet the thesis.*

### Week 2 — the moat: inject the real physics *(this is what makes the project matter)*
- Drive the cloud's **optical depth, single-scattering albedo, and phase function from real atmospheric values**, OR import a **real 3D cloud field from my EaR3T / PhD work** into the USD volume.
- Produce the headline result: **side-by-side of the USD-rendered cloud vs the EaR3T physically-correct radiative transfer, with a quantitative agreement metric.**
- **Deliverable:** the validation figure + write-up. This is the centerpiece of the demo and every interview conversation.

### Stretch — only after the above ships
- Small PyTorch neural surrogate predicting cloud radiance fast (ties in PINNs/ML background; hits NVIDIA's "neural reconstruction" theme).
- **Deliverable:** ×speedup vs full RT at fixed accuracy.

---

## Metrics (so it's not "just pretty")

- **Physical fidelity (primary):** RMSE / % agreement of USD-rendered radiance vs EaR3T benchmark — *the number that proves the bridge is real.*
- **Performance:** render time, voxel count / scene scale, fps if real-time.
- **Surrogate (stretch):** ×speedup at fixed accuracy.

---

## Interview pack (deliverables)

1. **One-pager** — problem → architecture → the physics-validation result → metrics. Lead with the EaR3T agreement figure.
2. **Demo** — fly-through video + stills on `yuwenchen.tw`; the USD-vs-EaR3T side-by-side front and center. (Interactive USD-on-web viewer is a nice-to-have, not MVP.)
3. **Postmortem** — fidelity-vs-performance trade-offs, OpenUSD volume limitations, what I'd build next. *Show the trade-offs — that's where the physics judgment shows.*

---

## Tech stack (recommended, accessible)

- **OpenUSD:** `usd-core` (`pxr`), author scene in **Python** — lean on Python strength over GUI clicking.
- **Volumes:** OpenVDB / NanoVDB for cloud density; USD `Volume` schema.
- **Render (free route):** **Blender USD import + Cycles** volumetric path tracer — beautiful renders, runs anywhere, no Omniverse license. Upgrade to **Omniverse Kit / Isaac Sim** later if a GPU box is available (and to name-drop Omniverse directly).
- **Physics source:** real 3D cloud fields from EaR3T / LES / satellite (the unfair advantage). Procedural cloud generator as a Week-1 placeholder if needed.
- **Validation:** EaR3T 3D radiative-transfer toolbox (already in my wheelhouse).
- **Web:** rendered video + stills on `yuwenchen.tw`; optional three.js / USD-wasm / glTF viewer.

---

## Suggested repo structure

```
usd-rt-clouds/
├── README.md                  # this brief, trimmed to the thesis + demo
├── src/
│   ├── author_cloud_usd.py    # Python: real cloud field → USD Volume
│   ├── cloud_field.py         # ingest EaR3T/LES/satellite → density + optical props
│   └── render.py              # Hydra / Blender-Cycles render driver
├── validation/
│   └── compare_ear3t.py       # USD-rendered radiance vs EaR3T → agreement metric
├── data/                      # sample cloud field (small, redistributable)
├── renders/                   # output stills + fly-through video
└── docs/
    ├── one-pager.md           # interview pack
    └── postmortem.md
```

### Python USD-authoring starter stub

```python
# src/author_cloud_usd.py
from pxr import Usd, UsdGeom, UsdVol, Sdf

def build_cloud_stage(vdb_path: str, out_usd: str) -> None:
    """Author an OpenUSD stage with a volumetric cloud from an OpenVDB density grid."""
    stage = Usd.Stage.CreateNew(out_usd)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

    vol = UsdVol.Volume.Define(stage, "/World/Cloud")
    field = UsdVol.OpenVDBAsset.Define(stage, "/World/Cloud/density")
    field.CreateFilePathAttr(vdb_path)
    field.CreateFieldNameAttr("density")
    vol.CreateFieldRelationship("density", field.GetPath())

    # TODO Week 2 — drive these from REAL atmospheric values (the moat):
    #   optical depth, single-scattering albedo, phase function (g)
    stage.GetRootLayer().Save()
```

---

## Open scoping decisions (answer these before Day 1)

1. **Render route:** GPU box / Omniverse access → Omniverse Kit; otherwise → **Blender-Cycles** (free, recommended default).
2. **Cloud data:** real EaR3T/PhD cloud field from Day 1, or procedural placeholder in Week 1 then swap real data in Week 2?

---

## How to talk about it (one-liner for CV / LinkedIn / interviews)

> *"Built a physically-grounded cloud digital-twin pipeline in OpenUSD: ingest a real 3D cloud field, author it as a USD volume, render it, and validate the light transport against a 3D radiative-transfer benchmark (EaR3T) to within [X]%. Demonstrates the bridge between atmospheric physics and real-time 3D / Omniverse."*

**Once this ships, flip `OpenUSD` to "claim" in the ATS keyword bank (`modes/_profile.md`).**
