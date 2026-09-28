# backend/main.py
# FastAPI service for Indian Railways ETA prediction.
# Run from project root:
#   .venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000 --reload

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import json
import math
import os
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import xgboost as xgb
from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.errors import (
    TrainETAError,
    InvalidTrainNumberError,
    NoActiveJourneyError,
    WhatIfOverrideInvalidError,
    ModelNotLoadedError,
    OutOfRangeFeatureError,
    ConfigurationError,
    SchemaValidationError,
    register_error_handlers,
)
from backend.reconciled_reader import get_latest_reconciled_row, get_data_freshness

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR  = ROOT / "backend" / "models"
MODEL_PATH = Path(os.environ.get("MODEL_A_PATH", str(MODEL_DIR / "model_a.json")))
ENCODER_PATH = Path(os.environ.get("ENCODER_PATH", str(MODEL_DIR / "label_encoders.json")))
FEATURE_IMPORTANCE_PATH = MODEL_DIR / "feature_importance.json"

MODEL_B_PATH = Path(os.environ.get("MODEL_B_PATH", str(MODEL_DIR / "model_b.json")))
MODEL_B_ENCODER_PATH = Path(os.environ.get("MODEL_B_ENCODER_PATH", str(MODEL_DIR / "model_b_encoder.json")))
MODEL_B_IMPORTANCE_PATH = MODEL_DIR / "model_b_importance.json"
PRECEDENCE_EVENTS_PATH = Path(os.environ.get("PRECEDENCE_EVENTS_PATH", str(ROOT / "backend" / "precedence_events.parquet")))

PARQUET_B_PATH = ROOT / "backend" / "model_B_features.parquet"
PARQUET_PATH = Path(os.environ.get("FEATURES_PARQUET_PATH", str(PARQUET_B_PATH if PARQUET_B_PATH.exists() else ROOT / "backend" / "model_A_features.parquet")))
SCHEDULE_PATH = ROOT / "Dataset" / "combined_schedule.csv"
TRAIN_DETAILS_PATH = ROOT / "Dataset" / "train_details.csv"
ETRAIN_DELAYS_PATH = ROOT / "Dataset" / "etrain_delays.csv"
STATION_COORDS_PATH = ROOT / "frontend" / "src" / "assets" / "station-coordinates.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Indian Railways ETA Prediction API",
    description="Dual-Model ETA Predictor (Model A: Section Delays, Model B: Precedence-Aware)",
    version="2.0.0",
)

# Register standard error handlers (E1+E2 — errors.py)
register_error_handlers(app)

