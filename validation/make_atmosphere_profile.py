"""Extract the EXACT molecular atmosphere EaR3T/MCARaTS uses at 650 nm so the
Cycles side can carry the same Rayleigh scattering + gas absorption.

Reproduces compare_ear3t.run_ear3t's atmosphere byte-for-byte: same level
grid (cloud layers 0..2.56 km @ 80 m, then 4..20 km @ 2 km), atm_atmmod +
abs_16g, Bodhaine Rayleigh per layer (cal_mol_ext_atm — the same call
er3t.rtm.mca.mca_atm_1d makes), and the 16-g gas absorption collapsed to a
gray per-layer coefficient beta_abs = -ln(sum_i w_i exp(-tau_i)) / dz.
The gray collapse is exact for a single vertical transit and errs by <<1% of
signal at 650 nm where total gas tau is only ~0.02 — Cycles cannot run
correlated-k without 16 weighted renders.

Output: data/processed/atmosphere_profile_650nm.json
  [{"z0_m", "z1_m", "beta_sca", "beta_abs"}, ...]  (bottom-up layers, 1/m)

Run:  conda run -n er3t python validation/make_atmosphere_profile.py
"""

import json
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_JSON = os.path.join(ROOT, "data", "processed", "atmosphere_profile_650nm.json")
TMP = os.path.join(ROOT, "data", "processed", "atm_profile_tmp")

WAVELENGTH = 650.0  # nm — keep in sync with compare_ear3t.py
NZ_CLD, DZ_CLD_M = 32, 80.0


def main():
    from er3t.pre.atm import atm_atmmod
    from er3t.pre.abs import abs_16g
    from er3t.util import cal_mol_ext_atm

    os.makedirs(TMP, exist_ok=True)
    lev_cld = np.arange(NZ_CLD + 1) * DZ_CLD_M / 1000.0
    levels = np.concatenate([lev_cld, np.arange(4.0, 21.0, 2.0)])

    atm0 = atm_atmmod(levels=levels, fname=os.path.join(TMP, "atm.pk"), overwrite=True)
    abs0 = abs_16g(wavelength=WAVELENGTH, atm_obj=atm0,
                   fname=os.path.join(TMP, "abs.pk"), overwrite=True)

    thick_m = atm0.lay["thickness"]["data"] * 1000.0
    # Rayleigh: identical call to er3t.rtm.mca.mca_atm_1d.pre_mca_1d_atm
    beta_sca = cal_mol_ext_atm(WAVELENGTH * 0.001, atm0) / thick_m

    od_abs = np.asarray(abs0.coef["abso_coef"]["data"], dtype=np.float64)  # (nlay, 16)
    w = np.asarray(abs0.coef["weight"]["data"], dtype=np.float64)
    tau_eff = -np.log(np.clip((w[None, :] * np.exp(-od_abs)).sum(axis=1), 1e-300, None))
    beta_abs = tau_eff / thick_m

    z_lev = atm0.lev["altitude"]["data"] * 1000.0  # m
    layers = [dict(z0_m=float(z_lev[i]), z1_m=float(z_lev[i + 1]),
                   beta_sca=float(beta_sca[i]), beta_abs=float(beta_abs[i]))
              for i in range(len(thick_m))]

    tau_sca = float((beta_sca * thick_m).sum())
    tau_abs = float((beta_abs * thick_m).sum())
    with open(OUT_JSON, "w") as fh:
        json.dump(dict(wavelength_nm=WAVELENGTH, tau_rayleigh=tau_sca,
                       tau_gas_gray=tau_abs, layers=layers), fh, indent=2)
    print(f"{len(layers)} layers 0..{z_lev[-1]/1000:.0f} km: "
          f"tau_Rayleigh={tau_sca:.4f}  tau_gas(gray)={tau_abs:.4f}")
    print("wrote", os.path.relpath(OUT_JSON, ROOT))


if __name__ == "__main__":
    main()
