#!/usr/bin/env python3
"""Week 7: true USD volume cloud scene.

Authors a real `UsdVol.Volume` that references an OpenVDB density grid. The
companion script `repro/generate_week7_vdb.sh` creates the `.vdb` file with the
Homebrew OpenVDB C++ library because the `openusd` Python environment does not
provide `openvdb`/`pyopenvdb` bindings.
"""

import math
import os
import random

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdShade, UsdVol

DOMAIN_X = 50.0
DOMAIN_Y = 50.0
DOMAIN_Z = 25.0
START_TIME = 1.0
END_TIME = 20.0
TIME_CODES_PER_SECOND = 4.0

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEEK7_DIR = os.path.join(PROJECT_ROOT, "assets", "week7")
VDB_DIR = os.path.join(WEEK7_DIR, "vdbs")
RENDERS_WEEK7_DIR = os.path.join(PROJECT_ROOT, "renders", "week7")


def create_preview_material(stage, path, color, roughness=0.75, specular=0.04):
    material = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/PreviewSurface")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    shader.CreateInput("specularColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(specular, specular, specular))
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return material


def bind_material(imageable, material):
    UsdShade.MaterialBindingAPI(imageable).Bind(material)


def finish_surface_mesh(mesh, color, material=None):
    mesh.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    mesh.CreateDoubleSidedAttr(True)
    mesh.CreateOrientationAttr(UsdGeom.Tokens.rightHanded)
    if material:
        bind_material(mesh, material)


def set_visibility(prim, visibility):
    UsdGeom.Imageable(prim).CreateVisibilityAttr().Set(visibility)


def create_rect_mesh(stage, path, x_min, x_max, y_min, y_max, z, color, material=None):
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr(
        [
            Gf.Vec3f(x_min, y_min, z),
            Gf.Vec3f(x_max, y_min, z),
            Gf.Vec3f(x_max, y_max, z),
            Gf.Vec3f(x_min, y_max, z),
        ]
    )
    mesh.CreateFaceVertexCountsAttr([4])
    mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    finish_surface_mesh(mesh, color, material)
    return mesh


def create_polygon_mesh(stage, path, points_xy, z, color, material=None):
    mesh = UsdGeom.Mesh.Define(stage, path)
    center_x = sum(point[0] for point in points_xy) / len(points_xy)
    center_y = sum(point[1] for point in points_xy) / len(points_xy)
    points = [Gf.Vec3f(center_x, center_y, z)] + [Gf.Vec3f(x, y, z) for x, y in points_xy]
    indices = []
    for index in range(len(points_xy)):
        current_index = index + 1
        next_index = 1 if index == len(points_xy) - 1 else current_index + 1
        indices.extend([0, current_index, next_index])
    mesh.CreatePointsAttr(points)
    mesh.CreateFaceVertexCountsAttr([3] * len(points_xy))
    mesh.CreateFaceVertexIndicesAttr(indices)
    finish_surface_mesh(mesh, color, material)
    return mesh


def create_ellipse_mesh(stage, path, center, radius_x, radius_y, z, color, material=None, segments=48):
    points = [(center[0], center[1])]
    for index in range(segments):
        angle = 2.0 * math.pi * index / segments
        points.append((center[0] + math.cos(angle) * radius_x, center[1] + math.sin(angle) * radius_y))
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr([Gf.Vec3f(x, y, z) for x, y in points])
    indices = []
    for index in range(segments):
        current_index = index + 1
        next_index = 1 if index == segments - 1 else current_index + 1
        indices.extend([0, current_index, next_index])
    mesh.CreateFaceVertexCountsAttr([3] * segments)
    mesh.CreateFaceVertexIndicesAttr(indices)
    finish_surface_mesh(mesh, color, material)
    return mesh


def create_curve(stage, path, points, color, width=0.08, material=None):
    curve = UsdGeom.BasisCurves.Define(stage, path)
    curve.CreateTypeAttr(UsdGeom.Tokens.linear)
    curve.CreateCurveVertexCountsAttr([len(points)])
    curve.CreatePointsAttr([Gf.Vec3f(*point) for point in points])
    curve.CreateWidthsAttr([width] * len(points))
    curve.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    if material:
        bind_material(curve, material)
    return curve


