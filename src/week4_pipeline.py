#!/usr/bin/env python3
"""Week 4: final composition, validation, and reproducibility.

This script does the local hardening work that can run without a GUI renderer:
  - validates Week 1-3 USD stages with OpenUSD Python APIs
  - creates a final composed scene with camera and render notes
  - writes a Markdown validation report

Actual RTX images/video are left as CURC `usdview`/renderer tasks because this
local environment does not provide a working GUI render session.
"""

import os
from dataclasses import dataclass

from pxr import Gf, Sdf, Usd, UsdGeom

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
WEEK1_STAGE = os.path.join(ASSETS_DIR, "week1", "environment.usda")
WEEK2_STAGE = os.path.join(ASSETS_DIR, "week2", "clouds_move.usda")
WEEK3_STAGE = os.path.join(ASSETS_DIR, "week3", "clouds_vol.usda")
WEEK4_DIR = os.path.join(ASSETS_DIR, "week4")
RENDERS_DIR = os.path.join(PROJECT_ROOT, "renders")


@dataclass
class CheckResult:
    path: str
    ok: bool
    details: list[str]


def require(condition, message, details):
    if condition:
        details.append(f"PASS: {message}")
        return True
    details.append(f"FAIL: {message}")
    return False


def validate_stage(path, expected_variants=None):
    expected_variants = expected_variants or {}
    details = []
    ok = True

    stage = Usd.Stage.Open(path)
    ok &= require(stage is not None, "stage opens", details)
    if stage is None:
        return CheckResult(path, False, details)

    default_prim = stage.GetDefaultPrim()
    ok &= require(default_prim.IsValid(), f"defaultPrim exists ({default_prim.GetPath()})", details)
    ok &= require(stage.GetMetadata("upAxis") == "Z", "upAxis is Z", details)
    ok &= require(stage.GetMetadata("metersPerUnit") == 1000.0, "metersPerUnit is 1000", details)

    for prim_path, variants in expected_variants.items():
        prim = stage.GetPrimAtPath(prim_path)
        ok &= require(prim.IsValid(), f"{prim_path} exists", details)
        if not prim.IsValid():
            continue
        variant_sets = prim.GetVariantSets()
        for variant_name in variants:
            variant_set = variant_sets.GetVariantSet(variant_name)
            names = variant_set.GetVariantNames()
            ok &= require(bool(names), f"{prim_path} has VariantSet {variant_name}", details)
            if names:
                details.append(f"      variants: {', '.join(names)}")

    return CheckResult(path, bool(ok), details)


def add_camera(stage):
    camera = UsdGeom.Camera.Define(stage, "/World/Camera/MainCamera")
    camera.CreateFocalLengthAttr(28.0)
    camera.CreateHorizontalApertureAttr(24.0)
    camera.CreateVerticalApertureAttr(18.0)
    eye = Gf.Vec3d(82.0, -72.0, 54.0)
    target = Gf.Vec3d(25.0, 25.0, 10.5)
    up = Gf.Vec3d(0.0, 0.0, 1.0)
    camera.AddTransformOp().Set(Gf.Matrix4d().SetLookAt(eye, target, up).GetInverse())
    return camera


