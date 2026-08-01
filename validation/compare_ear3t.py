"""Phase 8 validation — USD/Cycles nadir radiance vs EaR3T 3D-RT (the moat).

Both sides see the IDENTICAL cloud: `data/processed/cloud_field_64x64x32.npz`
with the same thin-fringe cutoff used by src/grid_to_vdb.py (MIN_BETA), the
same HG g=0.85 phase, ssa~1, Lambertian surface albedo, and the same
sun/sensor geometry (SZA/SAA below; nadir orthographic sensor, 128x128 over
the 6.4 km tile).

Pipeline:
  1. USD side (GPU node) — scene-linear nadir render:
       sbatch repro/curc/render_week7_cycles.sbatch \
           assets/phase8/les_cloud_scene.usda 1 1 4096 NadirCamera 128 128 \
           "--exr --world-strength 0 --flat-albedo 0.05"
     -> $OPENUSD_CLD_DATAROOT/renders/les_cloud_scene_cycles_NadirCamera/frame_0001.npy
  2. EaR3T side + comparison (er3t env, CPU):
       conda run -n er3t python validation/compare_ear3t.py --run-ear3t \
           --usd-npy $OPENUSD_CLD_DATAROOT/renders/les_cloud_scene_cycles_NadirCamera/frame_0001.npy
     Or with an existing EaR3T output:  --ear3t-h5 path/to/out.h5

Cycles radiance is in relative (unnormalized) units, so the comparison fits a
single global scale factor between the two fields, then reports relative RMSE
(% of mean EaR3T radiance) and Pearson r, and writes the side-by-side figure.
That is the honest formulation: it validates the spatial structure of 3D light
transport, not absolute radiometric calibration (see postmortem).

NOTE: the EaR3T section is scaffolded from /projects/yuch8913/les/
sim-rad-7SEAS_alpine_650.py; VERIFY-marked lines need a check against the
installed er3t version's API before the first run.
"""

import argparse
import json
import os

import numpy as np

# Keep in sync with the USD side.
MIN_BETA = 5e-4          # 1/m — same fringe cutoff as src/grid_to_vdb.py
SZA = 30.0               # deg — same as src/author_cloud_usd.py SUN_SZA_DEG
SAA = 40.0               # deg — VERIFY azimuth convention vs USD (az from +x CCW)
WAVELENGTH = 650.0       # nm
SURFACE_ALBEDO = 0.05    # Lambertian; USD render must use --flat-albedo 0.05
PHOTONS = 1e8
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NPZ = os.path.join(ROOT, "data", "processed", "cloud_field_64x64x32.npz")


def load_field():
    z = np.load(NPZ)
    ext = np.array(z["ext"], dtype=np.float64)          # (nz, ny, nx), 1/m
    ext[ext < MIN_BETA] = 0.0
    dx_m = float(z["dx_m"])                             # 100 m
    dz_m = float(z["dz_m"]) if "dz_m" in z.files else 80.0
    g = float(z["asymmetry_g"]) if "asymmetry_g" in z.files else 0.85
    ssa = float(z["ssa"]) if "ssa" in z.files else 0.999999
    return ext, dx_m, dz_m, g, ssa