def create_surface_materials(stage):
    return {
        "ocean": create_preview_material(stage, "/World/Materials/Ocean_Albedo006", (0.02, 0.14, 0.26), 0.48, 0.14),
        "marginal_ice": create_preview_material(stage, "/World/Materials/MarginalIce_Albedo050", (0.42, 0.58, 0.62), 0.74, 0.04),
        "sea_ice": create_preview_material(stage, "/World/Materials/SeaIce_Albedo080", (0.72, 0.80, 0.78), 0.82, 0.03),
        "snow": create_preview_material(stage, "/World/Materials/Snow_Albedo080", (0.82, 0.86, 0.84), 0.86, 0.02),
        "young_ice": create_preview_material(stage, "/World/Materials/YoungIce_Albedo055", (0.38, 0.58, 0.64), 0.76, 0.04),
        "melt_pond": create_preview_material(stage, "/World/Materials/MeltPond_Albedo035", (0.08, 0.36, 0.52), 0.46, 0.12),
        "lead": create_preview_material(stage, "/World/Materials/IceLead_DarkWater", (0.012, 0.07, 0.12), 0.52, 0.16),
    }


def create_surface(stage, materials):
    surfaces = UsdGeom.Xform.Define(stage, "/World/Surfaces")
    Usd.ModelAPI(surfaces.GetPrim()).SetKind("group")
    create_rect_mesh(stage, "/World/Surfaces/Ocean_DarkLowAlbedo", 0.0, DOMAIN_X, 0.0, 20.0, 0.0, (0.02, 0.14, 0.26), materials["ocean"])
    create_rect_mesh(stage, "/World/Surfaces/MarginalIce_Albedo050", 0.0, DOMAIN_X, 20.0, 30.0, 0.025, (0.42, 0.58, 0.62), materials["marginal_ice"])
    create_rect_mesh(stage, "/World/Surfaces/SeaIce_Albedo080", 0.0, DOMAIN_X, 30.0, DOMAIN_Y, 0.04, (0.72, 0.80, 0.78), materials["sea_ice"])
    create_rect_mesh(stage, "/World/Surfaces/SnowBand_Albedo080", 4.0, 47.0, 39.0, 48.0, 0.08, (0.82, 0.86, 0.84), materials["snow"])

    create_polygon_mesh(
        stage,
        "/World/Surfaces/Floe_A_Albedo055",
        [(4.8, 13.8), (7.5, 17.8), (13.8, 18.5), (15.5, 15.6), (12.2, 12.5), (7.0, 12.0)],
        0.08,
        (0.38, 0.58, 0.64),
        materials["young_ice"],
    )
    create_polygon_mesh(
        stage,
        "/World/Surfaces/Floe_B_Albedo052",
        [(18.2, 10.2), (21.6, 14.7), (28.6, 14.0), (30.0, 10.5), (25.2, 8.2), (20.5, 8.6)],
        0.08,
        (0.36, 0.55, 0.62),
        materials["young_ice"],
    )
    create_polygon_mesh(
        stage,
        "/World/Surfaces/Floe_C_Albedo058",
        [(34.0, 15.2), (38.0, 19.5), (46.5, 18.0), (47.8, 14.4), (41.5, 12.6), (36.0, 13.2)],
        0.08,
        (0.40, 0.60, 0.66),
        materials["young_ice"],
    )
    create_polygon_mesh(
        stage,
        "/World/Surfaces/YoungIce_Albedo055",
        [(29.5, 24.5), (47.5, 25.0), (48.0, 33.2), (42.0, 35.0), (32.0, 33.5), (28.5, 29.0)],
        0.08,
        (0.38, 0.58, 0.64),
        materials["young_ice"],
    )

    create_ellipse_mesh(stage, "/World/Surfaces/MeltPond_A", (16.0, 33.0), 5.4, 2.2, 0.11, (0.08, 0.36, 0.52), materials["melt_pond"])
    create_ellipse_mesh(stage, "/World/Surfaces/MeltPond_B", (38.0, 41.0), 3.8, 1.7, 0.11, (0.08, 0.36, 0.52), materials["melt_pond"])
    create_ellipse_mesh(stage, "/World/Surfaces/MeltPond_C", (26.0, 28.5), 2.8, 1.2, 0.11, (0.08, 0.36, 0.52), materials["melt_pond"])
    create_curve(
        stage,
        "/World/Surfaces/IceLead_DarkWater",
        [(0.0, 29.2, 0.13), (8.0, 28.6, 0.13), (18.0, 30.1, 0.13), (31.0, 29.4, 0.13), (50.0, 30.4, 0.13)],
        (0.012, 0.07, 0.12),
        0.35,
        materials["lead"],
    )
    return surfaces


