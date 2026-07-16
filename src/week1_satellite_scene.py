#!/usr/bin/env python3
"""Week 1: Local atmosphere scene.

Creates a simple OpenUSD baseline for the revised project goal:
  - x=50, y=50, z=25 atmospheric/cloud domain
  - surface split into half ocean and half land
  - low-resolution static cloud placeholder
  - variants to toggle surface mode, atmosphere bounds, and cloud visibility
"""

import os
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade

DOMAIN_X = 50.0
DOMAIN_Y = 50.0
DOMAIN_Z = 25.0

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "week1")


# ---------------------------------------------------------------------------
# Layer 1 – Environment (surfaces + atmosphere + static cloud placeholder)
# ---------------------------------------------------------------------------
def create_preview_material(stage, path, color, roughness=0.55):
    material = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/PreviewSurface")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return material


def create_rect_mesh(stage, path, x_min, x_max, y_min, y_max, z=0.0, color=(0.5, 0.5, 0.5)):
    """Create one rectangular surface patch in the z=0 plane."""
    mesh = UsdGeom.Mesh.Define(stage, path)
    pts = [
        Gf.Vec3f(x_min, y_min, z),
        Gf.Vec3f(x_max, y_min, z),
        Gf.Vec3f(x_max, y_max, z),
        Gf.Vec3f(x_min, y_max, z),
    ]
    mesh.CreatePointsAttr(pts)
    mesh.CreateFaceVertexCountsAttr([4])
    mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    mesh.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    return mesh


def create_domain_box(stage, path):
    """Create a transparent box marking the 50 x 50 x 25 cloud domain."""
    cube = UsdGeom.Cube.Define(stage, path)
    cube.CreateSizeAttr(1.0)
    cube.AddTranslateOp().Set(Gf.Vec3f(DOMAIN_X / 2.0, DOMAIN_Y / 2.0, DOMAIN_Z / 2.0))
    cube.AddScaleOp().Set(Gf.Vec3f(DOMAIN_X, DOMAIN_Y, DOMAIN_Z))
    cube.CreateDisplayColorAttr([Gf.Vec3f(0.55, 0.78, 1.0)])
    cube.CreateDisplayOpacityAttr([0.12])
    return cube


def make_cloud_points():
    """A small voxel-like ellipsoid inside the domain."""
    center = Gf.Vec3f(24.0, 25.0, 13.0)
    radii = Gf.Vec3f(13.0, 8.0, 4.0)
    points = []

    for ix in range(8):
        for iy in range(6):
            for iz in range(3):
                x = 12.0 + ix * 3.4
                y = 16.0 + iy * 3.5
                z = 9.0 + iz * 2.5
                normalized = (
                    ((x - center[0]) / radii[0]) ** 2
                    + ((y - center[1]) / radii[1]) ** 2
                    + ((z - center[2]) / radii[2]) ** 2
                )
                if normalized <= 1.0:
                    points.append(Gf.Vec3f(x, y, z))

    return points


def set_visibility(prim, visibility):
    UsdGeom.Imageable(prim).CreateVisibilityAttr().Set(visibility)


def add_visibility_variant(stage, prim_path, variant_name, visible_selection="visible"):
    prim = stage.GetPrimAtPath(prim_path)
    variant_set = prim.GetVariantSets().AddVariantSet(variant_name)

    for selection, visibility in (("visible", "inherited"), ("hidden", "invisible")):
        variant_set.AddVariant(selection)
        variant_set.SetVariantSelection(selection)
        with variant_set.GetVariantEditContext():
            set_visibility(prim, visibility)

    variant_set.SetVariantSelection(visible_selection)


def add_surface_variant(stage):
    surfaces = stage.GetPrimAtPath("/World/Surfaces")
    ocean = stage.GetPrimAtPath("/World/Surfaces/Ocean")
    land = stage.GetPrimAtPath("/World/Surfaces/Land")
    variant_set = surfaces.GetVariantSets().AddVariantSet("surface_mode")

    for selection in ("split_ocean_land", "ocean_only", "land_only"):
        variant_set.AddVariant(selection)
        variant_set.SetVariantSelection(selection)
        with variant_set.GetVariantEditContext():
            set_visibility(ocean, "inherited")
            set_visibility(land, "inherited")
            if selection == "ocean_only":
                set_visibility(land, "invisible")
            elif selection == "land_only":
                set_visibility(ocean, "invisible")

    variant_set.SetVariantSelection("split_ocean_land")


