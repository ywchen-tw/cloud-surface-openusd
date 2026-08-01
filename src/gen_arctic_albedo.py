"""Generate a procedural Arctic surface-albedo texture for the hero scene.

Multi-octave value noise builds a fractal ice edge, a marginal-ice-zone floe
field, melt ponds, and within-ice brightness variation — so the surface reads
as sea ice instead of flat vector polygons. Albedos follow the research
ranges (project goal #2): open water ~0.06, floes/sheet 0.6-0.85, snow ~0.9,
melt ponds ~0.3.

Output: data/processed/arctic_albedo_texture.png (2048^2, ~9.4 m/px over the
19.2 km tiled domain; v=0 is the south edge). Regenerable, gitignored.

Run:  conda run -n er3t python src/gen_arctic_albedo.py
"""

import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "processed", "arctic_albedo_texture.png")
N = 2048
RNG = np.random.default_rng(7)


def value_noise(n, cells):
    """Bilinear-interpolated random grid, values in [0, 1]."""
    g = RNG.random((cells + 1, cells + 1))
    idx = np.linspace(0, cells, n, endpoint=False)
    i0 = idx.astype(int)
    f = idx - i0
    fy, fx = np.meshgrid(f, f, indexing="ij")
    iy, ix = np.meshgrid(i0, i0, indexing="ij")
    s = lambda t: t * t * (3 - 2 * t)
    wy, wx = s(fy), s(fx)
    return ((g[iy, ix] * (1 - wx) + g[iy, ix + 1] * wx) * (1 - wy)
            + (g[iy + 1, ix] * (1 - wx) + g[iy + 1, ix + 1] * wx) * wy)


def fbm(n, octaves=6, base_cells=4):
    total, amp, norm = np.zeros((n, n)), 1.0, 0.0
    for o in range(octaves):
        total += amp * value_noise(n, base_cells * 2 ** o)
        norm += amp
        amp *= 0.5
    return total / norm


def smooth(x, lo, hi):
    return np.clip((x - lo) / (hi - lo), 0.0, 1.0)


def main():
    y = np.linspace(0, 1, N)[:, None] * np.ones((1, N))  # 0 = south edge (v=0)

    n_edge = fbm(N, octaves=6, base_cells=3)
    n_floe = fbm(N, octaves=7, base_cells=12)
    n_tex = fbm(N, octaves=7, base_cells=24)
    n_pond = fbm(N, octaves=5, base_cells=16)

    # Consolidated sheet north of a fractal ice edge (~y = 0.55 +/- noise).
    ice = smooth(y + 0.22 * (n_edge - 0.5), 0.55, 0.585)

    # Marginal-ice-zone floes: noise blobs, densest just south of the edge.
    mizw = np.exp(-(((y + 0.22 * (n_edge - 0.5)) - 0.47) / 0.13) ** 2)
    floes = smooth(n_floe, 0.62, 0.68) * mizw
    ice_all = np.clip(ice + floes, 0, 1)

    # Albedo assembly.
    albedo = 0.05 + 0.03 * n_tex                                   # water
    albedo += ice_all * (0.60 + 0.25 * n_tex - albedo)             # ice 0.6-0.85
    snow = smooth(n_tex, 0.62, 0.75) * ice * smooth(y, 0.7, 0.85)
    albedo += snow * (0.92 - albedo)                               # snow ~0.9
    ponds = smooth(n_pond, 0.70, 0.76) * ice * smooth(y, 0.6, 0.7)
    albedo += ponds * (0.30 - albedo)                              # ponds ~0.3

    # Tint: water steel-blue, ice slightly cool white, ponds teal.
    r = albedo * (0.35 + 0.65 * ice_all)
    g = albedo * (0.75 + 0.25 * ice_all)
    b = albedo * (1.05 - 0.07 * ice_all)
    b += ponds * 0.10
    rgb = np.clip(np.stack([r, g, b], axis=-1), 0, 1)

    from matplotlib.image import imsave
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    imsave(OUT, rgb, origin="lower")
    frac_ice = float((ice_all > 0.5).mean())
    print(f"wrote {OUT}  ({N}x{N}, ice fraction {frac_ice:.2f}, "
          f"albedo range {albedo.min():.2f}-{albedo.max():.2f})")


if __name__ == "__main__":
    main()
