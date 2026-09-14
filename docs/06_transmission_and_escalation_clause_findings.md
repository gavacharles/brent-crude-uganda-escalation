# Brent Transmission and Escalation-Clause Findings

## Date
2026-09-14

## Purpose
Answer the project's core question directly: how does a Brent crude shock move through the Ugandan economy into construction input prices, with what lag, which inputs are most exposed, and what that implies for the design of price-escalation clauses (including FIDIC-style formulae).

## Data and method
- `analysis/brent_transmission_policy.py`, run on `cio_pipeline-2/data/processed/panel_v1.0.csv` + FRED `DCOILBRENTEU` (monthly mean).
- Sample: 2017-07-01 to 2026-04-01 (106 months).
- HAC/Newey-West (maxlags=3) distributed-lag regressions at each stage of the transmission chain (Brent → FX, Brent/FX → CPI, Brent/FX/CPI → `CIPI_ALL`), a 0–12 month local-projection impulse response of Brent on construction inflation, a per-material pass-through ranking, and an out-of-sample comparison of a CPI-only escalation proxy vs. a CPI+FX+Brent proxy.
- Outputs: `results/transmission/tables/*.csv`, `results/transmission/tables/transmission_summary.json`, `results/transmission/figures/*.png`.

## 1. Propagation mechanism and lag
Point estimates trace the expected chain (Brent → FX/import costs → CPI/input costs → construction inflation), but **no stage is statistically significant at the 5% level in this sample**:
- Brent → FX: all lag coefficients insignificant (p = 0.15–0.86); signs are unstable.
- Brent/FX → CPI: all insignificant (p = 0.29–0.99); FX has the largest point effect (0.41 at lag 0, p = 0.20), ahead of Brent itself.
- Brent/FX/CPI → `CIPI_ALL`: largest effects at lag 1 (0.022, p = 0.15) and lag 2 (0.027, p = 0.17); cumulative pass-through over lags 0–6 is **0.066** (a 1% Brent move associates with ~0.07pp of cumulative monthly construction-inflation response) — small and not significant.
- Local projections (h = 0–12): point estimates peak at **h ≈ 2 months** (0.028, p = 0.12) with a secondary bump at **h ≈ 6 months** (0.028, p = 0.06, borderline); every horizon's 95% CI crosses zero.

**Reading**: the mechanism is directionally consistent with theory and the lag structure clusters around 1–2 months with a possible 6-month echo, but 106 monthly observations is not enough to pin the elasticity down precisely. Treat the lag estimate as provisional, not the significance.

## 2. Effect on other input prices (material heterogeneity)
From `material_brent_pass_through_rank.csv`, pass-through is concentrated in energy- and steel-linked materials, not spread evenly:

| Material | Cumulative Brent β (lags 0–6) | Peak lag | Significant lags (p<0.10) |
|---|---|---|---|
| Nails | 0.306 | 2mo | 7/7 |
| Diesel | 0.228 | 1mo | 6/7 |
| Iron/steel | 0.125 | 1mo | 7/7 |
| Sand | 0.093 | 0mo | 0/7 |
| Cement | 0.077 | 4mo | 0/7 |

Locally-sourced/bulk materials (sand, aggregate, murram, cement, lime, clay, labour) show weak, inconsistent, and sometimes negative-signed relationships with 0–1 significant lags — economically sensible, since these are less energy-intensive to produce/transport and more exposed to local, non-oil cost drivers. One exception (murram, cum β = −0.31 with 7/7 "significant" lags) is almost certainly a small-sample/multicollinearity artifact rather than a real effect — murram has no plausible oil linkage — and is a reminder not to over-trust per-material significance counts from 7-lag regressions on ~100 observations.

**Reading**: a single blended escalation index will systematically misallocate risk — under-compensating fuel/steel-heavy trades and over-compensating (or adding noise to) earthworks/bulk-material trades.

## 3. Is a CPI-only escalation proxy adequate?
`clause_proxy_model_comparison.csv`:

| Model | Adj. R² (in-sample) | AIC | Out-of-sample RMSE |
|---|---|---|---|
| CPI-only | −0.036 | 246.2 | 0.526 |
| CPI + FX + Brent | 0.028 | 247.4 | 0.670 (**27% worse**) |

