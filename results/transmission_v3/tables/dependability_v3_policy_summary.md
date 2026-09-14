# Tier A Dependability Pass — Summary

- Modeling sample: 2017-07-01 to 2026-04-01 (106 months)
- Brent full history used for regime narrative: 1987-05-01 to 2026-09-01

## Structural break tests (Brent -> Diesel, Chow test at known events)
- Break at 2020-03-01: F=0.095, p=0.9627 -> fail to reject stability
- Break at 2022-02-01: F=4.031, p=0.0095 -> reject stability (coefficients differ)

## Mediation bootstrap (2000 block-bootstrap draws, block=8 months)
- Brent-effect-on-CIPI absorbed by diesel: median 59.9%, 95% CI [-59.3%, 252.7%], same sign as median in 92% of draws
- Adj. R2 with diesel included: median 0.277 [0.101, 0.526]

## Regularized escalation-clause proxy (rolling-origin OOS RMSE)
- Naive persistence reference RMSE: 1.3200
- cpi_only: OLS 0.5261 | ElasticNet 0.5255
- cpi_diesel: OLS 0.6105 | ElasticNet 0.5130
- cpi_fx_brent_diesel: OLS 0.7724 | ElasticNet 0.5173

## Material systemic-importance ranking (diesel as mediator)
Top 5 materials by adj. R2 gain from adding diesel to a Brent-only model:
- CEM: adj R2 gain 0.081, Brent-effect absorption by diesel 184.1%
- AGG: adj R2 gain 0.075, Brent-effect absorption by diesel 132.9%
- LABOUR: adj R2 gain 0.073, Brent-effect absorption by diesel 75.4%
- IRON: adj R2 gain 0.065, Brent-effect absorption by diesel -329.6%
- STEEL: adj R2 gain 0.043, Brent-effect absorption by diesel 76.9%