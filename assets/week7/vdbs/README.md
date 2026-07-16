# Week 7 VDB Requirement

The USD scene `assets/week7/usdvol_cloud_scene.usda` expects:

- file: `assets/week7/vdbs/cloud_density.vdb`
- grid name: `density`
- grid class: `fogVolume`
- data type: float

The local `openusd` environment has `pxr.UsdVol`, but it does not have `openvdb` or `pyopenvdb` Python bindings.

Local generation with the Homebrew OpenVDB install:

```bash
repro/generate_week7_vdb.sh
```

This compiles `tools/generate_week7_vdb.cpp`, writes a synthetic fog-volume grid named `density`, and verifies it with `vdb_print`.

The OpenUSD build used for rendering must include `hioOpenVDB`; otherwise Storm reports `Unknown field data type 'vdb'`.
Rebuild OpenUSD with `PXR_ENABLE_OPENVDB_SUPPORT=ON` so `.vdb` field textures can be loaded.