Adding FX and Brent terms modestly improves in-sample fit but makes out-of-sample forecasts worse — a classic small-sample overfitting signature (12 regressors, ~100 months, no shrinkage). This **does not mean Brent/FX are irrelevant**; it means a naively expanded linear formula, estimated this way, isn't yet a demonstrably better predictor than CPI alone. It echoes the round-3 forecast calibration finding (`docs/05`): added model complexity has not yet beaten the simple benchmark out-of-sample on current data.

## 4. Implication for price-escalation clauses, including FIDIC
FIDIC's Clause 13.8 ("Adjustments for Changes in Cost") uses a weighted multi-index formula:

`Pn = a + b(Ln/Lo) + c(En/Eo) + d(Mn/Mo) + ...`

where `a` is the fixed/non-adjustable share and `b, c, d, …` are category weights (labour, plant/fuel, materials, …) applied to current/base published-index ratios.

**Verdict: the structure is right, the specification is usually not, without project-specific calibration.**
- The multi-index *idea* is correct — our data confirms materials are heterogeneously exposed, so a single blended index (e.g., general CPI) is the wrong instrument. FIDIC already avoids that trap in principle.
- In practice, contracts often default to a general CPI or a single national materials index rather than a dedicated fuel/energy sub-index. Given that diesel and steel-linked materials carry almost all of the measurable pass-through (§2), that default under-captures the real transmission channel and smooths over the materials that actually move.
- Weights (`b, c, d, …`) are fixed at signing and rarely revisited, but exposure is project-specific (a steel-heavy building vs. an earthworks-heavy road should carry very different fuel/steel weight) — this is exactly why the model spec (`docs/02`, §9) defines project-basket weights `w_i` rather than a generic index.
- Revision frequency and index dating should track the empirical lag: peak effect at 1–2 months (with a possible echo near 6 months) argues for **monthly** index application with base/current dates close to actual cost-incurred dates. Quarterly or loosely-dated applications risk under-compensating during the acute window and mistiming any secondary adjustment.
- Because a naively expanded formula doesn't yet reliably beat CPI-only out-of-sample (§3), a purely mechanical, "set-and-forget" formula is not safely upgradable to a Brent/FX-augmented version without periodic recalibration — the same champion/challenger discipline used for the internal forecast (`docs/05`) is the right posture for clause design too: adopt a broader index only once it shows sustained, out-of-sample benefit, not on in-sample plausibility alone.

**Bottom line**: FIDIC's formula mechanism is a reasonable, administrable default, but as commonly implemented (generic indices, fixed generic weights, quarterly-or-looser revision) it is not fit for purpose for oil-shock exposure in this market. It becomes fit for purpose when (i) fuel/energy and steel-linked inputs get their own index rather than being folded into CPI, (ii) weights are calibrated to the actual BoQ/material mix per project, (iii) indices are applied at least monthly, and (iv) weights/index choice are revisited periodically rather than frozen for the contract's life.

## Addendum (2026-09-14): diesel-mediated re-run
`globalpetrolprices.com`'s historical download/API is paid (per-data-point pricing); `dailyfuels.com` only exposes ~4 months of weekly history. Neither can supply a free 2017–2026 monthly Uganda pump-price series. Used the UBOS CIPI `DIESEL` sub-index already in `panel_v1.0` (same sample window) as the local pump/fuel-cost proxy instead, via `analysis/brent_diesel_transmission.py` → `results/transmission_v2/`.

Shortening the chain to Brent → Diesel → construction inflation (rather than routing everything through FX/CPI) produced a materially stronger, statistically solid result:
- Brent → Diesel: adj. R² 0.25, min lag p-value 0.009, peak at 1 month (vs. Brent → FX, which was insignificant at every lag, p up to 0.86).
- Diesel → `CIPI_ALL`: adj. R² 0.19, min lag p-value 0.0006, peak contemporaneous.
- **Mediation test**: adding diesel as a control roughly doubles adj. R² for explaining construction inflation (0.069 → 0.136) while Brent's own coefficient collapses from 0.061 to 0.013, and diesel's coefficient is 0.145. This is the standard mediation signature — diesel is the transmission channel; Brent matters to construction costs *because* it moves local diesel, not directly.
- Escalation clause proxy: `cpi_diesel` (OOS RMSE 0.610) beats `cpi_fx_brent` (0.670) but still loses to `cpi_only` (0.526) out-of-sample, despite far better in-sample fit (adj. R² 0.186 vs. −0.036). Same overfitting caveat as before, just less severe.

