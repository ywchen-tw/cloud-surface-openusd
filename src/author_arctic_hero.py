"""Arctic hero fly-through — the website showpiece scene.

Authors `assets/phase8/les_cloud_arctic_scene.usda`:
  - the real 7SEAS LES cloud field, 3x3 periodic-tiled (19.2 km visible domain)
  - an Arctic surface with research-grade albedos (project goal #2):
      open water ~0.06, marginal floes ~0.75, sea-ice sheet ~0.8,
      snow band ~0.9, melt ponds ~0.3 (teal)
  - polar low sun (SZA 55 deg — visualization choice; validation stays SZA 30)
  - /World/Camera/MainCamera animated over frames 1-20 with timeSamples
    (slow rising dolly across the marginal ice zone toward the ice edge)

Run:  conda run -n openusd python src/author_arctic_hero.py
Render (GPU hero route, 20 frames -> preview.mp4):
  sbatch repro/curc/render_week7_cycles.sbatch assets/phase8/les_cloud_arctic_scene.usda 1 20 256
"""

import math
import os
import sys

from pxr import Gf, Usd, UsdGeom, UsdLux

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from author_cloud_usd import (
    ROOT, SUN_SAA_DEG, bind, create_cloud_volume, load_domain,
    look_at_matrix, make_preview_material,
)

OUT_USD = os.path.join(ROOT, "assets", "phase8", "les_cloud_arctic_scene.usda")
SUN_SZA_DEG = 55.0   # polar low sun, long shadows
FRAMES = 20
FPS = 8              # matches the ffmpeg preview assembly in the sbatch scripts


def polygon(stage, path, pts_xy, z, mat):
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr([Gf.Vec3f(x, y, z) for x, y in pts_xy])
    mesh.CreateFaceVertexCountsAttr([len(pts_xy)])
    mesh.CreateFaceVertexIndicesAttr(list(range(len(pts_xy))))
    xs = [p[0] for p in pts_xy]
    ys = [p[1] for p in pts_xy]
    mesh.CreateExtentAttr([Gf.Vec3f(min(xs), min(ys), z), Gf.Vec3f(max(xs), max(ys), z)])
    bind(mesh, mat)


def ellipse_pts(cx, cy, rx, ry, n=36, jitter=0.0, seed=0):
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        j = 1.0 + jitter * math.sin(seed + 3 * a) if jitter else 1.0
        pts.append((cx + rx * j * math.cos(a), cy + ry * j * math.sin(a)))
    return pts


def create_arctic_surface(stage, lo, hi):
    mats = {
        "ocean": make_preview_material(stage, "/World/Materials/OpenWater", (0.015, 0.055, 0.11), roughness=0.55),
        "floe": make_preview_material(stage, "/World/Materials/Floe", (0.70, 0.76, 0.80)),
        "sheet": make_preview_material(stage, "/World/Materials/SeaIceSheet", (0.78, 0.82, 0.85)),
        "snow": make_preview_material(stage, "/World/Materials/SnowBand", (0.90, 0.92, 0.95)),
        "pond": make_preview_material(stage, "/World/Materials/MeltPond", (0.12, 0.34, 0.44), roughness=0.35),
    }
    UsdGeom.Xform.Define(stage, "/World/Surface")

    # Open water base across the whole tiled domain (albedo ~0.06).
    polygon(stage, "/World/Surface/OpenWater",
            [(lo, lo), (hi, lo), (hi, hi), (lo, hi)], 0.0, mats["ocean"])

    # Consolidated sea-ice sheet north of a jagged ice edge (albedo ~0.8).
    polygon(stage, "/World/Surface/SeaIceSheet",
            [(lo, 10500), (-2500, 9300), (1500, 10800), (5200, 9100),
             (8600, 10400), (hi, 9600), (hi, hi), (lo, hi)], 2.0, mats["sheet"])

    # Snow band on the upper sheet (albedo ~0.9).
    polygon(stage, "/World/Surface/SnowBand",
            [(lo, 11800), (2000, 11300), (7000, 12000), (hi, 11400),
             (hi, hi), (lo, hi)], 3.0, mats["snow"])

    # Marginal-ice-zone floes drifting in open water (albedo ~0.75).
    floes = [(-3500, 7200, 950), (500, 6800, 700), (3800, 7700, 1150),
             (7600, 6500, 820), (10800, 7900, 620), (-600, 4400, 520),
             (6100, 4100, 460), (12000, 5600, 700)]
    for k, (cx, cy, r) in enumerate(floes):
        polygon(stage, f"/World/Surface/Floe_{k:02d}",
                ellipse_pts(cx, cy, r, 0.8 * r, n=9, jitter=0.18, seed=k),
                2.0, mats["floe"])

    # Melt ponds on the ice sheet (albedo ~0.3, teal — the research signal).
    ponds = [(0, 11400, 620, 340), (4200, 11000, 820, 430),
             (8300, 11600, 520, 300), (-3100, 11200, 430, 260),
             (11000, 10800, 560, 330)]
    for k, (cx, cy, rx, ry) in enumerate(ponds):
        polygon(stage, f"/World/Surface/MeltPond_{k:02d}",
                ellipse_pts(cx, cy, rx, ry, n=28, jitter=0.10, seed=10 + k),
                4.0, mats["pond"])


