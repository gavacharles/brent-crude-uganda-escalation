#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNetCV, RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import statsmodels.api as sm

warnings.filterwarnings("ignore")


def dlog(s: pd.Series) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce")
    return 100.0 * np.log(x).diff()


def winsorize(s: pd.Series, q_low: float = 0.01, q_high: float = 0.99) -> pd.Series:
    x = s.copy()
    lo, hi = x.quantile(q_low), x.quantile(q_high)
    return x.clip(lower=lo, upper=hi)


def ensure_upstream(root: Path) -> Path:
    repo = root / "cio_pipeline-2"
    if not repo.exists():
        subprocess.run(
            ["git", "clone", "https://github.com/gavacharles/cio_pipeline-2.git", str(repo)],
            check=True,
        )
    return repo


def prepare(root: Path) -> pd.DataFrame:
    upstream = ensure_upstream(root)
    panel = pd.read_csv(upstream / "data" / "processed" / "panel_v1.0.csv")
    panel["date"] = pd.to_datetime(panel["date"])

    brent = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU")
    brent.columns = ["date", "brent_usd"]
    brent["date"] = pd.to_datetime(brent["date"], errors="coerce")
    brent["brent_usd"] = pd.to_numeric(brent["brent_usd"], errors="coerce")
    brent = brent.dropna(subset=["date", "brent_usd"]).set_index("date").sort_index().resample("MS").mean().reset_index()

    df = panel.merge(brent, on="date", how="left").sort_values("date")

    for c in ["CIPI_ALL", "exchange_rate", "cpi", "private_credit", "brent_usd"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["y"] = winsorize(dlog(df["CIPI_ALL"]))
    df["x_brent"] = winsorize(dlog(df["brent_usd"]))
    df["x_fx"] = winsorize(dlog(df["exchange_rate"]))
    df["x_cpi"] = winsorize(dlog(df["cpi"]))
    df["x_credit"] = winsorize(dlog(df["private_credit"]))

    for k in range(0, 7):
        df[f"b_l{k}"] = df["x_brent"].shift(k)
    for k in range(0, 4):
        df[f"fx_l{k}"] = df["x_fx"].shift(k)
        df[f"cpi_l{k}"] = df["x_cpi"].shift(k)
    for k in range(1, 4):
        df[f"y_l{k}"] = df["y"].shift(k)

    return df


def evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    err = y_true - y_pred
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(mean_squared_error(y_true, y_pred) ** 0.5)
    mape = float(np.mean(np.abs(err) / np.maximum(np.abs(y_true), 1e-3)) * 100.0)
    da = float(np.mean(np.sign(y_true) == np.sign(y_pred)) * 100.0)
    return {"mae": mae, "rmse": rmse, "mape_pct": mape, "directional_accuracy_pct": da}


def build_dataset(df: pd.DataFrame, horizon: int) -> tuple[pd.DataFrame, list[str]]:
    d = df.copy()
    if horizon == 1:
        d["target"] = d["y"].shift(-1)
    else:
        d["target"] = 100.0 * (np.log(d["CIPI_ALL"]).shift(-horizon) - np.log(d["CIPI_ALL"]))

    for k in range(0, 4):
        d[f"credit_l{k}"] = d["x_credit"].shift(k)

    for k in range(1, 7):
        d[f"y_l{k}"] = d["y"].shift(k)

    features = [c for c in d.columns if c.startswith(("b_l", "fx_l", "cpi_l", "y_l", "credit_l"))]
    data = d[["date", "target"] + features + ["CIPI_ALL"]].dropna().reset_index(drop=True)
    return data, features


def run_calibration_one_horizon(data: pd.DataFrame, features: list[str], horizon: int) -> tuple[pd.DataFrame, dict]:
    n = len(data)
    test_n = min(18, max(12, n // 5))
    val_n = min(12, max(8, (n - test_n) // 5))

    train_core_end = n - test_n - val_n
    val_end = n - test_n

    if train_core_end < 36:
        raise RuntimeError(f"Not enough observations for horizon {horizon}.")

    X = data[features].to_numpy(dtype=float)
    y = data["target"].to_numpy(dtype=float)
    dates = data["date"].to_numpy()

    # --- validation stage (alpha tuning for blend) ---
    ridge_pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("ridge", RidgeCV(alphas=np.logspace(-4, 4, 60))),
    ])

    enet_pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("enet", ElasticNetCV(alphas=np.logspace(-4, 1, 50), l1_ratio=[0.1, 0.3, 0.5, 0.7, 0.9], cv=5, max_iter=15000)),
    ])

    ridge_pipe.fit(X[:train_core_end], y[:train_core_end])
    enet_pipe.fit(X[:train_core_end], y[:train_core_end])

    y_val = y[train_core_end:val_end]
    ridge_val = ridge_pipe.predict(X[train_core_end:val_end])
    enet_val = enet_pipe.predict(X[train_core_end:val_end])
    # Naive baseline: persistence of previous target value
    naive_val = np.array([y[i - 1] for i in range(train_core_end, val_end)])

    best_alpha = 0.0
    best_rmse = 1e18
    for a in np.linspace(0.0, 1.0, 101):
        blend = a * ridge_val + (1.0 - a) * naive_val
        rmse = float(mean_squared_error(y_val, blend) ** 0.5)
        if rmse < best_rmse:
            best_rmse = rmse
            best_alpha = float(a)

    val_errors = y_val - (best_alpha * ridge_val + (1.0 - best_alpha) * naive_val)
    q80 = float(np.quantile(np.abs(val_errors), 0.80))
    q90 = float(np.quantile(np.abs(val_errors), 0.90))

    # --- test stage (expanding one-step forecasts) ---
    rows = []
    for i in range(val_end, n):
        ridge = Pipeline([
            ("scaler", StandardScaler()),
            ("ridge", RidgeCV(alphas=np.logspace(-4, 4, 60))),
        ])
        enet = Pipeline([
            ("scaler", StandardScaler()),
            ("enet", ElasticNetCV(alphas=np.logspace(-4, 1, 40), l1_ratio=[0.1, 0.3, 0.5, 0.7, 0.9], cv=5, max_iter=15000)),
        ])

        ridge.fit(X[:i], y[:i])
        enet.fit(X[:i], y[:i])

        y_true = float(y[i])
        y_naive = float(y[i - 1])
        y_ridge = float(ridge.predict(X[i : i + 1])[0])
        y_enet = float(enet.predict(X[i : i + 1])[0])
        y_blend = best_alpha * y_ridge + (1.0 - best_alpha) * y_naive

        rows.append(
            {
                "date": dates[i],
                "y_true": y_true,
                "y_naive": y_naive,
                "y_ridge": y_ridge,
                "y_enet": y_enet,
                "y_blend": y_blend,
                "blend_lo80": y_blend - q80,
                "blend_hi80": y_blend + q80,
                "blend_lo90": y_blend - q90,
                "blend_hi90": y_blend + q90,
            }
        )

    pred = pd.DataFrame(rows)
    pred["date"] = pd.to_datetime(pred["date"])

    metrics = {
        "horizon_months": int(horizon),
        "n_obs_total": int(n),
        "n_obs_train_core": int(train_core_end),
        "n_obs_validation": int(val_n),
        "n_obs_test": int(test_n),
        "blend_alpha_ridge_weight": float(best_alpha),
        "naive": evaluate(pred["y_true"].to_numpy(), pred["y_naive"].to_numpy()),
        "ridge": evaluate(pred["y_true"].to_numpy(), pred["y_ridge"].to_numpy()),
        "elastic_net": evaluate(pred["y_true"].to_numpy(), pred["y_enet"].to_numpy()),
        "blend": evaluate(pred["y_true"].to_numpy(), pred["y_blend"].to_numpy()),
    }

    in80 = (pred["y_true"].between(pred["blend_lo80"], pred["blend_hi80"])).mean() * 100.0
    in90 = (pred["y_true"].between(pred["blend_lo90"], pred["blend_hi90"])).mean() * 100.0
    metrics["blend_interval_coverage_pct"] = {"pi80": float(in80), "pi90": float(in90)}

    # Convert predicted returns to index paths for visualization
    idx_start = float(data.loc[val_end - 1, "CIPI_ALL"])
    pred = pred.sort_values("date").reset_index(drop=True)
    for c in ["y_true", "y_naive", "y_ridge", "y_blend"]:
        pred[f"idx_{c.split('_')[-1]}"] = idx_start * np.exp(np.cumsum(pred[c].to_numpy() / 100.0))

    return pred, metrics


def estimate_pass_through(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in df.columns if c.startswith(("b_l", "fx_l", "cpi_l", "y_l", "credit_l"))]
    z = df[["y"] + cols].dropna().copy()
    X = sm.add_constant(z[cols].astype(float))
    y = z["y"].astype(float)
    m = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 3})

    out = pd.DataFrame(
        {
            "term": m.params.index,
            "coef": m.params.values,
            "std_err": m.bse.values,
            "p_value": m.pvalues.values,
        }
    )
    return out