This strengthens §1 and §4 above: the case for a dedicated fuel/energy sub-index (rather than folding energy into CPI or a generic Brent/FX term) now rests on a statistically robust mechanism, not just point estimates that don't clear significance. The out-of-sample forecasting caveat (§3) still stands — don't wire a richer formula into a contract without regularized/validated forecasting performance behind it.

## Addendum 2 (2026-09-14): Tier A dependability pass
`analysis/brent_dependability_v3.py` → `results/transmission_v3/`. Five additions on top of the diesel-mediated re-run above:

1. **Regularization resolves the overfitting problem.** ElasticNet (rolling-origin, standardized features) instead of plain OLS: `cpi_diesel` achieves OOS RMSE **0.513**, beating `cpi_only` (0.526) — the first specification in the project to beat the CPI-only proxy out-of-sample. Unregularized OLS on the same spec scored 0.610 (worse). The earlier finding that "adding diesel hurts forecasts" was an overfitting artifact of unregularized OLS on ~100 months, not evidence against the diesel channel.
2. **Structural break: 2022, not 2020.** Chow test at 2020-03 (COVID): F=0.095, p=0.963, no break. Chow test at 2022-02 (Ukraine-war commodity shock): F=4.03, **p=0.0095**, reject stability. Split-sample coefficients show the Brent→Diesel 1-month-lag pass-through went from 0.025 (pre-2022) to **0.133 (post-2022)** — over 5x stronger. Escalation-clause calibration should use the post-2022 regime elasticity, not a whole-sample blend.
3. **Mediation bootstrap** (2000 block-bootstrap draws, block=8 months): diesel absorbs a median 60% of Brent's effect on construction inflation, same sign in 92% of draws (95% CI on the absorption share is wide: [-59%, +253%] — don't quote the point estimate as precise). More robust: diesel's incremental adj. R² contribution to explaining `CIPI_ALL` stays positive across the *entire* 95% CI [0.101, 0.526].
4. **Material-level systemic-importance ranking** (mediation loop across every material, ranked by adj. R² gain from adding diesel to a Brent-only model): top 5 are CEM (0.081), AGG (0.075), LABOUR (0.073), IRON (0.065), STEEL (0.043) — bulk/transport/production-energy-intensive trades, not diesel itself. Cross-referenced against the pre-existing, independent Diebold-Yilmaz spillover ranking already in this workspace (`cio_pipeline-2/p4_simi_ranking.csv`, a domestic material-to-material network with no Brent input at all): **CEM is also the #1-ranked systemically important material there (SIMI=14, top score)**. Two independent methods converge on cement. Revised framing: diesel is the gateway that imports the Brent shock into the domestic system; cement is the domestic hub that further amplifies and spreads it — "diesel is the most systemically important material" is not quite right; diesel is the conduit, cement is where it lands hardest.
5. **Brent historical regime narrative** produced for context: full available history (1987-2026) with era shading, plus a zoomed modeling-window chart. See `results/transmission_v3/tables/brent_historical_eras.csv` and figures 01-02.

**Caveats on this pass**: the "% of Brent's effect absorbed by diesel" ratio metric is unstable when a material's direct Brent effect is near zero (produces nonsense values like +719% for BRICK, +1149% for LIME) — treat adj. R² gain as the trustworthy ranking metric, not that ratio. Four materials (NAILS, IRONSTEEL, ALU, MURRAM) drop out of the mediation table for insufficient overlapping observations — a pre-existing data-coverage gap in those UBOS series, not new.

## Caveats
- 106 monthly observations is a modest sample for lag-rich, multi-material econometrics; most individual coefficients are not significant at conventional levels.
- Results should be read as directional evidence to inform escalation-clause *design choices* (which indices, what frequency, how to weight), not as precise elasticities to hard-code into a formula.
- Consistent with the project's existing governance stance (`docs/03`, `docs/05`): recalibrate on a schedule, and only promote a more complex specification once it earns its complexity out-of-sample.
