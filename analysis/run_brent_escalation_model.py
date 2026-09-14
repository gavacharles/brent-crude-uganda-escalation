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
    s = pd.to_numeric(s, errors="coerce")
    return 100.0 * np.log(s).diff()


def prepare_data(panel_path: Path) -> pd.DataFrame:
    panel = pd.read_csv(panel_path)
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.sort_values("date")

    # Brent from FRED (daily) -> monthly mean (month-start timestamp)
    brent_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU"
    brent = pd.read_csv(brent_url)
    brent.columns = ["date", "brent_usd"]
    brent["date"] = pd.to_datetime(brent["date"], errors="coerce")
    brent["brent_usd"] = pd.to_numeric(brent["brent_usd"], errors="coerce")
    brent = brent.dropna(subset=["date", "brent_usd"]).set_index("date").sort_index()
    brent_m = brent.resample("MS").mean().reset_index()

    df = panel.merge(brent_m, on="date", how="left")

    cols = [
        "date",
        "CIPI_ALL",
        "brent_usd",
        "exchange_rate",
        "cpi",
        "private_credit",
        "lending_rate",
        "central_bank_rate",
    ]
    df = df[cols].copy()

    df["y"] = dlog(df["CIPI_ALL"])
    df["x_brent"] = dlog(df["brent_usd"])
    df["x_fx"] = dlog(df["exchange_rate"])
    df["x_cpi"] = dlog(df["cpi"])
    df["x_credit"] = dlog(df["private_credit"])
    df["x_lend_d"] = pd.to_numeric(df["lending_rate"], errors="coerce").diff()
    df["x_cbr_d"] = pd.to_numeric(df["central_bank_rate"], errors="coerce").diff()

    for k in range(0, 7):
        df[f"brent_l{k}"] = df["x_brent"].shift(k)
    for k in range(0, 4):
        df[f"fx_l{k}"] = df["x_fx"].shift(k)
        df[f"cpi_l{k}"] = df["x_cpi"].shift(k)

    df["y_l1"] = df["y"].shift(1)
    df["month"] = df["date"].dt.month.astype("Int64")

    return df


