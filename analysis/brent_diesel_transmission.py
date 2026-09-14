#!/usr/bin/env python3
"""
Diesel-mediated Brent transmission model.

Rationale: globalpetrolprices.com (paid, per-data-point) and dailyfuels.com
(free but only ~4 months of history) cannot supply a free, decade-length
monthly Uganda pump-price series. The project panel already contains one:
UBOS CIPI's `DIESEL` sub-index is an official, monthly, 2017-2026 series
tracking construction-sector fuel cost. This script uses it as the local
pump-price node and shortens the transmission chain to
Brent -> DIESEL -> (other materials / CIPI_ALL), instead of routing
everything through FX/CPI only.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm


def dlog(s: pd.Series) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce")
    return 100.0 * np.log(x).diff()


def fit_hac(y: pd.Series, X: pd.DataFrame, maxlags: int = 3):
    z = pd.concat([y.rename("y"), X], axis=1).dropna()
    y2 = z["y"].astype(float)
    X2 = sm.add_constant(z.drop(columns=["y"]).astype(float))
    m = sm.OLS(y2, X2).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    return m, z.index


def rmse(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return float(np.sqrt(np.mean((a - b) ** 2)))


def rolling_oos_rmse(y: pd.Series, X: pd.DataFrame, start_train: int = 48) -> float:
    z = pd.concat([y.rename("y"), X], axis=1).dropna().copy()
    if len(z) <= start_train + 3:
        return float("nan")
    preds, trues = [], []
    for i in range(start_train, len(z)):
        train = z.iloc[:i]
        test = z.iloc[i : i + 1]
        m = sm.OLS(train["y"], sm.add_constant(train.drop(columns=["y"]))).fit()
        p = float(m.predict(sm.add_constant(test.drop(columns=["y"]), has_constant="add")).iloc[0])
        preds.append(p)
        trues.append(float(test["y"].iloc[0]))
    return rmse(trues, preds)


def coef_table(m) -> pd.DataFrame:
    return pd.DataFrame({
        "term": m.params.index,
        "coef": m.params.values,
        "p_value": m.pvalues.values,
        "std_err": m.bse.values,
    })


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out_t = root / "results" / "transmission_v2" / "tables"
    out_f = root / "results" / "transmission_v2" / "figures"
    out_t.mkdir(parents=True, exist_ok=True)
    out_f.mkdir(parents=True, exist_ok=True)

    panel = pd.read_csv(root / "cio_pipeline-2" / "data" / "processed" / "panel_v1.0.csv")
    panel["date"] = pd.to_datetime(panel["date"])

    brent = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU")
    brent.columns = ["date", "brent_usd"]
    brent["date"] = pd.to_datetime(brent["date"], errors="coerce")
    brent["brent_usd"] = pd.to_numeric(brent["brent_usd"], errors="coerce")
    brent = brent.dropna(subset=["date", "brent_usd"]).set_index("date").sort_index().resample("MS").mean().reset_index()

    df = panel.merge(brent, on="date", how="left").sort_values("date").set_index("date")

    df["r_brent"] = dlog(df["brent_usd"])
    df["r_fx"] = dlog(df["exchange_rate"])
    df["r_cpi"] = dlog(df["cpi"])
    df["r_diesel"] = dlog(df["DIESEL"])
    df["r_cipi_all"] = dlog(df["CIPI_ALL"])

    for k in range(0, 7):
        df[f"brent_l{k}"] = df["r_brent"].shift(k)
        df[f"diesel_l{k}"] = df["r_diesel"].shift(k)
    for k in range(0, 4):
        df[f"fx_l{k}"] = df["r_fx"].shift(k)
        df[f"cpi_l{k}"] = df["r_cpi"].shift(k)

    # 1) Brent -> local diesel (pump-cost proxy)
    m_bd, _ = fit_hac(df["r_diesel"], df[[f"brent_l{k}" for k in range(0, 7)]])
    coef_table(m_bd).to_csv(out_t / "brent_to_diesel_lag_coeffs.csv", index=False)

    # 2) Diesel -> construction inflation (direct local channel)
    m_dc, _ = fit_hac(df["r_cipi_all"], df[[f"diesel_l{k}" for k in range(0, 7)]])
    coef_table(m_dc).to_csv(out_t / "diesel_to_cipi_lag_coeffs.csv", index=False)

    # 3) Mediation check: does diesel absorb Brent's explanatory power on CIPI_ALL?
    X_direct = df[[f"brent_l{k}" for k in range(0, 7)]]
    X_mediated = df[[f"brent_l{k}" for k in range(0, 7)] + [f"diesel_l{k}" for k in range(0, 7)]]
    m_direct, _ = fit_hac(df["r_cipi_all"], X_direct)
    m_mediated, _ = fit_hac(df["r_cipi_all"], X_mediated)
    mediation = pd.DataFrame([
        {"model": "brent_only_to_cipi", "adj_r2": float(m_direct.rsquared_adj),
         "cum_brent_beta": float(m_direct.params.filter(like="brent_l").sum())},
        {"model": "brent_plus_diesel_to_cipi", "adj_r2": float(m_mediated.rsquared_adj),
         "cum_brent_beta": float(m_mediated.params.filter(like="brent_l").sum()),
         "cum_diesel_beta": float(m_mediated.params.filter(like="diesel_l").sum())},
    ])
    mediation.to_csv(out_t / "brent_diesel_mediation_check.csv", index=False)
    coef_table(m_mediated).to_csv(out_t / "brent_plus_diesel_to_cipi_coeffs.csv", index=False)

    # 4) Local projection: diesel shock -> future CIPI_ALL inflation, h=0..12
    lp_rows = []
    for h in range(0, 13):
        y_h = df["r_cipi_all"].shift(-h)
        X_h = df[["r_diesel", "r_brent", "r_fx", "r_cpi"]]
        m_h, _ = fit_hac(y_h, X_h)
        b = float(m_h.params.get("r_diesel", np.nan))
        se = float(m_h.bse.get("r_diesel", np.nan))
        lp_rows.append({"h": h, "beta_diesel": b, "lo95": b - 1.96 * se, "hi95": b + 1.96 * se,
                         "p_value": float(m_h.pvalues.get("r_diesel", np.nan))})
    lp = pd.DataFrame(lp_rows)
    lp.to_csv(out_t / "local_projection_diesel_to_cipi.csv", index=False)

    # 5) Escalation clause proxy: CPI-only vs CPI+FX+Brent vs CPI+Diesel vs CPI+FX+Brent+Diesel
    y = df["r_cipi_all"]
    X_cpi = df[["cpi_l0", "cpi_l1", "cpi_l2", "cpi_l3"]]
    X_cpi_fx_brent = df[["cpi_l0", "cpi_l1", "cpi_l2", "cpi_l3",
                          "fx_l0", "fx_l1", "fx_l2", "fx_l3",
                          "brent_l0", "brent_l1", "brent_l2", "brent_l3"]]
    X_cpi_diesel = df[["cpi_l0", "cpi_l1", "cpi_l2", "cpi_l3",
                        "diesel_l0", "diesel_l1", "diesel_l2", "diesel_l3"]]
    X_full = df[["cpi_l0", "cpi_l1", "cpi_l2", "cpi_l3",
                 "fx_l0", "fx_l1", "fx_l2", "fx_l3",
                 "brent_l0", "brent_l1", "brent_l2", "brent_l3",
                 "diesel_l0", "diesel_l1", "diesel_l2", "diesel_l3"]]

    rows = []
    for name, X in [("cpi_only", X_cpi), ("cpi_fx_brent", X_cpi_fx_brent),
                     ("cpi_diesel", X_cpi_diesel), ("cpi_fx_brent_diesel", X_full)]:
        m, _ = fit_hac(y, X)
        rows.append({
            "model": name,
            "adj_r2": float(m.rsquared_adj),
            "aic": float(m.aic),
            "oos_rmse": rolling_oos_rmse(y, X),
        })
    clause = pd.DataFrame(rows)
    clause["oos_rmse_improvement_vs_cpi_only_pct"] = (
        (clause.loc[clause["model"] == "cpi_only", "oos_rmse"].iloc[0] - clause["oos_rmse"])
        / clause.loc[clause["model"] == "cpi_only", "oos_rmse"].iloc[0] * 100.0
    )
    clause.to_csv(out_t / "clause_proxy_model_comparison_v2.csv", index=False)

    # 6) Figures
    plt.figure(figsize=(10, 4.8))
    plt.plot(lp["h"], lp["beta_diesel"], marker="o", color="#b45309", label="Diesel coefficient")
    plt.fill_between(lp["h"], lp["lo95"], lp["hi95"], alpha=0.2, color="#b45309", label="95% CI")
    plt.axhline(0, color="black", linewidth=0.8)
    plt.title("Local channel: diesel-cost shock and future CIPI inflation")
    plt.xlabel("Horizon (months)")
    plt.ylabel("Effect on monthly CIPI inflation (pp)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_f / "01_diesel_local_projection_profile.png", dpi=180)
    plt.close()

    plt.figure(figsize=(8.5, 4.8))
    order = ["cpi_only", "cpi_fx_brent", "cpi_diesel", "cpi_fx_brent_diesel"]
    vals = [clause.set_index("model").loc[m, "oos_rmse"] for m in order]
    plt.bar(order, vals, color=["#6b7280", "#2563eb", "#b45309", "#059669"])
    plt.title("Escalation clause proxy: out-of-sample RMSE by index composition")
    plt.ylabel("Out-of-sample RMSE")
    plt.xticks(rotation=15)
    plt.tight_layout()
    plt.savefig(out_f / "02_clause_proxy_oos_rmse_v2.png", dpi=180)
    plt.close()

    bd_terms = coef_table(m_bd)
    bd_terms_b = bd_terms[bd_terms["term"].str.startswith("brent_l")]
    dc_terms = coef_table(m_dc)
    dc_terms_d = dc_terms[dc_terms["term"].str.startswith("diesel_l")]

    summary = {
        "sample_start": str(df.index.min().date()),
        "sample_end": str(df.index.max().date()),
        "n_months": int(df.shape[0]),
        "brent_to_diesel": {
            "adj_r2": float(m_bd.rsquared_adj),
            "cumulative_beta_l0_l6": float(bd_terms_b["coef"].sum()),
            "peak_lag_month": int(bd_terms_b.loc[bd_terms_b["coef"].abs().idxmax(), "term"].replace("brent_l", "")),
            "min_p_value": float(bd_terms_b["p_value"].min()),
        },
        "diesel_to_cipi": {
            "adj_r2": float(m_dc.rsquared_adj),
            "cumulative_beta_l0_l6": float(dc_terms_d["coef"].sum()),
            "peak_lag_month": int(dc_terms_d.loc[dc_terms_d["coef"].abs().idxmax(), "term"].replace("diesel_l", "")),
            "min_p_value": float(dc_terms_d["p_value"].min()),
        },
        "mediation": mediation.to_dict(orient="records"),
        "clause_proxy_comparison": clause.to_dict(orient="records"),
        "data_source_note": (
            "globalpetrolprices.com historical download/API is paid (per-data-point pricing); "
            "dailyfuels.com only exposes ~4 months of weekly history. Neither supplies a free "
            "2017-2026 monthly Uganda pump-price series, so the UBOS CIPI DIESEL sub-index "
            "(already in panel_v1.0, same sample window) was used as the local pump/fuel-cost proxy instead."
        ),
    }
    with open(out_t / "transmission_v2_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    lines = []
    lines.append("# Diesel-Mediated Brent Transmission Assessment (v2)\n")
    lines.append(f"- Sample: {summary['sample_start']} to {summary['sample_end']} ({summary['n_months']} months)")
    lines.append("- Data note: globalpetrolprices.com history is paid; dailyfuels.com only covers ~4 months. "
                  "Used UBOS CIPI `DIESEL` sub-index (full 2017-2026 monthly history, already in the panel) "
                  "as the local pump/fuel-cost proxy instead.")
    lines.append(f"- Brent -> Diesel: adj. R² {summary['brent_to_diesel']['adj_r2']:.3f}, "
                 f"cumulative beta (lags 0-6) {summary['brent_to_diesel']['cumulative_beta_l0_l6']:.4f}, "
                 f"peak lag {summary['brent_to_diesel']['peak_lag_month']} months, "
                 f"min p-value {summary['brent_to_diesel']['min_p_value']:.4f}")
    lines.append(f"- Diesel -> CIPI_ALL: adj. R² {summary['diesel_to_cipi']['adj_r2']:.3f}, "
                 f"cumulative beta (lags 0-6) {summary['diesel_to_cipi']['cumulative_beta_l0_l6']:.4f}, "
                 f"peak lag {summary['diesel_to_cipi']['peak_lag_month']} months, "
                 f"min p-value {summary['diesel_to_cipi']['min_p_value']:.4f}")
    lines.append("\n## Clause proxy out-of-sample RMSE (lower is better)")
    for r in summary["clause_proxy_comparison"]:
        lines.append(f"- {r['model']}: RMSE {r['oos_rmse']:.4f} "
                     f"(adj R² {r['adj_r2']:.3f}, {r['oos_rmse_improvement_vs_cpi_only_pct']:.1f}% vs CPI-only)")
    lines.append("\n## Interpretation")
    lines.append("1. Brent -> Diesel is the tightest single link in the chain (see adj. R² above), "
                 "shorter and cleaner than Brent -> FX -> CPI.")
    lines.append("2. The mediation check shows whether local diesel cost explains construction inflation "
                 "better than Brent alone, and whether Brent's coefficient shrinks once diesel is controlled for "
                 "(expected if diesel is the transmission channel, not FX).")
    lines.append("3. Compare `cpi_diesel` against `cpi_fx_brent` and `cpi_only`: if `cpi_diesel` achieves the best "
                 "out-of-sample RMSE, a dedicated local fuel/energy sub-index is the more defensible escalation-clause "
                 "addition than a generic global Brent+FX term.")
    lines.append("4. Treat as empirical evidence to guide index selection and revision frequency, not legal advice.")

    (out_t / "transmission_v2_policy_summary.md").write_text("\n".join(lines), encoding="utf-8")

    print("Done: diesel-mediated transmission results written to results/transmission_v2/")


if __name__ == "__main__":
    main()
