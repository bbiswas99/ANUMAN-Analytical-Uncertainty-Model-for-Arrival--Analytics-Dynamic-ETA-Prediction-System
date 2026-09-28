"""
backend/pipeline/build_features.py
====================================
Step 02 + 03 implementation: reads raw Dataset CSVs and produces
  backend/model_A_features.parquet

Feature dictionary: Development Plan/03_Feature_Dictionary.md
Model spec: Development Plan/04_ML_Model_Spec.md

Run from project root:
    .\.venv\Scripts\python.exe backend\pipeline\build_features.py
"""

import os
import sys
import time
import numpy as np
import pandas as pd
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]   # e:\SIH 2026\Code
DATASET = ROOT / "Dataset"
OUT_PARQUET = ROOT / "backend" / "model_A_features.parquet"

SCHEDULE_CSV  = DATASET / "combined_schedule.csv"
DELAY_CSV     = DATASET / "combined_delay.csv"
DETAILS_CSV   = DATASET / "train_details.csv"
STN_NAMES_CSV = DATASET / "station_full_names.csv"
ETRAIN_CSV    = DATASET / "etrain_delays.csv"

OUTLIER_CAP_QUANTILE = 0.995   # cap delay at 99.5th percentile
OCCUPANCY_WINDOW_MIN = 30      # minutes window for congestion proxy


def load_schedule():
    print("Loading schedule...")
    df = pd.read_csv(SCHEDULE_CSV)
    df.columns = [c.strip() for c in df.columns]
    df["train_no"] = df["train_no"].astype(int)
    df["station_no"] = df["station_no"].astype(int)
    df["station_name"] = df["station_name"].astype(str).str.strip().str.upper()
    df["distance_from_origin"] = pd.to_numeric(df["distance_from_origin"], errors="coerce").fillna(0)
    df["arrival_day"] = pd.to_numeric(df["arrival_day"], errors="coerce").fillna(1).astype(int)
    df["departure_day"] = pd.to_numeric(df["departure_day"], errors="coerce").fillna(1).astype(int)
    df["arrival_time"] = df["arrival_time"].astype(str).str.strip()
    df["departure_time"] = df["departure_time"].astype(str).str.strip()
    print(f"  {len(df):,} stop rows, {df['train_no'].nunique():,} trains")
    return df


def load_delay():
    print("Loading delay data...")
    usecols = ["date", "station_no", "station_name", "delay", "train_no"]
    df = pd.read_csv(DELAY_CSV, usecols=usecols)
    df.columns = [c.strip() for c in df.columns]
    df["train_no"] = df["train_no"].astype(int)
    df["station_no"] = pd.to_numeric(df["station_no"], errors="coerce").astype("Int64")
    df["station_name"] = df["station_name"].astype(str).str.strip().str.upper()
    df["delay"] = pd.to_numeric(df["delay"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], format="mixed", dayfirst=False)
    df = df.dropna(subset=["date"])
    df = df.sort_values(["train_no", "date", "station_no"]).reset_index(drop=True)
    print(f"  {len(df):,} delay records, {df['train_no'].nunique():,} trains")
    return df


def load_train_details():
    print("Loading train details...")
    df = pd.read_csv(DETAILS_CSV)
    df.columns = [c.strip() for c in df.columns]
    if "train_no" not in df.columns and "train_number" in df.columns:
        df.rename(columns={"train_number": "train_no"}, inplace=True)
    df["train_no"] = df["train_no"].astype(int)
    return df


def load_station_names():
    print("Loading station names / zones...")
    df = pd.read_csv(STN_NAMES_CSV)
    df.columns = [c.strip() for c in df.columns]
    df["station_name"] = df["station_name"].astype(str).str.strip().str.upper()
    keep = ["station_name", "station_full_name", "station_zone"]
    df = df[[c for c in keep if c in df.columns]].drop_duplicates("station_name")
    return df


def load_etrain():
    print("Loading etrain stats...")
    df = pd.read_csv(ETRAIN_CSV)
    df.columns = [c.strip() for c in df.columns]
    if "train_number" in df.columns:
        df.rename(columns={"train_number": "train_no"}, inplace=True)
    df["train_no"] = pd.to_numeric(df["train_no"], errors="coerce")
    df = df.dropna(subset=["train_no"])
    df["train_no"] = df["train_no"].astype(int)
    per_train = (
        df.groupby("train_no")
          .agg(etrain_avg_delay=("average_delay_minutes", "mean"),
               etrain_pct_right_time=("pct_right_time", "mean"))
          .reset_index()
    )
    return per_train


def merge_schedule_delay(sched, delay):
    print("Merging schedule + delay...")
    merged = delay.merge(sched, on=["train_no", "station_no", "station_name"], how="inner")
    print(f"  Merged: {len(merged):,} rows, {merged['train_no'].nunique():,} trains")
    return merged


def cap_delay_outliers(df):
    cap = df["delay"].quantile(OUTLIER_CAP_QUANTILE)
    print(f"Capping delay at {OUTLIER_CAP_QUANTILE*100:.1f}th pct = {cap:.0f} min")
    df["delay"] = df["delay"].clip(upper=cap)
    return df


