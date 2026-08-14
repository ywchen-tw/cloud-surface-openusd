"""Bake the molecular-atmosphere profile (validation/make_atmosphere_profile.py)
into a two-grid OpenVDB for the Cycles side of the EaR3T benchmark:

  grid "scatter"  beta_sca(z)  Rayleigh scattering coefficient [1/m]
  grid "absorb"   beta_abs(z)  gray gas absorption coefficient [1/m]

Horizontally uniform, so the grid is deliberately coarse in x/y (3.2 km
voxels) and fine in z (80 m, matching the cloud grid, up to 20 km). Footprint
matches the buffered scene's ocean quad (-16.0 .. 22.4 km) so sun-slant paths
into the compared region stay inside the medium.

ALSO writes the COMBINED VDB `cloud_atmosphere_buffered.vdb` — the buffered
cloud `density` grid plus `scatter`/`absorb` in ONE file (per-grid
transforms). One volume prim/object must carry both media: with two separate
volume objects, Cycles drops the atmosphere's in-scattering inside the cloud
grid's sparse-node boxes (blocky radiance deficits around every cloud
cluster; CPU too — docs/rendering_artifacts.md). The driver assigns the
combined material (HG cloud + Rayleigh scatter + gray absorption) by prim
name.

Run (Blender-compatible OpenVDB 11 env — NEVER the openusd env):
  conda run -n vdbtools python src/atmosphere_to_vdb.py
"""

import json
import os

import numpy as np

try:
    import openvdb as vdb
except ImportError:  # pragma: no cover
    import pyopenvdb as vdb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE = os.path.join(ROOT, "data", "processed", "atmosphere_profile_650nm.json")
OUT_VDB = os.path.join(ROOT, "assets", "week7", "vdbs", "molecular_atmosphere.vdb")
CLOUD_RAW = os.path.join(ROOT, "data", "processed", "cloud_ext_192x192x32.f32")
OUT_COMBINED = os.path.join(ROOT, "assets", "week7", "vdbs", "cloud_atmosphere_buffered.vdb")

NXY, DXY_M = 12, 3200.0        # 38.4 km footprint
DZ_M = 80.0                    # matches cloud grid vertical resolution
ORIGIN_XY = -16000.0           # matches buffered-scene ocean quad
CLOUD_ORIGIN_XY = -6400.0      # buffered cloud crop origin (world m)
CLOUD_MIN_BETA = 5e-4          # keep in sync with grid_to_vdb.MIN_BETA_DEFAULT


def main():
    with open(PROFILE) as fh:
        prof = json.load(fh)
    layers = prof["layers"]
    z_top = layers[-1]["z1_m"]
    nz = int(round(z_top / DZ_M))

    z_centers = (np.arange(nz) + 0.5) * DZ_M
    beta_sca = np.zeros(nz)
    beta_abs = np.zeros(nz)
    for lay in layers:
        sel = (z_centers >= lay["z0_m"]) & (z_centers < lay["z1_m"])
        beta_sca[sel] = lay["beta_sca"]
        beta_abs[sel] = lay["beta_abs"]

    xform = vdb.createLinearTransform(
        [[DXY_M, 0, 0, 0], [0, DXY_M, 0, 0], [0, 0, DZ_M, 0],
         [ORIGIN_XY, ORIGIN_XY, 0, 1]])
    grids = []
    for name, col in (("scatter", beta_sca), ("absorb", beta_abs)):
        arr = np.broadcast_to(col[None, None, :], (NXY, NXY, nz)).astype(np.float32).copy()
        g = vdb.FloatGrid()
        g.copyFromArray(arr)
        g.name = name
        g.gridClass = vdb.GridClass.FOG_VOLUME
        g.transform = xform
        g["units"] = "per_meter"
        grids.append(g)

    os.makedirs(os.path.dirname(OUT_VDB), exist_ok=True)
    vdb.write(OUT_VDB, grids=grids)
    print(f"wrote {OUT_VDB}")
    print(f"  {NXY}x{NXY}x{nz} voxels {DXY_M:.0f}x{DXY_M:.0f}x{DZ_M:.0f} m, "
          f"origin ({ORIGIN_XY:.0f},{ORIGIN_XY:.0f}), top {z_top/1000:.0f} km")
    print(f"  column tau: scatter {beta_sca.sum()*DZ_M:.4f} "
          f"(profile {prof['tau_rayleigh']:.4f}), "
          f"absorb {beta_abs.sum()*DZ_M:.4f} (profile {prof['tau_gas_gray']:.4f})")

    # --- combined cloud + atmosphere file (single volume object) -----------
    with open(os.path.splitext(CLOUD_RAW)[0] + ".json") as fh:
        cmeta = json.load(fh)
    cnx, cny, cnz = cmeta["nx"], cmeta["ny"], cmeta["nz"]
    beta = np.fromfile(CLOUD_RAW, dtype=np.float32)
    assert beta.size == cnx * cny * cnz
    beta_xyz = beta.reshape(cnz, cny, cnx).transpose(2, 1, 0).astype(np.float64).copy()
    beta_xyz[beta_xyz < CLOUD_MIN_BETA] = 0.0
    cloud = vdb.FloatGrid()
    cloud.copyFromArray(beta_xyz)
    cloud.name = cmeta.get("grid_name", "density")
    cloud.gridClass = vdb.GridClass.FOG_VOLUME
    cloud.transform = vdb.createLinearTransform(
        [[cmeta["dx_m"], 0, 0, 0], [0, cmeta["dy_m"], 0, 0],
         [0, 0, cmeta["dz_m"], 0], [CLOUD_ORIGIN_XY, CLOUD_ORIGIN_XY, 0, 1]])
    cloud["units"] = "extinction_per_meter"
    cloud["min_beta_cut"] = float(CLOUD_MIN_BETA)
    vdb.write(OUT_COMBINED, grids=[cloud] + grids)
    print(f"wrote {OUT_COMBINED} (grids: density + scatter + absorb, "
          f"cloud {cnx}x{cny}x{cnz} @ origin {CLOUD_ORIGIN_XY:.0f}, "
          f"beta_max {beta_xyz.max():.4g}, active {(beta_xyz > 0).sum()})")


if __name__ == "__main__":
    main()
