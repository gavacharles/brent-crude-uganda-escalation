# Project Brief

## Project title
Brent Crude Shock Transmission and Construction Price Escalation in Uganda

## Problem statement
Construction projects in Uganda are exposed to cost escalation through imported energy, transport, FX pass-through, and inflation channels. Brent crude is a global upstream shock that may influence domestic construction input prices with non-zero lags. The objective is to quantify and forecast that transmission.

## Main research questions
1. Does Brent significantly affect Uganda construction input prices?
2. What is the lag structure (months to peak pass-through)?
3. Which channels dominate (FX, CPI, lending, activity)?
4. Can escalation be forecast accurately enough for budget risk management?

## Scope
- Geography: Uganda
- Frequency: monthly (primary)
- Time span: 2016–present (extend backward where possible)
- Targets: material-level CIPI series + project-level weighted escalation index

## Data foundation
The project reuses established pipelines from:
- `cio_pipeline-2`: UBOS CIPI ingestion/splicing + macro join + diagnostics
- `mofped-macrodata-api-downloader`: bulk extraction of MoFPED datasets via `ugatsdb`

## Expected outputs
- Elasticity and lag estimates of Brent transmission
- Rolling forecasts of escalation with uncertainty bands
- Scenario tool (e.g., +$10 Brent shock) for project contingency planning
- Technical report and reproducible artifacts

## Success criteria
- Stable monthly panel with complete provenance
- Econometric model with interpretable, statistically robust coefficients
- Forecast model outperforming naive/random-walk benchmark on out-of-sample windows
- Clear policy and project management interpretation