def create_domain_frame(stage, material):
    frame = UsdGeom.Xform.Define(stage, "/World/Atmosphere/DomainFrame")
    edges = [
        ((0, 0, 0), (DOMAIN_X, 0, 0)),
        ((DOMAIN_X, 0, 0), (DOMAIN_X, DOMAIN_Y, 0)),
        ((DOMAIN_X, DOMAIN_Y, 0), (0, DOMAIN_Y, 0)),
        ((0, DOMAIN_Y, 0), (0, 0, 0)),
        ((0, 0, DOMAIN_Z), (DOMAIN_X, 0, DOMAIN_Z)),
        ((DOMAIN_X, 0, DOMAIN_Z), (DOMAIN_X, DOMAIN_Y, DOMAIN_Z)),
        ((DOMAIN_X, DOMAIN_Y, DOMAIN_Z), (0, DOMAIN_Y, DOMAIN_Z)),
        ((0, DOMAIN_Y, DOMAIN_Z), (0, 0, DOMAIN_Z)),
        ((0, 0, 0), (0, 0, DOMAIN_Z)),
        ((DOMAIN_X, 0, 0), (DOMAIN_X, 0, DOMAIN_Z)),
        ((DOMAIN_X, DOMAIN_Y, 0), (DOMAIN_X, DOMAIN_Y, DOMAIN_Z)),
        ((0, DOMAIN_Y, 0), (0, DOMAIN_Y, DOMAIN_Z)),
    ]
    for index, (start, end) in enumerate(edges):
        curve = UsdGeom.BasisCurves.Define(stage, f"/World/Atmosphere/DomainFrame/Edge_{index:02d}")
        curve.CreateTypeAttr(UsdGeom.Tokens.linear)
        curve.CreateCurveVertexCountsAttr([2])
        curve.CreatePointsAttr([Gf.Vec3f(*start), Gf.Vec3f(*end)])
        curve.CreateWidthsAttr([0.04, 0.04])
        curve.CreateDisplayColorAttr([Gf.Vec3f(0.42, 0.58, 0.66)])
        bind_material(curve, material)
    return frame


def cloud_offset_at_time(time_code):
    t = (time_code - START_TIME) / (END_TIME - START_TIME)
    return Gf.Vec3f(23.0 * t, 2.0 * math.sin(t * math.pi), 0.35 * math.sin(t * math.pi))


def create_usdvol_cloud(stage):
    cloud_xform = UsdGeom.Xform.Define(stage, "/World/CloudVolume")
    Usd.ModelAPI(cloud_xform.GetPrim()).SetKind("component")
    translate = cloud_xform.AddTranslateOp()
    base_position = Gf.Vec3f(12.0, 27.5, 10.5)
    for time_code in (START_TIME, 5.0, 10.0, 15.0, END_TIME):
        translate.Set(Gf.Vec3d(base_position + cloud_offset_at_time(time_code)), Usd.TimeCode(time_code))

    volume = UsdVol.Volume.Define(stage, "/World/CloudVolume/Volume")
    volume.CreateExtentAttr([Gf.Vec3f(-10.0, -6.0, -3.0), Gf.Vec3f(10.0, 6.0, 5.0)])

    density_field = UsdVol.OpenVDBAsset.Define(stage, "/World/CloudVolume/Fields/Density")
    density_field.CreateFilePathAttr(Sdf.AssetPath("vdbs/cloud_density.vdb"))
    density_field.CreateFieldNameAttr("density")
    density_field.CreateFieldClassAttr(UsdVol.Tokens.fogVolume)
    density_field.CreateFieldDataTypeAttr(UsdVol.Tokens.float_)

    volume.CreateFieldRelationship("density", density_field.GetPath())
    return cloud_xform, volume, density_field