def enrich_train_details(df, details):
    print("Enriching train details...")
    available = details.columns.tolist()
    print(f"  train_details columns: {available}")

    merge_cols = ["train_no"]
    if "train_name" in available:
        merge_cols.append("train_name")
    if "type_code" in available:
        merge_cols.append("type_code")

    df = df.merge(details[merge_cols].drop_duplicates("train_no"), on="train_no", how="left")
    if "train_name" not in df.columns:
        df["train_name"] = "Unknown"
    if "type_code" not in df.columns:
        df["type_code"] = "EXP-TRAINS"
    df["train_name"] = df["train_name"].fillna("Unknown")
    df["type_code"] = df["type_code"].fillna("EXP-TRAINS")
    df["is_special_train"] = df["train_name"].str.upper().str.contains("SPL", na=False)
    return df


def enrich_station_info(df, stn):
    print("Enriching station zones...")
    df = df.merge(stn, on="station_name", how="left")
    df["station_full_name"] = df.get("station_full_name", pd.Series(dtype=str)).fillna(df["station_name"])
    df["station_zone"] = df.get("station_zone", pd.Series(dtype=str)).fillna("UNKNOWN")
    return df


def build_section_id(df):
    print("Building section IDs...")
    df = df.sort_values(["train_no", "date", "station_no"]).reset_index(drop=True)
    df["_next_stn"] = df.groupby(["train_no", "date"])["station_name"].shift(-1)
    df["section_id"] = df["station_name"] + "_" + df["_next_stn"].fillna("TERM")
    df["tracks"] = np.nan
    df["electrified"] = np.nan
    df["usage"] = np.nan
    df["expected_route_distance_km"] = np.nan
    df.drop(columns=["_next_stn"], inplace=True)
    return df


def build_section_occupancy(df):
    print("Computing section occupancy proxy...")
    occ = (df.groupby(["date", "section_id"])["train_no"]
             .transform("count")
             .rename("section_occupancy_count"))
    df["section_occupancy_count"] = occ.astype(int)
    return df


def sched_min_from_row(row):
    try:
        t = str(row["arrival_time"])
        if t in ("nan", "--:--", "NaT", ""):
            t = str(row["departure_time"])
        if t in ("nan", "--:--", "NaT", ""):
            return np.nan
        h, m = map(int, t.split(":"))
        return int(row["arrival_day"]) * 1440 + h * 60 + m
    except Exception:
        return np.nan


def build_temporal_features(df):
    print("Building temporal features...")
    df["_sched_min"] = df.apply(sched_min_from_row, axis=1)
    hour = (df["_sched_min"].fillna(0) % 1440 / 60).astype(int).clip(0, 23)
    df["hour_of_day_sin"] = np.sin(2 * np.pi * hour / 24)
    df["hour_of_day_cos"] = np.cos(2 * np.pi * hour / 24)
    dow = df["date"].dt.dayofweek
    df["day_of_week_sin"] = np.sin(2 * np.pi * dow / 7)
    df["day_of_week_cos"] = np.cos(2 * np.pi * dow / 7)
    df["month"] = df["date"].dt.month
    df["is_fog_season_flag"] = df["month"].isin([12, 1, 2])
    return df


def build_journey_features(df):
    print("Building journey features...")
    grp = df.groupby(["train_no", "date"])
    df["total_stops"] = grp["station_no"].transform("count")
    df["total_dist_km"] = grp["distance_from_origin"].transform("max").replace(0, np.nan)
    df["stops_remaining_count"] = df["total_stops"] - df["station_no"] + 1
    df["distance_remaining_total_km"] = df["total_dist_km"] - df["distance_from_origin"]
    df["elapsed_journey_pct"] = np.where(
        df["total_dist_km"] > 0,
        df["distance_from_origin"] / df["total_dist_km"],
        0
    )
    df.drop(columns=["total_stops", "total_dist_km"], inplace=True)
    return df


def build_rolling_delay_features(df):
    print("Building rolling delay averages (this may take ~1 min)...")
    df = df.sort_values(["section_id", "date"]).reset_index(drop=True)
    for win, col in [(30, "section_avg_delay_30d"),
                     (90, "section_avg_delay_90d"),
                     (365, "section_avg_delay_365d")]:
        df[col] = (
            df.groupby("section_id")["delay"]
              .transform(lambda x: x.rolling(win, min_periods=1).mean())
        )

    df = df.sort_values(["train_no", "date"]).reset_index(drop=True)
    df["train_number_avg_delay_30d"] = (
        df.groupby("train_no")["delay"]
          .transform(lambda x: x.rolling(30, min_periods=1).mean())
    )
    return df


def build_zone_punctuality(df):
    print("Building zone punctuality priors...")
    zone_pct = (
        df.groupby("station_zone")["delay"]
          .apply(lambda x: (x <= 0).mean() * 100)
          .rename("zone_avg_punctuality_pct")
          .reset_index()
    )
    df = df.merge(zone_pct, on="station_zone", how="left")
    return df


