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
# Periodic variant for validation: the same cloud tiled 3x3 so the center
# tile receives wrap-around shadows/illumination like MCARaTS's cyclic
# horizontal boundary. NadirCamera still frames only the center tile.
OUT_USD_PERIODIC = os.path.join(ROOT, "assets", "phase8", "les_cloud_scene_periodic.usda")
# Buffered-benchmark variant (supersedes the periodic one): the tile plus its
# REAL neighbors from the full 48-km domain (cloud_field.py --buffer). The
# compared region is the central 12.8 km; the outer 3.2 km buffer absorbs the
# open-box (Cycles) vs cyclic (MCARaTS) boundary mismatch on both sides.
OUT_USD_BUFFERED = os.path.join(ROOT, "assets", "phase8", "les_cloud_scene_buffered.usda")
# + molecular atmosphere variant: same buffered scene plus the Rayleigh/gas
# medium EaR3T carries (validation/make_atmosphere_profile.py ->
# src/atmosphere_to_vdb.py), NadirCamera raised above the 20 km atmosphere
# top so the sensor sees the full path radiance like the MCARaTS sensor.
OUT_USD_BUFFERED_ATM = os.path.join(ROOT, "assets", "phase8", "les_cloud_scene_buffered_atm.usda")
# Cloud + atmosphere MUST live in one VDB/one volume prim: as two separate
# volume objects Cycles drops the atmosphere's in-scattering inside the cloud
# grid's sparse-node boxes (blocky deficits around every cloud cluster,
# diagnosed 2026-08-14 — docs/rendering_artifacts.md).
COMBINED_VDB_REL = "../week7/vdbs/cloud_atmosphere_buffered.vdb"
ATM_TOP_M = 20000.0
VDB_REL = "../week7/vdbs/cloud_density.vdb"
VDB_BUFFERED_REL = "../week7/vdbs/cloud_density_buffered.vdb"
META_JSON = os.path.join(ROOT, "data", "processed", "cloud_ext_64x64x32.json")
BUFFERED_META_JSON = os.path.join(ROOT, "data", "processed", "cloud_ext_192x192x32.json")
BUFFER_M = 3200.0   # keep in sync with cloud_field.BUFFER_COLS * dx (32*100 m)

SUN_SZA_DEG = 30.0  # solar zenith angle; keep in sync with the EaR3T run
# Solar azimuth in the EaR3T/MCARaTS compass convention: 0 = north (+y),
# 90 = east (+x), clockwise positive (er3t mcarats.py cal_mca_azimuth).
# compare_ear3t.py passes this same value as solar_azimuth_angle.
SUN_SAA_DEG = 40.0


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


def create_ocean(stage, size_x, size_y, periodic=False):
    # 7SEAS is a tropical marine shallow-cumulus case: dark low-albedo ocean.
    lo_x, hi_x = (-size_x, 2 * size_x) if periodic else (0.0, size_x)
    lo_y, hi_y = (-size_y, 2 * size_y) if periodic else (0.0, size_y)
    mesh = UsdGeom.Mesh.Define(stage, "/World/Surface/Ocean")
    mesh.CreatePointsAttr(
        [Gf.Vec3f(lo_x, lo_y, 0), Gf.Vec3f(hi_x, lo_y, 0), Gf.Vec3f(hi_x, hi_y, 0), Gf.Vec3f(lo_x, hi_y, 0)]
    )
    mesh.CreateFaceVertexCountsAttr([4])
    mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    mesh.CreateExtentAttr([Gf.Vec3f(lo_x, lo_y, 0), Gf.Vec3f(hi_x, hi_y, 0)])
    mesh.CreateDisplayColorAttr([Gf.Vec3f(0.02, 0.09, 0.17)])
    ocean_mat = make_preview_material(stage, "/World/Materials/OceanDark", (0.02, 0.09, 0.17))
    bind(mesh, ocean_mat)


