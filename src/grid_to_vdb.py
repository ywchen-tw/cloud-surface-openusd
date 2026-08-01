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


def main(raw_path: str, out_path: str) -> None:
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

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    vdb.write(out_path, grids=[grid])

    active = int((beta_xyz > 0).sum())
    print(f"wrote {out_path}")
    print(f"  grid '{grid.name}' fogVolume {nx}x{ny}x{nz}, voxel {dx}x{dy}x{dz} m")
    print(f"  beta_max {beta_xyz.max():.4g} 1/m, active voxels {active}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
