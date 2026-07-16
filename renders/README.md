# Week 4 Render Outputs

Expected final outputs:

- `sun_slant.png`
- `sun_zenith.png`
- `final.mp4`
- `validation_report.md`

Local scripts generate the USD scenes and validation report. Render the still-image targets from `assets/week4/final_scene.usda` and the video target from `assets/week4/cloud_motion_scene.usda` in a CURC Core Desktop session with `usdview` or your RTX renderer.

Use `/World/Scene.sun_case = sun_slant` for the slant-angle still and `/World/Scene.sun_case = sun_zenith` for the overhead sun still.

Use frames `1-20` in `assets/week4/cloud_motion_scene.usda` for the cloud-motion video.