def run_ear3t(out_h5, ncpu=8, photons=PHOTONS, overwrite=False):
    """Run EaR3T/MCARaTS 3D radiance on the npz field.

    Scaffolded from sim-rad-7SEAS_alpine_650.py (run_rad_sim_3d). Uses HG
    phase via per-voxel asymmetry in the 3D atmosphere (no Mie/sca object) so
    the phase function matches Cycles' Henyey-Greenstein exactly.
    """
    import er3t
    from er3t.pre.atm import atm_atmmod
    from er3t.pre.abs import abs_16g
    from er3t.rtm.mca import mca_atm_1d, mca_atm_3d

    ext, dx_m, dz_m, g, ssa = load_field()
    nz, ny, nx = ext.shape
    fdir = os.path.dirname(out_h5) or "."
    os.makedirs(fdir, exist_ok=True)

    # --- atmosphere levels: cloud grid at dz, coarser above -------------------
    # VERIFY: altitude units are km throughout er3t pre/rtm objects.
    lev_cld = np.arange(nz + 1) * dz_m / 1000.0                     # 0..2.56 km
    levels = np.concatenate([lev_cld, np.arange(4.0, 21.0, 2.0)])
    atm0 = atm_atmmod(levels=levels, fname=f"{fdir}/atm.pk", overwrite=overwrite)
    abs0 = abs_16g(wavelength=WAVELENGTH, atm_obj=atm0,
                   fname=f"{fdir}/abs.pk", overwrite=overwrite)

    # --- cloud object from the npz array -------------------------------------
    # er3t's cld classes ingest LES NetCDF; here we adapt the array directly.
    # VERIFY field names/units against er3t.pre.cld.cld_les of the installed
    # version (their custom variant: /projects/yuch8913/les/util/les_cld_7SEAS.py).
    class cld_from_field:
        lay = {}
        lev = {}

    cld0 = cld_from_field()
    alt_lay = (np.arange(nz) + 0.5) * dz_m / 1000.0
    cld0.lay = {
        "nx": {"data": nx}, "ny": {"data": ny}, "nz": {"data": nz},
        "dx": {"data": dx_m / 1000.0}, "dy": {"data": dx_m / 1000.0},
        "dz": {"data": dz_m / 1000.0},
        "x": {"data": (np.arange(nx) + 0.5) * dx_m / 1000.0},
        "y": {"data": (np.arange(ny) + 0.5) * dx_m / 1000.0},
        "altitude": {"data": alt_lay},
        "thickness": {"data": np.full(nz, dz_m / 1000.0)},
        # VERIFY: extinction units expected by mca_atm_3d (1/m in er3t cld_les)
        "extinction": {"data": np.transpose(ext, (2, 1, 0))},  # -> (nx, ny, nz)
        "temperature": {"data": np.full((nx, ny, nz), 290.0)},
    }
    cld0.lev = {"altitude": {"data": lev_cld}}

    # --- MCARaTS run ----------------------------------------------------------
    atm1d0 = mca_atm_1d(atm_obj=atm0, abs_obj=abs0)
    # VERIFY: omitting pha/sca -> HG phase with per-voxel g; how to pass g=0.85
    # (some er3t versions read it from cld0.lay['asy'], others take a kwarg).
    atm3d0 = mca_atm_3d(cld_obj=cld0, atm_obj=atm0,
                        fname=f"{fdir}/mca_atm_3d.bin", overwrite=True)

    mca0 = er3t.rtm.mca.mcarats_ng(
        atm_1ds=[atm1d0], atm_3ds=[atm3d0],
        Ng=abs0.Ng,
        target="radiance",
        surface_albedo=SURFACE_ALBEDO,
        solar_zenith_angle=SZA,
        solar_azimuth_angle=SAA,
        sensor_zenith_angle=0.0,
        sensor_azimuth_angle=0.0,
        sensor_altitude=705000.0,
        fdir=f"{fdir}/rad_3d",
        Nrun=3,
        photons=photons,
        weights=abs0.coef["weight"]["data"],
        solver="3d",
        Ncpu=ncpu,
        mp_mode="py",
        overwrite=True,
    )
    er3t.rtm.mca.mca_out_ng(fname=out_h5, mca_obj=mca0, abs_obj=abs0,
                            mode="mean", squeeze=True, overwrite=True)
    return out_h5


def load_ear3t(h5_path):
    import h5py
    with h5py.File(h5_path, "r") as f:
        rad = f["mean/rad"][...]
        std = f["mean/rad_std"][...] if "mean/rad_std" in f else None
    # mean/rad is (nx, ny); transpose to image convention rows=y, cols=x
    # (verified against the tile tau map: un-transposed panels showed the
    # cluster pattern mirrored across the diagonal).
    return np.asarray(rad, dtype=np.float64).T, std


