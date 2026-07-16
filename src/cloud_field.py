#!/usr/bin/env python3
"""Ingest a real SAM/LES cloud field into a USD-ready optical grid.

Input  : data/7SEAS_480x480x150_dx100m_dz40m_dt2sec_480_0000081000_mod.nc
         (480 x 480 x 125 grid, dx=dy=100 m, dz=40 m, single timestep)

Pipeline:
  1. Pick the cloudiest 64 x 64 horizontal tile (max in-tile liquid water path).
  2. Crop vertically to z[0:64] -> a native 64 x 64 x 64 tile (6.4 x 6.4 x 2.56 km).
  3. Map cloud water -> extinction coefficient beta_ext (the physics moat), with
     single-scattering albedo and asymmetry parameter for the phase function.
  4. Regrid to a simple 64 x 64 x 32 grid (vertical dz 40 m -> 80 m), conserving
     optical depth.

Outputs (data/processed/):
  - cloud_field_64x64x64.npz   native-resolution arrays  (for EaR3T benchmark)
  - cloud_field_64x64x32.npz   regridded simple-project arrays
  - cloud_ext_64x64x32.f32     raw float32 extinction grid (-> OpenVDB via C++ tool)
  - cloud_ext_64x64x32.json    sidecar: dims, spacing, optical metadata
  - cloud_field_quicklook.png  LWP map + tile box + cross-sections

Run with the EaR3T conda env (has numpy / netCDF4 / scipy / matplotlib):
  /Users/wen/miniconda3/envs/er3t/bin/python src/cloud_field.py
"""

import json
import os

import numpy as np
from netCDF4 import Dataset

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NC_PATH = os.path.join(
    PROJECT_ROOT, "data", "7SEAS_480x480x150_dx100m_dz40m_dt2sec_480_0000081000_mod.nc"
)
OUT_DIR = os.path.join(PROJECT_ROOT, "data", "processed")

# --- tile selection -------------------------------------------------------
TILE_NX = 64          # horizontal tile (x), native 100 m -> 6.4 km
TILE_NY = 64          # horizontal tile (y)
TILE_NZ = 64          # vertical crop, native 40 m -> 2.56 km (covers cloud layer)
SIMPLE_NZ = 32        # regridded vertical levels (dz 40 m -> 80 m)

# --- physics constants ----------------------------------------------------
R_DRY = 287.0         # J/(kg K)  dry-air gas constant
RHO_WATER = 1000.0    # kg/m3
QC_THRESHOLD = 1.0e-3 # g/kg  cloud mask (drops sub-threshold haze/rain noise)
REFF_MIN_UM = 2.0     # clamp effective radius to physical liquid-cloud range
REFF_MAX_UM = 40.0    # (raw REL maxes at 636 um where rain contaminates it)
SSA_VIS = 0.999999    # single-scattering albedo, liquid water, visible band
ASYMMETRY_G = 0.85    # Henyey-Greenstein asymmetry parameter for cloud droplets


def load_les(path):
    """Return cloud-relevant fields and grid coordinates from the LES NetCDF."""
    def fill(arr, value):
        # netCDF4 returns MaskedArrays; collapse to plain float ndarrays.
        return np.ma.filled(np.ma.masked_invalid(arr).astype(np.float64), value)

    with Dataset(path) as d:
        x = fill(d["x"][:], 0.0)                     # (nx,) m
        y = fill(d["y"][:], 0.0)                     # (ny,) m
        z = fill(d["z"][:], 0.0)                     # (nz,) m
        p = fill(d["p"][:], 0.0)                     # (nz,) mb
        qc = fill(d["QC"][0], 0.0)                   # (z,y,x) g/kg cloud water
        rel = fill(d["REL"][0], 0.0)                 # (z,y,x) um effective radius
        tabs = fill(d["TABS"][0], 250.0)            # (z,y,x) K (safe fill, no div/0)
    return dict(x=x, y=y, z=z, p=p, qc=qc, rel=rel, tabs=tabs)


def air_density(p_mb, tabs):
    """Ideal-gas air density (kg/m3). p is per-level (nz,), tabs is (z,y,x)."""
    return (p_mb[:, None, None] * 100.0) / (R_DRY * tabs)


