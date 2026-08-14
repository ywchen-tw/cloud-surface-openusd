"""Draw the end-to-end project workflow scheme -> docs/workflow_scheme.png.

The figure documents the Phase 8 hero pipeline: real SAM-LES field -> physical
extinction -> OpenVDB fog volume -> OpenUSD scene -> Cycles CPU render on CURC
-> verified video, plus the EaR3T validation branch.

Run:  conda run -n er3t python src/make_workflow_diagram.py
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PNG = os.path.join(ROOT, "docs", "workflow_scheme.png")

# Palette by stage kind.
C_DATA = "#dbeafe"      # source / intermediate data artifacts
C_SCRIPT = "#ffedd5"    # repo Python scripts
C_HPC = "#dcfce7"       # CURC/Slurm compute stages
C_OUT = "#fef9c3"       # deliverables
C_VALID = "#ede9fe"     # EaR3T validation branch
EDGE = "#334155"

BOX_W, BOX_H = 2.55, 1.18


def box(ax, x, y, title, sub, color):
    ax.add_patch(FancyBboxPatch(
        (x - BOX_W / 2, y - BOX_H / 2), BOX_W, BOX_H,
        boxstyle="round,pad=0.06,rounding_size=0.12",
        facecolor=color, edgecolor=EDGE, linewidth=1.1, zorder=2))
    ax.text(x, y + 0.24, title, ha="center", va="center",
            fontsize=9.3, fontweight="bold", color="#0f172a", zorder=3)
    ax.text(x, y - 0.22, sub, ha="center", va="center",
            fontsize=7.6, color="#334155", zorder=3, linespacing=1.35)


def arrow(ax, p, q, label=None, style="-|>", color=EDGE, rad=0.0):
    ax.add_patch(FancyArrowPatch(
        p, q, arrowstyle=style, mutation_scale=14, linewidth=1.3,
        color=color, connectionstyle=f"arc3,rad={rad}", zorder=1))
    if label:
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        ax.text(mx, my + 0.14, label, ha="center", va="bottom",
                fontsize=7.3, style="italic", color="#475569", zorder=3)


def main():
    fig, ax = plt.subplots(figsize=(16.6, 7.6))
    ax.set_xlim(0, 16.6)
    ax.set_ylim(0, 7.6)
    ax.axis("off")

    ax.text(8.3, 7.25, "Atmospheric Digital Twin — LES-to-OpenUSD Workflow",
            ha="center", va="center", fontsize=13, fontweight="bold",
            color="#0f172a")

    xs = [1.7, 5.0, 8.3, 11.6, 14.9]
    y1, y2, yv = 5.9, 1.35, 3.62  # row 1 (data), row 2 (scene/render), validation

    # Row 1: LES field -> VDB (left to right).
    box(ax, xs[0], y1, "LES field",
        "48 km cyclic domain, NetCDF\nLWC + effective radius", C_DATA)
    box(ax, xs[1], y1, "src/cloud_field.py",
        "extinction $\\beta$ from LWC/$r_e$\nregrid to 32 levels  (er3t env)", C_SCRIPT)
    box(ax, xs[2], y1, "Raw extinction grid",
        ".f32 + .json sidecar\n480$\\times$480$\\times$32 @ 100/80 m", C_DATA)
    box(ax, xs[3], y1, "src/grid_to_vdb.py",
        "--origin, periodic --roll\n(vdbtools env, OpenVDB 11)", C_SCRIPT)
    box(ax, xs[4], y1, "OpenVDB fog volume",
        "density grid, meters-true\nworld placement baked in", C_DATA)

    # Row 2: USD scene -> video (right to left, serpentine).
    box(ax, xs[4], y2, "src/author_arctic_hero.py",
        "UsdVol + Arctic albedo surface\n+ sun + camera timeSamples", C_SCRIPT)
    box(ax, xs[3], y2, "OpenUSD stage (.usda)",
        "les_cloud_arctic_scene\nusdchecker clean", C_DATA)
    box(ax, xs[2], y2, "Blender 4.5 Cycles, CPU",
        "Slurm chunks on Blanca/Alpine\n2048 spp, 1920$\\times$1080", C_HPC)
    box(ax, xs[1], y2, "Frame verification",
        "stripe power, zero-pixel,\ncontiguity checks", C_HPC)
    box(ax, xs[0], y2, "Video deliverable",
        "ffmpeg preview.mp4 +\nhigh-bitrate website master", C_OUT)

    # Validation branch off the shared extinction grid.
    box(ax, 12.3, yv, "EaR3T 3D-RT benchmark",
        "same $\\beta$ field + molecular atm.;\nUSD vs EaR3T radiance agreement", C_VALID)

    # Molecular atmosphere: identical on both sides of the benchmark.
    box(ax, 3.2, yv, "Molecular atmosphere",
        "Rayleigh scattering + trace-gas\nabsorption (EaR3T profile, 0–20 km)", C_DATA)

    hw = BOX_W / 2 + 0.09
    for a, b in zip(xs[:-1], xs[1:]):  # row 1, left -> right
        arrow(ax, (a + hw, y1), (b - hw, y1))
    for a, b in zip(xs[:0:-1], xs[-2::-1]):  # row 2, right -> left
        arrow(ax, (a - hw, y2), (b + hw, y2))
    # Serpentine drop: VDB feeds the USD authoring script. Label sits to the
    # LEFT of the vertical arrow so it never overlaps the shaft.
    arrow(ax, (xs[4], y1 - BOX_H / 2 - 0.08), (xs[4], y2 + BOX_H / 2 + 0.08))
    ax.text(xs[4] - 0.22, 2.35, "referenced by\nUsdVol.OpenVDBAsset",
            ha="right", va="center", fontsize=7.3, style="italic",
            color="#475569", linespacing=1.35, zorder=3)
    # Validation branch: extinction grid in, rendered frames compared.
    arrow(ax, (xs[2] + 0.6, y1 - BOX_H / 2 - 0.08), (11.5, yv + BOX_H / 2 + 0.08),
          rad=-0.15, color="#7c3aed")
    arrow(ax, (xs[2] + 0.35, y2 + BOX_H / 2 + 0.08), (11.5, yv - BOX_H / 2 - 0.08),
          rad=0.15, color="#7c3aed")
    # Atmosphere feeds the render (combined cloud+atm volume) — and the same
    # profile is what EaR3T carries, hence "identical on both sides".
    arrow(ax, (3.2, yv - BOX_H / 2 - 0.08), (8.0, y2 + BOX_H / 2 + 0.12),
          rad=-0.08)

    # Legend.
    legend = [(C_DATA, "data artifact"), (C_SCRIPT, "repo script"),
              (C_HPC, "CURC / Slurm"), (C_OUT, "deliverable"),
              (C_VALID, "validation")]
    lx = 1.0
    for color, label in legend:
        ax.add_patch(FancyBboxPatch((lx, 0.18), 0.34, 0.22,
                                    boxstyle="round,pad=0.02",
                                    facecolor=color, edgecolor=EDGE,
                                    linewidth=0.8))
        ax.text(lx + 0.45, 0.29, label, ha="left", va="center",
                fontsize=7.8, color="#334155")
        lx += 0.45 + 0.14 * len(label) + 0.5

    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
    fig.savefig(OUT_PNG, dpi=220, bbox_inches="tight", facecolor="white")
    print(f"wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
