#!/usr/bin/env python3
"""
Tier B external validation, case study 1.

Parses the price-adjustment ("Adjust Local" / "Adjust Foreign") sheets of a
real, anonymized Ugandan road-works IPC package (a Design & Build contract
on MDB-harmonized FIDIC terms, 35 valuation periods, April 2019-February
2024) and compares its own independently-sourced fuel and bitumen indices
against (a) Brent crude and (b) this project's UBOS CIPI DIESEL sub-index,
over the overlapping window. This is the first check in the project against
a real contract's own price-adjustment mechanism rather than internal panel
data alone.

No contractor, employer, engineer, or project name is read into any output
file below — only dates, index values, weights, and computed ratios/amounts.
The source workbook itself is git-ignored (see .gitignore) and never committed.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import openpyxl
import pandas as pd
from scipy import stats as sps

SOURCE_XLSX = "IPC _No35a - Feb.2024-Final-09.04.24.xlsx"

CATEGORIES = [
    ("fuel", "F", "G", 6),      # (name, old-col-letter-ish label, n/a, start col index 1-based for FUo)
    ("bitumen", "BT", None, 8),
    ("steel", "ST", None, 10),
    ("cement", "CE", None, 12),
    ("equipment", "EQ", None, 14),
    ("labour", "L", None, 16),  # LL local / EL foreign
    ("metal", "MP", None, 18),
]

WEIGHTS = {
    "fixed": 0.20, "fuel": 0.10, "bitumen": 0.20, "steel": 0.05,
    "cement": 0.10, "equipment": 0.10, "labour": 0.15, "metal": 0.10,
}


def parse_adjust_sheet(ws) -> pd.DataFrame:
    rows = []
    for r in range(6, ws.max_row + 1):
        bill = ws.cell(row=r, column=1).value
        if bill is None or str(bill).strip().lower().startswith(("total", "previous", "this")):
            continue
        d_from = ws.cell(row=r, column=2).value
        d_to = ws.cell(row=r, column=3).value
        if not isinstance(d_from, (pd.Timestamp,)) and d_from is None:
            continue
        try:
            d_from = pd.Timestamp(d_from)
            d_to = pd.Timestamp(d_to)
        except Exception:
            continue
        specific = ws.cell(row=r, column=4).value
        rec = {
            "bill_no": bill, "period_from": d_from, "period_to": d_to,
            "index_ref_date": pd.Timestamp(specific) if specific else pd.NaT,
            "fixed_proportion": ws.cell(row=r, column=5).value,
            "fuel_o": ws.cell(row=r, column=6).value, "fuel_n": ws.cell(row=r, column=7).value,
            "bitumen_o": ws.cell(row=r, column=8).value, "bitumen_n": ws.cell(row=r, column=9).value,
            "steel_o": ws.cell(row=r, column=10).value, "steel_n": ws.cell(row=r, column=11).value,
            "cement_o": ws.cell(row=r, column=12).value, "cement_n": ws.cell(row=r, column=13).value,
            "equipment_o": ws.cell(row=r, column=14).value, "equipment_n": ws.cell(row=r, column=15).value,
            "labour_o": ws.cell(row=r, column=16).value, "labour_n": ws.cell(row=r, column=17).value,
            "metal_o": ws.cell(row=r, column=18).value, "metal_n": ws.cell(row=r, column=19).value,
            "adjustment_factor_pn": ws.cell(row=r, column=20).value,
            "ipc_amount": ws.cell(row=r, column=21).value,
            "amount_after_adjustment": ws.cell(row=r, column=22).value,
            "adjustment_amount": ws.cell(row=r, column=23).value,
        }
        rows.append(rec)
    df = pd.DataFrame(rows)
    # de-duplicate split-period bill numbers (source workbook repeats a bill_no
    # across a split period pair; period_from is unique, use it as the key)
    df = df.drop_duplicates(subset=["period_from"]).sort_values("period_from").reset_index(drop=True)
    for cat, *_ in CATEGORIES:
        df[f"{cat}_ret_pct"] = (df[f"{cat}_n"] / df[f"{cat}_o"] - 1.0) * 100.0
    df["adjustment_pct_of_ipc"] = df["adjustment_amount"] / df["ipc_amount"] * 100.0
    return df


def dlog_pct(s: pd.Series) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce")
    return 100.0 * np.log(x).diff()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out_t = root / "results" / "case_study_ipc" / "tables"
    out_f = root / "results" / "case_study_ipc" / "figures"
    out_t.mkdir(parents=True, exist_ok=True)
    out_f.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.load_workbook(root / SOURCE_XLSX, data_only=True)
    local = parse_adjust_sheet(wb["Adjust Local"])
    foreign = parse_adjust_sheet(wb["Adjust Foreign"])
    local.to_csv(out_t / "case_local_adjustment_series.csv", index=False)
    foreign.to_csv(out_t / "case_foreign_adjustment_series.csv", index=False)

    with open(out_t / "case_formula_weights.csv", "w", encoding="utf-8") as f:
        f.write("category,weight\n")
        for k, v in WEIGHTS.items():
            f.write(f"{k},{v}\n")
        f.write(f"petroleum_linked_total_(fuel+bitumen),{WEIGHTS['fuel'] + WEIGHTS['bitumen']}\n")

    # ---------------------------------------------------------------
    # External series over the same window: Brent, and this project's
    # own CIPI DIESEL sub-index from panel_v1.0
    # ---------------------------------------------------------------
    win_start, win_end = local["index_ref_date"].min() - pd.Timedelta(days=60), local["index_ref_date"].max() + pd.Timedelta(days=31)

    brent = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU")
    brent.columns = ["date", "brent_usd"]
    brent["date"] = pd.to_datetime(brent["date"], errors="coerce")
    brent["brent_usd"] = pd.to_numeric(brent["brent_usd"], errors="coerce")
    brent = brent.dropna().set_index("date").sort_index().resample("MS").mean()
    brent = brent[(brent.index >= win_start) & (brent.index <= win_end)]

    panel = pd.read_csv(root / "cio_pipeline-2" / "data" / "processed" / "panel_v1.0.csv")
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.set_index("date").sort_index()
    panel = panel[(panel.index >= win_start) & (panel.index <= win_end)]

    # align each contract period to the nearest panel/Brent month for comparison
    def nearest_monthly(series: pd.Series, dates: pd.Series) -> pd.Series:
        idx = series.index
        out = []
        for d in dates:
            if pd.isna(d):
                out.append(np.nan)
                continue
            pos = idx.get_indexer([pd.Timestamp(d).replace(day=1)], method="nearest")[0]
            out.append(series.iloc[pos] if pos >= 0 else np.nan)
        return pd.Series(out, index=dates.index)

    local["brent_usd_matched"] = nearest_monthly(brent["brent_usd"], local["index_ref_date"])
    local["cipi_diesel_matched"] = nearest_monthly(panel["DIESEL"], local["index_ref_date"])
    foreign["brent_usd_matched"] = nearest_monthly(brent["brent_usd"], foreign["index_ref_date"])

    # ---------------------------------------------------------------
    # Convergent validity: contract fuel index vs Brent, contract fuel index
    # vs this project's CIPI diesel index; and contract bitumen index vs Brent
    # ---------------------------------------------------------------
    def corr_report(a: pd.Series, b: pd.Series) -> dict:
        z = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
        if len(z) < 5:
            return {"n": len(z), "pearson_r": None, "p_value": None}
        r, p = sps.pearsonr(z["a"], z["b"])
        return {"n": int(len(z)), "pearson_r": float(r), "p_value": float(p)}

    validity = {
        "local_fuel_index_level_vs_brent_level": corr_report(local["fuel_n"], local["brent_usd_matched"]),
        "local_fuel_index_level_vs_cipi_diesel_level": corr_report(local["fuel_n"], local["cipi_diesel_matched"]),
        "foreign_fuel_index_level_vs_brent_level": corr_report(foreign["fuel_n"], foreign["brent_usd_matched"]),
        "local_bitumen_index_level_vs_brent_level": corr_report(local["bitumen_n"], local["brent_usd_matched"]),
        "local_fuel_return_vs_brent_return": corr_report(dlog_pct(local["fuel_n"]), dlog_pct(local["brent_usd_matched"])),
        "local_fuel_return_vs_cipi_diesel_return": corr_report(dlog_pct(local["cipi_diesel_matched"]), dlog_pct(local["fuel_n"])),
    }

    # ---------------------------------------------------------------
    # Structural break replication: split the contract's OWN fuel index
    # return series at Feb 2022, same design as the panel-based Chow test
    # ---------------------------------------------------------------
    local_ret = dlog_pct(local.set_index("index_ref_date")["fuel_n"]).dropna()
    pre = local_ret[local_ret.index < "2022-02-01"]
    post = local_ret[local_ret.index >= "2022-02-01"]
    break_check = {
        "pre_2022_02_mean_monthly_return_pct": float(pre.mean()) if len(pre) else None,
        "pre_2022_02_n": int(len(pre)),
        "post_2022_02_mean_monthly_return_pct": float(post.mean()) if len(post) else None,
        "post_2022_02_n": int(len(post)),
        "ratio_post_over_pre": float(post.mean() / pre.mean()) if len(pre) and pre.mean() != 0 else None,
    }

    # index-reference-date lag convention actually used by this real contract
    lag_days = (local["period_to"] - local["index_ref_date"]).dt.days.dropna()

    summary = {
        "n_periods_local": int(len(local)),
        "n_periods_foreign": int(len(foreign)),
        "window": [str(win_start.date()), str(win_end.date())],
        "formula_weights": WEIGHTS,
        "petroleum_linked_share_of_variable_portion_pct": round(
            (WEIGHTS["fuel"] + WEIGHTS["bitumen"]) / (1 - WEIGHTS["fixed"]) * 100, 1
        ),
        "convergent_validity": validity,
        "structural_break_replication_local_fuel_index": break_check,
        "contract_own_index_reference_lag_days": {
            "median": float(lag_days.median()), "min": float(lag_days.min()), "max": float(lag_days.max()),
        },
    }
    with open(out_t / "case_study_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    # ---------------------------------------------------------------
    # Figures
    # ---------------------------------------------------------------
    def norm100(s: pd.Series) -> pd.Series:
        s = s.dropna()
        return s / s.iloc[0] * 100.0

    plt.figure(figsize=(11, 5))
    x = local["index_ref_date"]
    plt.plot(x, norm100(local.set_index("index_ref_date")["fuel_n"]).reindex(x.values).values,
              label="Contract fuel index (local, UBOS-sourced)", color="#b45309", linewidth=1.6)
    plt.plot(x, norm100(local.set_index("index_ref_date")["brent_usd_matched"]).reindex(x.values).values,
              label="Brent crude (matched monthly)", color="#2563eb", linewidth=1.6)
    plt.axvline(pd.Timestamp("2022-02-01"), color="gray", linestyle="--", linewidth=1)
    plt.title("Case study: contract fuel index vs. Brent crude (rebased = 100 at first period)")
    plt.ylabel("Index (period 1 = 100)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_f / "01_case_fuel_index_vs_brent.png", dpi=180)
    plt.close()

    plt.figure(figsize=(11, 5))
    plt.plot(x, norm100(local.set_index("index_ref_date")["fuel_n"]).reindex(x.values).values,
              label="Contract fuel index (local, UBOS-sourced)", color="#b45309", linewidth=1.6)
    plt.plot(x, norm100(local.set_index("index_ref_date")["cipi_diesel_matched"]).reindex(x.values).values,
              label="This project's CIPI DIESEL sub-index", color="#3f7d5c", linewidth=1.6)
    plt.axvline(pd.Timestamp("2022-02-01"), color="gray", linestyle="--", linewidth=1)
    plt.title("Case study: contract fuel index vs. this project's CIPI diesel index")
    plt.ylabel("Index (period 1 = 100)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_f / "02_case_fuel_index_vs_cipi_diesel.png", dpi=180)
    plt.close()

    plt.figure(figsize=(11, 5))
    plt.bar(x, local["adjustment_pct_of_ipc"], color="#2563eb", width=20, label="Local (UGX)")
    plt.axhline(0, color="black", linewidth=0.8)
    plt.axvline(pd.Timestamp("2022-02-01"), color="gray", linestyle="--", linewidth=1)
    plt.title("Case study: price-adjustment amount as % of certified IPC value, by period")
    plt.ylabel("Adjustment as % of IPC amount")
    plt.tight_layout()
    plt.savefig(out_f / "03_case_adjustment_pct_of_ipc.png", dpi=180)
    plt.close()

    plt.figure(figsize=(8, 5))
    cats = ["fixed", "fuel", "bitumen", "steel", "cement", "equipment", "labour", "metal"]
    vals = [WEIGHTS[c] for c in cats]
    colors = ["#9ca3af" if c == "fixed" else ("#b45309" if c in ("fuel", "bitumen") else "#6b7280") for c in cats]
    plt.bar(cats, vals, color=colors)
    plt.title("Case study: contract's own formula weights\n(fuel + bitumen, both petroleum-linked, in amber)")
    plt.ylabel("Weight")
    plt.tight_layout()
    plt.savefig(out_f / "04_case_formula_weights.png", dpi=180)
    plt.close()

    lines = []
    lines.append("# Case Study: Real IPC Price-Adjustment History vs. This Project's Model\n")
    lines.append(f"- Anonymized case: Ugandan government road contract, Design & Build, MDB-harmonized FIDIC terms")
    lines.append(f"- {summary['n_periods_local']} valuation periods, {summary['window'][0]} to {summary['window'][1]}")
    lines.append(f"- Formula weights (as actually specified in this contract): fixed 0.20; fuel 0.10; bitumen 0.20; "
                 f"steel 0.05; cement 0.10; equipment 0.10; labour 0.15; metal products 0.10")
    lines.append(f"- Petroleum-linked share of the *variable* (non-fixed) portion — fuel + bitumen — is "
                 f"**{summary['petroleum_linked_share_of_variable_portion_pct']}%**")
    lines.append(f"- This contract's own index-reference lag (valuation date minus period end) is "
                 f"median {summary['contract_own_index_reference_lag_days']['median']:.0f} days "
                 f"(range {summary['contract_own_index_reference_lag_days']['min']:.0f}-"
                 f"{summary['contract_own_index_reference_lag_days']['max']:.0f})")
    lines.append("\n## Convergent validity")
    for k, v in validity.items():
        if v["pearson_r"] is not None:
            lines.append(f"- {k}: r = {v['pearson_r']:.3f} (p = {v['p_value']:.4f}, n = {v['n']})")
        else:
            lines.append(f"- {k}: insufficient overlap (n = {v['n']})")
    lines.append("\n## Structural break replication (contract's own fuel index, split at Feb 2022)")
    bc = break_check
    lines.append(f"- Pre-2022-02 mean monthly return: {bc['pre_2022_02_mean_monthly_return_pct']:.3f}% (n={bc['pre_2022_02_n']})")
    lines.append(f"- Post-2022-02 mean monthly return: {bc['post_2022_02_mean_monthly_return_pct']:.3f}% (n={bc['post_2022_02_n']})")
    if bc["ratio_post_over_pre"] is not None:
        lines.append(f"- Ratio post/pre: {bc['ratio_post_over_pre']:.2f}x")
    (out_t / "case_study_summary.md").write_text("\n".join(lines), encoding="utf-8")

    print("Done: case-study validation written to results/case_study_ipc/")


if __name__ == "__main__":
    main()
