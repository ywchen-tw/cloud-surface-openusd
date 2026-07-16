#!/usr/bin/env python3
"""Rebuild the seven-week OpenUSD demo assets in order."""

import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = [
    "src/week1_satellite_scene.py",
    "src/week2_timeseries_to_usd.py",
    "src/week3_clouds_vol.py",
    "src/week4_pipeline.py",
    "src/week5_realistic_arctic_cloud_scene.py",
    "src/week6_renderer_shadows.py",
    "src/week7_usdvol_cloud.py",
]


def main():
    for script in SCRIPTS:
        print(f"\n=== Running {script} ===")
        subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, script)], check=True)


if __name__ == "__main__":
    main()
