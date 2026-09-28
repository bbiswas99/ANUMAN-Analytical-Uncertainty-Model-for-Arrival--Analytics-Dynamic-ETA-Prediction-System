# 04 — ML Model Specification

**Scope note:** This is a specification only — inputs, outputs, expected behavior, and evaluation criteria. Actual training code, hyperparameter tuning, and model comparison are owned by the team's ML member. This document exists so that person (or an agent) has a complete, unambiguous target to build against.

---

## PHASE 1 — Model A

### Stage 1: Baseline (no training required)
**Input:** `baseline_delay_estimate`, `baseline_eta` (already computed in `02` Step 6/7 — pure arithmetic).
**Output:** `baseline_eta` — used directly whenever the ML layer is unavailable or `data_confidence_score` is below a defined threshold (recommend starting threshold: 0.3, tunable).
**Behavior requirement:** must always be computable with zero dependency on the trained model — this is the system's fallback guarantee.

### Stage 2: Tree-ensemble residual model
**Candidate models:** Random Forest, XGBoost, Extra Trees (all three, from `scikit-learn`/`xgboost`) — final selection and tuning is the ML owner's task.
**Input features:** columns 1–43 of `model_A_features.parquet` (all columns except `delay` and `residual_target` — see `03` Feature Dictionary). High-cardinality categoricals (`train_no`, `section_id`, `station_name`) should use target or frequency encoding, not one-hot.
**Target/label:** `residual_target` (column 45).
**Train/test split requirement:** split by `date`, never randomly shuffled — train on older dates, test on more recent dates, to avoid leaking future information. Recommend an 80/20 or 70/30 chronological split; exact cutoff date left to the ML owner based on final data volume.
**Output:** a trained model artifact file (e.g. `model_a.pkl` or `model_a.json` for XGBoost's native format) that accepts a 43-column feature vector and returns a single float: the predicted residual.
**Final ETA computation (done outside the model, in the API layer):** `predicted_eta = scheduled_time + baseline_delay_estimate + predicted_residual`.

### Stage 3: Network/congestion layer
**Phase 1 implementation:** none — `section_occupancy_count` (the engineered congestion proxy, already a Stage-2 input feature) stands in for this entirely. No separate model/layer exists in Phase 1.
**Production/future:** GNN or Temporal Fusion Transformer, per the master plan — out of scope here.

### Stage 4: Uncertainty / confidence interval
**Recommended approaches (ML owner picks one):**
- XGBoost quantile objective (`reg:quantileerror`) trained at two additional alphas (e.g. 0.1 and 0.9) alongside the point-prediction model, OR
- Random Forest / Extra Trees inter-tree prediction variance (no extra training run needed — compute the spread across individual trees' predictions at inference time).
**Output:** `confidence_interval_lower` and `confidence_interval_upper`, both in the same units as the final ETA (datetime or minutes-offset).
**Requirement:** the interval must widen for predictions further in the future (multi-day journeys) — validate this is actually happening before shipping; a model producing a constant-width interval regardless of horizon has failed this requirement.

### Explainability
**Requirement:** every prediction must be able to return its top 3 contributing features (via `feature_importances_` for Random Forest/Extra Trees, or SHAP values for XGBoost) as human-readable strings for the `/explain` endpoint (see `05`).
**Mapping table (build this as a small lookup, not a model):** translate feature names to passenger/staff-facing phrases, e.g. `section_occupancy_count` → "congestion at this section", `section_avg_delay_90d` → "historical delays on this route", `is_fog_season_flag` → "seasonal weather risk".

### Evaluation metrics (required, report all of these)
- MAE (Mean Absolute Error) in minutes — overall, and broken down by `type_code` and by prediction horizon (next-station vs. multi-day-ahead)
- Confidence interval coverage — what % of actual outcomes fall inside the predicted interval (should be close to the target, e.g. ~80% for an 80% interval)
- Comparison against the Stage 1 baseline alone — Model A must beat the baseline's MAE to justify its existence in the pitch

### Retraining
**Frequency:** nightly, on a rolling window (recommend last 90 days, tunable).
**Trigger for immediate retrain:** if nightly evaluation MAE degrades more than a defined threshold (e.g. 20%) versus the currently deployed model — flag for manual review rather than auto-deploying a worse model.
**Feedback data source:** actual `delay` values arriving via the scraper (Step 1-3 in `02`), written back into the historical store that feeds `combined_delay`-equivalent storage.

---

## PHASE 2 — Model B (do not build until the data-collection go/no-go checkpoint passes)

### What changes from Model A
**Everything in Model A stays identical.** Model B is Model A's exact pipeline plus two additional input features, joined in per `07`'s Phase 2 section:
- `precedence_risk_score_next_section` (float, 0-1)
- `historical_precedence_rate_vs_known_priority_trains` (float, 0-1)

**Input features:** columns 1–43 of `model_A_features.parquet` PLUS the two columns above (45 total input columns, since `delay`/`residual_target` remain the label, not inputs).
**Target/label:** same `residual_target` definition, unchanged.
**Training/serving:** identical process to Model A, run as a separate trained artifact (`model_b.pkl`).

### Required comparison methodology (this is the actual deliverable of Phase 2, not just "a better model")
- Same chronological train/test split, same date range, same evaluation trains as Model A — no exceptions, or the comparison is invalid.
- Report Model A vs. Model B MAE **overall**, AND **specifically on the subset of test rows where `precedence_risk_score_next_section` was non-null/non-zero** (i.e., where a precedence event was actually flagged) — this isolates whether the new feature helps where it should.
- Check for data leakage explicitly: confirm every precedence feature value used for a given test-set date was computed using only data available before that date.

### Serving fallback requirement
If precedence features are unavailable for a given train/section at prediction time (not yet scraped, or Phase 2 not yet live), the API must serve Model A's prediction rather than fail or serve a null-filled Model B prediction.