def compare(usd, rt, out_prefix):
    """Fit one global scale, then RMSE/Pearson + side-by-side figure."""
    assert usd.shape == rt.shape, f"grid mismatch {usd.shape} vs {rt.shape}"
    mask = np.isfinite(usd) & np.isfinite(rt)
    scale = float((usd[mask] * rt[mask]).sum() / (usd[mask] ** 2).sum())
    usd_s = usd * scale
    diff = usd_s - rt
    rmse = float(np.sqrt(np.mean(diff[mask] ** 2)))
    rel_rmse = 100.0 * rmse / float(rt[mask].mean())
    r = float(np.corrcoef(usd_s[mask].ravel(), rt[mask].ravel())[0, 1])
    metrics = {"scale": scale, "rmse": rmse, "rel_rmse_pct": rel_rmse,
               "pearson_r": r, "n_pixels": int(mask.sum()),
               "sza": SZA, "saa": SAA, "wavelength_nm": WAVELENGTH,
               "surface_albedo": SURFACE_ALBEDO, "min_beta": MIN_BETA}

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    vmax = float(np.nanpercentile(rt, 99.5))
    fig, axes = plt.subplots(1, 4, figsize=(19, 4.6))
    for ax, img, title in [
        (axes[0], usd_s, "OpenUSD + Cycles (scaled)"),
        (axes[1], rt, "EaR3T 3D-RT (MCARaTS)"),
        (axes[2], diff, "difference"),
    ]:
        im = ax.imshow(img, origin="lower",
                       cmap="RdBu_r" if title == "difference" else "viridis",
                       vmin=-0.3 * vmax if title == "difference" else 0,
                       vmax=0.3 * vmax if title == "difference" else vmax)
        ax.set_title(title)
        plt.colorbar(im, ax=ax, shrink=0.85)
    axes[3].plot([0, vmax], [0, vmax], "k--", lw=1)
    axes[3].plot(rt[mask].ravel(), usd_s[mask].ravel(), ".", ms=1, alpha=0.25)
    axes[3].set_xlabel("EaR3T radiance")
    axes[3].set_ylabel("USD render (scaled)")
    axes[3].set_title(f"r = {r:.4f}, rel. RMSE = {rel_rmse:.1f}%")
    fig.suptitle(
        f"USD volume render vs EaR3T 3D-RT — identical LES cloud field "
        f"({WAVELENGTH:.0f} nm, SZA {SZA:.0f}°, albedo {SURFACE_ALBEDO})")
    fig.tight_layout()
    fig.savefig(out_prefix + "_figure.png", dpi=180)
    with open(out_prefix + "_metrics.json", "w") as fh:
        json.dump(metrics, fh, indent=2)
    print(json.dumps(metrics, indent=2))
    print("wrote", out_prefix + "_figure.png")
    return metrics


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--usd-npy", required=True,
                   help=".npy radiance from the --exr NadirCamera render")
    p.add_argument("--ear3t-h5", default=None, help="existing EaR3T output h5")
    p.add_argument("--run-ear3t", action="store_true",
                   help="run EaR3T/MCARaTS now (er3t env, CPU-heavy)")
    p.add_argument("--ncpu", type=int, default=8)
    p.add_argument("--photons", type=float, default=PHOTONS,
                   help="MCARaTS photon count (default 1e8; 1e9 for the polished run)")
    p.add_argument("--out-prefix", default=os.path.join(
        os.environ.get("OPENUSD_CLD_DATAROOT", ROOT), "renders", "validation", "usd_vs_ear3t"))
    args = p.parse_args()

    os.makedirs(os.path.dirname(args.out_prefix), exist_ok=True)
    h5 = args.ear3t_h5
    if args.run_ear3t or h5 is None:
        h5 = run_ear3t(os.path.join(os.path.dirname(args.out_prefix), "ear3t_rad_3d.h5"),
                       ncpu=args.ncpu, photons=args.photons)

    usd = np.load(args.usd_npy).astype(np.float64)
    rt, _ = load_ear3t(h5)
    # USD npy is row 0 = top (image convention); EaR3T rad is (nx, ny) with
    # origin lower-left. VERIFY orientation by eye on the first figure and
    # adjust the flip/transpose here if the panels are mirrored.
    usd = usd[::-1]
    # MCARaTS radiance is on the native cloud grid (one pixel per column);
    # block-average the render down to it (sensor pixel = LES column).
    if usd.shape != rt.shape and usd.shape[0] % rt.shape[0] == 0 \
            and usd.shape[1] % rt.shape[1] == 0:
        fy, fx = usd.shape[0] // rt.shape[0], usd.shape[1] // rt.shape[1]
        usd = usd.reshape(rt.shape[0], fy, rt.shape[1], fx).mean(axis=(1, 3))
    if usd.shape != rt.shape and usd.T.shape == rt.shape:
        usd = usd.T
    compare(usd, rt, args.out_prefix)


if __name__ == "__main__":
    main()
