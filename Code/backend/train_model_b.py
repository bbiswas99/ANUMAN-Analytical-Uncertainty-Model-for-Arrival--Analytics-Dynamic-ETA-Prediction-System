# backend/train_model_b.py
# Step 04 (Phase 2): Train XGBoost Model B on model_B_features.parquet and save model_b.json.
# Run from project root: .venv\Scripts\python.exe backend\train_model_b.py
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import json
import time
import numpy as np
import pandas as pd
from pathlib import Path

import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import LabelEncoder

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "backend" / "model_B_features.parquet"
MODEL_DIR = ROOT / "backend" / "models"
MODEL_PATH = MODEL_DIR / "model_b.json"
ENCODER_PATH = MODEL_DIR / "model_b_encoder.json"
FEATURE_IMPORTANCE_PATH = MODEL_DIR / "model_b_importance.json"

MODEL_DIR.mkdir(exist_ok=True)

CATEGORICAL_COLS = ["type_code", "station_zone", "section_id"]

DISPLAY_ONLY = [
    "station_name", "station_full_name", "train_name",
    "arrival_time", "departure_time",
]

DROP_COLS = [
    "baseline_eta",
    "reported_delay_min",
    "platform_number",
    "source_agreement_score",
    "data_confidence_score",
]

LEAKAGE_COLS = ["delay"]


def load_and_prepare():
    print(f"Loading {PARQUET} ...")
    df = pd.read_parquet(PARQUET)
    print(f"  Shape: {df.shape}")
    print(f"  Trains: {df['train_no'].nunique()}")
    print(f"  Date range: {df['date'].min().date()} to {df['date'].max().date()}")

    # Ensure precedence columns have proper numerical types and default fills
    precedence_cols = [
        "precedence_conflict_detected",
        "precedence_relative_priority_diff",
        "precedence_scheduled_overtake_window",
        "precedence_confidence_score",
        "precedence_inferred_hold_min",
    ]
    for col in precedence_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0.0).astype(float)

    # Drop display-only + leakage (keep residual_target and date)
    to_drop = [c for c in DROP_COLS + DISPLAY_ONLY + LEAKAGE_COLS if c in df.columns]
    df = df.drop(columns=to_drop)
    return df


def chronological_split(df, train_frac=0.80):
    """Split by date: oldest 80% -> train, newest 20% -> test."""
    dates = df["date"].sort_values().unique()
    cutoff_idx = int(len(dates) * train_frac)
    cutoff_date = dates[cutoff_idx]
    train = df[df["date"] < cutoff_date].copy()
    test  = df[df["date"] >= cutoff_date].copy()
    print(f"Split: train {len(train):,} rows (before {cutoff_date.date()}), test {len(test):,} rows")
    return train, test


def encode_categoricals(train_df, test_df):
    """Frequency + label encode categoricals. Save mapping for inference."""
    encoders = {}

    # Frequency encode section_id
    freq = train_df["section_id"].value_counts().to_dict()
    train_df["section_id_freq"] = train_df["section_id"].map(freq).fillna(0)
    test_df["section_id_freq"]  = test_df["section_id"].map(freq).fillna(0)
    encoders["section_id_freq"] = freq

    # Label encode type_code, station_zone
    for col in ["type_code", "station_zone"]:
        if col not in train_df.columns:
            continue
        le = LabelEncoder()
        combined = pd.concat([train_df[col].fillna("UNKNOWN"), test_df[col].fillna("UNKNOWN")])
        le.fit(combined)
        train_df[col + "_enc"] = le.transform(train_df[col].fillna("UNKNOWN"))
        test_df[col + "_enc"]  = le.transform(test_df[col].fillna("UNKNOWN"))
        encoders[col] = list(le.classes_)

    drop_cats = [c for c in CATEGORICAL_COLS if c in train_df.columns]
    train_df = train_df.drop(columns=drop_cats + ["date"])
    test_df  = test_df.drop(columns=drop_cats + ["date"])

    return train_df, test_df, encoders


def train_xgboost(X_train, y_train, X_test, y_test):
    print("\nTraining XGBoost Model B...")
    model = xgb.XGBRegressor(
        n_estimators=500,
        max_depth=7,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=10,
        gamma=1,
        reg_alpha=0.1,
        reg_lambda=1.0,
        n_jobs=-1,
        random_state=42,
        early_stopping_rounds=30,
        eval_metric="mae",
        verbosity=1,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=50,
    )
    print(f"Best iteration: {model.best_iteration}")
    return model


