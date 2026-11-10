# brent-crude-uganda-escalation

![Rerun Brent calibration](https://github.com/gavacharles/brent-crude-uganda-escalation/actions/workflows/rerun-calibration.yml/badge.svg)

Python analysis scripts, results and write-ups on how Brent crude price shocks transmit to Ugandan construction costs, and what that implies for price-escalation clauses in construction contracts.

## Repository map

```
analysis/
  brent_transmission_policy.py       Brent -> exchange rate -> CPI -> construction input prices
  brent_diesel_transmission.py       Brent -> local diesel index -> construction input prices (mediation)
  brent_dependability_v3.py          regularisation, structural-break test, bootstrap, network check
  ipc_case_study_validation.py       validation against an anonymised contract's price-adjustment history
  calibrate_round3.py                forecast-calibration track (rerun monthly by CI)
  run_brent_escalation_model.py      original baseline run
docs/                                numbered project log: brief, model specification, execution report,
                                     snapshots, findings, manuscript
writing/                             audience-facing write-ups
results/
  transmission/, transmission_v2/, transmission_v3/   outputs of the three transmission scripts
  case_study_ipc/                    anonymised, numeric-only outputs of the contract validation
  round3/                            forecast-calibration outputs (CI-managed)
  tables/, figures/, report_run1.html   baseline outputs
.github/workflows/rerun-calibration.yml   monthly rerun of the calibration track
```

## Running

The scripts use the data panel built by [cio_pipeline-2](https://github.com/gavacharles/cio_pipeline-2) (`data/processed/panel_v1.0.csv`). Clone it alongside this repository, run its Phase 0 build (`cio_pipeline-2/run_phase0.sh`), then use its environment:

```bash
cio_pipeline-2/.venv/bin/python3 analysis/brent_transmission_policy.py
cio_pipeline-2/.venv/bin/python3 analysis/brent_diesel_transmission.py
cio_pipeline-2/.venv/bin/python3 analysis/brent_dependability_v3.py
```

Brent prices are pulled from FRED (`DCOILBRENTEU`) at run time. `ipc_case_study_validation.py` needs a contract workbook that is not in the repository.

## Data handling

Raw contract workbooks are git-ignored (`*.xlsx`) and never committed; only anonymised numeric extracts under `results/case_study_ipc/` are tracked.

## Related repositories

- [cio_pipeline-2](https://github.com/gavacharles/cio_pipeline-2): UBOS CIPI ingestion, macro join, panel diagnostics
- [mofped-macrodata-api-downloader](https://github.com/gavacharles/mofped-macrodata-api-downloader): bulk MoFPED macro data extraction
