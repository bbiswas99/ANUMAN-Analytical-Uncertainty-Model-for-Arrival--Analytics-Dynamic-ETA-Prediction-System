# backend/generate_empirical_accuracy.py
"""
Fully empirical, zero-approximation accuracy and residual evaluation script.
Reads directly from:
  - backend/models/model_b.json
  - backend/models/model_b_encoder.json
  - backend/models/model_a.json
  - backend/models/label_encoders.json
  - backend/model_B_features.parquet (all 774,291 rows -> exactly 156,216 test rows)

Outputs:
  - ml_models_accuracy_dashboard.png
  - ml_models_convergence_residuals.png
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import json
from pathlib import Path
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = Path(r"C:\Users\BHAVYA BISWAS\.gemini\antigravity-ide\brain\8c0d5680-2275-40fe-b65f-e2122e487c60")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
IMG_DASHBOARD = OUTPUT_DIR / "ml_models_accuracy_dashboard.png"
IMG_RESIDUALS = OUTPUT_DIR / "ml_models_convergence_residuals.png"

# Style tokens
bg_card = '#1e293b'
text_light = '#f8fafc'
text_muted = '#94a3b8'
grid_color = '#334155'
accent_blue = '#38bdf8'
accent_purple = '#a855f7'
accent_green = '#22c55e'
accent_red = '#f43f5e'
accent_amber = '#f59e0b'

def set_dark_theme(ax, title):
    ax.set_facecolor(bg_card)
    ax.set_title(title, fontsize=12, fontweight='bold', color=text_light, pad=10)
    ax.tick_params(colors=text_muted, labelsize=9)
    for spine in ax.spines.values():
        spine.set_color(grid_color)
    ax.grid(True, linestyle='--', alpha=0.3, color=grid_color)

def main():
    print("=" * 70)
    print("EMPIRICAL ML MODEL EVALUATION (ZERO APPROXIMATIONS)")
    print("=" * 70)

    # 1. Load Model B features parquet
    parquet_path = ROOT / "backend" / "model_B_features.parquet"
    print(f"Loading features from: {parquet_path}")
    df = pd.read_parquet(parquet_path)
    total_rows = len(df)
    print(f"Total rows loaded: {total_rows:,}")

    # 2. Chronological 80/20 train/test split (exact train_model_b.py logic)
    dates = df["date"].sort_values().unique()
    cutoff_idx = int(len(dates) * 0.80)
    cutoff_date = dates[cutoff_idx]
    train_df = df[df["date"] < cutoff_date]
    test_df = df[df["date"] >= cutoff_date].copy()
    n_test = len(test_df)
    print(f"Cutoff Date: {cutoff_date.date()} | Train: {len(train_df):,} | Test: {n_test:,} rows")
    assert n_test == 156216, f"Expected 156,216 test rows, got {n_test}"

    # 3. Load Model B and encoders
    with open(ROOT / "backend" / "models" / "model_b_encoder.json") as f:
        meta_b = json.load(f)
    model_b_features = meta_b["feature_names"]
    
    test_df_b = test_df.copy()
    test_df_b["section_id_freq"] = test_df_b["section_id"].map(meta_b["section_id_freq"]).fillna(0)
    for col in ["type_code", "station_zone"]:
        classes = meta_b[col]
        cmap = {c: i for i, c in enumerate(classes)}
        test_df_b[col + "_enc"] = test_df_b[col].fillna("UNKNOWN").map(cmap).fillna(0).astype(int)

    for c in ["precedence_conflict_detected", "precedence_relative_priority_diff",
              "precedence_scheduled_overtake_window", "precedence_confidence_score",
              "precedence_inferred_hold_min"]:
        if c in test_df_b.columns:
            test_df_b[c] = test_df_b[c].fillna(0.0).astype(float)

    X_test_b = test_df_b[model_b_features].astype(float)
    model_b = xgb.XGBRegressor()
    model_b.load_model(str(ROOT / "backend" / "models" / "model_b.json"))
    print(f"Loaded Model B ({len(model_b_features)} features). Running predictions on {n_test:,} test rows...")
    y_pred_res_b = model_b.predict(X_test_b)

    # 4. Load Model A and encoders
    with open(ROOT / "backend" / "models" / "label_encoders.json") as f:
        meta_a = json.load(f)
    model_a_features = meta_a["feature_names"]
    
    test_df_a = test_df.copy()
    test_df_a["section_id_freq"] = test_df_a["section_id"].map(meta_a["section_id_freq"]).fillna(0)
    for col in ["type_code", "station_zone"]:
        classes = meta_a[col]
        cmap = {c: i for i, c in enumerate(classes)}
        test_df_a[col + "_enc"] = test_df_a[col].fillna("UNKNOWN").map(cmap).fillna(0).astype(int)

    X_test_a = test_df_a[model_a_features].astype(float)
    model_a = xgb.XGBRegressor()
    model_a.load_model(str(ROOT / "backend" / "models" / "model_a.json"))
    print(f"Loaded Model A ({len(model_a_features)} features). Running predictions on {n_test:,} test rows...")
    y_pred_res_a = model_a.predict(X_test_a)

    # 5. Compute Empirical Errors on Test Set
    baseline_est = test_df["baseline_delay_estimate"].values
    actual_delay = test_df["delay"].values
    y_test_res = test_df["residual_target"].values

    pred_delay_b = baseline_est + y_pred_res_b
    pred_delay_a = baseline_est + y_pred_res_a

    # Real residual errors: actual - predicted
    residuals_b = actual_delay - pred_delay_b
    abs_errors_b = np.abs(residuals_b)

    mae_base = mean_absolute_error(actual_delay, baseline_est)
    rmse_base = np.sqrt(mean_squared_error(actual_delay, baseline_est))
    mae_a = mean_absolute_error(actual_delay, pred_delay_a)
    rmse_a = np.sqrt(mean_squared_error(actual_delay, pred_delay_a))
    mae_b = mean_absolute_error(actual_delay, pred_delay_b)
    rmse_b = np.sqrt(mean_squared_error(actual_delay, pred_delay_b))

    print("\n--- Empirical Benchmark on Full Test Set (156,216 rows) ---")
    print(f"Scheduled Baseline:  MAE = {mae_base:.2f} min | RMSE = {rmse_base:.2f} min")
    print(f"Model A (Congestion): MAE = {mae_a:.2f} min | RMSE = {rmse_a:.2f} min")
    print(f"Model B (Precedence): MAE = {mae_b:.2f} min | RMSE = {rmse_b:.2f} min")

    # 6. Precedence Conflict Subset (real filter: precedence_risk_score_next_section is non-null and non-zero)
    mask_conflict = (test_df["precedence_risk_score_next_section"].notna()) & (test_df["precedence_risk_score_next_section"] != 0)
    n_conflict = mask_conflict.sum()
    print(f"\n--- Empirical Precedence Conflict Subset (n={n_conflict:,} rows) ---")
    mae_conflict_base = mean_absolute_error(actual_delay[mask_conflict], baseline_est[mask_conflict])
    mae_conflict_a = mean_absolute_error(actual_delay[mask_conflict], pred_delay_a[mask_conflict])
    mae_conflict_b = mean_absolute_error(actual_delay[mask_conflict], pred_delay_b[mask_conflict])
    rmse_conflict_a = np.sqrt(mean_squared_error(actual_delay[mask_conflict], pred_delay_a[mask_conflict]))
    rmse_conflict_b = np.sqrt(mean_squared_error(actual_delay[mask_conflict], pred_delay_b[mask_conflict]))
    diff_conflict = mae_conflict_a - mae_conflict_b
    pct_conflict = (diff_conflict / mae_conflict_a) * 100

    print(f"Conflict Subset Baseline MAE: {mae_conflict_base:.2f} min")
    print(f"Conflict Subset Model A MAE:  {mae_conflict_a:.2f} min")
    print(f"Conflict Subset Model B MAE:  {mae_conflict_b:.2f} min")
    print(f"Precedence Error Reduction:   -{diff_conflict:.2f} min ({pct_conflict:.1f}%)")

    # 7. Empirical Cumulative Accuracy within Tolerances
    tolerances = np.arange(1, 61)
    cum_pct_b = np.array([(abs_errors_b <= t).mean() * 100 for t in tolerances])
    cum_pct_a = np.array([(np.abs(actual_delay - pred_delay_a) <= t).mean() * 100 for t in tolerances])
    cum_pct_base = np.array([(np.abs(actual_delay - baseline_est) <= t).mean() * 100 for t in tolerances])

    p5 = (abs_errors_b <= 5.0).mean() * 100
    p10 = (abs_errors_b <= 10.0).mean() * 100
    p15 = (abs_errors_b <= 15.0).mean() * 100
    p30 = (abs_errors_b <= 30.0).mean() * 100
    print(f"\n--- Empirical Cumulative Accuracies (Model B) ---")
    print(f"Within +/- 5 min:  {p5:.2f}%")
    print(f"Within +/- 10 min: {p10:.2f}%")
    print(f"Within +/- 15 min: {p15:.2f}%")
    print(f"Within +/- 30 min: {p30:.2f}%")

    # =========================================================================
    # PLOT 1: ML Model Accuracy & Performance Suite
    # =========================================================================
    print(f"\nRendering Plot 1: {IMG_DASHBOARD} ...")
    fig1 = plt.figure(figsize=(16, 11), facecolor='#0f172a')
    gs1 = gridspec.GridSpec(2, 2, figure=fig1, hspace=0.32, wspace=0.25)

    # Panel 1: Overall Test Benchmark
    ax1 = fig1.add_subplot(gs1[0, 0])
    set_dark_theme(ax1, '1. Overall Test Error Benchmark (156,216 Test Samples)')
    labels = ['Scheduled\nBaseline', 'Model A\n(Congestion)', 'Model B\n(Precedence)']
    mae_bar = [mae_base, mae_a, mae_b]
    rmse_bar = [rmse_base, rmse_a, rmse_b]
    x = np.arange(len(labels))
    w = 0.35
    r1 = ax1.bar(x - w/2, mae_bar, w, label='Test MAE (min)', color=['#ef4444', '#38bdf8', '#a855f7'], alpha=0.9, edgecolor='#0f172a', linewidth=1.5)
    r2 = ax1.bar(x + w/2, rmse_bar, w, label='Test RMSE (min)', color=['#b91c1c', '#0284c7', '#7e22ce'], alpha=0.7, edgecolor='#0f172a', linewidth=1.5)
    for rect in r1:
        h = rect.get_height()
        ax1.annotate(f'{h:.2f}m', xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 4), textcoords="offset points", ha='center', va='bottom', fontsize=9, fontweight='bold', color=text_light)
    for rect in r2:
        h = rect.get_height()
        ax1.annotate(f'{h:.2f}m', xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 4), textcoords="offset points", ha='center', va='bottom', fontsize=9, fontweight='bold', color=text_muted)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=9.5, fontweight='bold', color=text_light)
    ax1.set_ylabel('Error (Minutes)', color=text_light, fontsize=10)
    ax1.legend(loc='upper right', facecolor=bg_card, edgecolor=grid_color, labelcolor=text_light)
    ax1.set_ylim(0, max(rmse_bar) * 1.15)

    # Panel 2: Precedence Conflict Sections
    ax2 = fig1.add_subplot(gs1[0, 1])
    set_dark_theme(ax2, f'2. Precedence Conflict Sections (Empirical n={n_conflict:,})')
    conf_models = ['Model A\n(Agnostic to Priority)', 'Model B\n(Precedence-Aware)']
    conf_mae = [mae_conflict_a, mae_conflict_b]
    conf_rmse = [rmse_conflict_a, rmse_conflict_b]
    xc = np.arange(len(conf_models))
    rc1 = ax2.bar(xc - w/2, conf_mae, w, label='MAE (min)', color=['#38bdf8', '#a855f7'], alpha=0.9, edgecolor='#0f172a', linewidth=1.5)
    rc2 = ax2.bar(xc + w/2, conf_rmse, w, label='RMSE (min)', color=['#0284c7', '#7e22ce'], alpha=0.7, edgecolor='#0f172a', linewidth=1.5)
    for rect in rc1:
        h = rect.get_height()
        ax2.annotate(f'{h:.2f}m', xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 4), textcoords="offset points", ha='center', va='bottom', fontsize=10, fontweight='bold', color=text_light)
    for rect in rc2:
        h = rect.get_height()
        ax2.annotate(f'{h:.2f}m', xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 4), textcoords="offset points", ha='center', va='bottom', fontsize=9, fontweight='bold', color=text_muted)
    ax2.annotate(f'Error Reduction:\n-{diff_conflict:.2f}m (-{pct_conflict:.1f}%)',
                 xy=(1 - w/2, mae_conflict_b), xytext=(0.20, max(conf_rmse) * 0.85),
                 arrowprops=dict(arrowstyle="->", color=accent_green, lw=1.8),
                 fontsize=9.5, fontweight='bold', color=accent_green,
                 bbox=dict(boxstyle='round,pad=0.4', facecolor='#14532d', alpha=0.6, edgecolor=accent_green))
    ax2.set_xticks(xc)
    ax2.set_xticklabels(conf_models, fontsize=9.5, fontweight='bold', color=text_light)
    ax2.set_ylabel('Error (Minutes)', color=text_light, fontsize=10)
    ax2.legend(loc='upper right', facecolor=bg_card, edgecolor=grid_color, labelcolor=text_light)
    ax2.set_ylim(0, max(conf_rmse) * 1.30)

    # Panel 3: Empirical Cumulative Accuracy
    ax3 = fig1.add_subplot(gs1[1, 0])
    set_dark_theme(ax3, '3. Empirical Cumulative Accuracy across Tolerances')
    ax3.plot(tolerances, cum_pct_b, color=accent_purple, linewidth=2.5, label='Model B (Precedence)')
    ax3.plot(tolerances, cum_pct_a, color=accent_blue, linewidth=2.0, linestyle='--', label='Model A (Congestion)')
    ax3.plot(tolerances, cum_pct_base, color='#ef4444', linewidth=1.5, linestyle=':', label='Scheduled Baseline')
    for val, label in [(p5, '±5m'), (p10, '±10m'), (p15, '±15m'), (p30, '±30m')]:
        t_val = int(label.replace('±', '').replace('m', ''))
        ax3.scatter([t_val], [val], color=accent_green, s=40, zorder=5)
        ax3.annotate(f'{label}: {val:.1f}%', xy=(t_val, val), xytext=(t_val + 1.5, val - 4),
                     fontsize=8.5, fontweight='bold', color=accent_green,
                     bbox=dict(boxstyle='round,pad=0.2', facecolor='#064e3b', alpha=0.5, edgecolor=accent_green))
    ax3.set_xlabel('Tolerance Window (± Minutes)', color=text_light, fontsize=10)
    ax3.set_ylabel('% Predictions within Window', color=text_light, fontsize=10)
    ax3.set_xlim(0, 60)
    ax3.set_ylim(0, 105)
    ax3.legend(loc='lower right', facecolor=bg_card, edgecolor=grid_color, labelcolor=text_light)

    # Panel 4: Top Model B Feature Importances
    ax4 = fig1.add_subplot(gs1[1, 1])
    set_dark_theme(ax4, '4. Model B Top Empirical Feature Importances')
    importances = model_b.feature_importances_
    feat_series = pd.Series(importances, index=model_b_features).sort_values(ascending=True).tail(10)
    y_pos = np.arange(len(feat_series))
    ax4.barh(y_pos, feat_series.values, color=accent_purple, alpha=0.85, edgecolor='#0f172a')
    ax4.set_yticks(y_pos)
    ax4.set_yticklabels(feat_series.index, fontsize=8.5, color=text_light)
    for i, v in enumerate(feat_series.values):
        ax4.annotate(f'{v*100:.1f}%', xy=(v, i), xytext=(4, 0), textcoords="offset points", va='center', fontsize=8.5, fontweight='bold', color=text_light)
    ax4.set_xlabel('Relative Gain / Importance', color=text_light, fontsize=10)
    ax4.set_xlim(0, max(feat_series.values) * 1.25)

    plt.suptitle('TrainETA ML Performance Suite: Zero-Approximation Empirical Test Evaluation\n(Evaluated on 156,216 Historical Out-of-Sample Test Records)',
                 fontsize=15, fontweight='bold', color=text_light, y=0.98)
    fig1.savefig(IMG_DASHBOARD, dpi=160, bbox_inches='tight', facecolor=fig1.get_facecolor())
    plt.close(fig1)
    print(f"Successfully saved: {IMG_DASHBOARD}")

    # =========================================================================
    # PLOT 2: Convergence, Residuals & Error Breakdown
    # =========================================================================
    print(f"\nRendering Plot 2: {IMG_RESIDUALS} ...")
    fig2 = plt.figure(figsize=(16, 11), facecolor='#0f172a')
    gs2 = gridspec.GridSpec(2, 2, figure=fig2, hspace=0.32, wspace=0.25)

    # Panel 1: Real Hexbin of Actual vs Predicted Delay
    ax21 = fig2.add_subplot(gs2[0, 0])
    set_dark_theme(ax21, '1. Actual vs. Predicted Delay (156,216 Empirical Test Points)')
    clip_mask = (actual_delay >= -10) & (actual_delay <= 180) & (pred_delay_b >= -10) & (pred_delay_b <= 180)
    hb = ax21.hexbin(actual_delay[clip_mask], pred_delay_b[clip_mask], gridsize=50, cmap='plasma', mincnt=1, bins='log')
    cb = fig2.colorbar(hb, ax=ax21, orientation='vertical', pad=0.02)
    cb.set_label('Log10 Point Density', color=text_muted, fontsize=9)
    cb.ax.tick_params(colors=text_muted, labelsize=8)
    ax21.plot([-10, 180], [-10, 180], color=accent_green, linestyle='--', linewidth=1.5, label='Perfect Fit (y = x)')
    ax21.set_xlabel('Actual Arrival Delay (Minutes)', color=text_light, fontsize=10)
    ax21.set_ylabel('Model B Predicted Delay (Minutes)', color=text_light, fontsize=10)
    ax21.set_xlim(-10, 180)
    ax21.set_ylim(-10, 180)
    ax21.legend(loc='upper left', facecolor=bg_card, edgecolor=grid_color, labelcolor=text_light)

    # Panel 2: Real Residual Histogram (actual - predicted)
    ax22 = fig2.add_subplot(gs2[0, 1])
    set_dark_theme(ax22, '2. Empirical Residual Error Distribution (y_test - y_pred)')
    res_range = (-45, 45)
    counts, bins, patches = ax22.hist(residuals_b, bins=90, range=res_range, color=accent_blue, alpha=0.8, edgecolor='#0f172a', density=True)
    mean_res = np.mean(residuals_b)
    std_res = np.std(residuals_b)
    median_res = np.median(residuals_b)
    ax22.axvline(x=0, color=accent_green, linestyle='--', linewidth=1.5, label='Zero Error')
    ax22.axvline(x=median_res, color=accent_amber, linestyle=':', linewidth=1.5, label=f'Median ({median_res:+.2f}m)')
    ax22.annotate(f'Mean: {mean_res:+.2f}m\nStd: {std_res:.2f}m\nMedian: {median_res:+.2f}m\nIQR: {np.percentile(residuals_b, 75) - np.percentile(residuals_b, 25):.2f}m',
                  xy=(0.04, 0.70), xycoords='axes fraction',
                  fontsize=9, color=text_light, fontweight='bold',
                  bbox=dict(boxstyle='round,pad=0.5', facecolor='#0f172a', alpha=0.8, edgecolor=grid_color))
    ax22.set_xlabel('Residual Error: Actual - Predicted (Minutes)', color=text_light, fontsize=10)
    ax22.set_ylabel('Density', color=text_light, fontsize=10)
    ax22.set_xlim(-45, 45)
    ax22.legend(loc='upper right', facecolor=bg_card, edgecolor=grid_color, labelcolor=text_light)

    # Panel 3: Empirical MAE by Train Type Category
    ax23 = fig2.add_subplot(gs2[1, 0])
    set_dark_theme(ax23, '3. Empirical MAE by Train Category (Model B)')
    test_df_copy = test_df.copy()
    test_df_copy["abs_error"] = abs_errors_b
    cat_err = test_df_copy.groupby("type_code")["abs_error"].agg(['mean', 'count']).reset_index()
    cat_err = cat_err[cat_err["count"] >= 100].sort_values("mean", ascending=True)
    yc = np.arange(len(cat_err))
    ax23.barh(yc, cat_err["mean"], color=accent_blue, alpha=0.85, edgecolor='#0f172a')
    ax23.set_yticks(yc)
    ax23.set_yticklabels(cat_err["type_code"], fontsize=9, color=text_light)
    for i, (m, c) in enumerate(zip(cat_err["mean"], cat_err["count"])):
        ax23.annotate(f'{m:.2f}m (n={c:,})', xy=(m, i), xytext=(4, 0), textcoords="offset points", va='center', fontsize=8.5, fontweight='bold', color=text_light)
    ax23.set_xlabel('Mean Absolute Error (Minutes)', color=text_light, fontsize=10)
    ax23.set_xlim(0, max(cat_err["mean"]) * 1.35)

    # Panel 4: Empirical MAE by Journey Progression Deciles
    ax24 = fig2.add_subplot(gs2[1, 1])
    set_dark_theme(ax24, '4. Error Convergence across Journey Progression Deciles')
    test_df_copy["journey_bin"] = pd.qcut(test_df_copy["elapsed_journey_pct"], q=10, duplicates='drop')
    bin_mae = test_df_copy.groupby("journey_bin", observed=True)["abs_error"].mean()
    bin_labels = [f"{(i+1)*10}%" for i in range(len(bin_mae))]
    ax24.plot(bin_labels, bin_mae.values, marker='o', color=accent_green, linewidth=2.2, markersize=6, label='Model B Test MAE')
    for i, v in enumerate(bin_mae.values):
        ax24.annotate(f'{v:.1f}m', xy=(i, v), xytext=(0, 6), textcoords="offset points", ha='center', fontsize=8.5, fontweight='bold', color=text_light)
    ax24.set_xlabel('Elapsed Journey Percentage', color=text_light, fontsize=10)
    ax24.set_ylabel('Empirical MAE (Minutes)', color=text_light, fontsize=10)
    ax24.legend(loc='upper right', facecolor=bg_card, edgecolor=grid_color, labelcolor=text_light)
    ax24.set_ylim(0, max(bin_mae.values) * 1.3)

    plt.suptitle('TrainETA Model Error Diagnostics: Convergence, Residuals & Empirical Breakdown\n(Evaluated on 156,216 Historical Out-of-Sample Test Records)',
                 fontsize=15, fontweight='bold', color=text_light, y=0.98)
    fig2.savefig(IMG_RESIDUALS, dpi=160, bbox_inches='tight', facecolor=fig2.get_facecolor())
    plt.close(fig2)
    print(f"Successfully saved: {IMG_RESIDUALS}")
    print("\nEmpirical evaluation complete.")

if __name__ == "__main__":
    main()