def create_sun(stage):
    sun = UsdLux.DistantLight.Define(stage, "/World/Lighting/Sun")
    sun.CreateIntensityAttr(3000.0)
    sun.CreateAngleAttr(0.53)
    sun.CreateColorAttr(Gf.Vec3f(1.0, 0.96, 0.90))  # low-sun warmth
    xf = UsdGeom.Xformable(sun)
    xf.AddRotateZOp().Set(180.0 - SUN_SAA_DEG)
    xf.AddRotateXOp().Set(SUN_SZA_DEG)


def smoothstep(t):
    return t * t * (3.0 - 2.0 * t)


def create_flythrough_camera(stage):
    cam = UsdGeom.Camera.Define(stage, "/World/Camera/MainCamera")
    cam.CreateFocalLengthAttr(24.0)
    cam.CreateClippingRangeAttr(Gf.Vec2f(10.0, 90000.0))
    op = UsdGeom.Xformable(cam).AddTransformOp()

    # Steep aerial survey: stay well above the cloud tops (2240 m) and look
    # down at ~45-50 deg so the sightline crosses the broken cloud deck once
    # instead of skimming through kilometres of it (a shallow slant view
    # turns the whole lower frame into murk). The path drifts NE: open water
    # + floes under the clouds first, then the ice edge and melt ponds.
    eye_a, eye_b = (-1000.0, -500.0, 5400.0), (4600.0, 5200.0, 4600.0)
    tgt_a, tgt_b = (1800.0, 3000.0, 0.0), (7800.0, 9800.0, 0.0)
    for f in range(1, FRAMES + 1):
        t = smoothstep((f - 1) / (FRAMES - 1))
        eye = tuple(a + t * (b - a) for a, b in zip(eye_a, eye_b))
        tgt = tuple(a + t * (b - a) for a, b in zip(tgt_a, tgt_b))
        op.Set(look_at_matrix(eye, tgt), time=Usd.TimeCode(f))


def main():
    meta, size_x, size_y, size_z = load_domain()
    os.makedirs(os.path.dirname(OUT_USD), exist_ok=True)
    if os.path.exists(OUT_USD):
        os.remove(OUT_USD)

    stage = Usd.Stage.CreateNew(OUT_USD)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetMetadata("metersPerUnit", 1.0)
    stage.SetStartTimeCode(1)
    stage.SetEndTimeCode(FRAMES)
    stage.SetTimeCodesPerSecond(FPS)
    stage.SetFramesPerSecond(FPS)

    world = UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(world.GetPrim())
    Usd.ModelAPI(world.GetPrim()).SetKind("assembly")

    lo, hi = -size_x, 2 * size_x
    create_arctic_surface(stage, lo, hi)
    create_cloud_volume(stage, meta, size_x, size_y, size_z, periodic=True)
    create_sun(stage)
    create_flythrough_camera(stage)

    stage.GetRootLayer().Save()
    print(f"wrote {OUT_USD}")
    print(f"  {hi - lo:.0f} m domain, frames 1-{FRAMES} @ {FPS} fps, sun SZA {SUN_SZA_DEG:.0f}")


if __name__ == "__main__":
    main()
