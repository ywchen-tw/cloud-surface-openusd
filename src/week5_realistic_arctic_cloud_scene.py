#!/usr/bin/env python3
"""Week 5: renderer-stable Arctic cloud scene.

This scene is intentionally conservative for `usdrecord`/Storm:
  - no enclosing sky dome or huge background plane
  - no transparency-dependent cloud materials
  - no required custom lighting plugin behavior
  - solid display-colored geometry that should survive headless rendering

The visual goal is a readable research prototype: an Arctic albedo surface,
layered cloud particles, moving cloud shadow, and a camera that frames the
domain without clipping through large planes.
"""

import math
import os
import random

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdShade

DOMAIN_X = 50.0
DOMAIN_Y = 50.0
DOMAIN_Z = 25.0
START_TIME = 1.0
END_TIME = 20.0
TIME_CODES_PER_SECOND = 4.0

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEEK5_DIR = os.path.join(PROJECT_ROOT, "assets", "week5")
RENDERS_WEEK5_DIR = os.path.join(PROJECT_ROOT, "renders", "week5")


def create_preview_material(stage, path, color, roughness=0.65, specular=0.08):
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
    mesh.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    if material is not None:
        bind_material(mesh, material)
    return mesh


def create_ellipse_mesh(stage, path, center, radius_x, radius_y, z, color, material=None, segments=48):
    mesh = UsdGeom.Mesh.Define(stage, path)
    points = [Gf.Vec3f(center[0], center[1], z)]
    for index in range(segments):
        angle = 2.0 * math.pi * index / segments
        points.append(
            Gf.Vec3f(
                center[0] + math.cos(angle) * radius_x,
                center[1] + math.sin(angle) * radius_y,
                z,
            )
        )
    mesh.CreatePointsAttr(points)
    mesh.CreateFaceVertexCountsAttr([segments + 1])
    mesh.CreateFaceVertexIndicesAttr([0] + list(range(1, segments + 1)))
    mesh.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    if material is not None:
        bind_material(mesh, material)
    return mesh


def create_polygon_mesh(stage, path, points_xy, z, color, material=None):
    mesh = UsdGeom.Mesh.Define(stage, path)
    points = [Gf.Vec3f(x, y, z) for x, y in points_xy]
    mesh.CreatePointsAttr(points)
    mesh.CreateFaceVertexCountsAttr([len(points)])
    mesh.CreateFaceVertexIndicesAttr(list(range(len(points))))
    mesh.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    if material is not None:
        bind_material(mesh, material)
    return mesh


def create_curve(stage, path, points, color, width=0.08):
    curve = UsdGeom.BasisCurves.Define(stage, path)
    curve.CreateTypeAttr(UsdGeom.Tokens.linear)
    curve.CreateCurveVertexCountsAttr([len(points)])
    curve.CreatePointsAttr([Gf.Vec3f(*point) for point in points])
    curve.CreateWidthsAttr([width] * len(points))
    curve.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    return curve


def create_materials(stage):
    UsdGeom.Scope.Define(stage, "/World/Materials")
    return {
        "ocean": create_preview_material(stage, "/World/Materials/Ocean", (0.05, 0.20, 0.34), 0.42, 0.16),
        "sea_ice": create_preview_material(stage, "/World/Materials/SeaIceAlbedo075", (0.68, 0.82, 0.86), 0.72, 0.06),
        "snow": create_preview_material(stage, "/World/Materials/SnowAlbedo090", (0.86, 0.91, 0.90), 0.78, 0.04),
        "young_ice": create_preview_material(stage, "/World/Materials/YoungIceAlbedo055", (0.48, 0.66, 0.72), 0.68, 0.06),
        "melt_pond": create_preview_material(stage, "/World/Materials/MeltPondAlbedo035", (0.14, 0.38, 0.52), 0.45, 0.12),
        "shadow": create_preview_material(stage, "/World/Materials/CloudShadow", (0.005, 0.008, 0.008), 0.95, 0.0),
        "cooling": create_preview_material(stage, "/World/Materials/CoolingProxy", (0.18, 0.46, 0.66), 0.86, 0.02),
        "cloud_base": create_preview_material(stage, "/World/Materials/CloudBase", (0.78, 0.86, 0.90), 0.82, 0.04),
        "cloud_core": create_preview_material(stage, "/World/Materials/CloudCore", (0.93, 0.96, 0.96), 0.62, 0.05),
        "cloud_wisp": create_preview_material(stage, "/World/Materials/CloudWisp", (0.72, 0.82, 0.88), 0.88, 0.03),
        "domain": create_preview_material(stage, "/World/Materials/DomainFrame", (0.42, 0.58, 0.66), 0.85, 0.02),
    }


