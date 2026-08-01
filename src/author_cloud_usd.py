"""Phase 8 — author the real-LES cloud stage (plan.md: "the moat").

Authors `assets/phase8/les_cloud_scene.usda`: the 7SEAS shallow-cumulus
extinction field (assets/week7/vdbs/cloud_density.vdb, written by
src/grid_to_vdb.py from the cloudiest 64x64 LES tile) as a `UsdVol.Volume`
in a physically-scaled stage.

Scale convention — everything in meters (metersPerUnit = 1):
  - domain: 6400 x 6400 m tile, cloud layer ~560-2240 m altitude
  - the VDB's index->world transform already encodes the anisotropic
    100 x 100 x 80 m voxels, so the Volume prim needs NO extra transform
  - beta_ext stored per meter -> Cycles volume coefficients are per scene
    unit, so rendered optical depth is physically correct with no tuning

Cameras:
  - /World/Camera/MainCamera   oblique perspective hero view (default render)
  - /World/Camera/NadirCamera  orthographic straight-down 6.4 km sensor —
                               the EaR3T comparison geometry (each pixel is a
                               vertical ray, matching a nadir radiance grid)

Run:  conda run -n openusd python src/author_cloud_usd.py
Then: sbatch repro/curc/render_week7_cycles.sbatch assets/phase8/les_cloud_scene.usda 1 1 256
"""

import json
import math
import os

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdShade, UsdVol

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_USD = os.path.join(ROOT, "assets", "phase8", "les_cloud_scene.usda")
VDB_REL = "../week7/vdbs/cloud_density.vdb"
META_JSON = os.path.join(ROOT, "data", "processed", "cloud_ext_64x64x32.json")

SUN_SZA_DEG = 30.0  # solar zenith angle; keep in sync with the EaR3T run
SUN_AZ_DEG = 40.0   # solar azimuth (deg from +x, CCW)


def load_domain():
    with open(META_JSON) as fh:
        meta = json.load(fh)
    dx, dy, dz = meta["dx_m"], meta["dy_m"], meta["dz_m"]
    return meta, meta["nx"] * dx, meta["ny"] * dy, meta["nz"] * dz


def make_preview_material(stage, path, color, roughness=0.9):
    material = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, path + "/PreviewSurface")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
    shader.CreateInput("specular", Sdf.ValueTypeNames.Float).Set(0.02)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return material


def bind(prim, material):
    api = UsdShade.MaterialBindingAPI.Apply(prim.GetPrim())
    api.Bind(material)


def create_ocean(stage, size_x, size_y):
    # 7SEAS is a tropical marine shallow-cumulus case: dark low-albedo ocean.
    mesh = UsdGeom.Mesh.Define(stage, "/World/Surface/Ocean")
    mesh.CreatePointsAttr(
        [Gf.Vec3f(0, 0, 0), Gf.Vec3f(size_x, 0, 0), Gf.Vec3f(size_x, size_y, 0), Gf.Vec3f(0, size_y, 0)]
    )
    mesh.CreateFaceVertexCountsAttr([4])
    mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    mesh.CreateExtentAttr([Gf.Vec3f(0, 0, 0), Gf.Vec3f(size_x, size_y, 0)])
    mesh.CreateDisplayColorAttr([Gf.Vec3f(0.02, 0.09, 0.17)])
    ocean_mat = make_preview_material(stage, "/World/Materials/OceanDark", (0.02, 0.09, 0.17))
    bind(mesh, ocean_mat)


def create_cloud_volume(stage, meta, size_x, size_y, size_z):
    UsdGeom.Xform.Define(stage, "/World/CloudVolume")
    volume = UsdVol.Volume.Define(stage, "/World/CloudVolume/Volume")
    volume.CreateExtentAttr([Gf.Vec3f(0, 0, 0), Gf.Vec3f(size_x, size_y, size_z)])

    field = UsdVol.OpenVDBAsset.Define(stage, "/World/CloudVolume/Fields/Density")
    field.CreateFilePathAttr(VDB_REL)
    field.CreateFieldNameAttr(meta.get("grid_name", "density"))
    field.CreateFieldClassAttr(UsdVol.Tokens.fogVolume)
    volume.CreateFieldRelationship("density", field.GetPath())

    prim = volume.GetPrim()
    prim.SetCustomDataByKey("units", meta.get("units", "extinction_per_meter"))
    prim.SetCustomDataByKey("ssa", float(meta.get("ssa", 1.0)))
    prim.SetCustomDataByKey("asymmetry_g", float(meta.get("asymmetry_g", 0.85)))
    prim.SetCustomDataByKey("source", "7SEAS SAM-LES cloudiest 64x64 tile via src/cloud_field.py")


