#!/usr/bin/env python3
"""Week 3: cloud voxel/radiance placeholder scene.

This is a lightweight bridge toward true VDB + radiative transfer work:
  - references the Week 2 movable-cloud scene
  - hides the Week 2 point cloud so this stage owns the radiance preview
  - builds a structured cloud voxel placeholder inside the 50 x 50 x 25 domain
  - stores density and approximate radiance as primvars
  - adds a `sun_case` VariantSet for slant-angle vs zenith illumination
"""

import math
import os

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdShade

DOMAIN_X = 50.0
DOMAIN_Y = 50.0
DOMAIN_Z = 25.0
VOXEL_STEP = 1.75

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEEK2_DIR = os.path.join(PROJECT_ROOT, "assets", "week2")
WEEK3_DIR = os.path.join(PROJECT_ROOT, "assets", "week3")


def create_preview_material(stage, path, color, roughness=0.45, opacity=1.0):
    material = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/PreviewSurface")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(opacity)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return material


def normalized(vec):
    length = math.sqrt(vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2)
    return Gf.Vec3f(vec[0] / length, vec[1] / length, vec[2] / length)


def density_at(point):
    center = Gf.Vec3f(25.0, 25.0, 13.0)
    radii = Gf.Vec3f(14.0, 9.0, 5.0)
    q = (
        ((point[0] - center[0]) / radii[0]) ** 2
        + ((point[1] - center[1]) / radii[1]) ** 2
        + ((point[2] - center[2]) / radii[2]) ** 2
    )
    if q > 1.0:
        return 0.0
    return max(0.08, 1.0 - q)


def build_cloud_voxels():
    points = []
    densities = []

    nx = int(DOMAIN_X / VOXEL_STEP)
    ny = int(DOMAIN_Y / VOXEL_STEP)
    nz = int(DOMAIN_Z / VOXEL_STEP)
    for ix in range(nx):
        for iy in range(ny):
            for iz in range(nz):
                point = Gf.Vec3f(
                    (ix + 0.5) * VOXEL_STEP,
                    (iy + 0.5) * VOXEL_STEP,
                    (iz + 0.5) * VOXEL_STEP,
                )
                density = density_at(point)
                if density > 0.0:
                    points.append(point)
                    densities.append(density)

    return points, densities


def approximate_radiance(points, densities, sun_direction):
    """Small deterministic proxy for inscattered radiance before RT tooling exists."""
    sun = normalized(sun_direction)
    values = []
    colors = []

    for point, density in zip(points, densities):
        height_factor = 0.45 + 0.55 * (point[2] / DOMAIN_Z)
        slant_shadow = 0.72 + 0.28 * ((point[0] * abs(sun[0]) + point[1] * abs(sun[1])) / (DOMAIN_X + DOMAIN_Y))
        direct = max(0.15, sun[2]) * height_factor * slant_shadow
        radiance = density * direct
        values.append(radiance)

    vmax = max(values) if values else 1.0
    for value in values:
        t = max(0.0, min(1.0, value / vmax))
        colors.append(Gf.Vec3f(0.35 + 0.65 * t, 0.45 + 0.45 * t, 0.75 + 0.20 * t))

    return values, colors


def create_voxel_points(stage, path, points, densities, radiance_values, colors, material):
    voxels = UsdGeom.Points.Define(stage, path)
    voxels.CreatePointsAttr(points)
    voxels.CreateWidthsAttr([1.9] * len(points))
    voxels.CreateDisplayColorAttr(colors)
    UsdShade.MaterialBindingAPI(voxels).Bind(material)

    pvars = UsdGeom.PrimvarsAPI(voxels)
    density = pvars.CreatePrimvar("density", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex)
    radiance = pvars.CreatePrimvar("radiance", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex)
    density.Set(densities)
    radiance.Set(radiance_values)
    return voxels


def create_shadow_points(stage, path, points, densities, offset_xy, material):
    shadow = UsdGeom.Points.Define(stage, path)
    shadow_points = [
        Gf.Vec3f(
            max(1.0, min(DOMAIN_X - 1.0, point[0] + offset_xy[0])),
            max(1.0, min(DOMAIN_Y - 1.0, point[1] + offset_xy[1])),
            0.08,
        )
        for point in points
        if point[2] >= 11.0
    ]
    shadow.CreatePointsAttr(shadow_points)
    shadow.CreateWidthsAttr([3.0] * len(shadow_points))
    shadow.CreateDisplayColorAttr([Gf.Vec3f(0.004, 0.006, 0.004)])
    shadow.CreateDisplayOpacityAttr([0.75])
    UsdShade.MaterialBindingAPI(shadow).Bind(material)

    sampled_density = [density for point, density in zip(points, densities) if point[2] >= 11.0]
    density_pv = UsdGeom.PrimvarsAPI(shadow).CreatePrimvar(
        "shadowStrength", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
    )
    density_pv.Set(sampled_density)
    return shadow


def set_visibility(prim, visibility):
    UsdGeom.Imageable(prim).CreateVisibilityAttr().Set(visibility)


def create_sun(stage, path, color, intensity, rotation_xyz):
    light = UsdLux.DistantLight.Define(stage, path)
    light.CreateColorAttr(Gf.Vec3f(*color))
    light.CreateIntensityAttr(intensity)
    light.CreateAngleAttr(0.53)
    light.AddRotateXYZOp().Set(Gf.Vec3f(*rotation_xyz))
    return light