def create_surface(stage, materials):
    surfaces = UsdGeom.Xform.Define(stage, "/World/Surfaces")
    Usd.ModelAPI(surfaces.GetPrim()).SetKind("group")

    # Use displayColor only for the surface. In Storm/usdrecord this is more
    # stable than relying on shaded materials for large single-plane meshes.
    create_rect_mesh(stage, "/World/Surfaces/Ocean_DarkLowAlbedo", 0.0, DOMAIN_X, 0.0, 20.0, 0.0, (0.025, 0.12, 0.22))
    create_rect_mesh(stage, "/World/Surfaces/MarginalIce_Albedo050", 0.0, DOMAIN_X, 20.0, 30.0, 0.025, (0.36, 0.53, 0.58))
    create_rect_mesh(stage, "/World/Surfaces/SeaIce_Albedo075", 0.0, DOMAIN_X, 30.0, DOMAIN_Y, 0.04, (0.56, 0.69, 0.72))
    create_rect_mesh(stage, "/World/Surfaces/SnowBand_Albedo090", 4.0, 47.0, 39.0, 48.0, 0.08, (0.74, 0.82, 0.80))

    create_polygon_mesh(
        stage,
        "/World/Surfaces/IcePatch_A_Albedo060",
        [(4.8, 13.8), (7.5, 17.8), (13.8, 18.5), (15.5, 15.6), (12.2, 12.5), (7.0, 12.0)],
        0.08,
        (0.34, 0.55, 0.62),
    )
    create_polygon_mesh(
        stage,
        "/World/Surfaces/IcePatch_B_Albedo058",
        [(18.2, 10.2), (21.6, 14.7), (28.6, 14.0), (30.0, 10.5), (25.2, 8.2), (20.5, 8.6)],
        0.08,
        (0.32, 0.52, 0.60),
    )
    create_polygon_mesh(
        stage,
        "/World/Surfaces/IcePatch_C_Albedo062",
        [(34.0, 15.2), (38.0, 19.5), (46.5, 18.0), (47.8, 14.4), (41.5, 12.6), (36.0, 13.2)],
        0.08,
        (0.37, 0.57, 0.64),
    )
    create_polygon_mesh(
        stage,
        "/World/Surfaces/YoungIce_Albedo055",
        [(29.5, 24.5), (47.5, 25.0), (48.0, 33.2), (42.0, 35.0), (32.0, 33.5), (28.5, 29.0)],
        0.08,
        (0.34, 0.55, 0.63),
    )

    create_ellipse_mesh(stage, "/World/Surfaces/MeltPond_A", (16.0, 33.0), 5.4, 2.2, 0.11, (0.08, 0.32, 0.48))
    create_ellipse_mesh(stage, "/World/Surfaces/MeltPond_B", (38.0, 41.0), 3.8, 1.7, 0.11, (0.08, 0.32, 0.48))
    create_ellipse_mesh(stage, "/World/Surfaces/MeltPond_C", (26.0, 28.5), 2.8, 1.2, 0.11, (0.08, 0.32, 0.48))

    create_curve(
        stage,
        "/World/Surfaces/IceLead_DarkWater",
        [(0.0, 29.2, 0.13), (8.0, 28.6, 0.13), (18.0, 30.1, 0.13), (31.0, 29.4, 0.13), (50.0, 30.4, 0.13)],
        (0.015, 0.08, 0.14),
        0.35,
    )
    create_curve(
        stage,
        "/World/Surfaces/SnowCrack_01",
        [(7.0, 41.5, 0.14), (16.0, 42.5, 0.14), (23.0, 41.2, 0.14), (35.0, 43.0, 0.14)],
        (0.42, 0.55, 0.58),
        0.12,
    )
    create_curve(
        stage,
        "/World/Surfaces/SnowCrack_02",
        [(31.0, 33.5, 0.14), (37.0, 36.2, 0.14), (44.0, 35.0, 0.14)],
        (0.36, 0.50, 0.55),
        0.12,
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


def smooth_noise(index):
    return math.sin(index * 12.9898) * 43758.5453 % 1.0


def cloud_offset_at_time(time_code):
    t = (time_code - START_TIME) / (END_TIME - START_TIME)
    return Gf.Vec3f(23.0 * t, 2.0 * math.sin(t * math.pi), 0.35 * math.sin(t * math.pi))


def make_cloud_particles(seed=11):
    rng = random.Random(seed)
    particles = []

    for index in range(55):
        angle = rng.uniform(0.0, 2.0 * math.pi)
        radial = math.sqrt(rng.uniform(0.0, 1.0))
        particles.append(
            {
                "group": "base",
                "position": Gf.Vec3f(12.0 + math.cos(angle) * radial * 9.5, 28.0 + math.sin(angle) * radial * 5.8, 9.5 + rng.uniform(-0.8, 1.0)),
                "width": rng.uniform(1.7, 2.7),
                "color": Gf.Vec3f(0.76, 0.84, 0.88),
            }
        )

    for index in range(42):
        angle = rng.uniform(0.0, 2.0 * math.pi)
        radial = math.sqrt(rng.uniform(0.0, 1.0))
        particles.append(
            {
                "group": "core",
                "position": Gf.Vec3f(13.5 + math.cos(angle) * radial * 7.0, 27.5 + math.sin(angle) * radial * 4.4, 11.7 + rng.uniform(-0.3, 2.1)),
                "width": rng.uniform(1.5, 2.4),
                "color": Gf.Vec3f(0.92, 0.95, 0.96),
            }
        )

    for index in range(48):
        side = -1.0 if index % 2 == 0 else 1.0
        particles.append(
            {
                "group": "wisp",
                "position": Gf.Vec3f(rng.uniform(4.5, 23.5), 28.0 + side * rng.uniform(4.8, 8.0), 10.9 + rng.uniform(-0.8, 1.4)),
                "width": rng.uniform(0.7, 1.4),
                "color": Gf.Vec3f(0.68, 0.78, 0.84),
            }
        )

    return particles


def create_cloud_points(stage, particles):
    cloud = UsdGeom.Points.Define(stage, "/World/CloudSystem/LayeredCloud")
    colors = [particle["color"] for particle in particles]
    widths = [particle["width"] for particle in particles]
    cloud.CreateWidthsAttr(widths)
    cloud.CreateDisplayColorAttr(colors)

    base_positions = [particle["position"] for particle in particles]
    points_attr = cloud.CreatePointsAttr()
    for time_code in (START_TIME, 5.0, 10.0, 15.0, END_TIME):
        offset = cloud_offset_at_time(time_code)
        points_attr.Set([position + offset for position in base_positions], Usd.TimeCode(time_code))

    groups = {"base": 0.45, "core": 0.85, "wisp": 0.25}
    density = UsdGeom.PrimvarsAPI(cloud).CreatePrimvar(
        "densityProxy", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex
    )
    density.Set([groups[particle["group"]] + 0.1 * smooth_noise(index) for index, particle in enumerate(particles)])
    return cloud


def ellipse_points(center, radius_x, radius_y, z, segments=48):
    points = [Gf.Vec3f(center[0], center[1], z)]
    for index in range(segments):
        angle = 2.0 * math.pi * index / segments
        wobble = 1.0 + 0.07 * math.sin(index * 2.1) + 0.04 * math.cos(index * 3.7)
        points.append(
            Gf.Vec3f(
                center[0] + math.cos(angle) * radius_x * wobble,
                center[1] + math.sin(angle) * radius_y * wobble,
                z,
            )
        )
    return points


def create_shadow_fan_mesh(stage, path, color, material, segments=48):
    mesh = UsdGeom.Mesh.Define(stage, path)
    indices = []
    for index in range(segments):
        indices.extend([0, index + 1, 1 if index == segments - 1 else index + 2])
    mesh.CreateFaceVertexCountsAttr([3] * segments)
    mesh.CreateFaceVertexIndicesAttr(indices)
    mesh.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    bind_material(mesh, material)
    return mesh


def create_shadow_points(stage, particles, material):
    shadow_scope = UsdGeom.Xform.Define(stage, "/World/RadiativeCues/AnimatedCloudShadow")
    Usd.ModelAPI(shadow_scope.GetPrim()).SetKind("group")

    # Triangle fans avoid Storm n-gon triangulation artifacts. Keep this as a
    # single dark footprint; a second larger blanket made the adjacent bright
    # surface read like a white rim in usdrecord.
    core = create_shadow_fan_mesh(
        stage,
        "/World/RadiativeCues/AnimatedCloudShadow/CloudShadowFootprint",
        (0.006, 0.010, 0.010),
        material,
    )

    for time_code in (START_TIME, 5.0, 10.0, 15.0, END_TIME):
        t = (time_code - START_TIME) / (END_TIME - START_TIME)
        cloud_offset = cloud_offset_at_time(time_code)
        center = Gf.Vec3f(
            max(10.0, min(38.0, 17.0 + cloud_offset[0] * 0.72)),
            max(14.0, min(29.0, 18.5 + cloud_offset[1] - 1.2 * t)),
            0.34,
        )
        core.GetPointsAttr().Set(ellipse_points(center, 10.5, 4.2, 0.34), Usd.TimeCode(time_code))

    strength = UsdGeom.PrimvarsAPI(shadow_scope).CreatePrimvar(
        "shadowStrength", Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.constant
    )
    strength.Set([0.85])
    return shadow_scope


def create_cloud_system(stage, materials):
    clouds = UsdGeom.Xform.Define(stage, "/World/CloudSystem")
    Usd.ModelAPI(clouds.GetPrim()).SetKind("group")
    particles = make_cloud_particles()
    create_cloud_points(stage, particles)

    cues = UsdGeom.Xform.Define(stage, "/World/RadiativeCues")
    Usd.ModelAPI(cues.GetPrim()).SetKind("group")
    create_shadow_points(stage, particles, materials["shadow"])
    return particles


def create_lighting(stage):
    lighting = UsdGeom.Xform.Define(stage, "/World/Lighting")
    Usd.ModelAPI(lighting.GetPrim()).SetKind("group")

    sun = UsdLux.DistantLight.Define(stage, "/World/Lighting/PolarLowSun")
    sun.CreateColorAttr(Gf.Vec3f(1.0, 0.88, 0.72))
    sun.CreateIntensityAttr(350.0)
    sun.CreateAngleAttr(0.65)
    sun.AddRotateXYZOp().Set(Gf.Vec3f(-45.0, 0.0, -35.0))

    fill = UsdLux.DomeLight.Define(stage, "/World/Lighting/SkyFill")
    fill.CreateColorAttr(Gf.Vec3f(0.64, 0.72, 0.82))
    fill.CreateIntensityAttr(45.0)
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


def add_render_notes(stage):
    notes = UsdGeom.Scope.Define(stage, "/World/RenderNotes")
    prim = notes.GetPrim()
    prim.CreateAttribute("description", Sdf.ValueTypeNames.String).Set(
        "Week 5 renderer-stable Arctic cloud scene: colored albedo surface, point cloud layers, "
        "time-sampled cloud motion, and animated shadow/cooling proxy. Designed for usdrecord/Storm."
    )
    prim.CreateAttribute("renderCommand", Sdf.ValueTypeNames.String).Set(
        "usdrecord --camera /World/Camera/MainCamera --frames 1:20 --imageWidth 1280 "
        "assets/week5/realistic_arctic_cloud_scene.usda renders/week5/cloud_realistic_###.png"
    )


def create_realistic_scene(out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    os.makedirs(RENDERS_WEEK5_DIR, exist_ok=True)

    stage = Usd.Stage.CreateNew(out_path)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetMetadata("metersPerUnit", 1000.0)
    stage.SetStartTimeCode(START_TIME)
    stage.SetEndTimeCode(END_TIME)
    stage.SetTimeCodesPerSecond(TIME_CODES_PER_SECOND)

    world = UsdGeom.Xform.Define(stage, "/World")
    Usd.ModelAPI(world.GetPrim()).SetKind("assembly")

    materials = create_materials(stage)
    create_surface(stage, materials)

    atmosphere = UsdGeom.Xform.Define(stage, "/World/Atmosphere")
    Usd.ModelAPI(atmosphere.GetPrim()).SetKind("group")
    create_domain_frame(stage, materials["domain"])

    particles = create_cloud_system(stage, materials)
    create_lighting(stage)
    add_camera(stage)
    add_render_notes(stage)

    stage.SetDefaultPrim(world.GetPrim())
    stage.GetRootLayer().Save()
    print(f"Saved: {out_path}")
    print(f"Cloud particles: {len(particles)}")


def main():
    out_path = os.path.join(WEEK5_DIR, "realistic_arctic_cloud_scene.usda")

    print("=== Week 5: Renderer-Stable Arctic Cloud Scene ===\n")
    create_realistic_scene(out_path)
    print("\nPreview with:")
    print(f"  usdview {out_path}")
    print("\nRender with:")
    print(
        "  usdrecord --camera /World/Camera/MainCamera --frames 1:20 --imageWidth 1280 "
        f"{os.path.relpath(out_path, PROJECT_ROOT)} renders/week5/cloud_realistic_###.png"
    )


if __name__ == "__main__":
    main()
