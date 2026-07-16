#!/usr/bin/env bash
set -euo pipefail

mkdir -p renders/week5

/Users/wen/programing/OpenUSD_system/build/bin/usdrecord \
  --camera /World/Camera/MainCamera \
  --frames 1:20 \
  --imageWidth 1280 \
  --colorCorrectionMode disabled \
  assets/week5/realistic_arctic_cloud_scene.usda \
  renders/week5/cloud_realistic_###.png