def build_delay_trend(df):
    print("Building delay trend...")
    df = df.sort_values(["train_no", "date", "station_no"]).reset_index(drop=True)

    def slope_last3(series):
        arr = series.values
        out = np.zeros(len(arr), dtype=float)
        for i in range(2, len(arr)):
            w = arr[i-2:i+1]
            if not np.isnan(w).any():
                out[i] = np.polyfit(range(3), w, 1)[0]
        return pd.Series(out, index=series.index)

    df["delay_trend_last_3_points"] = (
        df.groupby(["train_no", "date"])["delay"].transform(slope_last3)
    )
    return df


def build_recovery_margin(df):
    print("Building recovery margin...")
    df["_arr_min"] = df.apply(sched_min_from_row, axis=1)
    grp = df.groupby(["train_no", "date"])
    df["_term_min"] = grp["_arr_min"].transform("max")
    df["recovery_margin_remaining_min"] = (df["_term_min"] - df["_arr_min"]).clip(lower=0)
    df.drop(columns=["_arr_min", "_term_min"], inplace=True)
    return df


def build_baseline(df):
    print("Building baseline delay estimate...")
    df["baseline_delay_estimate"] = (
        df["delay"] - df["recovery_margin_remaining_min"] * 0.3
    ).clip(lower=0).fillna(df["delay"].median())
    df["baseline_eta"] = df["_sched_min"] + df["baseline_delay_estimate"]
    return df


def add_stub_features(df, etrain):
    print("Adding stub features + etrain enrichment...")
    df["active_tsr_count_on_route"] = 0
    df["platform_number"] = np.nan
    df["source_agreement_score"] = np.nan
    df["data_confidence_score"] = np.nan
    df["reported_delay_min"] = df["delay"]
    df = df.merge(etrain, on="train_no", how="left")
    return df


def build_target(df):
    df["residual_target"] = df["delay"] - df["baseline_delay_estimate"]
    return df


FINAL_COLS = [
    "train_no", "station_no", "station_name", "station_full_name",
    "station_zone", "date",
    "distance_from_origin", "arrival_day", "arrival_time",
    "departure_day", "departure_time",
    "train_name", "type_code", "is_special_train",
    "reported_delay_min", "platform_number",
    "source_agreement_score", "data_confidence_score",
    "section_id", "tracks", "electrified", "usage",
    "expected_route_distance_km", "section_occupancy_count",
    "hour_of_day_sin", "hour_of_day_cos",
    "day_of_week_sin", "day_of_week_cos",
    "month", "is_fog_season_flag",
    "stops_remaining_count", "distance_remaining_total_km",
    "elapsed_journey_pct",
    "section_avg_delay_30d", "section_avg_delay_90d",
    "section_avg_delay_365d", "train_number_avg_delay_30d",
    "zone_avg_punctuality_pct", "delay_trend_last_3_points",
    "recovery_margin_remaining_min",
    "etrain_avg_delay", "etrain_pct_right_time",
    "active_tsr_count_on_route",
    "baseline_delay_estimate", "baseline_eta",
    "delay", "residual_target",
]


def main():
    t0 = time.time()

    sched = load_schedule()
    delay = load_delay()
    details = load_train_details()
    stn = load_station_names()
    etrain = load_etrain()

    df = merge_schedule_delay(sched, delay)
    df = cap_delay_outliers(df)
    df = enrich_train_details(df, details)
    df = enrich_station_info(df, stn)
    df = build_section_id(df)
    df = build_section_occupancy(df)
    df = build_temporal_features(df)
    df = build_journey_features(df)
    df = build_rolling_delay_features(df)
    df = build_zone_punctuality(df)
    df = build_delay_trend(df)
    df = build_recovery_margin(df)
    df = build_baseline(df)
    df = add_stub_features(df, etrain)
    df = build_target(df)

    before = len(df)
    df = df.dropna(subset=["delay", "residual_target"])
    print(f"Rows after NaN drop: {len(df):,} (dropped {before - len(df):,})")

    for c in FINAL_COLS:
        if c not in df.columns:
            df[c] = np.nan

    df = df[FINAL_COLS].reset_index(drop=True)
    print(f"\nFinal shape: {df.shape}")
    print(f"Date range:  {df['date'].min().date()} to {df['date'].max().date()}")
    print(f"Trains: {df['train_no'].nunique():,}   Stations: {df['station_name'].nunique():,}")

    print(f"\nSaving to {OUT_PARQUET} ...")
    df.to_parquet(OUT_PARQUET, index=False, compression="snappy")
    size_mb = OUT_PARQUET.stat().st_size / 1e6
    print(f"Done! {size_mb:.1f} MB in {time.time()-t0:.1f}s")

    print("\n--- Delay stats (capped) ---")
    print(df["delay"].describe())
    print("\n--- Residual target stats ---")
    print(df["residual_target"].describe())


if __name__ == "__main__":
    main()
