#!/usr/bin/env python3
"""Week 6: renderer-based cloud shadow experiment.

Builds from the Week 5 visual setup, but replaces fake shadow patches in the
primary mode with mesh cloud occluders and a sun light. The goal is to test
whether Storm/usdrecord can compute real shadows when the cloud is represented
as actual geometry instead of preview point sprites.
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
WEEK6_DIR = os.path.join(PROJECT_ROOT, "assets", "week6")
RENDERS_WEEK6_DIR = os.path.join(PROJECT_ROOT, "renders", "week6")


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
    mesh.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    if material:
        bind_material(mesh, material)
    return mesh


def create_polygon_mesh(stage, path, points_xy, z, color, material=None):
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr([Gf.Vec3f(x, y, z) for x, y in points_xy])
    mesh.CreateFaceVertexCountsAttr([len(points_xy)])
    mesh.CreateFaceVertexIndicesAttr(list(range(len(points_xy))))
    mesh.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    if material:
        bind_material(mesh, material)
    return mesh


def create_ellipse_mesh(stage, path, center, radius_x, radius_y, z, color, material=None, segments=48):
    points = [(center[0], center[1])]
    for index in range(segments):
        angle = 2.0 * math.pi * index / segments
        points.append((center[0] + math.cos(angle) * radius_x, center[1] + math.sin(angle) * radius_y))
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr([Gf.Vec3f(x, y, z) for x, y in points])
    mesh.CreateFaceVertexCountsAttr([segments + 1])
    mesh.CreateFaceVertexIndicesAttr([0] + list(range(1, segments + 1)))
    mesh.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    if material:
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
        "surface": create_preview_material(stage, "/World/Materials/SurfaceMatte", (0.55, 0.68, 0.70), 0.82, 0.02),
        "cloud": create_preview_material(stage, "/World/Materials/CloudOccluder", (0.88, 0.92, 0.92), 0.74, 0.04),
        "shadow": create_preview_material(stage, "/World/Materials/BakedShadowDebug", (0.005, 0.008, 0.008), 0.95, 0.0),
        "domain": create_preview_material(stage, "/World/Materials/DomainFrame", (0.42, 0.58, 0.66), 0.85, 0.02),
    }


def create_surface(stage, materials, use_baked_shadow=False):
    surfaces = UsdGeom.Xform.Define(stage, "/World/Surfaces")
    Usd.ModelAPI(surfaces.GetPrim()).SetKind("group")

    create_rect_mesh(stage, "/World/Surfaces/Ocean_DarkLowAlbedo", 0.0, DOMAIN_X, 0.0, 20.0, 0.0, (0.025, 0.12, 0.22))
    create_rect_mesh(stage, "/World/Surfaces/MarginalIce_Albedo050", 0.0, DOMAIN_X, 20.0, 30.0, 0.025, (0.28, 0.42, 0.47))
    create_rect_mesh(stage, "/World/Surfaces/SeaIce_Albedo080", 0.0, DOMAIN_X, 30.0, DOMAIN_Y, 0.04, (0.48, 0.58, 0.60))
    create_rect_mesh(stage, "/World/Surfaces/SnowBand_Albedo080", 4.0, 47.0, 39.0, 48.0, 0.08, (0.58, 0.66, 0.64))

    create_polygon_mesh(
        stage,
        "/World/Surfaces/IcePatch_A_Albedo055",
        [(4.8, 13.8), (7.5, 17.8), (13.8, 18.5), (15.5, 15.6), (12.2, 12.5), (7.0, 12.0)],
        0.08,
        (0.26, 0.44, 0.50),
    )
    create_polygon_mesh(
        stage,
        "/World/Surfaces/IcePatch_B_Albedo052",
        [(18.2, 10.2), (21.6, 14.7), (28.6, 14.0), (30.0, 10.5), (25.2, 8.2), (20.5, 8.6)],
        0.08,
        (0.24, 0.40, 0.48),
    )
    create_polygon_mesh(
        stage,
        "/World/Surfaces/IcePatch_C_Albedo058",
        [(34.0, 15.2), (38.0, 19.5), (46.5, 18.0), (47.8, 14.4), (41.5, 12.6), (36.0, 13.2)],
        0.08,
        (0.30, 0.47, 0.53),
    )
    create_polygon_mesh(
        stage,
        "/World/Surfaces/YoungIce_Albedo055",
        [(29.5, 24.5), (47.5, 25.0), (48.0, 33.2), (42.0, 35.0), (32.0, 33.5), (28.5, 29.0)],
        0.08,
        (0.26, 0.44, 0.52),
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

    if use_baked_shadow:
        create_baked_shadow_surface(stage, "/World/Surfaces/BakedShadowMask", (0.006, 0.010, 0.010), materials["shadow"])

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


def make_cloud_particles(seed=11):
    rng = random.Random(seed)
    particles = []

    for _ in range(34):
        angle = rng.uniform(0.0, 2.0 * math.pi)
        radial = math.sqrt(rng.uniform(0.0, 1.0))
        particles.append(
            {
                "group": "base",
                "position": Gf.Vec3f(
                    12.0 + math.cos(angle) * radial * 9.5,
                    28.0 + math.sin(angle) * radial * 5.8,
                    9.5 + rng.uniform(-0.6, 1.0),
                ),
                "scale": Gf.Vec3f(rng.uniform(2.0, 3.5), rng.uniform(1.3, 2.6), rng.uniform(0.55, 0.9)),
                "width": rng.uniform(1.7, 2.7),
                "color": Gf.Vec3f(0.76, 0.84, 0.88),
            }
        )

    for _ in range(28):
        angle = rng.uniform(0.0, 2.0 * math.pi)
        radial = math.sqrt(rng.uniform(0.0, 1.0))
        particles.append(
            {
                "group": "core",
                "position": Gf.Vec3f(
                    13.5 + math.cos(angle) * radial * 7.0,
                    27.5 + math.sin(angle) * radial * 4.4,
                    11.8 + rng.uniform(-0.2, 1.8),
                ),
                "scale": Gf.Vec3f(rng.uniform(1.5, 2.8), rng.uniform(1.2, 2.3), rng.uniform(0.9, 1.4)),
                "width": rng.uniform(1.5, 2.4),
                "color": Gf.Vec3f(0.92, 0.95, 0.96),
            }
        )

    for _ in range(28):
        side = -1.0 if len(particles) % 2 == 0 else 1.0
        particles.append(
            {
                "group": "wisp",
                "position": Gf.Vec3f(
                    rng.uniform(4.5, 23.5),
                    28.0 + side * rng.uniform(4.8, 8.0),
                    10.9 + rng.uniform(-0.8, 1.2),
                ),
                "scale": Gf.Vec3f(rng.uniform(0.8, 1.5), rng.uniform(0.4, 0.9), rng.uniform(0.35, 0.65)),
                "width": rng.uniform(0.7, 1.4),
                "color": Gf.Vec3f(0.68, 0.78, 0.84),
            }
        )

    return particles


def create_points_preview(stage, particles):
    cloud = UsdGeom.Points.Define(stage, "/World/CloudSystem/PointsPreview")
    cloud.CreateWidthsAttr([particle["width"] for particle in particles])
    cloud.CreateDisplayColorAttr([particle["color"] for particle in particles])
    points_attr = cloud.CreatePointsAttr()
    base_positions = [particle["position"] for particle in particles]
    for time_code in (START_TIME, 5.0, 10.0, 15.0, END_TIME):
        offset = cloud_offset_at_time(time_code)
        points_attr.Set([position + offset for position in base_positions], Usd.TimeCode(time_code))
    return cloud


def create_mesh_occluders(stage, particles, material):
    group = UsdGeom.Xform.Define(stage, "/World/CloudSystem/MeshOccluders")
    Usd.ModelAPI(group.GetPrim()).SetKind("group")
    translate = group.AddTranslateOp()
    for time_code in (START_TIME, 5.0, 10.0, 15.0, END_TIME):
        translate.Set(Gf.Vec3d(cloud_offset_at_time(time_code)), Usd.TimeCode(time_code))

    for index, particle in enumerate(particles):
        xform = UsdGeom.Xform.Define(stage, f"/World/CloudSystem/MeshOccluders/Lobe_{index:03d}")
        xform.AddTranslateOp().Set(Gf.Vec3d(particle["position"]))
        xform.AddScaleOp().Set(Gf.Vec3f(particle["scale"]))
        sphere = UsdGeom.Sphere.Define(stage, f"/World/CloudSystem/MeshOccluders/Lobe_{index:03d}/Sphere")
        sphere.CreateRadiusAttr(1.0)
        sphere.CreateDisplayColorAttr([particle["color"]])
        bind_material(sphere, material)

    return group


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


def create_baked_shadow_surface(stage, path, color, material):
    shadow = create_shadow_fan_mesh(stage, path, color, material)
    for time_code in (START_TIME, 5.0, 10.0, 15.0, END_TIME):
        t = (time_code - START_TIME) / (END_TIME - START_TIME)
        offset = cloud_offset_at_time(time_code)
        center = Gf.Vec3f(
            max(10.0, min(38.0, 17.0 + offset[0] * 0.72)),
            max(14.0, min(29.0, 18.5 + offset[1] - 1.2 * t)),
            0.34,
        )
        shadow.GetPointsAttr().Set(ellipse_points(center, 10.5, 4.2, 0.34), Usd.TimeCode(time_code))
    return shadow


def create_cloud_system(stage, materials):
    clouds = UsdGeom.Xform.Define(stage, "/World/CloudSystem")
    Usd.ModelAPI(clouds.GetPrim()).SetKind("group")

    particles = make_cloud_particles()
    create_points_preview(stage, particles)
    create_mesh_occluders(stage, particles, materials["cloud"])

    debug = UsdGeom.Xform.Define(stage, "/World/DebugShadowProxy")
    Usd.ModelAPI(debug.GetPrim()).SetKind("group")
    create_baked_shadow_surface(stage, "/World/DebugShadowProxy/DebugShadowFootprint", (0.006, 0.010, 0.010), materials["shadow"])
    return particles


def create_lighting(stage):
    lighting = UsdGeom.Xform.Define(stage, "/World/Lighting")
    Usd.ModelAPI(lighting.GetPrim()).SetKind("group")

    polar = UsdLux.DistantLight.Define(stage, "/World/Lighting/PolarLowSun")
    polar.CreateColorAttr(Gf.Vec3f(1.0, 0.86, 0.68))
    polar.CreateIntensityAttr(650.0)
    polar.CreateAngleAttr(0.45)
    polar.AddRotateXYZOp().Set(Gf.Vec3f(-34.0, 0.0, -38.0))

    zenith = UsdLux.DistantLight.Define(stage, "/World/Lighting/ZenithSun")
    zenith.CreateColorAttr(Gf.Vec3f(1.0, 0.96, 0.88))
    zenith.CreateIntensityAttr(520.0)
    zenith.CreateAngleAttr(0.35)
    zenith.AddRotateXYZOp().Set(Gf.Vec3f(-80.0, 0.0, 0.0))

    fill = UsdLux.DomeLight.Define(stage, "/World/Lighting/SkyFill")
    fill.CreateColorAttr(Gf.Vec3f(0.46, 0.54, 0.64))
    fill.CreateIntensityAttr(8.0)
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
    for name, points_vis, mesh_vis in (
        ("points_preview", "inherited", "invisible"),
        ("mesh_occluders", "invisible", "inherited"),
        ("future_vdb", "invisible", "invisible"),
    ):
        cloud_vs.AddVariant(name)
        cloud_vs.SetVariantSelection(name)
        with cloud_vs.GetVariantEditContext():
            set_visibility(stage.GetPrimAtPath("/World/CloudSystem/PointsPreview"), points_vis)
            set_visibility(stage.GetPrimAtPath("/World/CloudSystem/MeshOccluders"), mesh_vis)
    cloud_vs.SetVariantSelection("mesh_occluders")

    shadow_vs = world.GetVariantSets().AddVariantSet("shadow_mode")
    for name, debug_vis, baked_vis in (
        ("renderer_shadow", "invisible", "invisible"),
        ("baked_shadow_mask", "invisible", "inherited"),
        ("debug_shadow_proxy", "inherited", "invisible"),
    ):
        shadow_vs.AddVariant(name)
        shadow_vs.SetVariantSelection(name)
        with shadow_vs.GetVariantEditContext():
            set_visibility(stage.GetPrimAtPath("/World/DebugShadowProxy"), debug_vis)
            set_visibility(stage.GetPrimAtPath("/World/Surfaces/BakedShadowMask"), baked_vis)
    shadow_vs.SetVariantSelection("renderer_shadow")

    sun_vs = world.GetVariantSets().AddVariantSet("sun_case")
    for name, polar_vis, zenith_vis in (
        ("polar_low_sun", "inherited", "invisible"),
        ("zenith_sun", "invisible", "inherited"),
    ):
        sun_vs.AddVariant(name)
        sun_vs.SetVariantSelection(name)
        with sun_vs.GetVariantEditContext():
            set_visibility(stage.GetPrimAtPath("/World/Lighting/PolarLowSun"), polar_vis)
            set_visibility(stage.GetPrimAtPath("/World/Lighting/ZenithSun"), zenith_vis)
    sun_vs.SetVariantSelection("polar_low_sun")


def add_render_notes(stage):
    notes = UsdGeom.Scope.Define(stage, "/World/RenderNotes")
    prim = notes.GetPrim()
    prim.CreateAttribute("description", Sdf.ValueTypeNames.String).Set(
        "Week 6 renderer-shadow experiment. Primary mode uses mesh cloud occluders and UsdLux sun lighting. "
        "Render with camera light disabled to test whether Storm computes real surface shadows."
    )
    prim.CreateAttribute("renderCommand", Sdf.ValueTypeNames.String).Set(
        "usdrecord --disableCameraLight --camera /World/Camera/MainCamera --frames 1:20 --imageWidth 1280 "
        "assets/week6/renderer_shadow_scene.usda renders/week6/renderer_shadow_###.png"
    )


def write_shadow_comparison():
    os.makedirs(RENDERS_WEEK6_DIR, exist_ok=True)
    path = os.path.join(RENDERS_WEEK6_DIR, "shadow_comparison.md")
    lines = [
        "# Week 6 Shadow Comparison",
        "",
        "## Week 5 issue",
        "",
        "Week 5 used opaque dark USD geometry as a fake cloud shadow. That made the shadow behave like a pasted patch, not a physical darkening of the surface. Bright floes around the patch created white cutout boundaries.",
        "",
        "## Week 6 primary test",
        "",
        "- `cloud_representation = mesh_occluders`",
        "- `shadow_mode = renderer_shadow`",
        "- `sun_case = polar_low_sun`",
        "- Render with `usdrecord --disableCameraLight`.",
        "",
        "This tests whether Storm computes shadows from mesh cloud geometry.",
        "",
        "## Fallback",
        "",
        "If Storm does not produce reliable renderer shadows, switch `shadow_mode` to `baked_shadow_mask` and treat that as a stable visualization fallback until RTX/OpenVDB rendering is available.",
    ]
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


def create_renderer_shadow_scene(out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    os.makedirs(RENDERS_WEEK6_DIR, exist_ok=True)

    stage = Usd.Stage.CreateNew(out_path)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetMetadata("metersPerUnit", 1000.0)
    stage.SetStartTimeCode(START_TIME)
    stage.SetEndTimeCode(END_TIME)
    stage.SetTimeCodesPerSecond(TIME_CODES_PER_SECOND)

    world = UsdGeom.Xform.Define(stage, "/World")
    Usd.ModelAPI(world.GetPrim()).SetKind("assembly")

    materials = create_materials(stage)
    create_surface(stage, materials, use_baked_shadow=True)

    atmosphere = UsdGeom.Xform.Define(stage, "/World/Atmosphere")
    Usd.ModelAPI(atmosphere.GetPrim()).SetKind("group")
    create_domain_frame(stage, materials["domain"])

    particles = create_cloud_system(stage, materials)
    create_lighting(stage)
    add_camera(stage)
    add_variants(stage)
    add_render_notes(stage)
    report = write_shadow_comparison()

    stage.SetDefaultPrim(world.GetPrim())
    stage.GetRootLayer().Save()
    print(f"Saved: {out_path}")
    print(f"Cloud mesh occluders: {len(particles)}")
    print(f"Comparison notes: {report}")


def main():
    out_path = os.path.join(WEEK6_DIR, "renderer_shadow_scene.usda")
    print("=== Week 6: Renderer-Based Cloud Shadows ===\n")
    create_renderer_shadow_scene(out_path)
    print("\nPreview with:")
    print(f"  usdview {out_path}")
    print("\nRender with:")
    print(
        "  usdrecord --disableCameraLight --camera /World/Camera/MainCamera --frames 1:20 --imageWidth 1280 "
        f"{os.path.relpath(out_path, PROJECT_ROOT)} renders/week6/renderer_shadow_###.png"
    )


if __name__ == "__main__":
    main()
