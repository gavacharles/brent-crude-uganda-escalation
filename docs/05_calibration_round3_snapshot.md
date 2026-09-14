# Calibration Round 3 Snapshot

## Date
2026-09-14

## Scope
Calibration and model-improvement round focused on making forecasts operationally reliable.

## What was done
- Implemented candidate search across lag structures and model families.
- Benchmarked every candidate against naive persistence on holdout.
- Added uncertainty interval diagnostics and figure outputs.

## Key outcome
- Current data favors naive persistence as champion model.
- Best calibrated blend selected `alpha=0`, i.e., full benchmark weighting.
- Interpretation: no challenger yet beats benchmark consistently in holdout.

## Why this still improves confidence
- Forecasting now uses explicit champion/challenger governance.
- Decision bands are quantified (PI80/PI90), not ad hoc.
- Automated reruns monitor when a challenger truly outperforms.

## Artifacts
- `results/round3/summary.md`
- `results/round3/tables/metrics.json`
- `results/round3/tables/candidate_search.csv`
- `results/round3/tables/test_predictions.csv`
- `results/round3/figures/01_candidate_search_rmse.png`
- `results/round3/figures/02_forecast_with_pi90.png`
- `results/round3/figures/03_implied_index_path.png`
- `results/round3/figures/04_absolute_error_comparison.png`

## Promotion rule for a new champion
Promote challenger only if, over at least 3 consecutive monthly reruns:
1. RMSE skill vs naive is positive,
2. directional accuracy is not materially worse,
3. interval coverage remains acceptable.