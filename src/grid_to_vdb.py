"""Convert the Phase 8 LES extinction grid (.f32 + .json sidecar from
src/cloud_field.py) into an OpenVDB `density` fog volume with the anisotropic
voxel transform (dx=dy=100 m, dz=80 m after regridding).

This is the CURC/pure-Python replacement for extending the C++
tools/generate_week7_vdb.cpp: the conda-forge `openusd` env ships OpenVDB
Python bindings, so no compiler or Homebrew is needed.

Usage (CURC):
  conda run -n openusd python src/grid_to_vdb.py \
      data/processed/cloud_ext_64x64x32.f32 \
      assets/week7/vdbs/cloud_density.vdb
"""

import json
import os
import sys

import numpy as np

try:
    import openvdb as vdb  # OpenVDB >= 11 nanobind module (conda-forge)
except ImportError:  # pragma: no cover - older boost-python bindings
    import pyopenvdb as vdb


# Optically-thin fringe cutoff (1/m). The LES tile has broad ultra-thin
# cloud-base haze (beta < 5e-4 over ~7% of columns) that renders as blocky
# translucent veils over the ocean; cutting it costs at most tau 0.17 in the
# worst column (cloud tau_max 52.6). compare_ear3t.py MUST apply the same
# cutoff to the EaR3T field so both sides see the identical cloud.
MIN_BETA_DEFAULT = 5e-4


def main(raw_path: str, out_path: str, min_beta: float = MIN_BETA_DEFAULT) -> None:
    json_path = os.path.splitext(raw_path)[0] + ".json"
    with open(json_path) as fh:
        meta = json.load(fh)

    nx, ny, nz = meta["nx"], meta["ny"], meta["nz"]
    assert meta["order"] == "z_outer_y_mid_x_inner", meta["order"]
    beta = np.fromfile(raw_path, dtype=np.float32)
    assert beta.size == nx * ny * nz, f"{beta.size} != {nx}*{ny}*{nz}"
    # cloud_field.py wrote [z][y][x] x-fastest; OpenVDB copyFromArray uses
    # index order (i, j, k) = (x, y, z), so transpose to x-outer.
    beta_xyz = beta.reshape(nz, ny, nx).transpose(2, 1, 0).copy()
    if min_beta > 0:
        cut = beta_xyz < min_beta
        tau_lost = (beta_xyz * cut).sum(axis=2).max() * meta["dz_m"]
        beta_xyz[cut & (beta_xyz > 0)] = 0.0
        print(f"cut beta < {min_beta:g} 1/m: worst-column tau lost {tau_lost:.3f}")

    grid = vdb.FloatGrid()
    grid.copyFromArray(beta_xyz)
    grid.name = meta.get("grid_name", "density")
    grid.gridClass = vdb.GridClass.FOG_VOLUME
    # Anisotropic voxels: index -> world in meters.
    dx, dy, dz = meta["dx_m"], meta["dy_m"], meta["dz_m"]
    grid.transform = vdb.createLinearTransform(
        [[dx, 0, 0, 0], [0, dy, 0, 0], [0, 0, dz, 0], [0, 0, 0, 1]]
    )
    grid["units"] = meta.get("units", "extinction_per_meter")
    grid["ssa"] = float(meta.get("ssa", 1.0))
    grid["asymmetry_g"] = float(meta.get("asymmetry_g", 0.85))
    grid["min_beta_cut"] = float(min_beta)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    vdb.write(out_path, grids=[grid])

    active = int((beta_xyz > 0).sum())
    print(f"wrote {out_path}")
    print(f"  grid '{grid.name}' fogVolume {nx}x{ny}x{nz}, voxel {dx}x{dy}x{dz} m")
    print(f"  beta_max {beta_xyz.max():.4g} 1/m, active voxels {active}")


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__ + "\nOptional 3rd arg: min_beta cutoff in 1/m "
                 f"(default {MIN_BETA_DEFAULT:g}; 0 keeps the full field)")
    main(sys.argv[1], sys.argv[2],
         float(sys.argv[3]) if len(sys.argv) == 4 else MIN_BETA_DEFAULT)
