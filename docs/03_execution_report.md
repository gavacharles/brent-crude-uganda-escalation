# Comprehensive Execution Report (Living Document)

## Document control
- Project: Brent Crude → Construction Escalation (Uganda)
- Owner: Project workspace
- Created: 2026-09-13
- Last updated: 2026-09-13
- Status: Phase A (scoping and model design complete)

---

## 1. Executive summary
This project establishes a reproducible analytical workflow to quantify how Brent crude shocks pass through to construction price escalation in Uganda. The execution strategy builds on two existing repositories:
1) `cio_pipeline-2` for construction price panel assembly and macro integration
2) `mofped-macrodata-api-downloader` for bulk macro extraction from MoFPED portal APIs

A complete model specification has been drafted and committed in this workspace. The implementation phases, validation rules, and reporting standards are defined below.

---

## 2. What this project is about

### 2.1 Practical problem
Project budgets in construction are exposed to commodity and macro shocks. Brent crude is a plausible upstream driver through fuel, freight, FX, inflation, and financing channels.

### 2.2 Project objective
Produce a decision-grade forecasting and scenario framework that outputs:
- expected escalation
- uncertainty bands
- shock sensitivity
for Uganda construction projects.

### 2.3 Decision users
- quantity surveyors and cost engineers
- project finance/planning teams
- public procurement and infrastructure planners

---

## 3. Repository feasibility assessment

### 3.1 `cio_pipeline-2` capability summary
Confirmed capabilities include:
- UBOS CIPI ingestion and robust parsing across layout/rebasing changes
- MoFPED macro ingestion via `ugatsdb` and fallback options
- monthly harmonized output `panel_v1.0` with audit trail
- diagnostics for missingness, structural breaks, and stationarity
- workbench-style forecasting scaffolding

### 3.2 `mofped-macrodata-api-downloader` capability summary
Confirmed capabilities include:
- catalog and series discovery
- bulk dataset CSV download
- output folder structure that can feed fallback macro builders

### 3.3 Feasibility conclusion
The repositories are sufficient to build the Uganda-side data spine. Additional external Brent data ingestion is still required to complete the transmission model.

---

## 4. Methodology blueprint

### 4.1 Targets
- Material inflation (`Δlog(CIPI_i)`)
- Project basket escalation (`Esc_{t→t+h}`)

### 4.2 Drivers
- Brent (global)
- FX, CBR, lending, CPI, private credit, activity proxy (domestic transmission)
- optional fiscal and policy controls

### 4.3 Model stack
1. ARDL / distributed-lag baseline
2. ECM if cointegration conditions are met
3. VAR/SVAR robustness
4. ML benchmarks for predictive performance

### 4.4 Validation
- rolling-origin out-of-sample evaluation
- naive model benchmarks
- accuracy + interval calibration metrics

---

## 5. Execution phases

### Phase A — Scoping and design (completed)
- Confirm repository accessibility and fit
- Draft project brief
- Draft full model specification
- Start living execution report

### Phase B — Data assembly (pending)
- Pull/refresh UBOS and MoFPED components
- Ingest Brent monthly series
- Construct unified modeling table
- Run data quality checks

### Phase C — Estimation and diagnostics (pending)
- Run ARDL/ECM models
- Evaluate lag profiles and cumulative pass-through
- Run break/regime robustness

### Phase D — Forecasting and scenarios (pending)
- Run rolling backtests
- Compare econometric vs ML baselines
- Generate p50/p80/p90 escalation scenarios

### Phase E — Final reporting (pending)
- Consolidate methods, findings, limitations
- Package reproducible artifacts
- Produce implementation handover note

---

## 6. Execution log (chronological)

### Entry 001 — 2026-09-13
Actions completed:
1. Verified public accessibility and technical scope of both upstream repositories.
2. Confirmed `cio_pipeline-2` already contains relevant ingestion, panel, diagnostics, and forecast scaffold components.
3. Confirmed `mofped-macrodata-api-downloader` remains suitable as a MoFPED bulk extraction source.
4. Created this workspace documentation baseline:
   - `README.md`
   - `docs/01_project_brief.md`
   - `docs/02_model_spec_brent_to_construction_escalation_uganda.md`
   - `docs/03_execution_report.md`

Outputs produced in this entry:
- project charter and objective framing
- full technical model specification
- phased execution governance and audit trail starter

Open items after Entry 001:
- wire and run data pipelines locally in this workspace
- ingest external Brent source
- create first merged modeling dataset

---