def create_final_scene(out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    stage = Usd.Stage.CreateNew(out_path)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetMetadata("metersPerUnit", 1000.0)
    stage.SetStartTimeCode(1.0)
    stage.SetEndTimeCode(20.0)
    stage.SetTimeCodesPerSecond(4.0)

    world = UsdGeom.Xform.Define(stage, "/World")
    Usd.ModelAPI(world.GetPrim()).SetKind("assembly")

    scene = stage.DefinePrim("/World/Scene", "Xform")
    scene_reference = os.path.relpath(WEEK3_STAGE, WEEK4_DIR)
    scene.GetReferences().AddReference(scene_reference)
    scene.GetVariantSets().SetSelection("sun_case", "sun_slant")

    camera_scope = UsdGeom.Xform.Define(stage, "/World/Camera")
    Usd.ModelAPI(camera_scope.GetPrim()).SetKind("group")
    add_camera(stage)

    notes = UsdGeom.Scope.Define(stage, "/World/RenderNotes")
    notes.GetPrim().CreateAttribute("description", Sdf.ValueTypeNames.String).Set(
        "Final Week 4 composition. Switch /World/Scene sun_case between sun_slant and sun_zenith; "
        "scrub frames 1-20 in the referenced Week 2 cloud-motion scene."
    )

    stage.SetDefaultPrim(world.GetPrim())
    stage.GetRootLayer().Save()
    return out_path


def create_cloud_motion_scene(out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    stage = Usd.Stage.CreateNew(out_path)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetMetadata("metersPerUnit", 1000.0)
    stage.SetStartTimeCode(1.0)
    stage.SetEndTimeCode(20.0)
    stage.SetTimeCodesPerSecond(4.0)

    world = UsdGeom.Xform.Define(stage, "/World")
    Usd.ModelAPI(world.GetPrim()).SetKind("assembly")

    scene = stage.DefinePrim("/World/Scene", "Xform")
    scene_reference = os.path.relpath(WEEK2_STAGE, WEEK4_DIR)
    scene.GetReferences().AddReference(scene_reference)
    moving_system = stage.GetPrimAtPath("/World/Scene/MovingCloudSystem")
    moving_system.GetVariantSets().SetSelection("motion_mode", "manual_transform")

    camera_scope = UsdGeom.Xform.Define(stage, "/World/Camera")
    Usd.ModelAPI(camera_scope.GetPrim()).SetKind("group")
    add_camera(stage)

    notes = UsdGeom.Scope.Define(stage, "/World/RenderNotes")
    notes.GetPrim().CreateAttribute("description", Sdf.ValueTypeNames.String).Set(
        "Final Week 4 cloud-motion composition. Scrub frames 1-20 and render to renders/final.mp4."
    )

    stage.SetDefaultPrim(world.GetPrim())
    stage.GetRootLayer().Save()
    return out_path


def write_report(results, final_scene_path, motion_scene_path):
    os.makedirs(RENDERS_DIR, exist_ok=True)
    report_path = os.path.join(RENDERS_DIR, "validation_report.md")
    lines = [
        "# Week 4 Validation Report",
        "",
        f"Sun comparison scene: `{os.path.relpath(final_scene_path, PROJECT_ROOT)}`",
        f"Cloud-motion scene: `{os.path.relpath(motion_scene_path, PROJECT_ROOT)}`",
        "",
        "## Stage Checks",
        "",
    ]

    for result in results:
        status = "PASS" if result.ok else "FAIL"
        lines.append(f"### {status}: `{os.path.relpath(result.path, PROJECT_ROOT)}`")
        for detail in result.details:
            lines.append(f"- {detail}")
        lines.append("")

    lines.extend(
        [
            "## Render Targets",
            "",
            "- `renders/sun_slant.png`: set `/World/Scene.sun_case = sun_slant`.",
            "- `renders/sun_zenith.png`: set `/World/Scene.sun_case = sun_zenith`.",
            "- `renders/final.mp4`: open `assets/week4/cloud_motion_scene.usda`, scrub frames 1-20, and capture the cloud-motion comparison.",
            "",
            "## Notes",
            "",
            "- Local validation uses `pxr.Usd.Stage.Open` because the current `usdchecker` binary aborts with a Python dynamic-linker symbol error on this machine.",
            "- The Week 3 cloud is a structured `UsdGeom.Points` voxel placeholder. Real OpenVDB/EaR3T grids should be written under `assets/week3/vdbs/` later.",
        ]
    )

    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return report_path


def main():
    final_scene_path = os.path.join(WEEK4_DIR, "final_scene.usda")
    motion_scene_path = os.path.join(WEEK4_DIR, "cloud_motion_scene.usda")
    print("=== Week 4: Pipeline, Optimization & Validation ===\n")

    final_scene = create_final_scene(final_scene_path)
    motion_scene = create_cloud_motion_scene(motion_scene_path)
    print(f"Saved: {final_scene}")
    print(f"Saved: {motion_scene}")

    results = [
        validate_stage(
            WEEK1_STAGE,
            {
                "/World/Surfaces": ["surface_mode"],
                "/World/Atmosphere": ["atmosphere_bounds"],
                "/World/Clouds": ["cloud_visibility"],
            },
        ),
        validate_stage(WEEK2_STAGE, {"/World/MovingCloudSystem": ["motion_mode"]}),
        validate_stage(WEEK3_STAGE, {"/World": ["sun_case"]}),
        validate_stage(final_scene_path, {"/World/Scene": ["sun_case"]}),
        validate_stage(motion_scene_path, {"/World/Scene/MovingCloudSystem": ["motion_mode"]}),
    ]
    report = write_report(results, final_scene_path, motion_scene_path)

    for result in results:
        print(("PASS" if result.ok else "FAIL"), os.path.relpath(result.path, PROJECT_ROOT))
    print(f"\nReport: {report}")
    print("\nPreview with:")
    print(f"  usdview {final_scene_path}")
    print(f"  usdview {motion_scene_path}")


if __name__ == "__main__":
    main()
