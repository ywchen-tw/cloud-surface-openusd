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
    p.add_argument("--density-scale", type=float, default=1.0)
    p.add_argument("--skip-existing", action="store_true",
                   help="skip frames whose PNG already exists (resume after preemption)")
    return p.parse_args(argv)


def enable_gpu(scene):
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dev_type in ("OPTIX", "CUDA"):
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


def assign_cloud_material(obj, anisotropy, density_scale):
    mat = bpy.data.materials.new("CloudVolumeCycles")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    pv = nt.nodes.new("ShaderNodeVolumePrincipled")
    pv.inputs["Density Attribute"].default_value = "density"
    pv.inputs["Density"].default_value = density_scale
    pv.inputs["Anisotropy"].default_value = anisotropy
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


def ensure_light_and_world(scene):
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
        bg.inputs[1].default_value = 0.4


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
        assign_cloud_material(v, args.anisotropy, args.density_scale)

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    dev = enable_gpu(scene)
    scene.cycles.samples = args.samples
    scene.render.resolution_x, scene.render.resolution_y = args.res
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = args.out
    scene.frame_start, scene.frame_end = args.frame_start, args.frame_end
    scene.render.use_overwrite = not args.skip_existing
    scene.render.use_placeholder = args.skip_existing

    cam_info = ensure_camera(scene, args.camera)
    ensure_light_and_world(scene)

    print(f"[curc] device={dev} samples={args.samples} res={args.res} camera={cam_info}")
    print(f"[curc] rendering frames {args.frame_start}..{args.frame_end} -> {args.out}####.png")
    bpy.ops.render.render(animation=True)
    print("[curc] render complete")


if __name__ == "__main__":
    main()