def make_preview_points(seed=11):
    rng = random.Random(seed)
    points = []
    widths = []
    colors = []
    for index in range(130):
        angle = rng.uniform(0.0, 2.0 * math.pi)
        radial = math.sqrt(rng.uniform(0.0, 1.0))
        z = rng.uniform(-2.2, 3.8)
        points.append(Gf.Vec3f(math.cos(angle) * radial * 10.0, math.sin(angle) * radial * 6.0, z))
        widths.append(rng.uniform(0.7, 1.8))
        shade = 0.76 + 0.18 * rng.random()
        colors.append(Gf.Vec3f(shade, min(0.98, shade + 0.04), min(1.0, shade + 0.06)))
    return points, widths, colors


def create_points_preview(stage):
    preview = UsdGeom.Points.Define(stage, "/World/CloudVolume/PointsPreview")
    points, widths, colors = make_preview_points()
    preview.CreatePointsAttr(points)
    preview.CreateWidthsAttr(widths)
    UsdGeom.PrimvarsAPI(preview).CreatePrimvar(
        "displayColor",
        Sdf.ValueTypeNames.Color3fArray,
        UsdGeom.Tokens.vertex,
    ).Set(colors)
    return preview


def create_lighting(stage):
    lighting = UsdGeom.Xform.Define(stage, "/World/Lighting")
    Usd.ModelAPI(lighting.GetPrim()).SetKind("group")

    sun = UsdLux.DistantLight.Define(stage, "/World/Lighting/PolarLowSun")
    sun.CreateColorAttr(Gf.Vec3f(1.0, 0.86, 0.68))
    sun.CreateIntensityAttr(650.0)
    sun.CreateAngleAttr(0.45)
    sun.GetPrim().CreateAttribute("inputs:shadow:enable", Sdf.ValueTypeNames.Bool).Set(True)
    sun.GetPrim().CreateAttribute("inputs:shadow:distance", Sdf.ValueTypeNames.Float).Set(200.0)
    sun.GetPrim().CreateAttribute("inputs:shadow:falloff", Sdf.ValueTypeNames.Float).Set(0.0)
    sun.AddRotateXYZOp().Set(Gf.Vec3f(-34.0, 0.0, -38.0))

    fill = UsdLux.SphereLight.Define(stage, "/World/Lighting/SkyFill")
    fill.CreateColorAttr(Gf.Vec3f(0.46, 0.54, 0.64))
    fill.CreateIntensityAttr(42.0)
    fill.CreateRadiusAttr(80.0)
    fill.AddTranslateOp().Set(Gf.Vec3f(25.0, 25.0, 45.0))
    return lighting


def add_camera(stage):
    UsdGeom.Xform.Define(stage, "/World/Camera")
    camera = UsdGeom.Camera.Define(stage, "/World/Camera/MainCamera")
    camera.CreateFocalLengthAttr(28.0)
    camera.CreateHorizontalApertureAttr(24.0)
    camera.CreateVerticalApertureAttr(18.0)
    camera.CreateClippingRangeAttr(Gf.Vec2f(0.1, 100000.0))
    eye = Gf.Vec3d(72.0, -55.0, 42.0)
    target = Gf.Vec3d(25.0, 28.0, 7.5)
    up = Gf.Vec3d(0.0, 0.0, 1.0)
    camera.AddTransformOp().Set(Gf.Matrix4d().SetLookAt(eye, target, up).GetInverse())
    return camera


def add_variants(stage):
    world = stage.GetPrimAtPath("/World")
    cloud_vs = world.GetVariantSets().AddVariantSet("cloud_representation")
    for name, volume_vis, points_vis in (
        ("usdvol_density", "inherited", "invisible"),
        ("points_preview", "invisible", "inherited"),
    ):
        cloud_vs.AddVariant(name)
        cloud_vs.SetVariantSelection(name)
        with cloud_vs.GetVariantEditContext():
            set_visibility(stage.GetPrimAtPath("/World/CloudVolume/Volume"), volume_vis)
            set_visibility(stage.GetPrimAtPath("/World/CloudVolume/PointsPreview"), points_vis)
    cloud_vs.SetVariantSelection("usdvol_density")

    shadow_vs = world.GetVariantSets().AddVariantSet("shadow_mode")
    for name in ("renderer_volume_shadow", "surface_albedo_debug"):
        shadow_vs.AddVariant(name)
        shadow_vs.SetVariantSelection(name)
        with shadow_vs.GetVariantEditContext():
            # Placeholder for future baked/diagnostic albedo-mask layer.
            pass
    shadow_vs.SetVariantSelection("renderer_volume_shadow")


