#!/usr/bin/env bash
set -euo pipefail

mkdir -p renders/week7

# The local OpenUSD rebuild with PXR_ENABLE_OPENVDB_SUPPORT=ON installs
# hioOpenVDB under build/lib/usd, while the Python launcher can otherwise
# discover the older build/inst plugin tree first. Keep these paths explicit
# so HdStorm can register the "vdb" field texture data plugin.
export DYLD_LIBRARY_PATH="/Users/wen/programing/OpenUSD_system/build/lib:${DYLD_LIBRARY_PATH:-}"
export PXR_PLUGINPATH_NAME="/Users/wen/programing/OpenUSD_system/build/lib/usd:/Users/wen/programing/OpenUSD_system/build/plugin/usd:${PXR_PLUGINPATH_NAME:-}"

conda run -n openusd python src/week7_usdvol_cloud.py

/Users/wen/programing/OpenUSD_system/build/bin/usdrecord \
  --disableCameraLight \
  --camera /World/Camera/MainCamera \
  --frames 1:20 \
  --imageWidth 1280 \
  --colorCorrectionMode disabled \
  assets/week7/usdvol_cloud_scene.usda \
  renders/week7/usdvol_cloud_###.png