def extinction_field(qc, rel, rho_air, qc_mask):
    """beta_ext [1/m] = 1.5 * LWC / (rho_water * r_eff) inside cloudy voxels."""
    lwc = qc * 1.0e-3 * rho_air                      # kg/m3
    reff_m = np.clip(rel, REFF_MIN_UM, REFF_MAX_UM) * 1.0e-6
    beta = np.zeros_like(qc, dtype=np.float64)
    beta[qc_mask] = 1.5 * lwc[qc_mask] / (RHO_WATER * reff_m[qc_mask])
    return beta


def pick_cloudiest_tile(lwp, nx, ny):
    """Top-left (iy, ix) of the nx-by-ny window maximizing summed LWP."""
    # integral image -> O(1) window sums
    integ = np.zeros((lwp.shape[0] + 1, lwp.shape[1] + 1), dtype=np.float64)
    integ[1:, 1:] = np.cumsum(np.cumsum(lwp, axis=0), axis=1)

    def window_sum(iy, ix):
        return (
            integ[iy + ny, ix + nx]
            - integ[iy, ix + nx]
            - integ[iy + ny, ix]
            + integ[iy, ix]
        )

    best, best_yx = -1.0, (0, 0)
    for iy in range(0, lwp.shape[0] - ny + 1, 4):       # stride 4 = fast enough
        for ix in range(0, lwp.shape[1] - nx + 1, 4):
            s = window_sum(iy, ix)
            if s > best:
                best, best_yx = s, (iy, ix)
    return best_yx


def regrid_vertical(beta, n_out):
    """Average adjacent z-layers (conserves optical depth) -> (n_out, ny, nx)."""
    nz = beta.shape[0]
    assert nz % n_out == 0, f"{nz} not divisible by {n_out}"
    factor = nz // n_out
    return beta.reshape(n_out, factor, beta.shape[1], beta.shape[2]).mean(axis=1)


def save_npz(path, **arrays):
    np.savez_compressed(path, **arrays)


def write_raw_grid(beta_zyx, dx_m, dz_m, raw_path, json_path):
    """Raw float32 grid (x-fastest) + JSON sidecar for the OpenVDB C++ tool."""
    nz, ny, nx = beta_zyx.shape
    # x-fastest ordering so the C++ reader can index [z][y][x] linearly
    beta_zyx.astype(np.float32).ravel(order="C").tofile(raw_path)
    meta = dict(
        nx=nx, ny=ny, nz=nz,
        dx_m=dx_m, dy_m=dx_m, dz_m=dz_m,
        order="z_outer_y_mid_x_inner",
        grid_name="density",
        units="extinction_per_meter",
        ssa=SSA_VIS, asymmetry_g=ASYMMETRY_G,
        beta_max=float(beta_zyx.max()), beta_mean_cloudy=float(beta_zyx[beta_zyx > 0].mean()),
    )
    with open(json_path, "w") as fh:
        json.dump(meta, fh, indent=2)