def fit_and_forecast(df: pd.DataFrame) -> tuple[sm.regression.linear_model.RegressionResultsWrapper, pd.DataFrame, dict]:
    brent_cols = [f"brent_l{k}" for k in range(0, 7)]
    fx_cols = [f"fx_l{k}" for k in range(0, 4)]
    cpi_cols = [f"cpi_l{k}" for k in range(0, 4)]
    other_cols = ["x_credit", "x_lend_d", "x_cbr_d", "y_l1"]

    base = df[["date", "y", "CIPI_ALL"] + brent_cols + fx_cols + cpi_cols + other_cols + ["month"]].copy()
    model_df = base.dropna().copy()

    dummies = pd.get_dummies(model_df["month"].astype(int), prefix="m", drop_first=True)
    X = pd.concat([model_df[brent_cols + fx_cols + cpi_cols + other_cols], dummies], axis=1)
    X = X.apply(pd.to_numeric, errors="coerce").astype(float)
    X = sm.add_constant(X)
    y = pd.to_numeric(model_df["y"], errors="coerce").astype(float)

    split_idx = int(len(model_df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    test_dates = model_df["date"].iloc[split_idx:]

    model = sm.OLS(y_train, X_train).fit(cov_type="HAC", cov_kwds={"maxlags": 3})

    pred_test = model.predict(X_test)
    naive_test = y.shift(1).iloc[split_idx:]

    out = pd.DataFrame(
        {
            "date": test_dates.values,
            "y_actual": y_test.values,
            "y_pred": pred_test.values,
            "y_naive": naive_test.values,
        }
    )

    # Convert return forecasts to index path forecasts for visual interpretation
    idx_start = float(model_df["CIPI_ALL"].iloc[split_idx - 1])
    out = out.sort_values("date").reset_index(drop=True)
    out["idx_actual"] = idx_start * np.exp(np.cumsum(out["y_actual"] / 100.0))
    out["idx_pred"] = idx_start * np.exp(np.cumsum(out["y_pred"] / 100.0))
    out["idx_naive"] = idx_start * np.exp(np.cumsum(out["y_naive"].fillna(0.0) / 100.0))

    metrics = {
        "n_obs_model": int(len(model_df)),
        "n_obs_train": int(len(X_train)),
        "n_obs_test": int(len(X_test)),
        "r2_train": float(model.rsquared),
        "adj_r2_train": float(model.rsquared_adj),
        "mae_test": float(np.mean(np.abs(out["y_actual"] - out["y_pred"]))),
        "rmse_test": float(np.sqrt(np.mean((out["y_actual"] - out["y_pred"]) ** 2))),
        "mae_test_naive": float(np.mean(np.abs(out["y_actual"] - out["y_naive"]))),
        "rmse_test_naive": float(np.sqrt(np.mean((out["y_actual"] - out["y_naive"]) ** 2))),
    }

    return model, out, metrics


def save_outputs(df: pd.DataFrame, model, fcst: pd.DataFrame, metrics: dict, out_root: Path) -> None:
    fig_dir = out_root / "figures"
    tab_dir = out_root / "tables"
    fig_dir.mkdir(parents=True, exist_ok=True)
    tab_dir.mkdir(parents=True, exist_ok=True)

    # Tables
    fcst.to_csv(tab_dir / "forecast_test_window.csv", index=False)

    params = model.params
    bse = model.bse
    pvals = model.pvalues
    coef = pd.DataFrame({"term": params.index, "coef": params.values, "std_err": bse.values, "p_value": pvals.values})
    coef.to_csv(tab_dir / "ardl_coefficients.csv", index=False)

    with open(tab_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    # Figure 1: Normalized levels
    plot_df = df[["date", "CIPI_ALL", "brent_usd"]].dropna().copy()
    plot_df = plot_df.sort_values("date")
    plot_df["cipi_norm"] = 100 * plot_df["CIPI_ALL"] / plot_df["CIPI_ALL"].iloc[0]
    plot_df["brent_norm"] = 100 * plot_df["brent_usd"] / plot_df["brent_usd"].iloc[0]

    plt.figure(figsize=(11, 5))
    plt.plot(plot_df["date"], plot_df["cipi_norm"], label="CIPI_ALL (normalized)")
    plt.plot(plot_df["date"], plot_df["brent_norm"], label="Brent USD (normalized)")
    plt.title("Uganda Construction Index vs Brent (normalized to 100)")
    plt.ylabel("Index (start=100)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(fig_dir / "01_cipi_vs_brent_normalized.png", dpi=180)
    plt.close()

    # Figure 2: Cross-correlation profile
    tmp = df[["y", "x_brent"]].dropna().copy()
    lags = list(range(0, 13))
    c = []
    for k in lags:
        s = tmp["x_brent"].shift(k)
        c.append(tmp["y"].corr(s))

    plt.figure(figsize=(10, 4.5))
    plt.bar(lags, c)
    plt.axhline(0, color="black", linewidth=0.8)
    plt.title("Correlation: Brent return lag k vs CIPI_ALL inflation")
    plt.xlabel("Lag k (months)")
    plt.ylabel("Correlation")
    plt.tight_layout()
    plt.savefig(fig_dir / "02_brent_lag_correlation.png", dpi=180)
    plt.close()

    # Figure 3: Brent lag coefficients with 95% CI
    coef_b = coef[coef["term"].str.startswith("brent_l")].copy()
    coef_b["lag"] = coef_b["term"].str.replace("brent_l", "", regex=False).astype(int)
    coef_b = coef_b.sort_values("lag")
    ci = 1.96 * coef_b["std_err"]

    plt.figure(figsize=(10, 4.5))
    plt.errorbar(coef_b["lag"], coef_b["coef"], yerr=ci, fmt="o-", capsize=4)
    plt.axhline(0, color="black", linewidth=0.8)
    plt.title("Estimated Brent pass-through coefficients by lag")
    plt.xlabel("Lag (months)")
    plt.ylabel("Coefficient on Brent return")
    plt.tight_layout()
    plt.savefig(fig_dir / "03_brent_lag_coefficients.png", dpi=180)
    plt.close()

    # Figure 4: Forecast performance on test window (index path)
    plt.figure(figsize=(11, 5))
    plt.plot(fcst["date"], fcst["idx_actual"], label="Actual CIPI_ALL path")
    plt.plot(fcst["date"], fcst["idx_pred"], label="Model forecast path")
    plt.plot(fcst["date"], fcst["idx_naive"], label="Naive benchmark path", linestyle="--")
    plt.title("Test-window forecast: CIPI_ALL index path")
    plt.ylabel("Index level")
    plt.legend()
    plt.tight_layout()
    plt.savefig(fig_dir / "04_test_forecast_index_path.png", dpi=180)
    plt.close()

    # Figure 5: Scenario shock sensitivity
    cum_beta = float(coef_b["coef"].sum())
    shocks = np.array([-20, -10, 10, 20], dtype=float)
    impacts = cum_beta * shocks

    sc = pd.DataFrame({"brent_shock_pct": shocks, "estimated_monthly_inflation_impact_pp": impacts})
    sc.to_csv(tab_dir / "scenario_shock_impacts.csv", index=False)

    plt.figure(figsize=(8, 4.5))
    colors = ["#1b9e77" if x < 0 else "#d95f02" for x in impacts]
    plt.bar([str(int(s)) + "%" for s in shocks], impacts, color=colors)
    plt.axhline(0, color="black", linewidth=0.8)
    plt.title("Scenario sensitivity: Brent shock vs estimated CIPI inflation impact")
    plt.xlabel("Brent shock")
    plt.ylabel("Estimated impact (percentage points)")
    plt.tight_layout()
    plt.savefig(fig_dir / "05_scenario_brent_shock_impacts.png", dpi=180)
    plt.close()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    panel_path = root / "cio_pipeline-2" / "data" / "processed" / "panel_v1.0.csv"
    out_root = root / "results"

    df = prepare_data(panel_path)
    model, fcst, metrics = fit_and_forecast(df)
    save_outputs(df, model, fcst, metrics, out_root)

    print("Done. Results written to:")
    print(out_root / "figures")
    print(out_root / "tables")
    print("Metrics:")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
