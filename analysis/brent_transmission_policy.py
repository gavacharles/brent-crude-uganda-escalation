#!/usr/bin/env python3
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
        p = float(m.predict(sm.add_constant(test.drop(columns=["y"]), has_constant='add')).iloc[0])
        preds.append(p)
        trues.append(float(test["y"].iloc[0]))
    return rmse(trues, preds)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out_t = root / "results" / "transmission" / "tables"
    out_f = root / "results" / "transmission" / "figures"
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

    # core transformed variables
    df["r_brent"] = dlog(df["brent_usd"])
    df["r_fx"] = dlog(df["exchange_rate"])
    df["r_cpi"] = dlog(df["cpi"])
    df["r_cipi_all"] = dlog(df["CIPI_ALL"])

    for k in range(0, 7):
        df[f"brent_l{k}"] = df["r_brent"].shift(k)
        df[f"fx_l{k}"] = df["r_fx"].shift(k)
        df[f"cpi_l{k}"] = df["r_cpi"].shift(k)

    # 1) Propagation: Brent -> FX
    m_fx, _ = fit_hac(df["r_fx"], df[[f"brent_l{k}" for k in range(0, 7)]])
    fx_terms = pd.DataFrame({
        "term": m_fx.params.index,
        "coef": m_fx.params.values,
        "p_value": m_fx.pvalues.values,
        "std_err": m_fx.bse.values,
    })
    fx_terms.to_csv(out_t / "brent_to_fx_lag_coeffs.csv", index=False)

    # 2) Propagation: Brent/FX -> CPI
    X_cpi = df[[f"brent_l{k}" for k in range(0, 7)] + [f"fx_l{k}" for k in range(0, 4)]]
    m_cpi, _ = fit_hac(df["r_cpi"], X_cpi)
    cpi_terms = pd.DataFrame({
        "term": m_cpi.params.index,
        "coef": m_cpi.params.values,
        "p_value": m_cpi.pvalues.values,
        "std_err": m_cpi.bse.values,
    })
    cpi_terms.to_csv(out_t / "brent_fx_to_cpi_lag_coeffs.csv", index=False)

    # 3) Brent/FX/CPI -> Construction inflation
    X_cipi = df[[f"brent_l{k}" for k in range(0, 7)] + [f"fx_l{k}" for k in range(0, 4)] + [f"cpi_l{k}" for k in range(0, 4)]]
    m_cipi, idx_cipi = fit_hac(df["r_cipi_all"], X_cipi)
    cipi_terms = pd.DataFrame({
        "term": m_cipi.params.index,
        "coef": m_cipi.params.values,
        "p_value": m_cipi.pvalues.values,
        "std_err": m_cipi.bse.values,
    })
    cipi_terms.to_csv(out_t / "brent_fx_cpi_to_cipi_lag_coeffs.csv", index=False)

    # Local projection-like profile: h-step response of CIPI inflation to Brent shock today
    lp_rows = []
    for h in range(0, 13):
        y_h = df["r_cipi_all"].shift(-h)
        X_h = pd.concat([df[["r_brent", "r_fx", "r_cpi"]], df[["r_cipi_all"]].rename(columns={"r_cipi_all": "r_cipi_l0"})], axis=1)
        m_h, _ = fit_hac(y_h, X_h)
        b = float(m_h.params.get("r_brent", np.nan))
        se = float(m_h.bse.get("r_brent", np.nan))
        lp_rows.append({"h": h, "beta_brent": b, "lo95": b - 1.96 * se, "hi95": b + 1.96 * se, "p_value": float(m_h.pvalues.get("r_brent", np.nan))})
    lp = pd.DataFrame(lp_rows)
    lp.to_csv(out_t / "local_projection_brent_to_cipi.csv", index=False)

    # 4) Effects across input materials
    macro_cols = {"central_bank_rate", "cpi", "exchange_rate", "lending_rate", "private_credit", "brent_usd"}
    known_non_material = {"CIPI_ALL", "CIPI_BLDG", "CIPI_CIVIL", "CIPI_MAT"}
    material_cols = [c for c in panel.columns if c not in (["date"] + list(macro_cols) + list(known_non_material))]

    mat_rows = []
    for col in material_cols:
        r = dlog(df[col])
        X = df[[f"brent_l{k}" for k in range(0, 7)] + ["r_fx", "r_cpi"]]
        try:
            m, _ = fit_hac(r, X)
        except Exception:
            continue
        brent_coefs = {k: float(m.params.get(f"brent_l{k}", np.nan)) for k in range(0, 7)}
        absvals = {k: abs(v) for k, v in brent_coefs.items() if np.isfinite(v)}
        peak_lag = min(absvals, key=lambda k: -absvals[k]) if absvals else np.nan
        cum_beta = float(np.nansum([brent_coefs[k] for k in range(0, 7)]))
        sig_lags = int(sum((m.pvalues.get(f"brent_l{k}", 1.0) < 0.10) for k in range(0, 7)))
        mat_rows.append({
            "material": col,
            "cum_brent_beta_l0_l6": cum_beta,
            "peak_lag_month": peak_lag,
            "n_sig_lags_p_lt_0_10": sig_lags,
            "adj_r2": float(m.rsquared_adj),
        })

    mats = pd.DataFrame(mat_rows).sort_values("cum_brent_beta_l0_l6", ascending=False)
    mats.to_csv(out_t / "material_brent_pass_through_rank.csv", index=False)

    # 5) Escalation clause adequacy check (CPI-only vs multi-factor)
    y = df["r_cipi_all"]
    X_a = df[["cpi_l0", "cpi_l1", "cpi_l2", "cpi_l3"]]
    X_b = df[["cpi_l0", "cpi_l1", "cpi_l2", "cpi_l3", "fx_l0", "fx_l1", "fx_l2", "fx_l3", "brent_l0", "brent_l1", "brent_l2", "brent_l3"]]

    m_a, _ = fit_hac(y, X_a)
    m_b, _ = fit_hac(y, X_b)
    rmse_a = rolling_oos_rmse(y, X_a)
    rmse_b = rolling_oos_rmse(y, X_b)

    clause = pd.DataFrame([
        {"model": "cpi_only_proxy", "adj_r2": float(m_a.rsquared_adj), "aic": float(m_a.aic), "oos_rmse": rmse_a},
        {"model": "cpi_fx_brent_proxy", "adj_r2": float(m_b.rsquared_adj), "aic": float(m_b.aic), "oos_rmse": rmse_b},
    ])
    clause.to_csv(out_t / "clause_proxy_model_comparison.csv", index=False)

    # 6) figures
    # LP response
    plt.figure(figsize=(10, 4.8))
    plt.plot(lp["h"], lp["beta_brent"], marker="o", label="Brent coefficient")
    plt.fill_between(lp["h"], lp["lo95"], lp["hi95"], alpha=0.2, label="95% CI")
    plt.axhline(0, color="black", linewidth=0.8)
    plt.title("Propagation profile: Brent shock and future CIPI inflation")
    plt.xlabel("Horizon (months)")
    plt.ylabel("Effect on monthly CIPI inflation (pp)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_f / "01_local_projection_profile.png", dpi=180)
    plt.close()

    # top materials
    top = mats.head(10)
    plt.figure(figsize=(10, 5.5))
    plt.barh(top["material"][::-1], top["cum_brent_beta_l0_l6"][::-1])
    plt.axvline(0, color="black", linewidth=0.8)
    plt.title("Top materials by cumulative Brent pass-through (lags 0-6)")
    plt.xlabel("Cumulative coefficient")
    plt.tight_layout()
    plt.savefig(out_f / "02_top_material_pass_through.png", dpi=180)
    plt.close()

    # clause adequacy
    plt.figure(figsize=(7.5, 4.5))
    plt.bar(clause["model"], clause["oos_rmse"], color=["#6b7280", "#2563eb"])
    plt.title("Escalation clause proxy: predictive RMSE")
    plt.ylabel("Out-of-sample RMSE")
    plt.tight_layout()
    plt.savefig(out_f / "03_clause_proxy_oos_rmse.png", dpi=180)
    plt.close()

    # summary metrics
    b_cipi = cipi_terms[cipi_terms["term"].str.startswith("brent_l")]
    cumulative = float(b_cipi["coef"].sum())
    peak_row = b_cipi.loc[b_cipi["coef"].abs().idxmax()] if not b_cipi.empty else None
    peak_lag = int(str(peak_row["term"]).replace("brent_l", "")) if peak_row is not None else None

    summary = {
        "sample_start": str(df.index.min().date()),
        "sample_end": str(df.index.max().date()),
        "n_months": int(df.shape[0]),
        "brent_to_fx_adj_r2": float(m_fx.rsquared_adj),
        "brent_fx_to_cpi_adj_r2": float(m_cpi.rsquared_adj),
        "brent_fx_cpi_to_cipi_adj_r2": float(m_cipi.rsquared_adj),
        "cumulative_brent_pass_through_l0_l6_to_cipi": cumulative,
        "peak_brent_lag_month_for_cipi": peak_lag,
        "clause_proxy_rmse": {
            "cpi_only": rmse_a,
            "cpi_fx_brent": rmse_b,
            "improvement_pct": float((rmse_a - rmse_b) / rmse_a * 100.0) if np.isfinite(rmse_a) and rmse_a != 0 else None,
        },
    }
    with open(out_t / "transmission_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Narrative markdown report
    lines = []
    lines.append("# Brent Transmission and Escalation-Clause Assessment\n")
    lines.append(f"- Sample: {summary['sample_start']} to {summary['sample_end']} ({summary['n_months']} months)")
    lines.append(f"- Estimated cumulative Brent pass-through to monthly `CIPI_ALL` inflation (lags 0-6): {summary['cumulative_brent_pass_through_l0_l6_to_cipi']:.4f}")
    lines.append(f"- Peak Brent lag for construction inflation response: {summary['peak_brent_lag_month_for_cipi']} months")
    lines.append(f"- Clause proxy RMSE (CPI-only): {summary['clause_proxy_rmse']['cpi_only']:.4f}")
    lines.append(f"- Clause proxy RMSE (CPI+FX+Brent): {summary['clause_proxy_rmse']['cpi_fx_brent']:.4f}")
    if summary['clause_proxy_rmse']['improvement_pct'] is not None:
        lines.append(f"- Relative RMSE improvement from adding Brent+FX: {summary['clause_proxy_rmse']['improvement_pct']:.2f}%")
    lines.append("\n## Interpretation")
    lines.append("1. Brent appears to pass through via FX/CPI channels with measurable lags.")
    lines.append("2. Input-level sensitivity is heterogeneous across materials; see ranking table.")
    lines.append("3. If CPI-only proxy is weaker than CPI+FX+Brent, escalation clauses anchored only to CPI may miss imported energy/FX shocks.")
    lines.append("4. For contract practice, treat this as empirical evidence to calibrate coefficients and revision frequency, not legal advice.")

    (out_t / "transmission_policy_summary.md").write_text("\n".join(lines), encoding="utf-8")

    print("Done: transmission results written to results/transmission/")


if __name__ == "__main__":
    main()
