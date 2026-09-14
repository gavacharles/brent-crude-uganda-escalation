# Model Specification

## 1) Objective
Estimate and forecast how Brent crude price movements affect construction price escalation in Uganda, both at:
- material-series level (CIPI sub-indices)
- project basket level (weighted escalation metric)

## 2) Outcome variables

### 2.1 Material-level target
For each construction material series `i`:
- level: `CIPI_i,t`
- inflation form: `y_i,t = 100 * Δlog(CIPI_i,t)`

### 2.2 Project-level escalation target
Define project basket weights `w_i` (BoQ/cost-plan shares, sum to 1):

`B_t = Σ_i w_i * CIPI_i,t`

Escalation over horizon `h` months from decision date `t`:

`Esc_{t→t+h} = (B_{t+h}/B_t - 1) * 100`

## 3) Core explanatory variables

### 3.1 Global shock
- Brent crude price (USD/barrel), monthly average
- transform: `Δlog(Brent_t)` and lag stack

### 3.2 Domestic transmission channels (from MoFPED/BoU/UBOS pipelines)
- `exchange_rate` (UGX/USD)
- `central_bank_rate`
- `lending_rate`
- `cpi`
- `private_credit`
- `activity_indicator` (or proxy)
- optional fiscal block (revenue/expenditure/deficit/debt from MOF_POE-derived panel)

### 3.3 Optional controls
- global shipping/freight proxy
- imported materials unit values
- tax/policy dummy events
- 2022 commodity shock interaction dummy

## 4) Data architecture and alignment
- Frequency: monthly month-start timestamps
- Merge key: monthly date
- Missing policy: short forward fill for timing mismatch (`limit=1` or `2`) only where methodologically justified
- Outlier handling: winsorization at 1st/99th percentile on return space for robustness checks

## 5) Feature engineering
- Lag set candidates for Brent and key channels: `L1..L12`
- seasonal dummies: month-of-year
- shock regimes: high-volatility period indicators
- interaction terms: `Δlog(Brent) × Δlog(UGX/USD)`
- moving averages: 3m and 6m for smoother pass-through effects

## 6) Econometric baseline models

### 6.1 Distributed-lag regression (ARDL-style)
For each material / basket inflation:

`y_t = α + Σ_{k=1..p} φ_k y_{t-k} + Σ_{j=0..q} β_j x^{Brent}_{t-j} + Σ_m Γ_m Z_{m,t} + ε_t`

Outputs:
- short-run Brent pass-through by lag
- cumulative pass-through `Σ β_j`

### 6.2 Error-correction variant (if cointegration evidence exists)

`Δy_t = λ(y_{t-1} - θ'X_{t-1}) + short-run terms + ε_t`

Interpretation:
- `λ`: speed of adjustment
- `θ`: long-run relation

### 6.3 VAR/SVAR (system robustness)
Jointly model Brent, FX, CPI, basket inflation; derive impulse responses and FEVD.

## 7) Machine-learning benchmark models
- Elastic Net regression (lagged feature panel)
- Gradient boosting (`XGBoost`/`LightGBM`)
- Random forest regression

Use ML for forecast performance comparison; retain econometric models for interpretation and policy narrative.

## 8) Validation protocol

### 8.1 Train/test strategy
- Rolling-origin backtests (expanding window)
- Example: initial train 2016-2021, test 2022; then roll monthly/quarterly

### 8.2 Metrics
- MAE
- RMSE
- MAPE / sMAPE
- directional accuracy
- calibration of prediction intervals (coverage)

### 8.3 Benchmarks
- random walk / last-observation carry-forward
- seasonal naive

## 9) Scenario engine for project decisions
Evaluate deterministic and stochastic scenarios:
- Brent +10%, +20%, -10%
- FX stress (UGX depreciation) overlay
- combined shock scenario

Convert simulated monthly material paths to project escalation distributions:
- p50, p80, p90 escalation
- contingency recommendation by risk appetite

## 10) Identification and caveats
- Brent may proxy broader global commodity conditions; avoid over-claiming causality.
- Structural breaks (e.g., 2020, 2022) require regime checks.
- Construction escalation sensitivity varies by project material mix (`w_i`).

## 11) Implementation plan (code-level)
1. Data assembly module: merge `panel_v1.0` + external Brent + optional controls.
2. Feature builder: lag matrix, transformations, regime dummies.
3. Baseline econometric runner: ARDL/ECM + diagnostics.
4. ML benchmark runner: tuned but constrained model class.
5. Backtest orchestrator: rolling windows, metric tables, plots.
6. Reporting layer: impact tables, lag curves, scenario outputs.

## 12) Acceptance criteria
- Reproducible pipeline run from raw to final report
- Stable estimates under core robustness checks
- Forecast model outperforms naive on key metrics
- Practical escalation guidance (p50/p80/p90) available for project budgeting
