#!/usr/bin/env python3
"""Week 2: movable cloud scene.

Builds on the Week 1 local atmosphere domain:
  - references the 50 x 50 x 25 half-ocean/half-land environment
  - hides the Week 1 static cloud placeholder
  - adds a transformable cloud system with USD timeSamples
  - provides a `motion_mode` VariantSet:
      static_cloud, manual_transform, advected_points
"""

import os

from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade

DOMAIN_X = 50.0
DOMAIN_Y = 50.0
DOMAIN_Z = 25.0
START_TIME = 1.0
END_TIME = 20.0
TIME_CODES_PER_SECOND = 4.0

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEEK1_DIR = os.path.join(PROJECT_ROOT, "assets", "week1")
WEEK2_DIR = os.path.join(PROJECT_ROOT, "assets", "week2")


def create_preview_material(stage, path, color, roughness=0.35, opacity=1.0):
    material = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/PreviewSurface")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(opacity)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return material


def base_cloud_points():
    """Return a compact cloud cluster centered near the left side of the domain."""
    center = Gf.Vec3f(13.0, 25.0, 13.0)
    radii = Gf.Vec3f(8.0, 7.0, 4.0)
    points = []

    for ix in range(12):
        for iy in range(11):
            for iz in range(5):
                x = 5.8 + ix * 1.35
                y = 15.5 + iy * 1.85
                z = 8.8 + iz * 1.25
                normalized = (
                    ((x - center[0]) / radii[0]) ** 2
                    + ((y - center[1]) / radii[1]) ** 2
                    + ((z - center[2]) / radii[2]) ** 2
                )
                if normalized <= 1.0:
                    points.append(Gf.Vec3f(x, y, z))

    return points


def cloud_positions_at_time(points, time_code):
    """Simple advection placeholder: move east, bob slightly, and shear with height."""
    t = (time_code - START_TIME) / (END_TIME - START_TIME)
    dx = 24.0 * t
    dy = 3.0 * t
    wave = 0.75 if time_code >= (START_TIME + END_TIME) / 2.0 else 0.0

    advected = []
    for point in points:
        height_fraction = point[2] / DOMAIN_Z
        shear = 2.5 * height_fraction * t
        x = min(DOMAIN_X - 2.0, point[0] + dx + shear)
        y = min(DOMAIN_Y - 2.0, max(2.0, point[1] + dy))
        z = min(DOMAIN_Z - 2.0, max(2.0, point[2] + wave))
        advected.append(Gf.Vec3f(x, y, z))

    return advected


def shadow_points_from_cloud(points):
    return [Gf.Vec3f(point[0] + 2.5, point[1] - 2.0, 0.06) for point in points]


def create_cloud_points(stage, path, points, material):
    cloud = UsdGeom.Points.Define(stage, path)
    cloud.CreatePointsAttr(points)
    cloud.CreateWidthsAttr([1.6] * len(points))
    cloud.CreateDisplayColorAttr([Gf.Vec3f(0.92, 0.95, 1.0)])
    UsdShade.MaterialBindingAPI(cloud).Bind(material)

    density = UsdGeom.PrimvarsAPI(cloud).CreatePrimvar(
        "density", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
    )
    density.Set([0.55] * len(points))
    return cloud


def create_shadow_points(stage, path, points, material):
    shadow = UsdGeom.Points.Define(stage, path)
    shadow_points = shadow_points_from_cloud(points)
    shadow.CreatePointsAttr(shadow_points)
    shadow.CreateWidthsAttr([3.2] * len(shadow_points))
    shadow.CreateDisplayColorAttr([Gf.Vec3f(0.004, 0.006, 0.004)])
    shadow.CreateDisplayOpacityAttr([0.72])
    UsdShade.MaterialBindingAPI(shadow).Bind(material)
    return shadow


def set_visibility(prim, visibility):
    UsdGeom.Imageable(prim).CreateVisibilityAttr().Set(visibility)


def set_week1_cloud_placeholder_hidden(stage):
    """Hide the referenced Week 1 cloud so Week 2 owns the animated cloud."""
    clouds = stage.GetPrimAtPath("/World/Environment/Clouds")
    if clouds:
        clouds.GetVariantSets().SetSelection("cloud_visibility", "hidden")


def add_static_cloud_variant(stage, variant_set, material):
    variant_set.AddVariant("static_cloud")
    variant_set.SetVariantSelection("static_cloud")
    with variant_set.GetVariantEditContext():
        system = UsdGeom.Xform.Define(stage, "/World/MovingCloudSystem")
        Usd.ModelAPI(system.GetPrim()).SetKind("group")
        static = UsdGeom.Xform.Define(stage, "/World/MovingCloudSystem/StaticCloud")
        create_cloud_points(stage, "/World/MovingCloudSystem/StaticCloud/Points", base_cloud_points(), material)
        set_visibility(static.GetPrim(), "inherited")