## 7. Risks and mitigations

1. API/network access instability
- Mitigation: maintain manual CSV fallback path and clear source manifests.

2. Structural breaks causing unstable coefficients
- Mitigation: break tests, regime dummies, rolling estimation.

3. Overfitting in ML models
- Mitigation: strict rolling validation and benchmark discipline.

4. Causal over-interpretation
- Mitigation: report predictive and associational evidence clearly; use robustness checks.

---

## 8. Reproducibility and governance
- Maintain frozen raw inputs and versioned processed outputs.
- Log every run with timestamp, code reference, and data cut.
- Store diagnostics and metadata with each model release.
- Keep this execution report updated at each major step.

---

## 9. Immediate next run checklist
1. Add pipeline wiring notes and repository clone paths.
2. Define external Brent source and ingestion script.
3. Build first integrated monthly dataset.
4. Publish first model-run summary in this report.

---

## 10. Run completion update (2026-09-13)

### Entry 002 — End-to-end execution with results + visualisations
Actions completed:
1. Cloned and wired the two upstream repositories into this workspace:
   - `cio_pipeline-2`
   - `mofped-macrodata-api-downloader`
2. Installed Python dependencies in project virtual environment.
3. Executed full Phase 0 build in `cio_pipeline-2` (`run_phase0.sh`) with successful panel rebuild and green tests.
4. Implemented Brent transmission model runner:
   - `analysis/run_brent_escalation_model.py`
   - Brent source used: FRED `DCOILBRENTEU` (daily) aggregated to monthly means.
5. Produced first quantitative results tables and five visualisations under `results/`.

Core run outputs produced:
- `results/tables/metrics.json`
- `results/tables/ardl_coefficients.csv`
- `results/tables/forecast_test_window.csv`
- `results/tables/scenario_shock_impacts.csv`

Visual outputs produced:
- `results/figures/01_cipi_vs_brent_normalized.png`
- `results/figures/02_brent_lag_correlation.png`
- `results/figures/03_brent_lag_coefficients.png`
- `results/figures/04_test_forecast_index_path.png`
- `results/figures/05_scenario_brent_shock_impacts.png`

### First-pass modeling metrics
- Model observations: 91 (train 72, test 19)
- Train `R²`: 0.5497
- Test MAE (model): 0.7868
- Test RMSE (model): 1.0128
- Test MAE (naive): 0.1738
- Test RMSE (naive): 0.2261

### Interpretation of first pass
- The current ARDL specification is functional and reproducible, but underperforms a naive benchmark in the present split.
- This indicates the model is not yet calibrated for predictive superiority and requires refinement (lag pruning, variable transformations, regularization, and rolling-window re-tuning).
- The generated figures already provide a usable visual baseline for transmission pattern diagnostics and scenario communication.

### Execution status after Entry 002
- Phase B (data assembly): completed for first pass.
- Phase C (estimation): baseline completed.
- Phase D (forecasting/scenarios): first pass completed with visual outputs.
- Phase E (final reporting): in progress.

### Entry 003 — Calibration round and reliability hardening (2026-09-14)
Actions completed:
1. Implemented a dedicated calibration workflow script:
   - `analysis/calibrate_round3.py`
2. Added model-spec search over lag structures and model families for 6-month escalation horizon.
3. Added holdout evaluation, naive-benchmark comparison, and prediction interval coverage diagnostics.
4. Generated a new artifact pack:
   - `results/round3/tables/candidate_search.csv`
   - `results/round3/tables/test_predictions.csv`
   - `results/round3/tables/metrics.json`
   - `results/round3/figures/*.png`
   - `results/round3/summary.md`

Calibration outcome:
- On current sample, the optimized blend collapses to `alpha=0` (naive persistence), meaning exogenous challenger models do not yet beat naive in stable out-of-sample holdout.
- This is a valid and important calibration result: the bankable choice for short-run operational forecasting is currently the benchmark model with explicit uncertainty bands.

Reliability interpretation:
- Forecast governance is now champion/challenger rather than single-model faith.
- Confidence should be attached to:
  - robust benchmark performance,
  - interval coverage,
  - and monthly rerun monitoring.
- Causal/structural interpretation of Brent remains in scenario and pass-through analysis; point-forecast dominance is not yet established.

Decision-ready usage rule (current release):
1. Use champion forecast path from `results/round3`.
2. Budget with PI80/PI90 contingency bands.
3. Recalibrate monthly and only promote challenger when it shows sustained positive skill over naive.
