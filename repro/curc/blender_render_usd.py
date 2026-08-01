"""Headless Blender-Cycles render driver for the USD cloud scenes (CURC GPU nodes).

Imports the USD stage, ensures the cloud volume has a Principled Volume shader
driven by the `density` grid with the project's Henyey-Greenstein anisotropy,
picks OptiX/CUDA, and renders the frame range.

Usage (see render_week7_cycles.sbatch):
  blender -b --factory-startup -noaudio -P repro/curc/blender_render_usd.py -- \
      --usd assets/week7/usdvol_cloud_scene.usda \
      --vdb assets/week7/vdbs/cloud_density.vdb \
      --out $OPENUSD_CLD_DATAROOT/renders/week7_cycles/usdvol_cloud_ \
      --frame-start 1 --frame-end 20 --samples 256 --res 1280 720
"""

import argparse
import math
import sys

import bpy
from mathutils import Vector


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--usd", required=True, help="USD stage to render")
    p.add_argument("--vdb", default=None, help="fallback VDB if USD import yields no volume")
    p.add_argument("--out", required=True, help="output path prefix (frames get %%04d.png)")
    p.add_argument("--frame-start", type=int, default=1)
    p.add_argument("--frame-end", type=int, default=20)
    p.add_argument("--samples", type=int, default=256)
    p.add_argument("--res", type=int, nargs=2, default=[1280, 720], metavar=("X", "Y"))
    p.add_argument("--camera", default=None, help="prefer camera object whose name contains this")
    p.add_argument("--anisotropy", type=float, default=0.85, help="HG asymmetry g (plan.md: 0.85)")
    p.add_argument("--ssa", type=float, default=0.999999,
                   help="single-scattering albedo -> Principled Volume color (liquid cloud ~1)")
    p.add_argument("--volume-bounces", type=int, default=16,
                   help="Cycles volume scattering bounces; 0 = single scattering = dark clouds")
    p.add_argument("--density-scale", type=float, default=1.0)
    p.add_argument("--skip-existing", action="store_true",
                   help="skip frames whose PNG already exists (resume after preemption)")
    p.add_argument("--exr", action="store_true",
                   help="write scene-linear OpenEXR (+ .npy radiance dump) instead of "
                        "tone-mapped PNG — required for quantitative validation")
    p.add_argument("--world-strength", type=float, default=0.4,
                   help="background/sky strength; use 0 for sun-only validation renders")
    p.add_argument("--flat-albedo", type=float, default=None,
                   help="replace all mesh materials with a Lambertian gray of this "
                        "albedo (match EaR3T's surface_albedo for validation)")
    p.add_argument("--device", choices=("auto", "optix", "cuda", "cpu"), default="auto",
                   help="render device; OptiX shows zero-radiance leaf-box artifacts "
                        "on this volume — use cpu (or cuda) for validation renders")
    return p.parse_args(argv)


def enable_gpu(scene, device="auto"):
    if device == "cpu":
        scene.cycles.device = "CPU"
        return "CPU"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    order = ("CUDA",) if device == "cuda" else ("OPTIX",) if device == "optix" else ("OPTIX", "CUDA")
    for dev_type in order:
        try:
            prefs.compute_device_type = dev_type
        except TypeError:
            continue
        prefs.get_devices()
        if any(d.type == dev_type for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type != "CPU"
            scene.cycles.device = "GPU"
            return dev_type
    scene.cycles.device = "CPU"
    return "CPU"


def volume_objects():
    return [o for o in bpy.data.objects if o.type == "VOLUME"]


def assign_cloud_material(obj, anisotropy, density_scale, ssa):
    mat = bpy.data.materials.new("CloudVolumeCycles")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    pv = nt.nodes.new("ShaderNodeVolumePrincipled")
    pv.inputs["Density Attribute"].default_value = "density"
    pv.inputs["Density"].default_value = density_scale
    pv.inputs["Anisotropy"].default_value = anisotropy
    # Color = single-scattering albedo (the node's default 0.5 renders like
    # soot; liquid cloud at VIS wavelengths is ~1 -> white).
    pv.inputs["Color"].default_value = (ssa, ssa, ssa, 1.0)
    nt.links.new(pv.outputs["Volume"], out.inputs["Volume"])
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def scene_bounds():
    lo = [1e30] * 3
    hi = [-1e30] * 3
    for o in bpy.data.objects:
        if o.type not in {"MESH", "VOLUME"}:
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
    if lo[0] > hi[0]:
        return (0, 0, 0), 50.0
    center = tuple((lo[i] + hi[i]) / 2 for i in range(3))
    size = max(hi[i] - lo[i] for i in range(3))
    return center, size


def ensure_camera(scene, name_hint):
    cams = [o for o in bpy.data.objects if o.type == "CAMERA"]
    if name_hint:
        preferred = [c for c in cams if name_hint.lower() in c.name.lower()]
        if preferred:
            cams = preferred
    if cams:
        scene.camera = cams[0]
        return cams[0].name + " (imported)"
    center, size = scene_bounds()
    cam_data = bpy.data.cameras.new("AutoCam")
    cam = bpy.data.objects.new("AutoCam", cam_data)
    scene.collection.objects.link(cam)
    d = 1.6 * size
    cam.location = (center[0] + d * 0.7, center[1] - d * 0.7, center[2] + d * 0.55)
    target = bpy.data.objects.new("AutoCamTarget", None)
    target.location = center
    scene.collection.objects.link(target)
    con = cam.constraints.new("TRACK_TO")
    con.target = target
    scene.camera = cam
    return "AutoCam (generated oblique view)"


def ensure_light_and_world(scene, world_strength=0.4):
    if not any(o.type == "LIGHT" for o in bpy.data.objects):
        sun_data = bpy.data.lights.new("AutoSun", type="SUN")
        sun_data.energy = 3.0
        sun_data.angle = math.radians(0.53)
        sun = bpy.data.objects.new("AutoSun", sun_data)
        sun.rotation_euler = (math.radians(50), 0, math.radians(30))
        scene.collection.objects.link(sun)
    if scene.world is None:
        scene.world = bpy.data.worlds.new("AutoWorld")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.35, 0.5, 0.72, 1.0)  # hazy sky blue
        bg.inputs[1].default_value = world_strength