def quicklook(lwp, tile_yx, beta_native, x, y, z, out_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    iy, ix = tile_yx
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.4))

    m = ax[0]
    im = m.pcolormesh(x / 1000.0, y / 1000.0, lwp, cmap="bone_r", shading="auto")
    m.add_patch(Rectangle(
        (x[ix] / 1000.0, y[iy] / 1000.0),
        TILE_NX * (x[1] - x[0]) / 1000.0, TILE_NY * (y[1] - y[0]) / 1000.0,
        fill=False, edgecolor="red", lw=2,
    ))
    m.set(title="LES liquid water path (g/m$^2$) + picked tile", xlabel="x [km]", ylabel="y [km]")
    fig.colorbar(im, ax=m, shrink=0.85)

    tau_col = beta_native.sum(axis=0) * (z[1] - z[0])      # column optical depth
    im2 = ax[1].imshow(tau_col, origin="lower", cmap="viridis")
    ax[1].set(title="tile column optical depth $\\tau$", xlabel="x idx", ylabel="y idx")
    fig.colorbar(im2, ax=ax[1], shrink=0.85)

    xz = beta_native.max(axis=1)                            # max over y -> (z, x)
    im3 = ax[2].imshow(
        xz, origin="lower", aspect="auto", cmap="magma",
        extent=[0, TILE_NX * (x[1] - x[0]) / 1000.0, z[0] / 1000.0, z[TILE_NZ - 1] / 1000.0],
    )
    ax[2].set(title="tile x-z extinction (max over y) [1/m]", xlabel="x [km]", ylabel="height [km]")
    fig.colorbar(im3, ax=ax[2], shrink=0.85)

    fig.tight_layout()
    fig.savefig(out_png, dpi=110)
    plt.close(fig)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"Loading LES field: {os.path.relpath(NC_PATH, PROJECT_ROOT)}")
    f = load_les(NC_PATH)
    x, y, z, p = f["x"], f["y"], f["z"], f["p"]
    qc, rel, tabs = f["qc"], f["rel"], f["tabs"]
    dx_m, dz_m = float(x[1] - x[0]), float(z[1] - z[0])

    qc_mask = qc > QC_THRESHOLD
    rho = air_density(p, tabs)
    beta = extinction_field(qc, rel, rho, qc_mask)          # (nz, ny, nx) 1/m

    # full-domain LWP for tile selection (g/m2)
    lwc_full = qc * 1.0e-3 * rho
    lwp = (lwc_full * dz_m).sum(axis=0) * 1000.0
    iy, ix = pick_cloudiest_tile(lwp, TILE_NX, TILE_NY)
    print(f"Picked tile: x[{ix}:{ix+TILE_NX}] y[{iy}:{iy+TILE_NY}] z[0:{TILE_NZ}]  "
          f"(origin {x[ix]/1000:.1f},{y[iy]/1000:.1f} km)")

    # native 64 x 64 x 64 tile
    beta_native = beta[:TILE_NZ, iy:iy + TILE_NY, ix:ix + TILE_NX]
    qc_tile = qc[:TILE_NZ, iy:iy + TILE_NY, ix:ix + TILE_NX]
    rel_tile = np.clip(rel[:TILE_NZ, iy:iy + TILE_NY, ix:ix + TILE_NX], REFF_MIN_UM, REFF_MAX_UM)
    z_tile = z[:TILE_NZ]
    x_tile, y_tile = x[ix:ix + TILE_NX], y[iy:iy + TILE_NY]

    tau_native = beta_native.sum(axis=0) * dz_m
    print(f"Native tile: cloud-voxel frac={ (beta_native>0).mean():.3f}  "
          f"beta_max={beta_native.max():.4f} 1/m  tau_max={tau_native.max():.1f}")

    # regrid to simple 64 x 64 x 32
    beta_simple = regrid_vertical(beta_native, SIMPLE_NZ)
    dz_simple = dz_m * (TILE_NZ // SIMPLE_NZ)
    tau_simple = beta_simple.sum(axis=0) * dz_simple
    print(f"Regridded 64x64x{SIMPLE_NZ}: dz={dz_simple:.0f} m  "
          f"tau_max={tau_simple.max():.1f} (native {tau_native.max():.1f})")

    # --- save -------------------------------------------------------------
    save_npz(
        os.path.join(OUT_DIR, "cloud_field_64x64x64.npz"),
        ext=beta_native.astype(np.float32), qc=qc_tile.astype(np.float32),
        reff_um=rel_tile.astype(np.float32),
        x_m=x_tile, y_m=y_tile, z_m=z_tile, dx_m=dx_m, dz_m=dz_m,
        ssa=SSA_VIS, asymmetry_g=ASYMMETRY_G, tile_origin_ix_iy=np.array([ix, iy]),
    )
    save_npz(
        os.path.join(OUT_DIR, "cloud_field_64x64x32.npz"),
        ext=beta_simple.astype(np.float32),
        x_m=x_tile, y_m=y_tile, dx_m=dx_m, dz_m=dz_simple,
        ssa=SSA_VIS, asymmetry_g=ASYMMETRY_G,
    )
    write_raw_grid(
        beta_simple, dx_m, dz_simple,
        os.path.join(OUT_DIR, "cloud_ext_64x64x32.f32"),
        os.path.join(OUT_DIR, "cloud_ext_64x64x32.json"),
    )
    quicklook(lwp, (iy, ix), beta_native, x, y, z,
              os.path.join(OUT_DIR, "cloud_field_quicklook.png"))

    print("\nWrote to", os.path.relpath(OUT_DIR, PROJECT_ROOT) + "/:")
    for name in ("cloud_field_64x64x64.npz", "cloud_field_64x64x32.npz",
                 "cloud_ext_64x64x32.f32", "cloud_ext_64x64x32.json",
                 "cloud_field_quicklook.png"):
        print("  -", name)


if __name__ == "__main__":
    main()