def create_cloud_volume(stage, meta, size_x, size_y, size_z, periodic=False):
    """periodic: 3x3 plain-wrap neighbor tiles (validation only — matches
    MCARaTS cyclic BC, which wraps and does not mirror). For seamless HERO
    tiling use the pre-mirrored VDB (grid_to_vdb.py --mirror3x3) in a single
    prim: mirroring by instance transform (scale -1) causes GPU volume
    banding (docs/rendering_artifacts.md #6)."""
    UsdGeom.Xform.Define(stage, "/World/CloudVolume")
    shifts = [(i, j) for i in (-1, 0, 1) for j in (-1, 0, 1)] if periodic else [(0, 0)]
    for i, j in shifts:
        tile = UsdGeom.Xform.Define(stage, f"/World/CloudVolume/Tile_{i + 1}_{j + 1}")
        tile.AddTranslateOp().Set(Gf.Vec3d(i * size_x, j * size_y, 0.0))
        volume = UsdVol.Volume.Define(stage, tile.GetPath().AppendChild("Volume"))
        volume.CreateExtentAttr([Gf.Vec3f(0, 0, 0), Gf.Vec3f(size_x, size_y, size_z)])

        field = UsdVol.OpenVDBAsset.Define(stage, volume.GetPath().AppendChild("Density"))
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
    # angle, then orient the azimuth about Z. With ops [Rz, Rx] the light's
    # horizontal travel direction is (-sin(rz), cos(rz)); matching the
    # compass-SAA sun position (sin(saa), cos(saa)) requires rz = 180 - saa
    # (verified against the EaR3T shadow displacement, 2026-08-01).
    xf = UsdGeom.Xformable(sun)
    xf.AddRotateZOp().Set(180.0 - SUN_SAA_DEG)
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


def author_stage(out_usd, periodic=False):
    meta, size_x, size_y, size_z = load_domain()
    os.makedirs(os.path.dirname(out_usd), exist_ok=True)
    if os.path.exists(out_usd):
        os.remove(out_usd)

    stage = Usd.Stage.CreateNew(out_usd)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetMetadata("metersPerUnit", 1.0)

    world = UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(world.GetPrim())
    Usd.ModelAPI(world.GetPrim()).SetKind("assembly")

    create_ocean(stage, size_x, size_y, periodic=periodic)
    create_cloud_volume(stage, meta, size_x, size_y, size_z, periodic=periodic)
    create_sun(stage)
    create_cameras(stage, size_x, size_y, size_z)
    return stage, world, size_x, size_y, size_z