def evaluate(model, X_train, y_train, X_test, y_test, df_test):
    print("\n=== Model B Evaluation ===")
    pred_train = model.predict(X_train)
    pred_test  = model.predict(X_test)

    train_mae = mean_absolute_error(y_train, pred_train)
    test_mae  = mean_absolute_error(y_test,  pred_test)
    test_rmse = np.sqrt(mean_squared_error(y_test, pred_test))

    print(f"Train MAE: {train_mae:.2f} min")
    print(f"Test  MAE: {test_mae:.2f} min  |  RMSE: {test_rmse:.2f} min")

    baseline_mae = mean_absolute_error(y_test, np.zeros_like(y_test))
    print(f"Baseline MAE (residual=0): {baseline_mae:.2f} min")
    improvement = (baseline_mae - test_mae) / baseline_mae * 100
    print(f"Model B improvement over baseline: {improvement:.1f}%")

    # Evaluation on Precedence-Active Subset
    precedence_subset_results = {}
    if "precedence_conflict_detected" in X_test.columns:
        active_mask = (X_test["precedence_conflict_detected"] > 0) | (X_test["precedence_confidence_score"] > 0)
        n_active = int(active_mask.sum())
        print(f"\n--- Precedence-Active Subset Analysis (n={n_active:,}) ---")
        if n_active > 0:
            active_y_test = y_test[active_mask]
            active_pred_test = pred_test[active_mask]
            active_mae = mean_absolute_error(active_y_test, active_pred_test)
            active_baseline_mae = mean_absolute_error(active_y_test, np.zeros_like(active_y_test))
            active_improvement = (active_baseline_mae - active_mae) / active_baseline_mae * 100

            print(f"Precedence Subset Test MAE:     {active_mae:.2f} min")
            print(f"Precedence Subset Baseline MAE: {active_baseline_mae:.2f} min")
            print(f"Precedence Subset Improvement:  {active_improvement:.1f}%")

            precedence_subset_results = {
                "n_active_records": n_active,
                "subset_mae_min": round(active_mae, 2),
                "subset_baseline_mae_min": round(active_baseline_mae, 2),
                "subset_improvement_pct": round(active_improvement, 1),
            }
        else:
            print("No test records had active precedence flags.")

    return {
        "train_mae_min": round(train_mae, 2),
        "test_mae_min": round(test_mae, 2),
        "test_rmse_min": round(test_rmse, 2),
        "baseline_mae_min": round(baseline_mae, 2),
        "improvement_pct": round(improvement, 1),
        "best_iteration": int(model.best_iteration),
        "n_train": len(y_train),
        "n_test": len(y_test),
        "precedence_subset": precedence_subset_results,
    }


def save_artifacts(model, encoders, eval_results, feature_names):
    print(f"\nSaving Model B to {MODEL_PATH} ...")
    model.save_model(str(MODEL_PATH))

    imp = {k: float(v) for k, v in zip(feature_names, model.feature_importances_)}
    imp_sorted = dict(sorted(imp.items(), key=lambda x: x[1], reverse=True)[:35])
    with open(FEATURE_IMPORTANCE_PATH, "w") as f:
        json.dump({"feature_importance": imp_sorted, "eval": eval_results}, f, indent=2)
    print(f"Saved feature importance to {FEATURE_IMPORTANCE_PATH}")

    clean_encoders = {}
    for k, v in encoders.items():
        if isinstance(v, dict):
            clean_encoders[k] = {str(kk): float(vv) if hasattr(vv, 'item') else vv
                                  for kk, vv in v.items()}
        elif isinstance(v, list):
            clean_encoders[k] = [float(x) if hasattr(x, 'item') else x for x in v]
        elif hasattr(v, 'item'):
            clean_encoders[k] = v.item()
        else:
            clean_encoders[k] = v
    clean_encoders["feature_names"] = feature_names
    clean_encoders["eval"] = eval_results
    with open(ENCODER_PATH, "w") as f:
        json.dump(clean_encoders, f, indent=2)
    print(f"Saved encoder metadata to {ENCODER_PATH}")


def main():
    t0 = time.time()
    df = load_and_prepare()
    train_df, test_df = chronological_split(df)
    train_df, test_df, encoders = encode_categoricals(train_df, test_df)

    TARGET = "residual_target"
    feature_cols = [c for c in train_df.columns if c != TARGET and c != "train_no"]

    print(f"\nModel B Feature count: {len(feature_cols)}")
    print(f"Features: {feature_cols}")

    X_train = train_df[feature_cols].astype(float)
    y_train = train_df[TARGET].astype(float)
    X_test  = test_df[feature_cols].astype(float)
    y_test  = test_df[TARGET].astype(float)

    print(f"\nX_train shape: {X_train.shape}, NaN count: {X_train.isna().sum().sum()}")
    print(f"X_test  shape: {X_test.shape},  NaN count: {X_test.isna().sum().sum()}")

    model = train_xgboost(X_train, y_train, X_test, y_test)
    eval_results = evaluate(model, X_train, y_train, X_test, y_test, test_df)

    print("\nTop 15 feature importances:")
    imp = sorted(zip(feature_cols, model.feature_importances_), key=lambda x: x[1], reverse=True)
    for feat, score in imp[:15]:
        print(f"  {feat}: {score:.4f}")

    save_artifacts(model, encoders, eval_results, feature_cols)
    print(f"\nTotal Model B training time: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