def add_render_notes(stage):
    notes = UsdGeom.Scope.Define(stage, "/World/RenderNotes")
    prim = notes.GetPrim()
    prim.CreateAttribute("description", Sdf.ValueTypeNames.String).Set(
        "Week 7 UsdVol scene. /World/CloudVolume/Volume references vdbs/cloud_density.vdb "
        "with field name 'density'. Generate the VDB locally with repro/generate_week7_vdb.sh. "
        "HdStorm can display the volume, but may not cast VDB volume shadows onto surface receivers; "
        "use RTX/HdPrman or a radiative-transfer shadow mask for production cloud shadows."
    )
    prim.CreateAttribute("renderCommand", Sdf.ValueTypeNames.String).Set(
        "usdrecord --disableCameraLight --camera /World/Camera/MainCamera --frames 1:20 --imageWidth 1280 "
        "assets/week7/usdvol_cloud_scene.usda renders/week7/usdvol_cloud_###.png"
    )


def write_vdb_readme():
    os.makedirs(VDB_DIR, exist_ok=True)
    path = os.path.join(VDB_DIR, "README.md")
    lines = [
        "# Week 7 VDB Requirement",
        "",
        "The USD scene `assets/week7/usdvol_cloud_scene.usda` expects:",
        "",
        "- file: `assets/week7/vdbs/cloud_density.vdb`",
        "- grid name: `density`",
        "- grid class: `fogVolume`",
        "- data type: float",
        "",
        "The local `openusd` environment has `pxr.UsdVol`, but it does not have `openvdb` or `pyopenvdb` Python bindings.",
        "",
        "Local generation with the Homebrew OpenVDB install:",
        "",
        "```bash",
        "repro/generate_week7_vdb.sh",
        "```",
        "",
        "This compiles `tools/generate_week7_vdb.cpp`, writes a synthetic fog-volume grid named `density`, and verifies it with `vdb_print`.",
        "",
        "The OpenUSD build used for rendering must include `hioOpenVDB`; otherwise Storm reports `Unknown field data type 'vdb'`.",
        "Rebuild OpenUSD with `PXR_ENABLE_OPENVDB_SUPPORT=ON` so `.vdb` field textures can be loaded.",
    ]
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


def create_usdvol_cloud_scene(out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    os.makedirs(RENDERS_WEEK7_DIR, exist_ok=True)

    stage = Usd.Stage.CreateNew(out_path)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetMetadata("metersPerUnit", 1000.0)
    stage.SetStartTimeCode(START_TIME)
    stage.SetEndTimeCode(END_TIME)
    stage.SetTimeCodesPerSecond(TIME_CODES_PER_SECOND)

    world = UsdGeom.Xform.Define(stage, "/World")
    Usd.ModelAPI(world.GetPrim()).SetKind("assembly")

    materials = UsdGeom.Scope.Define(stage, "/World/Materials")
    Usd.ModelAPI(materials.GetPrim()).SetKind("group")
    surface_materials = create_surface_materials(stage)
    domain_material = create_preview_material(stage, "/World/Materials/DomainFrame", (0.42, 0.58, 0.66), 0.85, 0.02)

    create_surface(stage, surface_materials)
    atmosphere = UsdGeom.Xform.Define(stage, "/World/Atmosphere")
    Usd.ModelAPI(atmosphere.GetPrim()).SetKind("group")
    create_domain_frame(stage, domain_material)
    create_usdvol_cloud(stage)
    create_points_preview(stage)
    create_lighting(stage)
    add_camera(stage)
    add_variants(stage)
    add_render_notes(stage)
    readme = write_vdb_readme()

    stage.SetDefaultPrim(world.GetPrim())
    stage.GetRootLayer().Save()
    print(f"Saved: {out_path}")
    print(f"VDB instructions: {readme}")


def main():
    out_path = os.path.join(WEEK7_DIR, "usdvol_cloud_scene.usda")
    print("=== Week 7: UsdVol OpenVDB Cloud ===\n")
    create_usdvol_cloud_scene(out_path)
    print("\nPreview fallback with:")
    print(f"  usdview {out_path}")
    print("\nExpected VDB:")
    print("  assets/week7/vdbs/cloud_density.vdb (grid name: density)")
    print("\nGenerate it locally with:")
    print("  repro/generate_week7_vdb.sh")


if __name__ == "__main__":
    main()
