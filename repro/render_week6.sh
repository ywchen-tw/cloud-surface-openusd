#!/usr/bin/env bash
set -euo pipefail

mkdir -p renders/week6

/Users/wen/programing/OpenUSD_system/build/bin/usdrecord \
  --disableCameraLight \
  --camera /World/Camera/MainCamera \
  --frames 1:20 \
  --imageWidth 1280 \
  --colorCorrectionMode disabled \
  assets/week6/renderer_shadow_scene.usda \
  renders/week6/renderer_shadow_###.png