def create_environment_layer(path):
    """Create the Week 1 baseline domain, surface, and cloud placeholder."""
    stage = Usd.Stage.CreateNew(path)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetMetadata("metersPerUnit", 1000.0)  # 1 USD unit = 1 km for this practice scene

    world = UsdGeom.Xform.Define(stage, "/World")
    Usd.ModelAPI(world.GetPrim()).SetKind("assembly")

    materials = UsdGeom.Scope.Define(stage, "/World/Materials")
    ocean_mat = create_preview_material(stage, "/World/Materials/OceanMaterial", (0.02, 0.16, 0.48), 0.18)
    land_mat = create_preview_material(stage, "/World/Materials/LandMaterial", (0.28, 0.46, 0.18), 0.75)
    cloud_mat = create_preview_material(stage, "/World/Materials/CloudMaterial", (0.92, 0.95, 1.0), 0.35)
    Usd.ModelAPI(materials.GetPrim()).SetKind("group")

    surfaces = UsdGeom.Xform.Define(stage, "/World/Surfaces")
    Usd.ModelAPI(surfaces.GetPrim()).SetKind("group")

    ocean = create_rect_mesh(
        stage,
        "/World/Surfaces/Ocean",
        x_min=0.0,
        x_max=DOMAIN_X / 2.0,
        y_min=0.0,
        y_max=DOMAIN_Y,
        color=(0.02, 0.16, 0.48),
    )
    land = create_rect_mesh(
        stage,
        "/World/Surfaces/Land",
        x_min=DOMAIN_X / 2.0,
        x_max=DOMAIN_X,
        y_min=0.0,
        y_max=DOMAIN_Y,
        color=(0.28, 0.46, 0.18),
    )
    UsdShade.MaterialBindingAPI(ocean).Bind(ocean_mat)
    UsdShade.MaterialBindingAPI(land).Bind(land_mat)

    atmosphere = UsdGeom.Xform.Define(stage, "/World/Atmosphere")
    Usd.ModelAPI(atmosphere.GetPrim()).SetKind("group")
    create_domain_box(stage, "/World/Atmosphere/DomainBounds")

    clouds = UsdGeom.Xform.Define(stage, "/World/Clouds")
    Usd.ModelAPI(clouds.GetPrim()).SetKind("group")
    cloud_pts = UsdGeom.Points.Define(stage, "/World/Clouds/StaticCloud")
    cloud_positions = make_cloud_points()
    cloud_pts.CreatePointsAttr(cloud_positions)
    cloud_pts.CreateWidthsAttr([1.6] * len(cloud_positions))
    cloud_pts.CreateDisplayColorAttr([Gf.Vec3f(0.92, 0.95, 1.0)])
    UsdShade.MaterialBindingAPI(cloud_pts).Bind(cloud_mat)

    cloud_density = UsdGeom.PrimvarsAPI(cloud_pts).CreatePrimvar(
        "density", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
    )
    cloud_density.Set([0.55] * len(cloud_positions))

    add_surface_variant(stage)
    add_visibility_variant(stage, "/World/Atmosphere", "atmosphere_bounds", "visible")
    add_visibility_variant(stage, "/World/Clouds", "cloud_visibility", "visible")

    stage.SetDefaultPrim(world.GetPrim())
    stage.GetRootLayer().Save()
    print(f"  Saved: {path}")


# ---------------------------------------------------------------------------
# Root stage – compose all layers
# ---------------------------------------------------------------------------
def create_satellite_scene(scene_path, env_path):
    stage = Usd.Stage.CreateNew(scene_path)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetMetadata("metersPerUnit", 1000.0)

    world = stage.DefinePrim("/World", "Xform")
    Usd.ModelAPI(world).SetKind("assembly")

    env_prim = stage.DefinePrim("/World/Environment", "Xform")
    env_prim.GetReferences().AddReference(os.path.basename(env_path))

    stage.SetDefaultPrim(world)
    stage.GetRootLayer().Save()
    print(f"  Saved: {scene_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    env_path = os.path.join(OUT_DIR, "environment.usda")
    scene_path = os.path.join(OUT_DIR, "satellite_scene.usda")

    print("=== Week 1: Local Atmosphere Scene ===\n")
    print("Creating Week 1 baseline layer...")
    create_environment_layer(env_path)

    print("\nComposing root stage...")
    create_satellite_scene(scene_path, env_path)

    print("\nVerify with:")
    print(f"  usdview    {scene_path}")


if __name__ == "__main__":
    main()
