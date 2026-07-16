# 🛰️ Atmospheric Digital Twin: Project Standards

## 🛠️ Environment
- [cite_start]**HPC:** CURC Alpine (A100/RTX 8000 nodes).
- [cite_start]**Stack:** Python 3.10+, `usd-core` (`pxr` library).

## 🎯 Primary Research Goals
1. **Bias Visualization:** Map OCO-2 CO2 retrieval biases using 3D simulations.
2. **Arctic Albedo:** Model cloud-induced warming on sea ice (0.5 to 0.9 range).
3. **Pollutant Transport:** Animate autoregressive CNN/LSTM ozone transport.

## ⚖️ OpenUSD Standards
- **Composition:** Follow **LIVERPS** strength order.
- **Data:** Use `timeSamples` for all spatiotemporal atmospheric data.
- **Efficiency:** Use **Instancing** for large-scale cloud particle systems.

## 🚀 Execution Commands
- **Check:** `usdchecker filename.usda`.
- [cite_start]**Render:** Launch `usdview` via CURC Core Desktop session.
