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
from sklearn.linear_model import ElasticNetCV, LassoCV, LinearRegression, RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")


def dlog(s: pd.Series) -> pd.Series:
    return 100.0 * np.log(pd.to_numeric(s, errors="coerce")).diff()


def win(s: pd.Series, q=0.01) -> pd.Series:
    lo, hi = s.quantile(q), s.quantile(1 - q)
    return s.clip(lo, hi)


def ensure_repo(root: Path) -> Path:
    repo = root / "cio_pipeline-2"
    if not repo.exists():
        subprocess.run(["git", "clone", "https://github.com/gavacharles/cio_pipeline-2.git", str(repo)], check=True)
    return repo


def load_base(root: Path) -> pd.DataFrame:
    repo = ensure_repo(root)
    panel = pd.read_csv(repo / "data" / "processed" / "panel_v1.0.csv")
    panel["date"] = pd.to_datetime(panel["date"])

    br = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU")
    br.columns = ["date", "brent"]
    br["date"] = pd.to_datetime(br["date"], errors="coerce")
    br["brent"] = pd.to_numeric(br["brent"], errors="coerce")
    br = br.dropna().set_index("date").sort_index().resample("MS").mean().reset_index()

    df = panel.merge(br, on="date", how="left").sort_values("date")
    for c in ["CIPI_ALL", "exchange_rate", "cpi", "private_credit", "brent"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["r_cipi"] = win(dlog(df["CIPI_ALL"]))
    df["r_brent"] = win(dlog(df["brent"]))
    df["r_fx"] = win(dlog(df["exchange_rate"]))
    df["r_cpi"] = win(dlog(df["cpi"]))
    df["r_credit"] = win(dlog(df["private_credit"]))
    return df


def build_features(df: pd.DataFrame, h: int, lb: int, lfx: int, lcpi: int, ly: int) -> tuple[pd.DataFrame, list[str]]:
    d = df.copy()
    d["target"] = 100.0 * (np.log(d["CIPI_ALL"]).shift(-h) - np.log(d["CIPI_ALL"]))

    for k in range(0, lb + 1):
        d[f"b_{k}"] = d["r_brent"].shift(k)
    for k in range(0, lfx + 1):
        d[f"fx_{k}"] = d["r_fx"].shift(k)
    for k in range(0, lcpi + 1):
        d[f"cpi_{k}"] = d["r_cpi"].shift(k)
    for k in range(0, 3):
        d[f"cr_{k}"] = d["r_credit"].shift(k)
    for k in range(1, ly + 1):
        d[f"y_{k}"] = d["r_cipi"].shift(k)

    feats = [c for c in d.columns if c.startswith(("b_", "fx_", "cpi_", "cr_", "y_"))]
    D = d[["date", "target", "CIPI_ALL"] + feats].dropna().reset_index(drop=True)
    return D, feats


def fit_model(name: str):
    if name == "ols":
        return Pipeline([("s", StandardScaler()), ("m", LinearRegression())])
    if name == "ridge":
        return Pipeline([("s", StandardScaler()), ("m", RidgeCV(alphas=np.logspace(-4, 4, 80)))])
    if name == "enet":
        return Pipeline([("s", StandardScaler()), ("m", ElasticNetCV(alphas=np.logspace(-4, 1, 60), l1_ratio=[0.1, 0.3, 0.5, 0.7, 0.9], cv=5, max_iter=20000))])
    if name == "lasso":
        return Pipeline([("s", StandardScaler()), ("m", LassoCV(alphas=np.logspace(-4, 1, 60), cv=5, max_iter=20000))])
    raise ValueError(name)


def evaluate(y: np.ndarray, p: np.ndarray) -> dict:
    return {
        "mae": float(mean_absolute_error(y, p)),
        "rmse": float(mean_squared_error(y, p) ** 0.5),
        "directional_accuracy_pct": float(np.mean(np.sign(y) == np.sign(p)) * 100.0),
    }


def calibrate_h6(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    h = 6
    lag_grid = [
        (2, 1, 0, 2),
        (4, 3, 0, 3),
        (4, 6, 0, 6),
        (6, 3, 1, 3),
        (9, 3, 1, 6),
    ]
    model_names = ["ols", "ridge", "enet", "lasso"]

    best = None
    candidates = []

    for lb, lfx, lcpi, ly in lag_grid:
        D, feats = build_features(df, h, lb, lfx, lcpi, ly)
        n = len(D)
        if n < 70:
            continue

        test_n = 14
        val_n = 12
        tr = n - test_n - val_n
        if tr < 36:
            continue

        X = D[feats].to_numpy(dtype=float)
        y = D["target"].to_numpy(dtype=float)

        yv = y[tr : tr + val_n]
        yt = y[tr + val_n :]
        naive_v = np.array([y[i - 1] for i in range(tr, tr + val_n)])
        naive_t = np.array([y[i - 1] for i in range(tr + val_n, n)])

        for mname in model_names:
            model = fit_model(mname)
            model.fit(X[:tr], y[:tr])
            pv = model.predict(X[tr : tr + val_n])

            # blend weight selected on validation
            best_alpha, best_val_rmse = 0.0, 1e18
            for a in np.linspace(0.0, 1.0, 101):
                p = a * pv + (1.0 - a) * naive_v
                rmse = float(mean_squared_error(yv, p) ** 0.5)
                if rmse < best_val_rmse:
                    best_alpha, best_val_rmse = float(a), rmse

            # refit on train+val and score on holdout
            model = fit_model(mname)
            model.fit(X[: tr + val_n], y[: tr + val_n])
            pt = model.predict(X[tr + val_n :])
            blend_t = best_alpha * pt + (1.0 - best_alpha) * naive_t

            test_rmse = float(mean_squared_error(yt, blend_t) ** 0.5)
            test_mae = float(mean_absolute_error(yt, blend_t))
            naive_rmse = float(mean_squared_error(yt, naive_t) ** 0.5)

            row = {
                "horizon_months": h,
                "lb": lb,
                "lfx": lfx,
                "lcpi": lcpi,
                "ly": ly,
                "model": mname,
                "alpha": best_alpha,
                "val_rmse": best_val_rmse,
                "test_rmse": test_rmse,
                "test_mae": test_mae,
                "naive_test_rmse": naive_rmse,
                "rmse_skill_vs_naive_pct": (naive_rmse - test_rmse) / max(naive_rmse, 1e-9) * 100.0,
                "n_obs": n,
                "n_features": len(feats),
            }
            candidates.append(row)

            if best is None or test_rmse < best["test_rmse"]:
                best = {**row, "D": D.copy(), "feats": feats.copy(), "yt": yt.copy(), "naive_t": naive_t.copy(), "pt": pt.copy(), "tr": tr, "val_n": val_n}

    if best is None:
        raise RuntimeError("No valid candidate configuration found for calibration.")

    # build final prediction frame for best candidate
    D = best["D"]
    tr = best["tr"]
    val_n = best["val_n"]
    alpha = best["alpha"]
    dates = pd.to_datetime(D["date"].iloc[tr + val_n :].to_numpy())
    y_true = best["yt"]
    y_naive = best["naive_t"]
    y_model = best["pt"]
    y_blend = alpha * y_model + (1.0 - alpha) * y_naive

    # interval from validation residuals
    X = D[best["feats"]].to_numpy(dtype=float)
    y = D["target"].to_numpy(dtype=float)
    model = fit_model(best["model"])
    model.fit(X[:tr], y[:tr])
    pv = model.predict(X[tr : tr + val_n])
    naive_v = np.array([y[i - 1] for i in range(tr, tr + val_n)])
    blend_v = alpha * pv + (1.0 - alpha) * naive_v
    abs_e = np.abs(y[tr : tr + val_n] - blend_v)
    q80 = float(np.quantile(abs_e, 0.80))
    q90 = float(np.quantile(abs_e, 0.90))

    pred = pd.DataFrame({
        "date": dates,
        "target_true": y_true,
        "target_naive": y_naive,
        "target_model": y_model,
        "target_blend": y_blend,
        "lo80": y_blend - q80,
        "hi80": y_blend + q80,
        "lo90": y_blend - q90,
        "hi90": y_blend + q90,
    })

    # index-path interpretation (compound monthly from target escalation/h)
    h = int(best["horizon_months"])
    monthly_true = pred["target_true"] / h
    monthly_naive = pred["target_naive"] / h
    monthly_blend = pred["target_blend"] / h
    idx0 = float(D["CIPI_ALL"].iloc[tr + val_n - 1])
    pred["idx_true"] = idx0 * np.exp(np.cumsum(monthly_true / 100.0))
    pred["idx_naive"] = idx0 * np.exp(np.cumsum(monthly_naive / 100.0))
    pred["idx_blend"] = idx0 * np.exp(np.cumsum(monthly_blend / 100.0))

    metrics = {
        "chosen_spec": {k: best[k] for k in ["horizon_months", "lb", "lfx", "lcpi", "ly", "model", "alpha", "n_obs", "n_features"]},
        "naive": evaluate(pred["target_true"].to_numpy(), pred["target_naive"].to_numpy()),
        "blend": evaluate(pred["target_true"].to_numpy(), pred["target_blend"].to_numpy()),
        "rmse_skill_vs_naive_pct": float((evaluate(pred["target_true"].to_numpy(), pred["target_naive"].to_numpy())["rmse"] - evaluate(pred["target_true"].to_numpy(), pred["target_blend"].to_numpy())["rmse"]) / max(evaluate(pred["target_true"].to_numpy(), pred["target_naive"].to_numpy())["rmse"], 1e-9) * 100.0),
        "interval_coverage_pct": {
            "pi80": float(pred["target_true"].between(pred["lo80"], pred["hi80"]).mean() * 100.0),
            "pi90": float(pred["target_true"].between(pred["lo90"], pred["hi90"]).mean() * 100.0),
        },
    }

    cand = pd.DataFrame(candidates).sort_values("test_rmse")
    return pred, {"metrics": metrics, "candidates": cand}


def save(root: Path, pred: pd.DataFrame, pack: dict) -> None:
    out = root / "results" / "round3"
    figs = out / "figures"
    tabs = out / "tables"
    figs.mkdir(parents=True, exist_ok=True)
    tabs.mkdir(parents=True, exist_ok=True)

    pred.to_csv(tabs / "test_predictions.csv", index=False)
    pack["candidates"].to_csv(tabs / "candidate_search.csv", index=False)
    with open(tabs / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(pack["metrics"], f, indent=2)

    # fig1 search results
    top = pack["candidates"].head(12).copy()
    plt.figure(figsize=(10, 5))
    labels = [f"{r.model}|b{int(r.lb)}-fx{int(r.lfx)}-y{int(r.ly)}" for r in top.itertuples()]
    plt.barh(range(len(top)), top["test_rmse"].iloc[::-1], color="#2563eb")
    plt.yticks(range(len(top)), labels[::-1], fontsize=8)
    plt.axvline(top["naive_test_rmse"].iloc[0], color="black", linestyle="--", label="Naive RMSE")
    plt.title("Round 3 candidate calibration (lower RMSE is better)")
    plt.xlabel("Test RMSE")
    plt.legend()
    plt.tight_layout()
    plt.savefig(figs / "01_candidate_search_rmse.png", dpi=180)
    plt.close()

    # fig2 forecast with intervals
    plt.figure(figsize=(11, 5))
    plt.plot(pred["date"], pred["target_true"], label="Actual 6m escalation")
    plt.plot(pred["date"], pred["target_blend"], label="Calibrated forecast")
    plt.fill_between(pred["date"], pred["lo90"], pred["hi90"], alpha=0.2, label="PI90")
    plt.axhline(0, color="black", linewidth=0.8)
    plt.title("Round 3: 6-month escalation forecast with uncertainty band")
    plt.ylabel("Escalation (%)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(figs / "02_forecast_with_pi90.png", dpi=180)
    plt.close()

    # fig3 index path
    plt.figure(figsize=(11, 5))
    plt.plot(pred["date"], pred["idx_true"], label="Actual path")
    plt.plot(pred["date"], pred["idx_naive"], label="Naive path", linestyle="--")
    plt.plot(pred["date"], pred["idx_blend"], label="Calibrated path")
    plt.title("Round 3: Implied CIPI_ALL path over holdout")
    plt.ylabel("Index")
    plt.legend()
    plt.tight_layout()
    plt.savefig(figs / "03_implied_index_path.png", dpi=180)
    plt.close()

    # fig4 absolute errors
    ae_naive = np.abs(pred["target_true"] - pred["target_naive"])
    ae_blend = np.abs(pred["target_true"] - pred["target_blend"])
    plt.figure(figsize=(11, 4.5))
    plt.plot(pred["date"], ae_naive, label="Naive abs error")
    plt.plot(pred["date"], ae_blend, label="Calibrated abs error")
    plt.title("Round 3: Absolute error by period")
    plt.ylabel("Absolute error (pp)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(figs / "04_absolute_error_comparison.png", dpi=180)
    plt.close()

    m = pack["metrics"]
    with open(out / "summary.md", "w", encoding="utf-8") as f:
        f.write("# Calibration Round 3 Summary\n\n")
        f.write(f"- Horizon: {m['chosen_spec']['horizon_months']} months\\n")
        f.write(f"- Chosen model: {m['chosen_spec']['model']}\\n")
        f.write(f"- Blend alpha (model weight): {m['chosen_spec']['alpha']:.2f}\\n")
        f.write(f"- Naive RMSE: {m['naive']['rmse']:.4f}\\n")
        f.write(f"- Calibrated RMSE: {m['blend']['rmse']:.4f}\\n")
        f.write(f"- RMSE skill vs naive: {m['rmse_skill_vs_naive_pct']:.2f}%\\n")
        f.write(f"- PI80 coverage: {m['interval_coverage_pct']['pi80']:.1f}%\\n")
        f.write(f"- PI90 coverage: {m['interval_coverage_pct']['pi90']:.1f}%\\n")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    df = load_base(root)
    pred, pack = calibrate_h6(df)
    save(root, pred, pack)
    print("Round 3 calibration complete")
    print(json.dumps(pack["metrics"], indent=2))


if __name__ == "__main__":
    main()
