# Week 4 Optimization Notes

Current optimization choices:

- The final Week 4 scenes reference Week 2 and Week 3 assets instead of flattening them.
- Heavy future VDB outputs should stay as external files under `assets/week3/vdbs/`.
- VariantSets are used to switch motion and sun cases without duplicating whole scene files.
- The current cloud volume is a small structured `UsdGeom.Points` placeholder. If the cloud is expanded to many repeated clusters, move repeated particles or cloudlets to `UsdGeom.PointInstancer` prototypes.

Future upgrade path:

- Replace structured points with `UsdVol.OpenVDBAsset` references.
- Stream per-frame VDBs for advected cloud fields.
- Use `PointInstancer` for repeated cloud clusters or surface tiles when the scene becomes large.