def select_champion(results: dict[int, dict]) -> tuple[int, dict]:
    # Prefer positive RMSE skill vs naive; otherwise choose the lowest RMSE overall
    best_h = None
    best_score = -1e9
    for h, r in results.items():
        naive_rmse = r["metrics"]["naive"]["rmse"]
        blend_rmse = r["metrics"]["blend"]["rmse"]
        skill = (naive_rmse - blend_rmse) / max(naive_rmse, 1e-9)
        da = r["metrics"]["blend"]["directional_accuracy_pct"]
        score = skill + 0.002 * da
        if score > best_score:
            best_score = score
            best_h = h

    assert best_h is not None
    return best_h, results[best_h]


def save_outputs(root: Path, pred: pd.DataFrame, metrics: dict, coefs: pd.DataFrame, horizon_results: pd.DataFrame) -> None:
    out = root / "results" / "round2"
    fig_dir = out / "figures"
    tab_dir = out / "tables"
    fig_dir.mkdir(parents=True, exist_ok=True)
    tab_dir.mkdir(parents=True, exist_ok=True)

    pred.to_csv(tab_dir / "test_predictions.csv", index=False)
    coefs.to_csv(tab_dir / "pass_through_coefficients.csv", index=False)
    horizon_results.to_csv(tab_dir / "horizon_model_selection.csv", index=False)

    model_rows = []
    for k in ["naive", "ridge", "elastic_net", "blend"]:
        row = {"model": k}
        row.update(metrics[k])
        model_rows.append(row)
    pd.DataFrame(model_rows).to_csv(tab_dir / "model_comparison.csv", index=False)

    with open(tab_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    # Figure A: Model RMSE comparison (champion horizon)
    mc = pd.DataFrame(model_rows)
    plt.figure(figsize=(8, 4.5))
    plt.bar(mc["model"], mc["rmse"], color=["#6b7280", "#2563eb", "#16a34a", "#dc2626"])
    plt.title("Calibration Round 2: RMSE by model")
    plt.ylabel("RMSE (percentage points)")
    plt.tight_layout()
    plt.savefig(fig_dir / "01_model_rmse_comparison.png", dpi=180)
    plt.close()

    # Figure A2: Horizon skill chart
    hs = horizon_results.copy()
    plt.figure(figsize=(8.5, 4.5))
    plt.plot(hs["horizon_months"], hs["naive_rmse"], marker="o", label="Naive RMSE")
    plt.plot(hs["horizon_months"], hs["blend_rmse"], marker="o", label="Blend RMSE")
    plt.title("Calibration Round 2: RMSE by horizon")
    plt.xlabel("Forecast horizon (months)")
    plt.ylabel("RMSE")
    plt.legend()
    plt.tight_layout()
    plt.savefig(fig_dir / "00_horizon_selection_rmse.png", dpi=180)
    plt.close()

    # Figure B: Actual vs blend forecast with PI90
    plt.figure(figsize=(11, 5))
    plt.plot(pred["date"], pred["y_true"], label="Actual inflation")
    plt.plot(pred["date"], pred["y_blend"], label="Blend forecast")
    plt.fill_between(pred["date"], pred["blend_lo90"], pred["blend_hi90"], alpha=0.2, label="PI90")
    plt.axhline(0, color="black", linewidth=0.8)
    plt.title("Round 2 Test Window: Actual vs blend forecast (monthly inflation)")
    plt.ylabel("Percent")
    plt.legend()
    plt.tight_layout()
    plt.savefig(fig_dir / "02_blend_forecast_with_pi90.png", dpi=180)
    plt.close()

    # Figure C: Index path comparison
    plt.figure(figsize=(11, 5))
    plt.plot(pred["date"], pred["idx_true"], label="Actual index path")
    plt.plot(pred["date"], pred["idx_naive"], label="Naive path", linestyle="--")
    plt.plot(pred["date"], pred["idx_blend"], label="Blend path")
    plt.title("Round 2 Test Window: CIPI_ALL index path")
    plt.ylabel("Index")
    plt.legend()
    plt.tight_layout()
    plt.savefig(fig_dir / "03_index_path_actual_vs_models.png", dpi=180)
    plt.close()

    # Figure D: Brent lag coefficients
    b = coefs[coefs["term"].str.startswith("b_l")].copy()
    b["lag"] = b["term"].str.replace("b_l", "", regex=False).astype(int)
    b = b.sort_values("lag")
    ci = 1.96 * b["std_err"]
    plt.figure(figsize=(9, 4.5))
    plt.errorbar(b["lag"], b["coef"], yerr=ci, fmt="o-", capsize=4)
    plt.axhline(0, color="black", linewidth=0.8)
    plt.title("Round 2: Brent pass-through coefficients by lag")
    plt.xlabel("Lag (months)")
    plt.ylabel("Coefficient")
    plt.tight_layout()
    plt.savefig(fig_dir / "04_brent_pass_through_lags.png", dpi=180)
    plt.close()

    # concise markdown summary
    naive_rmse = metrics["naive"]["rmse"]
    blend_rmse = metrics["blend"]["rmse"]
    skill = (naive_rmse - blend_rmse) / max(naive_rmse, 1e-9) * 100.0
    with open(out / "summary.md", "w", encoding="utf-8") as f:
        f.write("# Calibration Round 2 Summary\n\n")
        f.write(f"- Champion horizon: {metrics['horizon_months']} months\n")
        f.write(f"- Blend ridge weight (alpha): {metrics['blend_alpha_ridge_weight']:.2f}\n")
        f.write(f"- Naive RMSE: {naive_rmse:.4f}\n")
        f.write(f"- Blend RMSE: {blend_rmse:.4f}\n")
        f.write(f"- RMSE skill vs naive: {skill:.2f}%\n")
        f.write(f"- PI80 coverage: {metrics['blend_interval_coverage_pct']['pi80']:.1f}%\n")
        f.write(f"- PI90 coverage: {metrics['blend_interval_coverage_pct']['pi90']:.1f}%\n")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    df = prepare(root)

    results: dict[int, dict] = {}
    horizon_rows = []
    for h in (1, 3, 6):
        data_h, features_h = build_dataset(df, h)
        pred_h, metrics_h = run_calibration_one_horizon(data_h, features_h, h)
        results[h] = {"pred": pred_h, "metrics": metrics_h, "data": data_h}

        horizon_rows.append(
            {
                "horizon_months": h,
                "naive_rmse": metrics_h["naive"]["rmse"],
                "blend_rmse": metrics_h["blend"]["rmse"],
                "ridge_rmse": metrics_h["ridge"]["rmse"],
                "elastic_net_rmse": metrics_h["elastic_net"]["rmse"],
                "blend_skill_vs_naive_pct": (metrics_h["naive"]["rmse"] - metrics_h["blend"]["rmse"]) / max(metrics_h["naive"]["rmse"], 1e-9) * 100.0,
            }
        )

    champion_h, champion = select_champion(results)
    coefs = estimate_pass_through(df)
    save_outputs(
        root,
        champion["pred"],
        champion["metrics"],
        coefs,
        pd.DataFrame(horizon_rows).sort_values("horizon_months"),
    )

    print("Calibration round 2 complete.")
    print(f"Champion horizon: {champion_h} months")
    print(json.dumps(champion["metrics"], indent=2))


if __name__ == "__main__":
    main()
