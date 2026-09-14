# Brent Crude → Construction Price Escalation (Uganda)

This workspace is the implementation and documentation hub for estimating how Brent crude price shocks transmit into construction price escalation in Uganda.

## Purpose
Build a reproducible modeling pipeline that combines:
1) CiO construction-price panel data workflows
2) MoFPED macro data extraction workflows
3) external Brent crude series

and produces:
- interpretable impact estimates (magnitude + lag)
- forecast models for escalation risk
- scenario analysis for project budgeting

## Upstream repositories
- https://github.com/gavacharles/cio_pipeline-2
- https://github.com/gavacharles/mofped-macrodata-api-downloader

## Core project deliverables in this workspace
- Project brief: [docs/01_project_brief.md](docs/01_project_brief.md)
- Full model specification: [docs/02_model_spec_brent_to_construction_escalation_uganda.md](docs/02_model_spec_brent_to_construction_escalation_uganda.md)
- Comprehensive execution report (living document): [docs/03_execution_report.md](docs/03_execution_report.md)
- Results snapshot: [docs/04_results_snapshot.md](docs/04_results_snapshot.md)
- Visual report (HTML): [results/report_run1.html](results/report_run1.html)
- Calibration round 3 summary: [results/round3/summary.md](results/round3/summary.md)
- Calibration round 3 figures: [results/round3/figures](results/round3/figures)

## Current status
- Documentation baseline created
- Model design specified
- Execution framework defined
- Data assembly and model implementation pending

## Next immediate actions
1. Add project-specific BoQ basket weights and run project-level escalation calibration.
2. Expand backtest window as new monthly UBOS releases arrive.
3. Track rolling model skill versus naive baseline in automated reruns.
