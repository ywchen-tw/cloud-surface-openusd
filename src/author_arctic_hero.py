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

import os
import sys

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdShade

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from author_cloud_usd import (
    ROOT, SUN_SAA_DEG, bind, create_cloud_volume, load_domain, look_at_matrix,
)

ALBEDO_TEX_REL = "../../data/processed/arctic_albedo_texture.png"  # gen_arctic_albedo.py

OUT_USD = os.path.join(ROOT, "assets", "phase8", "les_cloud_arctic_scene.usda")
SUN_SZA_DEG = 55.0   # polar low sun, long shadows
FRAMES = 20
FPS = 8              # matches the ffmpeg preview assembly in the sbatch scripts


def create_arctic_surface(stage, lo, hi):
    """One quad draped with the procedural albedo texture (gen_arctic_albedo.py).

    Flat constant-color polygons read as paper cutouts at any resolution;
    realism comes from multi-scale variation in the albedo map itself —
    which is also the physically meaningful quantity for the Arctic story.
    """
    mat = UsdShade.Material.Define(stage, "/World/Materials/ArcticAlbedo")
    st_reader = UsdShade.Shader.Define(stage, "/World/Materials/ArcticAlbedo/StReader")
    st_reader.CreateIdAttr("UsdPrimvarReader_float2")
    st_reader.CreateInput("varname", Sdf.ValueTypeNames.String).Set("st")
    tex = UsdShade.Shader.Define(stage, "/World/Materials/ArcticAlbedo/AlbedoTex")
    tex.CreateIdAttr("UsdUVTexture")
    tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(ALBEDO_TEX_REL)
    tex.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
        st_reader.ConnectableAPI(), "result")
    tex.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set("clamp")
    tex.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set("clamp")
    surf = UsdShade.Shader.Define(stage, "/World/Materials/ArcticAlbedo/PreviewSurface")
    surf.CreateIdAttr("UsdPreviewSurface")
    surf.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(
        tex.ConnectableAPI(), "rgb")
    surf.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.7)
    surf.CreateInput("specular", Sdf.ValueTypeNames.Float).Set(0.02)
    mat.CreateSurfaceOutput().ConnectToSource(surf.ConnectableAPI(), "surface")

    mesh = UsdGeom.Mesh.Define(stage, "/World/Surface/ArcticSurface")
    mesh.CreatePointsAttr([Gf.Vec3f(lo, lo, 0), Gf.Vec3f(hi, lo, 0),
                           Gf.Vec3f(hi, hi, 0), Gf.Vec3f(lo, hi, 0)])
    mesh.CreateFaceVertexCountsAttr([4])
    mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    mesh.CreateExtentAttr([Gf.Vec3f(lo, lo, 0), Gf.Vec3f(hi, hi, 0)])
    UsdGeom.PrimvarsAPI(mesh).CreatePrimvar(
        "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.varying
    ).Set([(0, 0), (1, 0), (1, 1), (0, 1)])
    bind(mesh, mat)


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
