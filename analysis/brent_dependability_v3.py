#!/usr/bin/env python3
"""
Tier A dependability pass.

1. Brent historical regime narrative (full available history + modeling-window zoom).
2. Structural break tests (Chow at known events + rolling-coefficient diagnostic)
   for the Brent -> Diesel link.
3. Block-bootstrap confidence interval on the Brent -> Diesel -> CIPI_ALL
   mediation share.
4. Regularized (ElasticNet) escalation-clause proxy, rolling-origin OOS RMSE,
   vs. the unregularized results from brent_diesel_transmission.py.
5. Mediation loop across every material column to rank diesel's systemic
   importance as a transmission channel, cross-referenced against the
   pre-existing Diebold-Yilmaz SIMI ranking in cio_pipeline-2/p4_simi_ranking.csv.
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
from scipy import stats as sps
from sklearn.linear_model import ElasticNetCV
from sklearn.preprocessing import StandardScaler

RNG = np.random.default_rng(20260914)


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


def rolling_oos_rmse_ols(y: pd.Series, X: pd.DataFrame, start_train: int = 48) -> float:
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


def rolling_oos_rmse_enet(y: pd.Series, X: pd.DataFrame, start_train: int = 48) -> float:
    z = pd.concat([y.rename("y"), X], axis=1).dropna().copy()
    if len(z) <= start_train + 10:
        return float("nan")
    preds, trues = [], []
    l1_ratios = [0.1, 0.5, 0.7, 0.9, 0.95, 0.99, 1.0]
    for i in range(start_train, len(z)):
        train = z.iloc[:i]
        test = z.iloc[i : i + 1]
        scaler = StandardScaler()
        Xtr = scaler.fit_transform(train.drop(columns=["y"]).astype(float))
        Xte = scaler.transform(test.drop(columns=["y"]).astype(float))
        n_splits = min(5, max(2, (len(train) - 1) // 8))
        try:
            model = ElasticNetCV(l1_ratio=l1_ratios, cv=n_splits, max_iter=20000, n_alphas=50)
            model.fit(Xtr, train["y"].astype(float).values)
            p = float(model.predict(Xte)[0])
        except Exception:
            p = float(train["y"].mean())
        preds.append(p)
        trues.append(float(test["y"].iloc[0]))
    return rmse(trues, preds)


def chow_test(y: pd.Series, X: pd.DataFrame, break_date) -> dict:
    z = pd.concat([y.rename("y"), X], axis=1).dropna()
    pre = z[z.index < break_date]
    post = z[z.index >= break_date]
    k = X.shape[1] + 1
    if len(pre) < k + 3 or len(post) < k + 3:
        return {"break_date": str(break_date), "status": "insufficient_obs_in_a_subsample",
                "n_pre": len(pre), "n_post": len(post)}

    def rss(d):
        m = sm.OLS(d["y"], sm.add_constant(d.drop(columns=["y"]))).fit()
        return float(np.sum(m.resid ** 2))

    rss_pooled = rss(z)
    rss_pre = rss(pre)
    rss_post = rss(post)
    n = len(z)
    num = (rss_pooled - (rss_pre + rss_post)) / k
    den = (rss_pre + rss_post) / (n - 2 * k)
    f_stat = num / den if den > 0 else float("nan")
    p_val = float(sps.f.sf(f_stat, k, n - 2 * k)) if np.isfinite(f_stat) else float("nan")
    return {"break_date": str(break_date), "status": "ok", "n_pre": len(pre), "n_post": len(post),
            "f_stat": float(f_stat), "p_value": p_val,
            "interpretation": "reject stability (coefficients differ)" if p_val < 0.05 else "fail to reject stability"}


def block_bootstrap_mediation(df: pd.DataFrame, n_boot: int = 2000, block_len: int = 8) -> pd.DataFrame:
    brent_cols = [f"brent_l{k}" for k in range(0, 7)]
    diesel_cols = [f"diesel_l{k}" for k in range(0, 7)]
    z = pd.concat([df["r_cipi_all"].rename("y"), df[brent_cols + diesel_cols]], axis=1).dropna().reset_index(drop=True)
    n = len(z)
    n_blocks = int(np.ceil(n / block_len))
    rows = []
    for _ in range(n_boot):
        starts = RNG.integers(0, n - block_len + 1, size=n_blocks)
        idx = np.concatenate([np.arange(s, s + block_len) for s in starts])[:n]
        zb = z.iloc[idx].reset_index(drop=True)
        try:
            m_direct = sm.OLS(zb["y"], sm.add_constant(zb[brent_cols])).fit()
            m_med = sm.OLS(zb["y"], sm.add_constant(zb[brent_cols + diesel_cols])).fit()
        except Exception:
            continue
        cum_brent_direct = float(m_direct.params[brent_cols].sum())
        cum_brent_med = float(m_med.params[brent_cols].sum())
        cum_diesel_med = float(m_med.params[diesel_cols].sum())
        absorption = ((cum_brent_direct - cum_brent_med) / cum_brent_direct * 100.0
                      if abs(cum_brent_direct) > 1e-9 else np.nan)
        rows.append({
            "adj_r2_direct": float(m_direct.rsquared_adj),
            "adj_r2_mediated": float(m_med.rsquared_adj),
            "cum_brent_direct": cum_brent_direct,
            "cum_brent_mediated": cum_brent_med,
            "cum_diesel_mediated": cum_diesel_med,
            "absorption_pct": absorption,
        })
    return pd.DataFrame(rows)


def summarize_ci(s: pd.Series) -> dict:
    s = s.dropna()
    return {
        "mean": float(s.mean()), "median": float(s.median()),
        "lo95": float(np.percentile(s, 2.5)), "hi95": float(np.percentile(s, 97.5)),
        "pct_same_sign_as_median": float((np.sign(s) == np.sign(s.median())).mean() * 100.0),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out_t = root / "results" / "transmission_v3" / "tables"
    out_f = root / "results" / "transmission_v3" / "figures"
    out_t.mkdir(parents=True, exist_ok=True)
    out_f.mkdir(parents=True, exist_ok=True)

    panel = pd.read_csv(root / "cio_pipeline-2" / "data" / "processed" / "panel_v1.0.csv")
    panel["date"] = pd.to_datetime(panel["date"])

    # Full-history Brent (for the historical narrative, not clipped to panel window)
    brent_full = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU")
    brent_full.columns = ["date", "brent_usd"]
    brent_full["date"] = pd.to_datetime(brent_full["date"], errors="coerce")
    brent_full["brent_usd"] = pd.to_numeric(brent_full["brent_usd"], errors="coerce")
    brent_full = brent_full.dropna(subset=["date", "brent_usd"]).set_index("date").sort_index()
    brent_m = brent_full["brent_usd"].resample("MS").mean().to_frame("brent_usd").reset_index()

    df = panel.merge(brent_m, on="date", how="left").sort_values("date").set_index("date")
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

    # ---------------------------------------------------------------
    # 1) Brent historical regime narrative
    # ---------------------------------------------------------------
    eras = [
        ("2003-01-01", "2008-06-30", "Pre-GFC boom"),
        ("2008-07-01", "2009-02-28", "GFC crash"),
        ("2009-03-01", "2014-10-31", "Post-GFC high plateau ($90-115)"),
        ("2014-11-01", "2016-01-31", "2014-16 price collapse"),
        ("2016-02-01", "2019-12-31", "Recovery / range-bound ($45-75)"),
        ("2020-01-01", "2020-04-30", "COVID demand shock"),
        ("2020-05-01", "2021-12-31", "COVID recovery"),
        ("2022-01-01", "2022-06-30", "2022 Ukraine-war spike"),
        ("2022-07-01", "2026-04-30", "2022-26 moderation / current regime"),
    ]
    era_rows = []
    bfull_m = brent_full["brent_usd"].resample("MS").mean()
    r_full = 100.0 * np.log(bfull_m).diff()
    for start, end, label in eras:
        seg = bfull_m[start:end]
        r_seg = r_full[start:end].dropna()
        if seg.empty:
            continue
        era_rows.append({
            "era": label, "start": start, "end": end,
            "start_price": float(seg.iloc[0]), "end_price": float(seg.iloc[-1]),
            "min_price": float(seg.min()), "max_price": float(seg.max()),
            "mean_monthly_return_pct": float(r_seg.mean()) if not r_seg.empty else np.nan,
            "monthly_vol_pct": float(r_seg.std()) if not r_seg.empty else np.nan,
            "n_big_moves_gt10pct": int((r_seg.abs() > 10).sum()) if not r_seg.empty else 0,
            "max_drawdown_pct": float((seg / seg.cummax() - 1).min() * 100.0),
        })
    era_df = pd.DataFrame(era_rows)
    era_df.to_csv(out_t / "brent_historical_eras.csv", index=False)

    plt.figure(figsize=(12, 5))
    plt.plot(bfull_m.index, bfull_m.values, color="#1f2937", linewidth=1.1)
    palette = plt.cm.tab10.colors
    for i, (start, end, label) in enumerate(eras):
        plt.axvspan(pd.Timestamp(start), pd.Timestamp(end), color=palette[i % 10], alpha=0.15)
    plt.title("Brent crude (USD/bbl, monthly mean) — full available history by regime")
    plt.ylabel("USD/barrel")
    plt.tight_layout()
    plt.savefig(out_f / "01_brent_full_history_regimes.png", dpi=180)
    plt.close()

    sample = bfull_m[df.index.min():df.index.max()]
    plt.figure(figsize=(12, 5))
    plt.plot(sample.index, sample.values, color="#b45309", linewidth=1.3)
    plt.title(f"Brent crude — modeling window ({df.index.min().date()} to {df.index.max().date()})")
    plt.ylabel("USD/barrel")
    plt.tight_layout()
    plt.savefig(out_f / "02_brent_modeling_window.png", dpi=180)
    plt.close()

    # ---------------------------------------------------------------
    # 2) Structural break tests, Brent -> Diesel
    # ---------------------------------------------------------------
    y_d = df["r_diesel"]
    X_d = df[["brent_l0", "brent_l1"]]
    break_dates = ["2020-03-01", "2022-02-01"]
    chow_results = [chow_test(y_d, X_d, pd.Timestamp(bd)) for bd in break_dates]
    with open(out_t / "structural_break_chow_tests.json", "w", encoding="utf-8") as f:
        json.dump(chow_results, f, indent=2)

    # rolling 36-month coefficient of brent_l0 in the diesel regression
    z_roll = pd.concat([y_d.rename("y"), X_d], axis=1).dropna()
    win = 36
    roll_rows = []
    for i in range(win, len(z_roll) + 1):
        seg = z_roll.iloc[i - win : i]
        try:
            m = sm.OLS(seg["y"], sm.add_constant(seg.drop(columns=["y"]))).fit()
            roll_rows.append({"date": seg.index[-1], "brent_l0_coef": float(m.params.get("brent_l0", np.nan)),
                               "brent_l1_coef": float(m.params.get("brent_l1", np.nan))})
        except Exception:
            continue
    roll_df = pd.DataFrame(roll_rows)
    roll_df.to_csv(out_t / "rolling36m_brent_diesel_coeffs.csv", index=False)

    plt.figure(figsize=(11, 4.8))
    plt.plot(roll_df["date"], roll_df["brent_l0_coef"], label="Brent (lag 0) coef", color="#2563eb")
    plt.plot(roll_df["date"], roll_df["brent_l1_coef"], label="Brent (lag 1) coef", color="#b45309")
    plt.axhline(0, color="black", linewidth=0.8)
    for bd in break_dates:
        plt.axvline(pd.Timestamp(bd), color="gray", linestyle="--", linewidth=1)
    plt.title("Rolling 36-month Brent->Diesel coefficient (stability diagnostic)")
    plt.ylabel("Coefficient")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_f / "03_rolling_brent_diesel_coeff.png", dpi=180)
    plt.close()

    # ---------------------------------------------------------------
    # 3) Block-bootstrap mediation CI (Brent -> Diesel -> CIPI_ALL)
    # ---------------------------------------------------------------
    boot = block_bootstrap_mediation(df, n_boot=2000, block_len=8)
    boot.to_csv(out_t / "mediation_bootstrap_draws.csv", index=False)
    mediation_ci = {col: summarize_ci(boot[col]) for col in boot.columns}
    with open(out_t / "mediation_bootstrap_summary.json", "w", encoding="utf-8") as f:
        json.dump(mediation_ci, f, indent=2)

    plt.figure(figsize=(9, 4.8))
    plt.hist(boot["absorption_pct"].clip(-200, 200), bins=50, color="#059669", alpha=0.85)
    plt.axvline(mediation_ci["absorption_pct"]["median"], color="black", linestyle="--",
                label=f"median {mediation_ci['absorption_pct']['median']:.1f}%")
    plt.title("Block-bootstrap: % of Brent's CIPI effect absorbed by diesel")
    plt.xlabel("Absorption (%)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_f / "04_mediation_bootstrap_hist.png", dpi=180)
    plt.close()

    # ---------------------------------------------------------------
    # 4) Regularized clause proxy (ElasticNet rolling-origin OOS RMSE)
    # ---------------------------------------------------------------
    y = df["r_cipi_all"]
    specs = {
        "cpi_only": df[["cpi_l0", "cpi_l1", "cpi_l2", "cpi_l3"]],
        "cpi_diesel": df[["cpi_l0", "cpi_l1", "cpi_l2", "cpi_l3", "diesel_l0", "diesel_l1", "diesel_l2", "diesel_l3"]],
        "cpi_fx_brent_diesel": df[["cpi_l0", "cpi_l1", "cpi_l2", "cpi_l3",
                                    "fx_l0", "fx_l1", "fx_l2", "fx_l3",
                                    "brent_l0", "brent_l1", "brent_l2", "brent_l3",
                                    "diesel_l0", "diesel_l1", "diesel_l2", "diesel_l3"]],
    }
    reg_rows = []
    for name, X in specs.items():
        ols_rmse = rolling_oos_rmse_ols(y, X)
        enet_rmse = rolling_oos_rmse_enet(y, X)
        reg_rows.append({"model": name, "oos_rmse_ols": ols_rmse, "oos_rmse_elasticnet": enet_rmse})
    reg_df = pd.DataFrame(reg_rows)
    naive_rmse = float(np.sqrt(np.mean((y.dropna().iloc[48:].values) ** 2))) if len(y.dropna()) > 48 else np.nan
    # naive persistence RMSE over the same rolling-origin test span, for a fair reference line
    z_naive = y.dropna()
    naive_preds = z_naive.shift(1).iloc[48:]
    naive_true = z_naive.iloc[48:]
    naive_rmse = rmse(naive_true.dropna(), naive_preds.reindex(naive_true.dropna().index))
    reg_df["naive_persistence_rmse_ref"] = naive_rmse
    reg_df.to_csv(out_t / "clause_proxy_regularized_comparison.csv", index=False)

    plt.figure(figsize=(9, 5))
    x = np.arange(len(reg_df))
    w = 0.35
    plt.bar(x - w / 2, reg_df["oos_rmse_ols"], width=w, label="OLS", color="#6b7280")
    plt.bar(x + w / 2, reg_df["oos_rmse_elasticnet"], width=w, label="ElasticNet", color="#059669")
    plt.axhline(naive_rmse, color="#dc2626", linestyle="--", label=f"naive persistence ({naive_rmse:.3f})")
    plt.xticks(x, reg_df["model"], rotation=15)
    plt.ylabel("Out-of-sample RMSE")
    plt.title("OLS vs. regularized (ElasticNet) escalation-proxy RMSE")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_f / "05_regularized_clause_proxy_rmse.png", dpi=180)
    plt.close()

    # ---------------------------------------------------------------
    # 5) Mediation loop across every material -> systemic importance ranking
    # ---------------------------------------------------------------
    macro_cols = {"central_bank_rate", "cpi", "exchange_rate", "lending_rate", "private_credit", "brent_usd"}
    known_non_material = {"CIPI_ALL", "CIPI_BLDG", "CIPI_CIVIL", "CIPI_MAT", "DIESEL"}
    material_cols = [c for c in panel.columns if c not in (["date"] + list(macro_cols) + list(known_non_material))]

    brent_cols = [f"brent_l{k}" for k in range(0, 7)]
    diesel_cols = [f"diesel_l{k}" for k in range(0, 7)]
    med_rows = []
    for col in material_cols:
        r = dlog(df[col])
        try:
            m_direct, _ = fit_hac(r, df[brent_cols])
            m_med, _ = fit_hac(r, df[brent_cols + diesel_cols])
        except Exception:
            continue
        cum_brent_direct = float(m_direct.params[brent_cols].sum())
        cum_brent_med = float(m_med.params[brent_cols].sum())
        cum_diesel_med = float(m_med.params[diesel_cols].sum())
        adj_r2_gain = float(m_med.rsquared_adj - m_direct.rsquared_adj)
        absorption = ((cum_brent_direct - cum_brent_med) / cum_brent_direct * 100.0
                      if abs(cum_brent_direct) > 1e-6 else np.nan)
        med_rows.append({
            "material": col,
            "adj_r2_direct_brent_only": float(m_direct.rsquared_adj),
            "adj_r2_mediated_brent_plus_diesel": float(m_med.rsquared_adj),
            "adj_r2_gain_from_diesel": adj_r2_gain,
            "cum_diesel_beta_mediated": cum_diesel_med,
            "cum_brent_beta_direct": cum_brent_direct,
            "cum_brent_beta_mediated": cum_brent_med,
            "brent_absorption_by_diesel_pct": absorption,
        })
    med_df = pd.DataFrame(med_rows).sort_values("adj_r2_gain_from_diesel", ascending=False)

    simi_path = root / "cio_pipeline-2" / "p4_simi_ranking.csv"
    if simi_path.exists():
        simi = pd.read_csv(simi_path)
        simi.columns = ["material"] + list(simi.columns[1:])
        med_df = med_df.merge(simi[["material", "SIMI", "to_others", "from_others", "net"]],
                               on="material", how="left")
    med_df.to_csv(out_t / "material_systemic_importance_via_diesel.csv", index=False)

    top = med_df.dropna(subset=["adj_r2_gain_from_diesel"]).head(12)
    plt.figure(figsize=(10, 6))
    plt.barh(top["material"][::-1], top["adj_r2_gain_from_diesel"][::-1], color="#b45309")
    plt.axvline(0, color="black", linewidth=0.8)
    plt.title("Diesel's incremental explanatory power by material (adj. R2 gain over Brent-only)")
    plt.xlabel("Adj. R2 gain from adding diesel")
    plt.tight_layout()
    plt.savefig(out_f / "06_diesel_systemic_importance_by_material.png", dpi=180)
    plt.close()

    diesel_row = med_df[med_df["material"] == "DIESEL"] if "DIESEL" in med_df["material"].values else None
    diesel_rank_by_gain = int((med_df["adj_r2_gain_from_diesel"] > med_df.loc[med_df["material"] == "DIESEL", "adj_r2_gain_from_diesel"].values[0]).sum() + 1) \
        if "DIESEL" in med_df["material"].values else None

    diesel_simi_rank = None
    if simi_path.exists() and "DIESEL" in med_df["material"].values:
        diesel_simi = med_df.loc[med_df["material"] == "DIESEL", "SIMI"]
        if not diesel_simi.empty and pd.notna(diesel_simi.values[0]):
            diesel_simi_rank = int((med_df["SIMI"] > diesel_simi.values[0]).sum() + 1)

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------
    summary = {
        "sample_start": str(df.index.min().date()),
        "sample_end": str(df.index.max().date()),
        "n_months": int(df.shape[0]),
        "brent_full_history_start": str(bfull_m.index.min().date()),
        "brent_full_history_end": str(bfull_m.index.max().date()),
        "structural_breaks_brent_to_diesel": chow_results,
        "mediation_bootstrap_ci": mediation_ci,
        "clause_proxy_regularized": reg_df.to_dict(orient="records"),
        "material_systemic_importance_top5_by_diesel_adj_r2_gain": med_df.head(5)[
            ["material", "adj_r2_gain_from_diesel", "brent_absorption_by_diesel_pct"]
        ].to_dict(orient="records"),
        "diesel_rank_by_own_diesel_gain_metric": diesel_rank_by_gain,
        "diesel_rank_by_pre_existing_simi": diesel_simi_rank,
    }
    with open(out_t / "dependability_v3_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    lines = []
    lines.append("# Tier A Dependability Pass — Summary\n")
    lines.append(f"- Modeling sample: {summary['sample_start']} to {summary['sample_end']} ({summary['n_months']} months)")
    lines.append(f"- Brent full history used for regime narrative: {summary['brent_full_history_start']} to {summary['brent_full_history_end']}\n")

    lines.append("## Structural break tests (Brent -> Diesel, Chow test at known events)")
    for r in chow_results:
        if r.get("status") == "ok":
            lines.append(f"- Break at {r['break_date'][:10]}: F={r['f_stat']:.3f}, p={r['p_value']:.4f} -> {r['interpretation']}")
        else:
            lines.append(f"- Break at {r['break_date'][:10]}: {r['status']} (n_pre={r.get('n_pre')}, n_post={r.get('n_post')})")

    lines.append("\n## Mediation bootstrap (2000 block-bootstrap draws, block=8 months)")
    a = mediation_ci["absorption_pct"]
    lines.append(f"- Brent-effect-on-CIPI absorbed by diesel: median {a['median']:.1f}%, "
                 f"95% CI [{a['lo95']:.1f}%, {a['hi95']:.1f}%], "
                 f"same sign as median in {a['pct_same_sign_as_median']:.0f}% of draws")
    g = mediation_ci["adj_r2_mediated"]
    lines.append(f"- Adj. R2 with diesel included: median {g['median']:.3f} [{g['lo95']:.3f}, {g['hi95']:.3f}]")

    lines.append("\n## Regularized escalation-clause proxy (rolling-origin OOS RMSE)")
    lines.append(f"- Naive persistence reference RMSE: {naive_rmse:.4f}")
    for _, r in reg_df.iterrows():
        lines.append(f"- {r['model']}: OLS {r['oos_rmse_ols']:.4f} | ElasticNet {r['oos_rmse_elasticnet']:.4f}")

    lines.append("\n## Material systemic-importance ranking (diesel as mediator)")
    lines.append("Top 5 materials by adj. R2 gain from adding diesel to a Brent-only model:")
    for r in summary["material_systemic_importance_top5_by_diesel_adj_r2_gain"]:
        lines.append(f"- {r['material']}: adj R2 gain {r['adj_r2_gain_from_diesel']:.3f}, "
                     f"Brent-effect absorption by diesel {r['brent_absorption_by_diesel_pct']:.1f}%")
    if diesel_rank_by_gain is not None:
        lines.append(f"- DIESEL itself ranks #{diesel_rank_by_gain} by this metric (trivially near the top, since it's the mediator).")
    if diesel_simi_rank is not None:
        lines.append(f"- Cross-check against the pre-existing Diebold-Yilmaz SIMI ranking "
                     f"(cio_pipeline-2/p4_simi_ranking.csv, a domestic material-to-material spillover network, "
                     f"independent of Brent): DIESEL ranks #{diesel_simi_rank} there. "
                     "SIMI measures domestic cross-material spillover connectivity; this analysis measures "
                     "which material best carries the *external* Brent shock. They can legitimately disagree.")

    (out_t / "dependability_v3_policy_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("Done: dependability v3 results written to results/transmission_v3/")


if __name__ == "__main__":
    main()
