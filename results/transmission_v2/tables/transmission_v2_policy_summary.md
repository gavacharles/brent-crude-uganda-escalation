# Diesel-Mediated Brent Transmission Assessment (v2)

- Sample: 2017-07-01 to 2026-04-01 (106 months)
- Data note: globalpetrolprices.com history is paid; dailyfuels.com only covers ~4 months. Used UBOS CIPI `DIESEL` sub-index (full 2017-2026 monthly history, already in the panel) as the local pump/fuel-cost proxy instead.
- Brent -> Diesel: adj. R² 0.252, cumulative beta (lags 0-6) 0.2328, peak lag 1 months, min p-value 0.0091
- Diesel -> CIPI_ALL: adj. R² 0.187, cumulative beta (lags 0-6) 0.1546, peak lag 0 months, min p-value 0.0006

## Clause proxy out-of-sample RMSE (lower is better)
- cpi_only: RMSE 0.5261 (adj R² -0.036, 0.0% vs CPI-only)
- cpi_fx_brent: RMSE 0.6703 (adj R² 0.028, -27.4% vs CPI-only)
- cpi_diesel: RMSE 0.6105 (adj R² 0.186, -16.0% vs CPI-only)
- cpi_fx_brent_diesel: RMSE 0.7724 (adj R² 0.137, -46.8% vs CPI-only)

## Interpretation
1. Brent -> Diesel is the tightest single link in the chain (see adj. R² above), shorter and cleaner than Brent -> FX -> CPI.
2. The mediation check shows whether local diesel cost explains construction inflation better than Brent alone, and whether Brent's coefficient shrinks once diesel is controlled for (expected if diesel is the transmission channel, not FX).
3. Compare `cpi_diesel` against `cpi_fx_brent` and `cpi_only`: if `cpi_diesel` achieves the best out-of-sample RMSE, a dedicated local fuel/energy sub-index is the more defensible escalation-clause addition than a generic global Brent+FX term.
4. Treat as empirical evidence to guide index selection and revision frequency, not legal advice.