def create_sun(stage):
    sun = UsdLux.DistantLight.Define(stage, "/World/Lighting/Sun")
    sun.CreateIntensityAttr(2500.0)
    sun.CreateAngleAttr(0.53)
    sun.CreateColorAttr(Gf.Vec3f(1.0, 0.985, 0.95))
    # Identity aims the light straight down (-Z); tilt by the solar zenith
    # angle, then set the azimuth about Z.
    xf = UsdGeom.Xformable(sun)
    xf.AddRotateZOp().Set(SUN_AZ_DEG)
    xf.AddRotateXOp().Set(SUN_SZA_DEG)


def look_at_matrix(eye, target):
    """World transform for a USD camera at `eye` looking at `target` (Z-up)."""
    fwd = (Gf.Vec3d(*target) - Gf.Vec3d(*eye)).GetNormalized()
    right = Gf.Cross(fwd, Gf.Vec3d(0, 0, 1)).GetNormalized()
    up = Gf.Cross(right, fwd)
    m = Gf.Matrix4d(1.0)
    # camera space: +X right, +Y up, -Z forward
    m.SetRow(0, Gf.Vec4d(right[0], right[1], right[2], 0))
    m.SetRow(1, Gf.Vec4d(up[0], up[1], up[2], 0))
    m.SetRow(2, Gf.Vec4d(-fwd[0], -fwd[1], -fwd[2], 0))
    m.SetRow(3, Gf.Vec4d(eye[0], eye[1], eye[2], 1))
    return m


def create_cameras(stage, size_x, size_y, size_z):
    center = (size_x / 2, size_y / 2, size_z * 0.4)

    main = UsdGeom.Camera.Define(stage, "/World/Camera/MainCamera")
    main.CreateFocalLengthAttr(28.0)
    main.CreateClippingRangeAttr(Gf.Vec2f(10.0, 60000.0))
    eye = (-0.45 * size_x, -0.75 * size_y, 1.6 * size_z)
    UsdGeom.Xformable(main).AddTransformOp().Set(look_at_matrix(eye, center))

    # Orthographic nadir sensor covering the full tile: the EaR3T geometry.
    nadir = UsdGeom.Camera.Define(stage, "/World/Camera/NadirCamera")
    nadir.CreateProjectionAttr(UsdGeom.Tokens.orthographic)
    # Blender's USD importer maps the raw aperture value to Cycles ortho
    # scale in scene units (meters here), so author the tile width directly
    # (verified: value*10 rendered a 64 km sensor with the tile at ~10%).
    nadir.CreateHorizontalApertureAttr(size_x)
    nadir.CreateVerticalApertureAttr(size_y)
    nadir.CreateClippingRangeAttr(Gf.Vec2f(100.0, 30000.0))
    UsdGeom.Xformable(nadir).AddTranslateOp().Set(
        Gf.Vec3d(size_x / 2, size_y / 2, size_z + 6000.0)
    )  # identity orientation looks down -Z = nadir in a Z-up stage


def main():
    meta, size_x, size_y, size_z = load_domain()
    os.makedirs(os.path.dirname(OUT_USD), exist_ok=True)

    stage = Usd.Stage.CreateNew(OUT_USD)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetMetadata("metersPerUnit", 1.0)

    world = UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(world.GetPrim())
    Usd.ModelAPI(world.GetPrim()).SetKind("assembly")

    create_ocean(stage, size_x, size_y)
    create_cloud_volume(stage, meta, size_x, size_y, size_z)
    create_sun(stage)
    create_cameras(stage, size_x, size_y, size_z)

    world.GetPrim().SetCustomDataByKey(
        "renderNote",
        "Cycles route: sbatch repro/curc/render_week7_cycles.sbatch "
        "assets/phase8/les_cloud_scene.usda 1 1 256; nadir validation render "
        "uses --camera NadirCamera at SZA %g deg." % SUN_SZA_DEG,
    )
    stage.GetRootLayer().Save()
    print("wrote", OUT_USD)
    print("domain %.0f x %.0f x %.0f m, sun SZA %.0f az %.0f" % (size_x, size_y, size_z, SUN_SZA_DEG, SUN_AZ_DEG))


if __name__ == "__main__":
    main()