def author_buffered_stage(atmosphere=False):
    """les_cloud_scene_buffered[_atm].usda — the buffered-benchmark geometry.

    World convention: the validated 64x64 tile keeps 0..6400 m. The full
    192x192 crop spans -6400..12800 m (VDB origin baked at -6400); the
    compared VAL region spans -3200..9600 m, and NadirCamera frames exactly
    that 12.8 km at 256x256 px (2x2 px per 100 m LES column).

    atmosphere=True adds the molecular Rayleigh/gas volume (0..20 km, the
    exact EaR3T profile) and raises NadirCamera above the atmosphere top."""
    out_usd = OUT_USD_BUFFERED_ATM if atmosphere else OUT_USD_BUFFERED
    meta, size_x, size_y, size_z = load_domain()
    with open(BUFFERED_META_JSON) as fh:
        meta_buf = json.load(fh)
    crop_xy = meta_buf["nx"] * meta_buf["dx_m"]           # 19200 m
    lo = -(crop_xy - size_x) / 2.0                        # -6400 m
    val_xy = crop_xy - 2.0 * BUFFER_M                     # 12800 m compared

    os.makedirs(os.path.dirname(out_usd), exist_ok=True)
    if os.path.exists(out_usd):
        os.remove(out_usd)
    stage = Usd.Stage.CreateNew(out_usd)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetMetadata("metersPerUnit", 1.0)
    world = UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(world.GetPrim())
    Usd.ModelAPI(world.GetPrim()).SetKind("assembly")

    # Ocean well past the crop so no nadir/oblique ray sees the table edge.
    o_lo, o_hi = lo - crop_xy / 2.0, lo + 1.5 * crop_xy
    mesh = UsdGeom.Mesh.Define(stage, "/World/Surface/Ocean")
    mesh.CreatePointsAttr([Gf.Vec3f(o_lo, o_lo, 0), Gf.Vec3f(o_hi, o_lo, 0),
                           Gf.Vec3f(o_hi, o_hi, 0), Gf.Vec3f(o_lo, o_hi, 0)])
    mesh.CreateFaceVertexCountsAttr([4])
    mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    mesh.CreateExtentAttr([Gf.Vec3f(o_lo, o_lo, 0), Gf.Vec3f(o_hi, o_hi, 0)])
    mesh.CreateDisplayColorAttr([Gf.Vec3f(0.02, 0.09, 0.17)])
    bind(mesh, make_preview_material(stage, "/World/Materials/OceanDark",
                                     (0.02, 0.09, 0.17)))

    UsdGeom.Xform.Define(stage, "/World/CloudVolume")
    if atmosphere:
        # ONE prim carrying cloud + molecular atmosphere (combined VDB). The
        # prim NAME carries "Atmosphere" — the render driver keys the
        # combined material (HG cloud + Rayleigh scatter + gray absorption)
        # on it. Never author these as two volume prims (see COMBINED_VDB_REL
        # note above).
        volume = UsdVol.Volume.Define(
            stage, "/World/CloudVolume/CloudAtmosphereVolume")
        volume.CreateExtentAttr([Gf.Vec3f(-16000.0, -16000.0, 0),
                                 Gf.Vec3f(22400.0, 22400.0, ATM_TOP_M)])
        for fname in ("density", "scatter", "absorb"):
            fld = UsdVol.OpenVDBAsset.Define(
                stage,
                f"/World/CloudVolume/CloudAtmosphereVolume/{fname.capitalize()}")
            fld.CreateFilePathAttr(COMBINED_VDB_REL)
            fld.CreateFieldNameAttr(fname)
            fld.CreateFieldClassAttr(UsdVol.Tokens.fogVolume)
            volume.CreateFieldRelationship(fname, fld.GetPath())
        volume.GetPrim().SetCustomDataByKey(
            "source", "buffered LES cloud + EaR3T molecular atmosphere "
                      "(make_atmosphere_profile.py -> atmosphere_to_vdb.py)")
    else:
        volume = UsdVol.Volume.Define(stage, "/World/CloudVolume/Volume")
        volume.CreateExtentAttr([Gf.Vec3f(lo, lo, 0),
                                 Gf.Vec3f(lo + crop_xy, lo + crop_xy, size_z)])
        field = UsdVol.OpenVDBAsset.Define(stage, "/World/CloudVolume/Volume/Density")
        field.CreateFilePathAttr(VDB_BUFFERED_REL)
        field.CreateFieldNameAttr(meta_buf.get("grid_name", "density"))
        field.CreateFieldClassAttr(UsdVol.Tokens.fogVolume)
        volume.CreateFieldRelationship("density", field.GetPath())
        volume.GetPrim().SetCustomDataByKey(
            "source", "cloudiest tile + 3.2 km real-neighbor buffer "
                      "(cloud_field.py --buffer, compare center 12.8 km only)")

    create_sun(stage)

    nadir = UsdGeom.Camera.Define(stage, "/World/Camera/NadirCamera")
    nadir.CreateProjectionAttr(UsdGeom.Tokens.orthographic)
    nadir.CreateHorizontalApertureAttr(val_xy)
    nadir.CreateVerticalApertureAttr(val_xy)
    # With the atmosphere present the sensor sits ABOVE the 20 km top so it
    # integrates the full path radiance, like the MCARaTS sensor at 705 km.
    cam_z = ATM_TOP_M + 2000.0 if atmosphere else size_z + 6000.0
    nadir.CreateClippingRangeAttr(Gf.Vec2f(100.0, 40000.0))
    UsdGeom.Xformable(nadir).AddTranslateOp().Set(
        Gf.Vec3d(size_x / 2, size_y / 2, cam_z))

    stage.GetRootLayer().Save()
    print(f"wrote {out_usd} (crop {crop_xy:.0f} m at {lo:.0f}, "
          f"nadir sensor {val_xy:.0f} m at z {cam_z:.0f}"
          f"{', molecular atmosphere 0-20 km' if atmosphere else ''})")


def main():
    stage, world, size_x, size_y, size_z = author_stage(OUT_USD, periodic=False)

    world.GetPrim().SetCustomDataByKey(
        "renderNote",
        "Cycles route: sbatch repro/curc/render_week7_cycles.sbatch "
        "assets/phase8/les_cloud_scene.usda 1 1 256; nadir validation render "
        "uses --camera NadirCamera at SZA %g deg." % SUN_SZA_DEG,
    )
    stage.GetRootLayer().Save()
    print("wrote", OUT_USD)

    pstage, _, _, _, _ = author_stage(OUT_USD_PERIODIC, periodic=True)
    pstage.GetRootLayer().Save()
    print("wrote", OUT_USD_PERIODIC, "(3x3 tiled for MCARaTS cyclic-BC match)")

    author_buffered_stage()
    author_buffered_stage(atmosphere=True)
    print("domain %.0f x %.0f x %.0f m, sun SZA %.0f az %.0f" % (size_x, size_y, size_z, SUN_SZA_DEG, SUN_SAA_DEG))


if __name__ == "__main__":
    main()