# CORS — allow configured origins + localhost for dev (fail fast if wildcard '*')
raw_origins = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
)
_ALLOWED_ORIGINS = [o.strip() for o in raw_origins.split(",") if o.strip()]
if not _ALLOWED_ORIGINS or "*" in _ALLOWED_ORIGINS:
    raise ConfigurationError(
        "ALLOWED_ORIGINS must be non-empty and must not contain wildcard '*' (per 08_Deployment_Spec.md)"
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Model + data store (loaded once at startup)
# ---------------------------------------------------------------------------
STATION_COORDS_PATH = ROOT / "frontend" / "src" / "assets" / "station-coordinates.json"

class ModelStore:
    # Model A (Baseline & Congestion)
    model: Optional[xgb.XGBRegressor] = None
    encoders: dict = {}
    feature_names: list = []
    feature_importance: dict = {}
    eval_metrics: dict = {}

    # Model B (Precedence-Aware)
    model_b: Optional[xgb.XGBRegressor] = None
    model_b_encoders: dict = {}
    model_b_feature_names: list = []
    model_b_feature_importance: dict = {}
    model_b_eval_metrics: dict = {}
    model_b_enabled: bool = False
    precedence_events: Optional[pd.DataFrame] = None

    train_data: Optional[pd.DataFrame] = None
    schedule_data: Optional[pd.DataFrame] = None
    train_metadata: dict = {}      # train_no -> {"name": ..., "type": ...}
    etrain_delays: dict = {}       # (train_no, station_code) -> avg_delay
    ml_train_set: set = set()
    station_coords: dict = {}      # station_code -> [lat, lon]
    station_full_names: dict = {}  # station_code -> Full Station Name
    ready: bool = False
    load_error: str = ""


def safe_float(val, default: float = 0.0) -> float:
    """Return a JSON-compliant float, replacing NaN/Inf/None with default."""
    if val is None or pd.isna(val):
        return default
    try:
        f = float(val)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return default


store = ModelStore()


@app.on_event("startup")
async def startup_check_and_load_model():
    """Validate startup config and load XGBoost model + encoders + feature data + schedules."""
    try:
        is_prod = os.environ.get("ENVIRONMENT", "development").lower() == "production"

        # 1. Environment check for production
        if is_prod:
            for required_var in ["ALLOWED_ORIGINS", "MODEL_A_PATH", "RECONCILED_DATA_PATH"]:
                if not os.environ.get(required_var):
                    raise ConfigurationError(f"Required environment variable '{required_var}' is missing in production")

        # 2. Check RECONCILED_DATA_PATH reachability if set
        rec_path_str = os.environ.get("RECONCILED_DATA_PATH")
        if rec_path_str:
            rec_path = Path(rec_path_str)
            if not rec_path.parent.exists():
                raise ConfigurationError(f"RECONCILED_DATA_PATH parent directory does not exist: {rec_path.parent}")
            log.info(f"RECONCILED_DATA_PATH configured: {rec_path} (exists={rec_path.exists()})")
        else:
            log.warning("RECONCILED_DATA_PATH unset; scraper live positions unavailable (using static snapshot).")

        # 3. Check MODEL_PATH
        if not MODEL_PATH.exists():
            store.load_error = f"model_a.json not found at {MODEL_PATH}"
            log.error(store.load_error)
            raise ModelNotLoadedError(store.load_error)

        log.info(f"Loading Model A from {MODEL_PATH} ...")
        store.model = xgb.XGBRegressor()
        store.model.load_model(str(MODEL_PATH))

        with open(ENCODER_PATH) as f:
            meta = json.load(f)
        store.encoders = meta
        store.feature_names = meta.get("feature_names", [])
        store.eval_metrics = meta.get("eval", {})

        if FEATURE_IMPORTANCE_PATH.exists():
            with open(FEATURE_IMPORTANCE_PATH) as f:
                fi = json.load(f)
            store.feature_importance = fi.get("feature_importance", {})

        # Load Model B (Precedence-Aware) if available
        if MODEL_B_PATH.exists():
            try:
                log.info(f"Loading Model B from {MODEL_B_PATH} ...")
                store.model_b = xgb.XGBRegressor()
                store.model_b.load_model(str(MODEL_B_PATH))
                if MODEL_B_ENCODER_PATH.exists():
                    with open(MODEL_B_ENCODER_PATH) as f:
                        meta_b = json.load(f)
                    store.model_b_encoders = meta_b
                    store.model_b_feature_names = meta_b.get("feature_names", [])
                    store.model_b_eval_metrics = meta_b.get("eval", {})
                if MODEL_B_IMPORTANCE_PATH.exists():
                    with open(MODEL_B_IMPORTANCE_PATH) as f:
                        fi_b = json.load(f)
                    store.model_b_feature_importance = fi_b.get("feature_importance", {})
                log.info(f"Model B loaded successfully ({len(store.model_b_feature_names)} features).")
            except Exception as e:
                log.warning(f"Could not load Model B: {e}")

        # Load confirmed Precedence Events if available
        if PRECEDENCE_EVENTS_PATH.exists():
            try:
                store.precedence_events = pd.read_parquet(PRECEDENCE_EVENTS_PATH)
                log.info(f"Loaded {len(store.precedence_events)} confirmed precedence events.")
            except Exception as e:
                log.warning(f"Could not load precedence events: {e}")

        # Load feature data for per-train aggregates used in ML inference (415 trains)
        if PARQUET_PATH.exists():
            log.info(f"Loading feature parquet ({PARQUET_PATH.name}) for inference lookups ...")
            desired_columns = [
                "train_no", "station_no", "station_name", "station_full_name",
                "station_zone", "date", "distance_from_origin",
                "arrival_time", "arrival_day", "departure_time", "departure_day",
                "train_name", "type_code",
                "section_id", "section_occupancy_count",
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
                "is_special_train",
                "delay", "residual_target",
                # Model B precedence features
                "precedence_risk_score_next_section",
                "historical_precedence_rate_vs_known_priority_trains",
                "precedence_conflict_detected",
                "precedence_confidence_score",
                "precedence_inferred_hold_min",
            ]
            import pyarrow.parquet as pq
            file_schema = pq.read_schema(PARQUET_PATH)
            read_cols = [c for c in desired_columns if c in file_schema.names]
            store.train_data = pd.read_parquet(PARQUET_PATH, columns=read_cols)
            store.ml_train_set = set(store.train_data["train_no"].unique())
            log.info(f"Loaded {len(store.train_data):,} ML feature rows for {len(store.ml_train_set)} trains")

        # Load master schedule table (all 8,673 Indian Railways trains)
        if SCHEDULE_PATH.exists():
            log.info("Loading master schedule table ...")
            store.schedule_data = pd.read_csv(SCHEDULE_PATH)
            log.info(f"Loaded schedules for {store.schedule_data['train_no'].nunique():,} trains")

        if TRAIN_DETAILS_PATH.exists():
            td = pd.read_csv(TRAIN_DETAILS_PATH)
            for _, r in td.iterrows():
                try:
                    tno = int(r["train_no"])
                    store.train_metadata[tno] = {
                        "name": str(r["train_name"]),
                        "type": str(r.get("type_code", "EXP-TRAINS")),
                    }
                except Exception:
                    pass

        if ETRAIN_DELAYS_PATH.exists():
            ed = pd.read_csv(ETRAIN_DELAYS_PATH)
            for _, r in ed.iterrows():
                try:
                    tno = int(r["train_number"])
                    stn = str(r["station_code"])
                    val = r.get("average_delay_minutes", 0.0)
                    store.etrain_delays[(tno, stn)] = safe_float(val, default=15.0)
                except Exception:
                    pass

        # Load station coordinates for replay stop enrichment
        if STATION_COORDS_PATH.exists():
            with open(STATION_COORDS_PATH, encoding="utf-8") as f:
                store.station_coords = json.load(f)
            log.info(f"Loaded {len(store.station_coords):,} station coordinates")

        # Load station full names for detailed replay view
        STATION_NAMES_PATH = ROOT / "Dataset" / "station_full_names.csv"
        if STATION_NAMES_PATH.exists():
            df_stn = pd.read_csv(STATION_NAMES_PATH)
            for _, r in df_stn.iterrows():
                try:
                    c = str(r["station_name"]).strip().upper()
                    raw_n = str(r.get("station_full_name", "")).strip()
                    n = format_station_name(raw_n) if raw_n and raw_n != "nan" else c
                    if c and n:
                        store.station_full_names[c] = n
                except Exception:
                    pass
            log.info(f"Loaded {len(store.station_full_names):,} station full names")

        # Initialize Model B switch state (default: False until live scraped dataset is active)
        store.model_b_enabled = os.environ.get("ENABLE_MODEL_B", "false").lower() in ("true", "1")
        log.info(f"Model B switch initialized to: {'ENABLED' if store.model_b_enabled else 'DISABLED'}")

        store.ready = True
        log.info("Model store ready.")
    except Exception as e:
        store.load_error = str(e)
        log.error(f"Model load failed: {e}", exc_info=True)


def format_station_name(name: str) -> str:
    """Format all-caps or abbreviated station names into clean title-cased names."""
    if not name or str(name) == "nan":
        return ""
    words = str(name).strip().split()
    formatted = []
    for w in words:
        w_up = w.upper()
        if w_up in ("JN", "JN.", "JCT", "JUNCTION"):
            formatted.append("Junction")
        elif w_up in ("TERM", "TERMINUS", "TERMINAL"):
            formatted.append("Terminus")
        elif w_up in ("CANTT", "CANTT.", "CANT"):
            formatted.append("Cantt")
        elif w_up in ("RD", "RD."):
            formatted.append("Road")
        elif w_up in ("CY", "CITY"):
            formatted.append("City")
        elif w_up in ("CENTRAL", "CTRL"):
            formatted.append("Central")
        elif w_up in ("NORTH", "NRTH"):
            formatted.append("North")
        elif w_up in ("SOUTH", "STH"):
            formatted.append("South")
        elif w_up in ("EAST", "EST"):
            formatted.append("East")
        elif w_up in ("WEST", "WST"):
            formatted.append("West")
        elif w_up in ("CABIN", "CBN"):
            formatted.append("Cabin")
        elif w_up in ("HG", "HALT", "PH", "PASSENGER"):
            formatted.append("Halt")
        elif w_up in ("IR", "NR", "WR", "CR", "ER", "SR", "ECR", "NCR", "NER", "NFR", "NWR", "SECR", "SWR", "WCR"):
            formatted.append(w_up)
        else:
            formatted.append(w.capitalize())
    return " ".join(formatted)


def compute_station_schedule_times(
    sched_arr: str,
    sched_dep: str,
    delay_min: float,
    is_origin: bool = False,
    is_dest: bool = False,
) -> dict:
    """
    Computes exact scheduled and expected arrival/departure times, expected delays,
    and halt durations according to standard Indian Railways timetable arithmetic.
    """
    def to_min(t_str):
        if not t_str or str(t_str) == "nan" or str(t_str) == "--:--" or ":" not in str(t_str):
            return None
        parts = str(t_str).split(":")
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except Exception:
            return None

    def to_str(m_val, day_offset=0):
        if m_val is None:
            return "--:--"
        days = m_val // (24 * 60) + day_offset
        norm_m = m_val % (24 * 60)
        hh = norm_m // 60
        mm = norm_m % 60
        base = f"{hh:02d}:{mm:02d}"
        if days > 0:
            return f"{base} (+{days}d)"
        return base

    arr_m = to_min(sched_arr)
    dep_m = to_min(sched_dep)
    d = max(0, int(round(delay_min or 0)))

    # Halt duration calculation
    halt_str = "--"
    if is_origin:
        halt_str = "Origin"
    elif is_dest:
        halt_str = "Destination"
    elif arr_m is not None and dep_m is not None:
        halt_m = (dep_m - arr_m) % (24 * 60)
        halt_str = f"{halt_m} min"

    # Scheduled & Expected arrival
    if is_origin:
        clean_sched_arr = "Origin"
        exp_arr = "Origin"
    elif arr_m is not None:
        clean_sched_arr = to_str(arr_m)
        exp_arr = to_str(arr_m + d)
    else:
        clean_sched_arr = "--:--"
        exp_arr = "--:--"

    # Scheduled & Expected departure
    if is_dest:
        clean_sched_dep = "Destination"
        exp_dep = "Destination"
    elif dep_m is not None:
        clean_sched_dep = to_str(dep_m)
        scheduled_halt = ((dep_m - arr_m) % (24 * 60)) if (arr_m is not None and not is_origin) else 0
        min_halt = min(scheduled_halt, 5)
        if arr_m is not None and not is_origin:
            exp_dep_m = max(dep_m + d, arr_m + d + min_halt)
        else:
            exp_dep_m = dep_m + d
        exp_dep = to_str(exp_dep_m)
    else:
        clean_sched_dep = "--:--"
        exp_dep = "--:--"

    return {
        "scheduled_arr": clean_sched_arr,
        "scheduled_dep": clean_sched_dep,
        "expected_arr": exp_arr,
        "expected_dep": exp_dep,
        "expected_delay_min": round(float(delay_min or 0), 1),
        "actual_delay_min": round(float(delay_min or 0), 1),
        "halt_duration": halt_str,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def encode_features_for_inference(row: pd.Series) -> np.ndarray:
    """Encode a single row for model inference, matching training feature order."""
    enc = store.encoders

    # Frequency encode section_id
    section_id = str(row.get("section_id", ""))
    section_freq = enc.get("section_id_freq", {}).get(section_id, 0)

    # Label encode type_code
    type_classes = enc.get("type_code", ["EXP-TRAINS"])
    tc = str(row.get("type_code", "EXP-TRAINS"))
    type_enc = type_classes.index(tc) if tc in type_classes else 0

    # Label encode station_zone
    zone_classes = enc.get("station_zone", ["NR"])
    zone = str(row.get("station_zone", "NR"))
    zone_enc = zone_classes.index(zone) if zone in zone_classes else 0

    feature_map = {
        "station_no":                   float(row.get("station_no", 1)),
        "distance_from_origin":         float(row.get("distance_from_origin", 0)),
        "arrival_day":                  float(row.get("arrival_day", 1)),
        "departure_day":                float(row.get("departure_day", 1)),
        "is_special_train":             float(bool(row.get("is_special_train", False))),
        "tracks":                       float(row.get("tracks", np.nan)),
        "electrified":                  float(row.get("electrified", np.nan)),
        "usage":                        float(row.get("usage", np.nan)),
        "expected_route_distance_km":   float(row.get("expected_route_distance_km", np.nan)),
        "section_occupancy_count":      float(row.get("section_occupancy_count", 1)),
        "hour_of_day_sin":              float(row.get("hour_of_day_sin", 0)),
        "hour_of_day_cos":              float(row.get("hour_of_day_cos", 1)),
        "day_of_week_sin":              float(row.get("day_of_week_sin", 0)),
        "day_of_week_cos":              float(row.get("day_of_week_cos", 1)),
        "month":                        float(row.get("month", 6)),
        "is_fog_season_flag":           float(bool(row.get("is_fog_season_flag", False))),
        "stops_remaining_count":        float(row.get("stops_remaining_count", 1)),
        "distance_remaining_total_km":  float(row.get("distance_remaining_total_km", 0)),
        "elapsed_journey_pct":          float(row.get("elapsed_journey_pct", 0)),
        "section_avg_delay_30d":        float(row.get("section_avg_delay_30d", 20)),
        "section_avg_delay_90d":        float(row.get("section_avg_delay_90d", 20)),
        "section_avg_delay_365d":       float(row.get("section_avg_delay_365d", 20)),
        "train_number_avg_delay_30d":   float(row.get("train_number_avg_delay_30d", 20)),
        "zone_avg_punctuality_pct":     float(row.get("zone_avg_punctuality_pct", 50)),
        "delay_trend_last_3_points":    float(row.get("delay_trend_last_3_points", 0)),
        "recovery_margin_remaining_min": float(row.get("recovery_margin_remaining_min", 0)),
        "etrain_avg_delay":             float(row.get("etrain_avg_delay", 30)),
        "etrain_pct_right_time":        float(row.get("etrain_pct_right_time", 0.4)),
        "active_tsr_count_on_route":    float(row.get("active_tsr_count_on_route", 0)),
        "baseline_delay_estimate":      float(row.get("baseline_delay_estimate", 20)),
        "section_id_freq":              float(section_freq),
        "type_code_enc":                float(type_enc),
        "station_zone_enc":             float(zone_enc),
    }

    # Build vector in the exact same order as training
    feat_names = store.feature_names or list(feature_map.keys())
    vec = np.array([feature_map.get(f, 0.0) for f in feat_names], dtype=float)
    return vec


def get_train_latest_snapshot(train_no: int) -> Optional[pd.DataFrame]:
    """Get the most recent date's stop data for a train from ML features or schedule table."""
    if store.train_data is not None and train_no in store.ml_train_set:
        sub = store.train_data[store.train_data["train_no"] == train_no]
        if not sub.empty:
            latest_date = sub["date"].max()
            df = sub[sub["date"] == latest_date].sort_values("station_no").reset_index(drop=True).copy()
            df["_is_schedule_only"] = False
            return df

    # Fallback to schedule dataset (all 8,673 trains)
    if store.schedule_data is not None:
        sub = store.schedule_data[store.schedule_data["train_no"] == train_no]
        if not sub.empty:
            df = sub.sort_values("station_no").reset_index(drop=True).copy()
            meta = store.train_metadata.get(train_no, {})
            tname = meta.get("name", f"Train {train_no}")
            ttype = meta.get("type", "EXP-TRAINS")
            df["train_name"] = tname
            df["type_code"] = ttype
            df["station_full_name"] = df["station_name"]

            cat_delay = 10.0 if any(k in ttype for k in ["RAJ", "T18"]) else (15.0 if any(k in ttype for k in ["SF", "SHT"]) else 25.0)
            delays = []
            for _, r in df.iterrows():
                stn = str(r["station_name"])
                ed = store.etrain_delays.get((train_no, stn))
                delays.append(safe_float(ed, default=cat_delay))

            df["baseline_delay_estimate"] = delays
            df["stops_remaining_count"] = (len(df) - df["station_no"]).fillna(0).astype(int)
            max_dist = safe_float(df["distance_from_origin"].max(), default=0.0)
            df["distance_remaining_total_km"] = (max_dist - df["distance_from_origin"].fillna(0)).astype(float)
            df["_is_schedule_only"] = True
            return df

    return None


def minutes_to_hhmm(total_minutes: float) -> str:
    """Convert absolute minutes (day-offset) to a readable HH:MM string."""
    if math.isnan(total_minutes) or total_minutes < 0:
        return "--:--"
    mins_in_day = int(total_minutes) % 1440
    hh = mins_in_day // 60
    mm = mins_in_day % 60
    return f"{hh:02d}:{mm:02d}"


def delay_label(delay_min: float) -> str:
    if delay_min <= 0:
        return "On Time"
    elif delay_min < 15:
        return "Slight Delay"
    elif delay_min < 60:
        return f"{int(delay_min)} min late"
    else:
        hours = delay_min / 60
        return f"{hours:.1f} hr late"


def encode_features_for_model_b(row: pd.Series, precedence_risk: float = 0.0) -> dict:
    """Encode features specifically matching Model B's 35 trained features."""
    enc = store.model_b_encoders or store.encoders

    section_id = str(row.get("section_id", ""))
    section_freq = enc.get("section_id_freq", {}).get(section_id, 0)

    type_classes = enc.get("type_code", ["EXP-TRAINS"])
    tc = str(row.get("type_code", "EXP-TRAINS"))
    type_enc = type_classes.index(tc) if tc in type_classes else 0

    zone_classes = enc.get("station_zone", ["NR"])
    zone = str(row.get("station_zone", "NR"))
    zone_enc = zone_classes.index(zone) if zone in zone_classes else 0

    risk_val = precedence_risk if precedence_risk > 0.0 else safe_float(row.get("precedence_risk_score_next_section"), 0.0)
    hist_rate = safe_float(row.get("historical_precedence_rate_vs_known_priority_trains"), 0.0)

    return {
        "station_no":                   float(row.get("station_no", 1)),
        "distance_from_origin":         float(row.get("distance_from_origin", 0)),
        "arrival_day":                  float(row.get("arrival_day", 1)),
        "departure_day":                float(row.get("departure_day", 1)),
        "is_special_train":             float(bool(row.get("is_special_train", False))),
        "tracks":                       float(row.get("tracks", np.nan)),
        "electrified":                  float(row.get("electrified", np.nan)),
        "usage":                        float(row.get("usage", np.nan)),
        "expected_route_distance_km":   float(row.get("expected_route_distance_km", np.nan)),
        "section_occupancy_count":      float(row.get("section_occupancy_count", 1)),
        "hour_of_day_sin":              float(row.get("hour_of_day_sin", 0)),
        "hour_of_day_cos":              float(row.get("hour_of_day_cos", 1)),
        "day_of_week_sin":              float(row.get("day_of_week_sin", 0)),
        "day_of_week_cos":              float(row.get("day_of_week_cos", 1)),
        "month":                        float(row.get("month", 6)),
        "is_fog_season_flag":           float(bool(row.get("is_fog_season_flag", False))),
        "stops_remaining_count":        float(row.get("stops_remaining_count", 1)),
        "distance_remaining_total_km":  float(row.get("distance_remaining_total_km", 0)),
        "elapsed_journey_pct":          float(row.get("elapsed_journey_pct", 0)),
        "section_avg_delay_30d":        float(row.get("section_avg_delay_30d", 20)),
        "section_avg_delay_90d":        float(row.get("section_avg_delay_90d", 20)),
        "section_avg_delay_365d":       float(row.get("section_avg_delay_365d", 20)),
        "train_number_avg_delay_30d":   float(row.get("train_number_avg_delay_30d", 20)),
        "zone_avg_punctuality_pct":     float(row.get("zone_avg_punctuality_pct", 50)),
        "delay_trend_last_3_points":    float(row.get("delay_trend_last_3_points", 0)),
        "recovery_margin_remaining_min":float(row.get("recovery_margin_remaining_min", 0)),
        "etrain_avg_delay":             float(row.get("etrain_avg_delay", 30)),
        "etrain_pct_right_time":        float(row.get("etrain_pct_right_time", 0.4)),
        "active_tsr_count_on_route":    float(row.get("active_tsr_count_on_route", 0)),
        "baseline_delay_estimate":      float(row.get("baseline_delay_estimate", 20)),
        "precedence_risk_score_next_section": float(risk_val),
        "historical_precedence_rate_vs_known_priority_trains": float(hist_rate),
        "section_id_freq":              float(section_freq),
        "type_code_enc":                float(type_enc),
        "station_zone_enc":             float(zone_enc),
    }


def get_train_precedence_conflicts(train_no: int, stops: pd.DataFrame) -> dict:
    """Analyze confirmed precedence events along this train's route."""
    conflicts = []
    max_risk = 0.0

    if store.precedence_events is not None and not store.precedence_events.empty:
        ev = store.precedence_events
        as_delayed = ev[ev["delayed_train_no"] == train_no]
        as_priority = ev[ev["priority_train_no"] == train_no]

        for _, r in as_delayed.iterrows():
            conf_score = float(r.get("confidence_score", 0.0))
            max_risk = max(max_risk, conf_score)
            p_no = int(r["priority_train_no"])
            p_meta = store.train_metadata.get(p_no, {})
            conflicts.append({
                "section_id": str(r["section_id"]),
                "role": "delayed",
                "interacting_train_no": p_no,
                "interacting_train_name": p_meta.get("name", f"Train {p_no}"),
                "confidence_score": round(conf_score, 2),
                "total_crossings_observed": int(r.get("total_crossings_observed", 1)),
                "estimated_hold_min": round(conf_score * 18.0, 1),
                "description": f"Subject to hold behind priority Train {p_no} ({p_meta.get('name', '')}) on section {r['section_id']}"
            })

        for _, r in as_priority.iterrows():
            conf_score = float(r.get("confidence_score", 0.0))
            d_no = int(r["delayed_train_no"])
            d_meta = store.train_metadata.get(d_no, {})
            conflicts.append({
                "section_id": str(r["section_id"]),
                "role": "priority",
                "interacting_train_no": d_no,
                "interacting_train_name": d_meta.get("name", f"Train {d_no}"),
                "confidence_score": round(conf_score, 2),
                "total_crossings_observed": int(r.get("total_crossings_observed", 1)),
                "estimated_hold_min": 0.0,
                "description": f"Has track clearance priority over Train {d_no} ({d_meta.get('name', '')}) on section {r['section_id']}"
            })

    # Check if features table has precomputed precedence risk
    mid_idx = max(0, len(stops) // 2)
    mid_stop = stops.iloc[mid_idx]
    feature_risk = safe_float(mid_stop.get("precedence_risk_score_next_section"), 0.0)
    risk_score = max(max_risk, feature_risk)

    return {
        "train_no": train_no,
        "train_name": str(mid_stop.get("train_name", f"Train {train_no}")),
        "precedence_active": len(conflicts) > 0 or risk_score > 0.05,
        "precedence_risk_score": round(risk_score, 2),
        "total_conflicts_count": len(conflicts),
        "conflicts": conflicts[:10],
        "model_b_available": store.model_b is not None,
    }


# ---------------------------------------------------------------------------
# What-If overrides (A1 + Phase 2 Precedence Simulation)
# ---------------------------------------------------------------------------

# Fields allowed to be overridden by the client, with their plausible ranges
_WHAT_IF_ALLOWED = {
    "reported_delay_min":                 (-60, 3000),   # minutes; negative = running early
    "section_occupancy_count":            (0, 200),      # trains sharing the section
    "precedence_risk_score_next_section": (0.0, 1.0),    # simulated precedence conflict risk
}


def apply_what_if_overrides(feature_map: dict, overrides: dict) -> dict:
    """
    Returns a copy of feature_map with allowed fields replaced by hypothetical values.
    Raises WhatIfOverrideInvalidError for unknown fields or out-of-range values.
    Per 05_Backend_API_Spec.md §2 apply_what_if_overrides().
    """
    result = dict(feature_map)
    for key, value in overrides.items():
        if key not in _WHAT_IF_ALLOWED:
            raise WhatIfOverrideInvalidError(
                f"'{key}' is not an allowed what-if field. "
                f"Allowed fields: {list(_WHAT_IF_ALLOWED.keys())}",
                detail={"rejected_field": key},
            )
        lo, hi = _WHAT_IF_ALLOWED[key]
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise WhatIfOverrideInvalidError(
                f"'{key}' must be a number, got: {value!r}",
                detail={"field": key, "value": value},
            )
        if not (lo <= value <= hi):
            raise WhatIfOverrideInvalidError(
                f"'{key}' value {value} is outside the plausible range [{lo}, {hi}].",
                detail={"field": key, "value": value, "range": [lo, hi]},
            )
        # Map what-if field names to internal feature names
        if key == "reported_delay_min":
            result["baseline_delay_estimate"] = value
        elif key == "section_occupancy_count":
            result["section_occupancy_count"] = value
        elif key == "precedence_risk_score_next_section":
            result["precedence_risk_score_next_section"] = value
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    freshness = get_data_freshness()
    return {
        "status": "ok" if store.ready else "degraded",
        "model_a_loaded": store.model is not None,
        "model_b_loaded": store.model_b is not None,
        "model_b_enabled": store.model_b_enabled,
        "model_loaded": (store.model is not None or store.model_b is not None),
        "precedence_events_count": len(store.precedence_events) if store.precedence_events is not None else 0,
        "trains_indexed": store.train_data["train_no"].nunique() if store.train_data is not None else 0,
        "eval_model_a": store.eval_metrics,
        "eval_model_b": store.model_b_eval_metrics,
        "eval": store.eval_metrics,
        "error": store.load_error or None,
        # Live scraper data freshness (A3)
        "last_scraper_update": freshness["last_scraper_update"],
        "data_freshness_warning": freshness["data_freshness_warning"],
        "reconciled_data_configured": freshness["reconciled_data_configured"],
        "live_trains_count": freshness["live_trains_count"],
    }


@app.get("/config/model-b")
def get_model_b_config():
    """Returns the current operational status of Model B (Precedence-Aware)."""
    return {
        "model_b_enabled": store.model_b_enabled,
        "model_b_loaded": store.model_b is not None,
        "status": "active" if store.model_b_enabled else "disabled_pending_scraper",
        "message": "Model B enabled" if store.model_b_enabled else "Model B disabled (serving Model A baseline pending scraped dataset)"
    }


@app.post("/config/model-b")
def set_model_b_config(payload: dict = Body(...)):
    """Toggles Model B operational status globally."""
    enabled = bool(payload.get("enabled", False))
    store.model_b_enabled = enabled
    log.info(f"Model B global switch updated to: {store.model_b_enabled}")
    return {
        "model_b_enabled": store.model_b_enabled,
        "status": "active" if store.model_b_enabled else "disabled_pending_scraper",
        "message": f"Model B (Precedence-Aware) set to {'ON' if store.model_b_enabled else 'OFF'}"
    }


@app.get("/precedence")
def precedence(train_no: int = Query(..., description="Indian Railways train number")):
    """
    Returns precedence conflict risk, active conflict pairs, and precedence features.
    Per 07_Dynamic_Polling_Spec.md Part C.
    """
    if train_no <= 0:
        raise InvalidTrainNumberError(train_no=train_no)

    if not store.ready:
        raise ModelNotLoadedError("Model not loaded — service is starting up")

    stops = get_train_latest_snapshot(train_no)
    if stops is None or stops.empty:
        raise InvalidTrainNumberError(train_no=train_no)

    return get_train_precedence_conflicts(train_no, stops)


@app.get("/predict")
def predict(
    train_no: int = Query(..., description="Indian Railways train number"),
    what_if: Optional[str] = Query(None, description="JSON-encoded what-if overrides"),
    enable_model_b: Optional[bool] = Query(None, description="Client override to toggle Model B (Precedence-Aware) on/off"),
):
    """
    Returns predicted ETA, delay, and confidence for a train's destination.
    Accepts optional what_if overrides (JSON-encoded dict).
    Serves Model B (Precedence-Aware) when precedence risk/conflicts exist and Model B is switched ON,
    falling back to Model A and baseline when appropriate or when Model B is switched OFF.
    """
    # A4: explicit positive-integer guard
    if train_no <= 0:
        raise InvalidTrainNumberError(train_no=train_no)

    # A1: parse and validate what_if JSON
    overrides: dict = {}
    if what_if:
        try:
            overrides = json.loads(what_if)
            if not isinstance(overrides, dict):
                raise ValueError("must be a JSON object")
        except (json.JSONDecodeError, ValueError) as e:
            raise WhatIfOverrideInvalidError(f"what_if parameter must be valid JSON: {e}")

        for key, value in overrides.items():
            if key not in _WHAT_IF_ALLOWED:
                raise WhatIfOverrideInvalidError(
                    f"Invalid what-if override: '{key}' is not a recognized feature. "
                    f"Allowed fields: {list(_WHAT_IF_ALLOWED.keys())}",
                    detail={"rejected_field": key},
                )
            lo, hi = _WHAT_IF_ALLOWED[key]
            try:
                val_num = float(value)
            except (TypeError, ValueError):
                raise WhatIfOverrideInvalidError(
                    f"Invalid what-if override: '{key}' must be a number, got: {value!r}",
                    detail={"field": key, "value": value},
                )
            if not (lo <= val_num <= hi):
                raise WhatIfOverrideInvalidError(
                    f"Invalid what-if override: '{key}' value {val_num} is outside allowed range [{lo}, {hi}].",
                    detail={"field": key, "value": val_num, "range": [lo, hi]},
                )

    if not store.ready or store.model is None:
        raise ModelNotLoadedError("Model not loaded — service is starting up")

    stops = get_train_latest_snapshot(train_no)
    if stops is None or stops.empty:
        raise InvalidTrainNumberError(train_no=train_no)

    # C2: Use live reconciled position if available, else mid-route static snapshot
    live_row = get_latest_reconciled_row(train_no)
    mid_idx = max(0, len(stops) // 2)
    current_stop = stops.iloc[mid_idx]
    dest_stop    = stops.iloc[-1]
    is_sched_only = bool(current_stop.get("_is_schedule_only", False) or (train_no not in store.ml_train_set))

    # Precedence conflict check & Model B switch gating
    model_b_allowed = enable_model_b if enable_model_b is not None else store.model_b_enabled
    precedence_info = get_train_precedence_conflicts(train_no, stops)
    precedence_risk = float(precedence_info.get("precedence_risk_score", 0.0))
    has_precedence_conflict = precedence_info.get("precedence_active", False)
    use_model_b = (
        bool(model_b_allowed)
        and store.model_b is not None
        and not is_sched_only
        and (has_precedence_conflict or precedence_risk > 0.05 or "precedence_risk_score_next_section" in overrides)
    )

    # Determine data_confidence_score based on data source
    if live_row is not None:
        data_confidence = float(live_row.get("source_agreement_score", 0.72))
        model_used_label = "model_b" if use_model_b else "model_a"
        live_delay = float(live_row.get("delay", current_stop.get("baseline_delay_estimate", 20)))
    else:
        ttype = str(current_stop.get("type_code", ""))
        data_confidence = 0.85 if any(k in ttype for k in ["RAJ", "T18", "SHT"]) else 0.72
        if is_sched_only:
            model_used_label = "baseline"
        elif use_model_b:
            model_used_label = "model_b"
        else:
            model_used_label = "model_a_static"
        live_delay = None

    if is_sched_only:
        # Schedule-only train (not in 415 ML historical training set)
        raw_base = live_delay if live_delay is not None else current_stop.get("baseline_delay_estimate")
        baseline = safe_float(raw_base, default=15.0)
        if overrides:
            if "reported_delay_min" in overrides:
                baseline = safe_float(overrides["reported_delay_min"], default=baseline)
            model_used_label = "model_a_whatif"
        predicted_residual = 0.0
        predicted_delay = max(0.0, baseline)
        arr_str = str(dest_stop.get("arrival_time", "") or "12:00")
        predicted_eta_str = arr_str if arr_str not in ("nan", "--:--") else "12:00"
    elif use_model_b:
        # Model B (Precedence-Aware inference)
        try:
            feat_map_dict = encode_features_for_model_b(current_stop, precedence_risk=precedence_risk)
            if live_delay is not None:
                feat_map_dict["baseline_delay_estimate"] = live_delay

            if overrides:
                feat_map_dict = apply_what_if_overrides(feat_map_dict, overrides)
                model_used_label = "model_b_whatif"
            else:
                model_used_label = "model_b"

            feat_names = store.model_b_feature_names or list(feat_map_dict.keys())
            feat_vec = [feat_map_dict.get(f, 0.0) for f in feat_names]
            feat_df = pd.DataFrame([feat_vec], columns=feat_names)
            predicted_residual = float(store.model_b.predict(feat_df)[0])

            # OutOfRange guard
            if math.isnan(predicted_residual) or math.isinf(predicted_residual) or abs(predicted_residual) > 2000:
                log.warning(f"OutOfRange prediction for {train_no} with Model B: {predicted_residual} — using baseline")
                predicted_residual = 0.0
                model_used_label = "baseline"
        except WhatIfOverrideInvalidError:
            raise
        except Exception as e:
            log.error(f"Model B prediction error for train {train_no}: {e}")
            predicted_residual = 0.0
            model_used_label = "baseline"

        raw_base = live_delay if live_delay is not None else current_stop.get("baseline_delay_estimate")
        baseline = safe_float(raw_base, default=20.0)
        predicted_residual = safe_float(predicted_residual, default=0.0)
        predicted_delay = max(0.0, baseline + predicted_residual)

        dest_sched_min = safe_float(dest_stop.get("baseline_eta"), default=0.0)
        predicted_eta_min = dest_sched_min + predicted_residual
        predicted_eta_str = minutes_to_hhmm(predicted_eta_min)
    else:
        # Model A inference
        try:
            feat_map = encode_features_for_inference(current_stop)
            feat_map_dict = dict(zip(
                store.feature_names or [],
                feat_map.tolist() if hasattr(feat_map, 'tolist') else feat_map,
            ))
            if live_delay is not None:
                feat_map_dict["baseline_delay_estimate"] = live_delay

            # A1: apply what-if overrides
            if overrides:
                feat_map_dict = apply_what_if_overrides(feat_map_dict, overrides)
                model_used_label = "model_a_whatif"

            feat_names = store.feature_names or list(feat_map_dict.keys())
            feat_vec = [feat_map_dict.get(f, 0.0) for f in feat_names]
            feat_df = pd.DataFrame([feat_vec], columns=feat_names)
            predicted_residual = float(store.model.predict(feat_df)[0])

            # OutOfRange guard
            if math.isnan(predicted_residual) or math.isinf(predicted_residual) or abs(predicted_residual) > 2000:
                log.warning(f"OutOfRange prediction for {train_no}: {predicted_residual} — using baseline")
                predicted_residual = 0.0
                model_used_label = "baseline"

        except WhatIfOverrideInvalidError:
            raise
        except Exception as e:
            log.error(f"Prediction error for train {train_no}: {e}")
            predicted_residual = 0.0
            model_used_label = "baseline"

        raw_base = live_delay if live_delay is not None else current_stop.get("baseline_delay_estimate")
        baseline = safe_float(raw_base, default=20.0)
        predicted_residual = safe_float(predicted_residual, default=0.0)
        predicted_delay = max(0.0, baseline + predicted_residual)

        # ETA = scheduled arrival at destination + predicted delay
        dest_sched_min = safe_float(dest_stop.get("baseline_eta"), default=0.0)
        predicted_eta_min = dest_sched_min + predicted_residual
        predicted_eta_str = minutes_to_hhmm(predicted_eta_min)

    # Confidence below threshold -> degrade to baseline
    DATA_CONFIDENCE_THRESHOLD = float(os.environ.get("DATA_CONFIDENCE_THRESHOLD", "0.3"))
    if data_confidence < DATA_CONFIDENCE_THRESHOLD:
        model_used_label = "baseline"
        log.info(f"Train {train_no}: data_confidence {data_confidence:.2f} below threshold, using baseline")

    # A2: per-prediction uncertainty
    active_eval = store.model_b_eval_metrics if use_model_b else store.eval_metrics
    test_mae = safe_float(active_eval.get("test_mae_min"), default=20.0)
    uncertainty_low  = round(max(0.0, predicted_delay - test_mae * 0.5), 1)
    uncertainty_high = round(predicted_delay + test_mae * 0.5, 1)

    now = datetime.utcnow()
    eta_abs      = now + timedelta(minutes=float(predicted_delay + 60))
    ci_lower     = eta_abs - timedelta(minutes=float(test_mae * 0.5))
    ci_upper     = eta_abs + timedelta(minutes=float(test_mae * 0.5))
    baseline_abs = now + timedelta(minutes=float(baseline + 60))

    return {
        # Primary spec fields
        "train_no": train_no,
        "train_name": str(current_stop.get("train_name", f"Train {train_no}")),
        "predicted_delay_min": round(predicted_delay, 1),
        "predicted_residual_min": round(predicted_residual, 1),
        "baseline_delay_min": round(baseline, 1),
        "predicted_eta": predicted_eta_str,
        "delay_label": delay_label(predicted_delay),
        "confidence_score": data_confidence,
        "uncertainty_range": [max(0, uncertainty_low), uncertainty_high],
        "current_station": str(current_stop.get("station_name", "?")),
        "destination": str(dest_stop.get("station_name", "?")),
        "destination_full": str(dest_stop.get("station_full_name", dest_stop.get("station_name", "?"))),
        "stops_remaining": int(safe_float(current_stop.get("stops_remaining_count"), 0)),
        "model_version": "model_b_v1" if use_model_b else "model_a_v1",
        "timestamp": now.isoformat() + "Z",
        "live_data_used": live_row is not None,
        # ETACard.jsx aliases
        "current_delay_min": round(predicted_delay, 1),
        "eta": eta_abs.isoformat() + "Z",
        "confidence_interval_lower": ci_lower.isoformat() + "Z",
        "confidence_interval_upper": ci_upper.isoformat() + "Z",
        "baseline_eta": baseline_abs.isoformat() + "Z",
        "last_station_name": str(current_stop.get("station_full_name",
                                  current_stop.get("station_name", "--"))),
        "last_station_code": str(current_stop.get("station_name", "--")),
        "data_confidence_score": data_confidence,
        "model_used": model_used_label,
        "type_code": str(current_stop.get("type_code", "EXP-TRAINS")),
        # Precedence Phase 2 fields & Model B toggle status
        "model_b_enabled": bool(model_b_allowed),
        "precedence_adjustment_applied": bool(use_model_b),
        "precedence_active": precedence_info["precedence_active"],
        "precedence_risk_score": precedence_info["precedence_risk_score"],
        "precedence_conflicts_count": precedence_info["total_conflicts_count"],
        "precedence_conflicts": precedence_info["conflicts"],
    }


@app.get("/explain")
def explain(train_no: int = Query(..., description="Train number")):
    """
    Returns top delay factors for the given train in human-readable form.
    Uses the model's feature importance combined with the train's feature values.
    """
    if train_no <= 0:
        raise InvalidTrainNumberError(train_no=train_no)

    if not store.ready:
        raise ModelNotLoadedError("Model not loaded")

    stops = get_train_latest_snapshot(train_no)
    if stops is None or stops.empty:
        raise InvalidTrainNumberError(train_no=train_no)

    mid_stop = stops.iloc[max(0, len(stops) // 2)]
    is_sched_only = bool(mid_stop.get("_is_schedule_only", False) or (train_no not in store.ml_train_set))

    if is_sched_only:
        meta = store.train_metadata.get(train_no, {})
        ttype = meta.get("type", "EXP-TRAINS")
        is_priority = any(k in ttype for k in ["RAJ", "T18", "SHT"])
        top_delay_factors = [
            "High priority service with green corridor section clearance" if is_priority else "Moderate section density on approaching division corridor",
            "Scheduled buffer maintained across intermediate divisions" if is_priority else "Junction interlocking and crossing precedence window",
            "Historical section punctuality within normal operating tolerance"
        ]
        curr_d = safe_float(mid_stop.get("baseline_delay_estimate"), default=15.0)
        return {
            "train_no": train_no,
            "train_name": str(mid_stop.get("train_name", f"Train {train_no}")),
            "current_delay_min": round(curr_d, 1),
            "top_factors": [],
            "top_delay_factors": top_delay_factors,
            "model_version": "baseline_v1",
        }

    FEATURE_LABELS = {
        "baseline_delay_estimate":       "Existing delay carried forward",
        "section_avg_delay_30d":         "This section's recent delay history (30d)",
        "section_avg_delay_90d":         "This section's seasonal delay pattern (90d)",
        "train_number_avg_delay_30d":    "This train's own punctuality record",
        "delay_trend_last_3_points":     "Delay worsening or improving trend",
        "recovery_margin_remaining_min": "Scheduled recovery time remaining",
        "section_occupancy_count":       "Track congestion (other trains sharing section)",
        "is_fog_season_flag":            "Winter fog season (Dec-Feb)",
        "elapsed_journey_pct":           "Journey progress (later = more chance to recover)",
        "distance_remaining_total_km":   "Distance remaining to destination",
        "etrain_avg_delay":              "Historical average delay for this train",
        "hour_of_day_sin":               "Time of day (peak hours)",
        "month":                         "Current month",
        "type_code_enc":                 "Train priority class",
        "zone_avg_punctuality_pct":      "Railway zone punctuality record",
    }

    # Sort global importance, take top 5
    top_features = sorted(store.feature_importance.items(), key=lambda x: x[1], reverse=True)[:5]

    factors = []
    for feat, imp_score in top_features:
        val = mid_stop.get(feat, None)
        label = FEATURE_LABELS.get(feat, feat.replace("_", " ").title())

        impact = "neutral"
        if val is not None and not (isinstance(val, float) and math.isnan(val)):
            if feat in ("baseline_delay_estimate", "section_avg_delay_30d",
                        "train_number_avg_delay_30d", "delay_trend_last_3_points",
                        "section_occupancy_count", "etrain_avg_delay"):
                impact = "negative" if float(val) > 10 else "positive"
            elif feat in ("recovery_margin_remaining_min", "zone_avg_punctuality_pct",
                          "etrain_pct_right_time"):
                impact = "positive" if float(val) > 20 else "negative"
            elif feat == "is_fog_season_flag":
                impact = "negative" if val else "positive"

        factors.append({
            "feature": feat,
            "label": label,
            "value": round(float(val), 2) if isinstance(val, (int, float)) and not math.isnan(float(val)) else None,
            "importance_score": round(imp_score, 4),
            "impact": impact,
        })

    baseline = float(mid_stop.get("baseline_delay_estimate", 20))
    top_delay_factors = [f["label"] for f in factors]

    return {
        "train_no": train_no,
        "train_name": str(mid_stop.get("train_name", f"Train {train_no}")),
        "current_delay_min": round(baseline, 1),
        "top_factors": factors,
        "top_delay_factors": top_delay_factors,
        "model_version": "model_a_v1",
    }


@app.get("/replay")
def replay(
    train_no: int = Query(...),
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD; defaults to most recent"),
):
    """
    Returns stop-by-stop delay history for a train on a specific date.
    Used by the frontend LiveReplay component.
    """
    if train_no <= 0:
        raise InvalidTrainNumberError(train_no=train_no)

    sub = store.train_data[store.train_data["train_no"] == train_no] if (store.train_data is not None and train_no in store.ml_train_set) else pd.DataFrame()

    if sub.empty:
        # Check master schedule dataset (all 8,673 trains)
        if store.schedule_data is not None:
            sched_sub = store.schedule_data[store.schedule_data["train_no"] == train_no]
            if not sched_sub.empty:
                if date:
                    import re
                    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
                        raise WhatIfOverrideInvalidError(f"date must be in YYYY-MM-DD format")
                    # Schedule-only train has no past date recordings
                    if date < "2025-01-01":
                        raise NoActiveJourneyError(train_no=train_no, date=date)

                day_data = sched_sub.sort_values("station_no").reset_index(drop=True)
                meta = store.train_metadata.get(train_no, {})
                tname = meta.get("name", f"Train {train_no}")
                ttype = meta.get("type", "EXP-TRAINS")
                cat_delay = 10.0 if any(k in ttype for k in ["RAJ", "T18"]) else (15.0 if any(k in ttype for k in ["SF", "SHT"]) else 25.0)
                stops_out = []
                total_s = len(day_data)
                for idx, row in day_data.iterrows():
                    stn_code = str(row.get("station_name", "")).strip().upper()
                    coords = store.station_coords.get(stn_code, None)
                    d = safe_float(store.etrain_delays.get((train_no, stn_code)), default=cat_delay)
                    arr_raw = str(row.get("arrival_time", ""))
                    dep_raw = str(row.get("departure_time", ""))
                    is_orig = (idx == 0)
                    is_dst = (idx == total_s - 1)

                    time_info = compute_station_schedule_times(arr_raw, dep_raw, d, is_orig, is_dst)
                    full_name = store.station_full_names.get(stn_code, stn_code)
                    dist = safe_float(row.get("distance_from_origin"), default=0.0)

                    stops_out.append({
                        "station_no":        int(safe_float(row.get("station_no"), idx + 1)),
                        "station_code":      stn_code,
                        "station_name":      stn_code,
                        "station_full_name": full_name,
                        "scheduled_arr":     time_info["scheduled_arr"],
                        "scheduled_dep":     time_info["scheduled_dep"],
                        "expected_arr":      time_info["expected_arr"],
                        "expected_dep":      time_info["expected_dep"],
                        "actual_delay_min":  time_info["actual_delay_min"],
                        "expected_delay_min": time_info["expected_delay_min"],
                        "halt_duration":     time_info["halt_duration"],
                        "delay_label":       delay_label(d),
                        "distance_km":       dist,
                        "lat":               coords[0] if (coords and coords[0] > 5) else None,
                        "lon":               coords[1] if (coords and coords[1] > 60) else None,
                    })

                # Interpolate any missing intermediate station coordinates to prevent map drift
                for i, stp in enumerate(stops_out):
                    if stp["lat"] is None or stp["lon"] is None:
                        prev_stop = next((stops_out[p] for p in range(i - 1, -1, -1) if stops_out[p]["lat"] is not None), None)
                        next_stop = next((stops_out[n] for n in range(i + 1, len(stops_out)) if stops_out[n]["lat"] is not None), None)
                        if prev_stop and next_stop:
                            d_span = max(0.1, next_stop["distance_km"] - prev_stop["distance_km"])
                            frac = min(1.0, max(0.0, (stp["distance_km"] - prev_stop["distance_km"]) / d_span))
                            stp["lat"] = round(prev_stop["lat"] + frac * (next_stop["lat"] - prev_stop["lat"]), 4)
                            stp["lon"] = round(prev_stop["lon"] + frac * (next_stop["lon"] - prev_stop["lon"]), 4)
                        elif prev_stop:
                            stp["lat"] = prev_stop["lat"]
                            stp["lon"] = prev_stop["lon"]
                        elif next_stop:
                            stp["lat"] = next_stop["lat"]
                            stp["lon"] = next_stop["lon"]

                return {
                    "train_no": train_no,
                    "train_name": tname,
                    "date": date or datetime.now().strftime("%Y-%m-%d"),
                    "total_stops": len(stops_out),
                    "stops": stops_out,
                }
        raise InvalidTrainNumberError(train_no=train_no)

    filtered_by_date = False
    if date:
        import re
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            raise WhatIfOverrideInvalidError(f"date must be in YYYY-MM-DD format")
        try:
            target_date = pd.to_datetime(date)
            date_matches = sub[sub["date"].dt.date == target_date.date()]
            if not date_matches.empty:
                sub = date_matches
                filtered_by_date = True
            else:
                raise NoActiveJourneyError(train_no=train_no, date=date)
        except NoActiveJourneyError:
            raise
        except Exception:
            raise WhatIfOverrideInvalidError(f"Invalid date: {date}")

    # Use the most recent date available in sub
    latest = sub["date"].max()
    day_data = sub[sub["date"] == latest].sort_values("station_no").reset_index(drop=True)

    stops_out = []
    total_s = len(day_data)
    for idx, row in day_data.iterrows():
        d = safe_float(row.get("delay"), default=0.0)
        stn_code = str(row.get("station_name", "")).strip().upper()
        coords = store.station_coords.get(stn_code, None)
        dist = safe_float(row.get("distance_from_origin"), default=0.0)
        arr_raw = str(row.get("arrival_time", ""))
        dep_raw = str(row.get("departure_time", ""))
        is_orig = (idx == 0)
        is_dst = (idx == total_s - 1)

        time_info = compute_station_schedule_times(arr_raw, dep_raw, d, is_orig, is_dst)
        full_name = store.station_full_names.get(stn_code, str(row.get("station_full_name", stn_code)))

        stops_out.append({
            "station_no":        int(safe_float(row.get("station_no"), idx + 1)),
            "station_code":      stn_code,
            "station_name":      stn_code,
            "station_full_name": full_name,
            "scheduled_arr":     time_info["scheduled_arr"],
            "scheduled_dep":     time_info["scheduled_dep"],
            "expected_arr":      time_info["expected_arr"],
            "expected_dep":      time_info["expected_dep"],
            "actual_delay_min":  time_info["actual_delay_min"],
            "expected_delay_min": time_info["expected_delay_min"],
            "halt_duration":     time_info["halt_duration"],
            "delay_label":       delay_label(d),
            "distance_km":       dist,
            "lat":               coords[0] if (coords and coords[0] > 5) else None,
            "lon":               coords[1] if (coords and coords[1] > 60) else None,
        })

    # Interpolate any missing intermediate station coordinates to prevent map drift
    for i, stp in enumerate(stops_out):
        if stp["lat"] is None or stp["lon"] is None:
            prev_stop = next((stops_out[p] for p in range(i - 1, -1, -1) if stops_out[p]["lat"] is not None), None)
            next_stop = next((stops_out[n] for n in range(i + 1, len(stops_out)) if stops_out[n]["lat"] is not None), None)
            if prev_stop and next_stop:
                d_span = max(0.1, next_stop["distance_km"] - prev_stop["distance_km"])
                frac = min(1.0, max(0.0, (stp["distance_km"] - prev_stop["distance_km"]) / d_span))
                stp["lat"] = round(prev_stop["lat"] + frac * (next_stop["lat"] - prev_stop["lat"]), 4)
                stp["lon"] = round(prev_stop["lon"] + frac * (next_stop["lon"] - prev_stop["lon"]), 4)
            elif prev_stop:
                stp["lat"] = prev_stop["lat"]
                stp["lon"] = prev_stop["lon"]
            elif next_stop:
                stp["lat"] = next_stop["lat"]
                stp["lon"] = next_stop["lon"]

    return {
        "train_no": train_no,
        "train_name": str(day_data.iloc[0].get("train_name", f"Train {train_no}")),
        "date": date if date else str(latest.date()),
        "total_stops": len(stops_out),
        "stops": stops_out,
    }


@app.get("/trains")
def list_trains():
    """Return the list of trains available in the model's training data."""
    if store.train_data is None:
        raise HTTPException(503, detail="Data not loaded")

    summary = (
        store.train_data
        .drop_duplicates("train_no")[["train_no", "train_name"]]
        .sort_values("train_no")
    )
    return {
        "count": len(summary),
        "trains": summary.to_dict(orient="records"),
    }


# ---------------------------------------------------------------------------
# Serve Frontend Static Assets (Single-Origin Deploy for Any Domain / IP)
# ---------------------------------------------------------------------------
from fastapi.staticfiles import StaticFiles

frontend_dist = ROOT / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
