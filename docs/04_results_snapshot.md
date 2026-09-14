# Results Snapshot (Run 1)

## Date
2026-09-13

## Objective of this run
Execute the end-to-end pipeline and produce first-pass Brent-to-construction escalation estimates with visual outputs.

## Pipeline execution status
- Upstream repositories cloned and available locally.
- `cio_pipeline-2` full run executed successfully.
- Tests passed (`10 passed`).
- Brent model script executed successfully.

## Data used
- Uganda construction index panel (`panel_v1.0.csv`) from `cio_pipeline-2`.
- Domestic macro controls from the same panel.
- Brent crude series from FRED (`DCOILBRENTEU`), aggregated from daily to monthly means.

## Model used in run 1
- ARDL-style linear model on monthly inflation of `CIPI_ALL`.
- Brent lags: 0–6 months.
- FX and CPI lags: 0–3 months.
- Additional controls: private credit growth, lending-rate change, CBR change, autoregressive term (`y_l1`), and month seasonality dummies.
- Robust covariance: HAC/Newey-West (`maxlags=3`).

## Key metrics (test window)
- MAE (model): 0.7868
- RMSE (model): 1.0128
- MAE (naive): 0.1738
- RMSE (naive): 0.2261

## Interpretation
- First-pass model is operational and reproducible.
- Predictive quality is currently weaker than naive baseline in this split.
- The model still provides useful structural diagnostics and scenario scaffolding; forecast calibration is the immediate next optimization step.

## Visual outputs
1. `results/figures/01_cipi_vs_brent_normalized.png`
2. `results/figures/02_brent_lag_correlation.png`
3. `results/figures/03_brent_lag_coefficients.png`
4. `results/figures/04_test_forecast_index_path.png`
5. `results/figures/05_scenario_brent_shock_impacts.png`

## Tabular outputs
1. `results/tables/metrics.json`
2. `results/tables/ardl_coefficients.csv`
3. `results/tables/forecast_test_window.csv`
4. `results/tables/scenario_shock_impacts.csv`

## Recommended next actions
1. Run rolling-window model selection for lag-length stability.
2. Add Elastic Net benchmark with standardized lag features.
3. Build project-basket-specific targets (BoQ weights) and evaluate p50/p80 escalation error.
4. Generate a second results run and compare against this baseline.
