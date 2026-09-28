"""
backend/precedence_engine.py
Phase 2: Precedence-Inference Pipeline & Feature Generator.
Per Development Plan: 07_DataCollection_Scraper_and_Precedence_Phase2.md (Part C)
and 04_ML_Model_Spec.md (Phase 2 Model B).

Functions:
  1. compute_delay_picked_up(reconciled_df, section_id)
  2. baseline_against_own_history(train_no, section_id, delay_picked_up_series)
  3. systemic_cause_filter(section_id, date, all_trains_delay_picked_up)
  4. cross_reference_priority(delayed_train_no, section_id, date, nearby_trains, train_details_df)
  5. require_repetition_confidence(delayed_train_no, priority_train_no, section_id, all_observed_crossings, min_occurrences, min_total_crossings)
  6. platform_deviation_signal(train_no, station_code, observed_platform, historical_platform_mode)
  7. add_precedence_features(model_A_features_df, precedence_events_df)
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from backend.errors import SchemaValidationError

log = logging.getLogger("traineta.precedence")

# Priority ranking hierarchy: lower number = higher operational precedence
PRIORITY_RANKS: Dict[str, int] = {
    "RAJ": 1,      # Rajdhani
    "T18": 1,      # Vande Bharat
    "SHT": 1,      # Shatabdi
    "DRNT": 2,     # Duronto
    "GRB": 2,      # Garib Rath
    "SF": 3,       # Superfast
    "EXP": 4,      # Mail / Express
    "PASS": 5,     # Ordinary Passenger / Suburban
}


def get_priority_rank(type_code: str) -> int:
    """Map type_code to operational priority class (1=highest, 5=lowest)."""
    if not isinstance(type_code, str):
        return 4
    tc = type_code.upper()
    for key, rank in PRIORITY_RANKS.items():
        if key in tc:
            return rank
    return 4


def compute_delay_picked_up(reconciled_df: pd.DataFrame, section_id: Optional[str] = None) -> pd.DataFrame:
    """
    Computes delay_picked_up = delay_at_exit - delay_at_entry for each train crossing.
    Uses scheduled times which already net out planned dwell.
    
    Safety checks: raises SchemaValidationError if missing required columns.
    Rows with missing entry or exit produce NaN delay_picked_up.
    """
    required_cols = {"train_no", "date", "station_no", "section_id", "delay"}
    missing = required_cols - set(reconciled_df.columns)
    if missing:
        raise SchemaValidationError(
            f"compute_delay_picked_up missing required columns: {missing}",
            detail={"missing_columns": list(missing)}
        )

    df = reconciled_df.copy()
    if section_id is not None:
        df = df[df["section_id"] == section_id].copy()

    # Sort journeys chronologically by train, date, and station sequence
    df = df.sort_values(["train_no", "date", "station_no"]).reset_index(drop=True)
    
    # Calculate delay change across adjacent stations (exit - entry)
    df["delay_at_entry"] = df["delay"]
    # Group by journey to ensure shift stays within the same train trip
    df["delay_at_exit"] = df.groupby(["train_no", "date"])["delay"].shift(-1)
    df["delay_picked_up"] = df["delay_at_exit"] - df["delay_at_entry"]

    return df


def baseline_against_own_history(
    train_no: int,
    section_id: str,
    delay_picked_up_series: pd.Series
) -> Tuple[Optional[float], Optional[float]]:
    """
    Returns (mean, std) of this train's own historical delay_picked_up at this exact section.
    
    Safety check: returns (None, None) if fewer than 5 historical crossings exist
    (Insufficient data to establish a statistically meaningful baseline).
    """
    valid = delay_picked_up_series.dropna()
    if len(valid) < 5:
        return None, None
    mean_val = float(valid.mean())
    std_val = float(valid.std()) if len(valid) > 1 else 0.0
    return round(mean_val, 2), round(std_val, 2)


def systemic_cause_filter(
    section_id: str,
    date: str,
    all_trains_delay_picked_up: Dict[int, float]
) -> bool:
    """
    Returns True (systemic cause, DISCARD as precedence candidate) if most/all trains
    crossing this section on this date show an anomalous delay_picked_up (>10 min delay surge).
    Returns False (proceed) if only one train is anomalous while others are normal.
    
    Safety check: if only one train observed, returns False (cannot confirm systemic).
    """
    if not all_trains_delay_picked_up or len(all_trains_delay_picked_up) <= 1:
        return False

    delays = list(all_trains_delay_picked_up.values())
    anomalous_count = sum(1 for d in delays if d > 10.0)
    ratio = anomalous_count / len(delays)
    
    # If 60% or more trains suffered delay surge on this section, it is systemic (track fault/weather)
    return ratio >= 0.60


def cross_reference_priority(
    delayed_train_no: int,
    section_id: str,
    date: str,
    nearby_trains: List[int],
    train_details_df: pd.DataFrame
) -> Optional[int]:
    """
    Returns the train_no of any higher-priority train present in/near the same section,
    or None if no such train is found.
    
    Safety check: raises SchemaValidationError if train_details_df lacks required columns.
    """
    if "train_no" not in train_details_df.columns or "type_code" not in train_details_df.columns:
        raise SchemaValidationError("train_details_df must contain 'train_no' and 'type_code'")

    lookup = dict(zip(train_details_df["train_no"], train_details_df["type_code"]))
    
    delayed_type = lookup.get(delayed_train_no, "EXP-TRAINS")
    delayed_rank = get_priority_rank(delayed_type)

    for cand_no in nearby_trains:
        if cand_no == delayed_train_no:
            continue
        cand_type = lookup.get(cand_no, "EXP-TRAINS")
        cand_rank = get_priority_rank(cand_type)
        # Lower rank number = higher precedence
        if cand_rank < delayed_rank:
            return cand_no

    return None


def require_repetition_confidence(
    delayed_train_no: int,
    priority_train_no: int,
    section_id: str,
    all_observed_crossings: pd.DataFrame,
    min_occurrences: int = 6,
    min_total_crossings: int = 10
) -> float:
    """
    Returns confidence_score = (occurrences where precedence held) / (total observed joint crossings).
    Guards against division by zero (returns 0.0 if crossings < min_total_crossings).
    """
    if all_observed_crossings is None or all_observed_crossings.empty:
        return 0.0

    total_crossings = len(all_observed_crossings)
    if total_crossings < min_total_crossings:
        return 0.0

    # Pattern held: occurrences where delayed_train picked up delay in presence of priority train
    if "held" in all_observed_crossings.columns:
        held = int(all_observed_crossings["held"].sum())
    elif "delay_surge_delayed" in all_observed_crossings.columns:
        held = int((all_observed_crossings["delay_surge_delayed"] >= 8.0).sum())
    elif "delay_surge" in all_observed_crossings.columns:
        held = int((all_observed_crossings["delay_surge"] >= 8.0).sum())
    else:
        held = total_crossings

    if held < min_occurrences:
        return 0.0

    confidence = float(held / total_crossings)
    return round(min(1.0, max(0.0, confidence)), 3)


def platform_deviation_signal(
    train_no: int,
    station_code: str,
    observed_platform: Optional[str],
    historical_platform_mode: Optional[str]
) -> float:
    """
    Returns a confidence boost (+0.15) if observed_platform differs from historical norm.
    Platform reassignment during congestion corroborates precedence holds.
    """
    if not observed_platform or not historical_platform_mode:
        return 0.0
    if str(observed_platform).strip() != str(historical_platform_mode).strip():
        return 0.15
    return 0.0


def add_precedence_features(
    model_A_features_df: pd.DataFrame,
    precedence_events_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Left-joins precedence_events onto model_A_features producing model_B_features.
    
    Columns added:
      - precedence_risk_score_next_section: float (0-1) or NaN
      - historical_precedence_rate_vs_known_priority_trains: float (0-1) or NaN
      
    Safety check: raises SchemaValidationError if model_A_features_df does not
    contain all required identifiers.
    """
    required = {"train_no", "section_id", "date"}
    missing = required - set(model_A_features_df.columns)
    if missing:
        raise SchemaValidationError(
            f"add_precedence_features missing required Model A columns: {missing}"
        )

    df = model_A_features_df.copy()

    if precedence_events_df is None or precedence_events_df.empty:
        df["precedence_risk_score_next_section"] = np.nan
        df["historical_precedence_rate_vs_known_priority_trains"] = np.nan
        return df

    # Prepare lookup table indexed by (delayed_train_no, section_id)
    # Aggregating across multiple priority train conflicts if any
    event_agg = precedence_events_df.groupby(["delayed_train_no", "section_id"]).agg(
        precedence_risk_score_next_section=("confidence_score", "max"),
        historical_precedence_rate_vs_known_priority_trains=("confidence_score", "mean"),
    ).reset_index()

    # Left join
    merged = df.merge(
        event_agg,
        left_on=["train_no", "section_id"],
        right_on=["delayed_train_no", "section_id"],
        how="left"
    )

    # Clean up auxiliary join key
    if "delayed_train_no" in merged.columns:
        merged = merged.drop(columns=["delayed_train_no"])

    return merged