def add_sun_case_variants(stage):
    world = stage.GetPrimAtPath("/World")
    variants = world.GetVariantSets().AddVariantSet("sun_case")

    cases = {
        "sun_slant": {
            "visible": "/World/Radiance/CloudVoxelsSlant",
            "visible_shadow": "/World/Radiance/CloudShadowSlant",
            "hidden": "/World/Radiance/CloudVoxelsZenith",
            "hidden_shadow": "/World/Radiance/CloudShadowZenith",
            "light_path": "/World/Lighting/SunSlant",
            "light_color": (1.0, 0.88, 0.68),
            "intensity": 1200.0,
            "rotation": (-45.0, 0.0, -35.0),
        },
        "sun_zenith": {
            "visible": "/World/Radiance/CloudVoxelsZenith",
            "visible_shadow": "/World/Radiance/CloudShadowZenith",
            "hidden": "/World/Radiance/CloudVoxelsSlant",
            "hidden_shadow": "/World/Radiance/CloudShadowSlant",
            "light_path": "/World/Lighting/SunZenith",
            "light_color": (1.0, 0.96, 0.86),
            "intensity": 1500.0,
            "rotation": (0.0, 0.0, 0.0),
        },
    }

    for name, settings in cases.items():
        variants.AddVariant(name)
        variants.SetVariantSelection(name)
        with variants.GetVariantEditContext():
            set_visibility(stage.GetPrimAtPath(settings["visible"]), "inherited")
            set_visibility(stage.GetPrimAtPath(settings["visible_shadow"]), "inherited")
            set_visibility(stage.GetPrimAtPath(settings["hidden"]), "invisible")
            set_visibility(stage.GetPrimAtPath(settings["hidden_shadow"]), "invisible")
            set_visibility(stage.GetPrimAtPath("/World/Lighting/SunSlant"), "invisible")
            set_visibility(stage.GetPrimAtPath("/World/Lighting/SunZenith"), "invisible")
            set_visibility(stage.GetPrimAtPath(settings["light_path"]), "inherited")

    variants.SetVariantSelection("sun_slant")


def create_cloud_volume_scene(out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    os.makedirs(os.path.join(WEEK3_DIR, "vdbs"), exist_ok=True)

    stage = Usd.Stage.CreateNew(out_path)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetMetadata("metersPerUnit", 1000.0)
    stage.SetStartTimeCode(1.0)
    stage.SetEndTimeCode(20.0)
    stage.SetTimeCodesPerSecond(4.0)

    world = UsdGeom.Xform.Define(stage, "/World")
    Usd.ModelAPI(world.GetPrim()).SetKind("assembly")

    scene = stage.DefinePrim("/World/Week2Scene", "Xform")
    scene_reference = os.path.relpath(os.path.join(WEEK2_DIR, "clouds_move.usda"), WEEK3_DIR)
    scene.GetReferences().AddReference(scene_reference)
    moving_system = stage.GetPrimAtPath("/World/Week2Scene/MovingCloudSystem")
    moving_system.GetVariantSets().SetSelection("motion_mode", "static_cloud")
    set_visibility(moving_system, "invisible")

    materials = UsdGeom.Scope.Define(stage, "/World/Materials")
    Usd.ModelAPI(materials.GetPrim()).SetKind("group")
    voxel_material = create_preview_material(stage, "/World/Materials/CloudRadianceMaterial", (0.9, 0.93, 1.0), 0.3, 0.9)
    shadow_material = create_preview_material(stage, "/World/Materials/CloudShadowMaterial", (0.004, 0.006, 0.004), 0.9, 0.75)

    radiance_scope = UsdGeom.Xform.Define(stage, "/World/Radiance")
    Usd.ModelAPI(radiance_scope.GetPrim()).SetKind("group")
    points, densities = build_cloud_voxels()

    slant_values, slant_colors = approximate_radiance(points, densities, Gf.Vec3f(0.65, -0.35, 0.68))
    zenith_values, zenith_colors = approximate_radiance(points, densities, Gf.Vec3f(0.0, 0.0, 1.0))
    create_voxel_points(
        stage,
        "/World/Radiance/CloudVoxelsSlant",
        points,
        densities,
        slant_values,
        slant_colors,
        voxel_material,
    )
    create_voxel_points(
        stage,
        "/World/Radiance/CloudVoxelsZenith",
        points,
        densities,
        zenith_values,
        zenith_colors,
        voxel_material,
    )
    create_shadow_points(stage, "/World/Radiance/CloudShadowSlant", points, densities, (7.0, -4.0), shadow_material)
    create_shadow_points(stage, "/World/Radiance/CloudShadowZenith", points, densities, (0.0, 0.0), shadow_material)

    lighting = UsdGeom.Xform.Define(stage, "/World/Lighting")
    Usd.ModelAPI(lighting.GetPrim()).SetKind("group")
    create_sun(stage, "/World/Lighting/SunSlant", (1.0, 0.88, 0.68), 1200.0, (-45.0, 0.0, -35.0))
    create_sun(stage, "/World/Lighting/SunZenith", (1.0, 0.96, 0.86), 1500.0, (0.0, 0.0, 0.0))
    add_sun_case_variants(stage)

    stage.SetDefaultPrim(world.GetPrim())
    stage.GetRootLayer().Save()
    print(f"Saved: {out_path}")
    print(f"Cloud voxel placeholder count: {len(points)}")


def main():
    out_path = os.path.join(WEEK3_DIR, "clouds_vol.usda")

    print("=== Week 3: Cloud Voxels & Sun Cases ===\n")
    create_cloud_volume_scene(out_path)
    print("\nPreview with:")
    print(f"  usdview {out_path}")
    print("\nTry the VariantSet on /World:")
    print("  sun_case = sun_slant | sun_zenith")


if __name__ == "__main__":
    main()