def main():
    args = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)

    bpy.ops.wm.usd_import(filepath=args.usd)
    print(f"[curc] imported USD: {args.usd}")

    vols = volume_objects()
    if not vols and args.vdb:
        bpy.ops.object.volume_import(filepath=args.vdb, align="WORLD")
        vols = volume_objects()
        print(f"[curc] USD import had no volume; loaded VDB directly: {args.vdb}")
    if not vols:
        print("[curc] WARNING: no volume object in scene — rendering surfaces only")
    for v in vols:
        assign_cloud_material(v, args.anisotropy, args.density_scale, args.ssa)

    if args.flat_albedo is not None:
        mat = bpy.data.materials.new("FlatLambertian")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        a = args.flat_albedo
        bsdf.inputs["Base Color"].default_value = (a, a, a, 1.0)
        bsdf.inputs["Roughness"].default_value = 1.0
        for k in ("Specular IOR Level", "Specular"):
            if k in bsdf.inputs:
                bsdf.inputs[k].default_value = 0.0
                break
        for o in bpy.data.objects:
            if o.type == "MESH":
                o.data.materials.clear()
                o.data.materials.append(mat)
        print(f"[curc] all mesh surfaces -> Lambertian albedo {a}")

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    dev = enable_gpu(scene, args.device)
    scene.cycles.samples = args.samples
    # Multiple scattering is what makes clouds white; Cycles defaults to 0.
    scene.cycles.volume_bounces = args.volume_bounces
    scene.cycles.max_bounces = max(scene.cycles.max_bounces, args.volume_bounces)
    scene.render.resolution_x, scene.render.resolution_y = args.res
    if args.exr:
        scene.render.image_settings.file_format = "OPEN_EXR"
        scene.render.image_settings.color_depth = "32"
        scene.view_settings.view_transform = "Standard"
    else:
        scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = args.out
    scene.frame_start, scene.frame_end = args.frame_start, args.frame_end
    scene.render.use_overwrite = not args.skip_existing
    scene.render.use_placeholder = args.skip_existing

    cam_info = ensure_camera(scene, args.camera)
    ensure_light_and_world(scene, args.world_strength)

    ext = "exr" if args.exr else "png"
    print(f"[curc] device={dev} samples={args.samples} res={args.res} camera={cam_info}")
    print(f"[curc] rendering frames {args.frame_start}..{args.frame_end} -> {args.out}####.{ext}")
    bpy.ops.render.render(animation=True)

    if args.exr:
        # Dump each frame as float32 npy (mean of RGB — the scene is
        # monochromatic gray) so validation scripts need no EXR reader.
        import numpy as np
        for f in range(args.frame_start, args.frame_end + 1):
            path = f"{args.out}{f:04d}.exr"
            img = bpy.data.images.load(path)
            w, h = img.size
            px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
            rad = px[..., :3].mean(axis=2)[::-1]  # flip to row 0 = top
            np.save(path.replace(".exr", ".npy"), rad)
            bpy.data.images.remove(img)
            print(f"[curc] wrote {path.replace('.exr', '.npy')} (min {rad.min():.4g} max {rad.max():.4g})")
    print("[curc] render complete")


if __name__ == "__main__":
    main()