# ---------------------------------------------------------------------------
# Pipeline Execution: Detect Events & Produce model_B_features.parquet
# ---------------------------------------------------------------------------
def run_precedence_pipeline(
    input_features_path: Path,
    output_events_path: Path,
    output_b_features_path: Path
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Executes full Phase 2 Precedence-Inference pipeline on model_A_features.parquet:
    1. Computes section-level delay surges.
    2. Flags priority overtakes across all 415 historical trains.
    3. Evaluates systemic filters and repetition confidence.
    4. Writes precedence_events.parquet and model_B_features.parquet.
    """
    log.info(f"Loading Model A features from {input_features_path} ...")
    df = pd.read_parquet(input_features_path)
    log.info(f"Loaded {len(df):,} rows across {df['train_no'].nunique()} trains.")

    # 1. Section crossings and delay picked up
    log.info("Computing delay surges across section crossings...")
    # Calculate exit delay by shifting within each train-date trip
    df_sorted = df.sort_values(["train_no", "date", "station_no"]).reset_index(drop=True)
    df_sorted["next_delay"] = df_sorted.groupby(["train_no", "date"])["delay"].shift(-1)
    df_sorted["delay_surge"] = (df_sorted["next_delay"] - df_sorted["delay"]).fillna(0.0)

    # 2. Extract priority and section-date aggregations
    train_types = df[["train_no", "type_code"]].drop_duplicates()
    priority_map = {tno: get_priority_rank(tc) for tno, tc in zip(train_types["train_no"], train_types["type_code"])}

    # 2. Vectorized precedence detection
    log.info("Cross-referencing section occupancies and priority hierarchies...")
    df_sorted["priority_rank"] = df_sorted["type_code"].map(lambda tc: get_priority_rank(str(tc)))

    # Candidates that suffered delay surge >= 8.0 min
    delayed_rows = df_sorted[df_sorted["delay_surge"] >= 8.0][
        ["train_no", "section_id", "date", "delay_surge", "priority_rank"]
    ].copy()

    # Co-present trains on the same (section_id, date)
    co_present = df_sorted[
        ["train_no", "section_id", "date", "delay_surge", "priority_rank"]
    ].drop_duplicates()

    # Systemic check per (section_id, date): filter out section-wide failures
    sec_stats = df_sorted.groupby(["section_id", "date"])["delay_surge"].agg(
        total_trains="count",
        anom_trains=lambda s: (s > 10.0).sum()
    ).reset_index()
    sec_stats["is_systemic"] = (sec_stats["total_trains"] > 1) & (
        (sec_stats["anom_trains"] / sec_stats["total_trains"]) >= 0.60
    )
    non_systemic_pairs = set(zip(
        sec_stats[~sec_stats["is_systemic"]]["section_id"],
        sec_stats[~sec_stats["is_systemic"]]["date"]
    ))

    # Join delayed trains with co-present trains on identical section and date
    pairs = delayed_rows.merge(
        co_present,
        on=["section_id", "date"],
        suffixes=("_delayed", "_priority")
    )

    # Filter: strictly different trains, and priority train has higher rank (lower number)
    pairs = pairs[
        (pairs["train_no_delayed"] != pairs["train_no_priority"]) &
        (pairs["priority_rank_priority"] < pairs["priority_rank_delayed"])
    ]

    # Filter out systemic bottleneck section-dates
    pairs["sec_date"] = list(zip(pairs["section_id"], pairs["date"]))
    pairs = pairs[pairs["sec_date"].isin(non_systemic_pairs)]

    log.info(f"Identified {len(pairs):,} raw precedence observation instances.")

    # Joint co-presences across non-systemic section-dates to evaluate true repetition rate
    all_joint = co_present.merge(
        co_present,
        on=["section_id", "date"],
        suffixes=("_delayed", "_priority")
    )
    all_joint = all_joint[
        (all_joint["train_no_delayed"] != all_joint["train_no_priority"]) &
        (all_joint["priority_rank_priority"] < all_joint["priority_rank_delayed"])
    ]
    all_joint["sec_date"] = list(zip(all_joint["section_id"], all_joint["date"]))
    all_joint = all_joint[all_joint["sec_date"].isin(non_systemic_pairs)]
    all_joint["held"] = (all_joint["delay_surge_delayed"] >= 8.0).astype(int)

    # 3. Apply repetition gate (min occurrences and confidence scoring)
    events = []
    if not all_joint.empty:
        grouped = all_joint.groupby(["train_no_delayed", "train_no_priority", "section_id"])
        
        for (d_tno, p_tno, sec), g in grouped:
            total_crossings = len(g)
            confidence = require_repetition_confidence(
                delayed_train_no=int(d_tno),
                priority_train_no=int(p_tno),
                section_id=str(sec),
                all_observed_crossings=g,
                min_occurrences=6,
                min_total_crossings=10,
            )
            if confidence > 0.0:
                events.append({
                    "delayed_train_no": int(d_tno),
                    "priority_train_no": int(p_tno),
                    "section_id": str(sec),
                    "confidence_score": float(confidence),
                    "first_observed_date": g["date"].min().date(),
                    "last_observed_date": g["date"].max().date(),
                    "total_crossings_observed": int(total_crossings),
                })

    events_df = pd.DataFrame(events)
    if events_df.empty:
        # Provide baseline schema if no pairs crossed threshold
        events_df = pd.DataFrame(columns=[
            "delayed_train_no", "priority_train_no", "section_id",
            "confidence_score", "first_observed_date", "last_observed_date",
            "total_crossings_observed"
        ])
    
    log.info(f"Writing {len(events_df)} confirmed precedence events to {output_events_path} ...")
    events_df.to_parquet(output_events_path, index=False)

    # 4. Join onto Model A features to produce Model B features
    log.info("Generating Model B 45-feature dataset...")
    b_features = add_precedence_features(df, events_df)
    
    # Fill precedence scores for rows with known events, keep null/NaN for non-event rows per spec
    log.info(f"Writing Model B features to {output_b_features_path} ...")
    b_features.to_parquet(output_b_features_path, index=False)
    log.info(f"Model B features written: {b_features.shape[0]:,} rows, {b_features.shape[1]} columns.")

    return events_df, b_features


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    
    root = Path(__file__).resolve().parent.parent
    in_parquet = root / "backend" / "model_A_features.parquet"
    out_events = root / "backend" / "precedence_events.parquet"
    out_b_features = root / "backend" / "model_B_features.parquet"

    events_df, b_df = run_precedence_pipeline(in_parquet, out_events, out_b_features)
    print(f"\nPipeline Run Complete:")
    print(f"  Precedence Events: {len(events_df)}")
    print(f"  Model B Features: {b_df.shape} (Columns: {list(b_df.columns[-3:])})")
