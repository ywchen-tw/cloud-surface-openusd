#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENVDB_PREFIX="${OPENVDB_PREFIX:-$(brew --prefix openvdb)}"
TBB_PREFIX="${TBB_PREFIX:-$(brew --prefix tbb)}"
BLOSC_PREFIX="${BLOSC_PREFIX:-$(brew --prefix c-blosc)}"
BOOST_PREFIX="${BOOST_PREFIX:-$(brew --prefix boost)}"

BUILD_DIR="$ROOT_DIR/build/week7_vdb"
OUT_VDB="$ROOT_DIR/assets/week7/vdbs/cloud_density.vdb"
mkdir -p "$BUILD_DIR" "$(dirname "$OUT_VDB")"

clang++ -std=c++17 \
  "$ROOT_DIR/tools/generate_week7_vdb.cpp" \
  -I"$OPENVDB_PREFIX/include" \
  -I"$TBB_PREFIX/include" \
  -I"$BLOSC_PREFIX/include" \
  -I"$BOOST_PREFIX/include" \
  -L"$OPENVDB_PREFIX/lib" \
  -L"$TBB_PREFIX/lib" \
  -L"$BLOSC_PREFIX/lib" \
  -L"$BOOST_PREFIX/lib" \
  -lopenvdb \
  -ltbb \
  -lblosc \
  -lboost_iostreams \
  -o "$BUILD_DIR/generate_week7_vdb"

"$BUILD_DIR/generate_week7_vdb" "$OUT_VDB" 0.20
"$OPENVDB_PREFIX/bin/vdb_print" -l "$OUT_VDB"