def add_manual_transform_variant(stage, variant_set, cloud_material, shadow_material):
    variant_set.AddVariant("manual_transform")
    variant_set.SetVariantSelection("manual_transform")
    with variant_set.GetVariantEditContext():
        system = UsdGeom.Xform.Define(stage, "/World/MovingCloudSystem")
        Usd.ModelAPI(system.GetPrim()).SetKind("group")
        moving = UsdGeom.Xform.Define(stage, "/World/MovingCloudSystem/ManualTransformCloud")
        translate_op = moving.AddTranslateOp()
        translate_op.Set(Gf.Vec3d(0.0, 0.0, 0.0), Usd.TimeCode(START_TIME))
        translate_op.Set(Gf.Vec3d(12.0, 1.5, 0.0), Usd.TimeCode(8.0))
        translate_op.Set(Gf.Vec3d(24.0, 3.0, 0.0), Usd.TimeCode(END_TIME))
        points = base_cloud_points()
        create_shadow_points(stage, "/World/MovingCloudSystem/ManualTransformCloud/SurfaceShadow", points, shadow_material)
        create_cloud_points(stage, "/World/MovingCloudSystem/ManualTransformCloud/Points", points, cloud_material)


def add_advected_points_variant(stage, variant_set, cloud_material, shadow_material):
    variant_set.AddVariant("advected_points")
    variant_set.SetVariantSelection("advected_points")
    with variant_set.GetVariantEditContext():
        system = UsdGeom.Xform.Define(stage, "/World/MovingCloudSystem")
        Usd.ModelAPI(system.GetPrim()).SetKind("group")
        advected = UsdGeom.Points.Define(stage, "/World/MovingCloudSystem/AdvectedPointsCloud")
        points = base_cloud_points()
        advected.CreateWidthsAttr([1.6] * len(points))
        advected.CreateDisplayColorAttr([Gf.Vec3f(0.92, 0.95, 1.0)])
        UsdShade.MaterialBindingAPI(advected).Bind(cloud_material)

        density = UsdGeom.PrimvarsAPI(advected).CreatePrimvar(
            "density", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
        )
        density.Set([0.55] * len(points))

        shadow = UsdGeom.Points.Define(stage, "/World/MovingCloudSystem/AdvectedSurfaceShadow")
        shadow.CreateWidthsAttr([3.2] * len(points))
        shadow.CreateDisplayColorAttr([Gf.Vec3f(0.004, 0.006, 0.004)])
        shadow.CreateDisplayOpacityAttr([0.72])
        UsdShade.MaterialBindingAPI(shadow).Bind(shadow_material)

        for time_code in (START_TIME, 5.0, 10.0, 15.0, END_TIME):
            moved_points = cloud_positions_at_time(points, time_code)
            advected.GetPointsAttr().Set(moved_points, Usd.TimeCode(time_code))
            shadow.GetPointsAttr().Set(shadow_points_from_cloud(moved_points), Usd.TimeCode(time_code))


def create_cloud_motion_scene(out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    stage = Usd.Stage.CreateNew(out_path)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetMetadata("metersPerUnit", 1000.0)
    stage.SetStartTimeCode(START_TIME)
    stage.SetEndTimeCode(END_TIME)
    stage.SetTimeCodesPerSecond(TIME_CODES_PER_SECOND)

    world = UsdGeom.Xform.Define(stage, "/World")
    Usd.ModelAPI(world.GetPrim()).SetKind("assembly")

    env = stage.DefinePrim("/World/Environment", "Xform")
    env_reference = os.path.relpath(os.path.join(WEEK1_DIR, "environment.usda"), WEEK2_DIR)
    env.GetReferences().AddReference(env_reference)

    materials = UsdGeom.Scope.Define(stage, "/World/Materials")
    Usd.ModelAPI(materials.GetPrim()).SetKind("group")
    cloud_material = create_preview_material(stage, "/World/Materials/AnimatedCloudMaterial", (0.92, 0.95, 1.0))
    shadow_material = create_preview_material(
        stage, "/World/Materials/CloudShadowMaterial", (0.004, 0.006, 0.004), 0.9, 0.72
    )

    set_week1_cloud_placeholder_hidden(stage)

    system = UsdGeom.Xform.Define(stage, "/World/MovingCloudSystem")
    Usd.ModelAPI(system.GetPrim()).SetKind("group")
    variant_set = system.GetPrim().GetVariantSets().AddVariantSet("motion_mode")
    add_static_cloud_variant(stage, variant_set, cloud_material)
    add_manual_transform_variant(stage, variant_set, cloud_material, shadow_material)
    add_advected_points_variant(stage, variant_set, cloud_material, shadow_material)
    variant_set.SetVariantSelection("manual_transform")

    stage.SetDefaultPrim(world.GetPrim())
    stage.GetRootLayer().Save()
    print(f"Saved: {out_path}")


def main():
    out_path = os.path.join(WEEK2_DIR, "clouds_move.usda")

    print("=== Week 2: Movable Clouds ===\n")
    create_cloud_motion_scene(out_path)

    print("\nPreview with:")
    print(f"  usdview {out_path}")
    print("\nTry these VariantSet selections on /World/MovingCloudSystem:")
    print("  motion_mode = static_cloud | manual_transform | advected_points")


if __name__ == "__main__":
    main()
