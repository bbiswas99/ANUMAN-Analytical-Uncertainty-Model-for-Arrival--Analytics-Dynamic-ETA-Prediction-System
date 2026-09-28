# 05 — Backend API Specification (FastAPI)

Function-level specs only (signature, inputs/outputs, behavior) — no implementation code, per project decision.

---

# 05 — Backend API Specification (FastAPI)

Function-level specs only (signature, inputs/outputs, behavior) — no implementation code, per project decision. All error handling below uses the exception taxonomy and standard response shape defined in `10_Error_Handling_and_Validation.md` — this file does not redefine error formats, only which exception applies where.

---

## 1. Endpoints

### `GET /predict`
**Query params:** `train_no: int` (required), `what_if: dict` (optional, JSON-encoded — see What-If behavior below)
**Input validation (before any processing):** `train_no` must parse as a positive integer — a non-numeric or negative value returns HTTP 400 with message "train_no must be a positive integer" before any lookup is attempted. `what_if`, if present, must be valid JSON — malformed JSON returns HTTP 400 with message "what_if parameter must be valid JSON."
**Behavior:**
1. Look up `train_no` in the schedule; if absent, raise `InvalidTrainNumberError` (10) → HTTP 404.
2. Check for an active journey at the current time; if none, raise `NoActiveJourneyError` (10) → HTTP 404.
3. Look up the latest `reconciled_positions` row for `train_no` via `get_latest_reconciled_row()`.
4. Call `compute_live_features()` (from `02` Step 7) — this itself may raise `InvalidTrainNumberError`/`NoActiveJourneyError` again defensively; both are caught and mapped identically.
5. If `what_if` params are present, validate and apply them via `apply_what_if_overrides()` — invalid fields/values raise `WhatIfOverrideInvalidError` → HTTP 422.
6. If `data_confidence_score` < threshold (default 0.3, from `DATA_CONFIDENCE_THRESHOLD` env var) → return the Stage 1 baseline only, with `"model_used": "baseline"`.
7. Otherwise → run Stage 2 model + Stage 4 uncertainty → return the full response.
8. Any exception not explicitly handled above is caught by a top-level handler, logged with full detail server-side, and returned as HTTP 500 with the generic message from `10` — never the raw exception text.
**Response schema:**
```json
{
  "train_no": 12301,
  "eta": "2026-09-15T14:32:00",
  "confidence_interval_lower": "2026-09-15T14:24:00",
  "confidence_interval_upper": "2026-09-15T14:41:00",
  "model_used": "model_a",
  "data_confidence_score": 0.91,
  "baseline_eta": "2026-09-15T14:40:00"
}
```
**Error responses** (all in the standard shape from `10`):
| Condition | Exception | Status |
|---|---|---|
| `train_no` not numeric/positive | input validation (no exception object, direct 400) | 400 |
| `train_no` not in schedule | `InvalidTrainNumberError` | 404 |
| No journey scheduled today | `NoActiveJourneyError` | 404 |
| Invalid `what_if` field/value | `WhatIfOverrideInvalidError` | 422 |
| Model not loaded (should never happen post-startup; defensive only) | `ModelNotLoadedError` | 503 |
| Anything else unexpected | generic 500 | 500 |
**Note:** "no reconciled position available at all" is NOT an error — it's the expected trigger for `"model_used": "baseline_no_live_data"`, handled in step 6/7 above, not in the error table.

### `GET /explain`
**Query params:** `train_no: int` (required)
**Input validation:** identical to `/predict`'s `train_no` validation.
**Behavior:** Calls `/predict`'s internal logic (inheriting all of its error handling above), then extracts the top 3 contributing features via the model's feature-importance/SHAP output, maps them through the human-readable phrase lookup (see `04`).
**Safety check specific to this endpoint:** if the model's feature-importance output returns fewer than 3 non-zero-importance features (a degenerate/undertrained model), `top_delay_factors` returns however many are genuinely non-zero rather than padding with meaningless low-importance features — never fabricate a 3rd reason that isn't actually meaningful.
**Response schema:**
```json
{
  "train_no": 12301,
  "top_delay_factors": [
    "historical delays on this route",
    "congestion at this section",
    "seasonal weather risk"
  ]
}
```
**Error responses:** identical table to `/predict` (this endpoint calls the same underlying logic).

### `GET /replay`
**Query params:** `train_no: int` (required), `date: string` (required, YYYY-MM-DD)
**Input validation:** `train_no` per above. `date` must match `YYYY-MM-DD` exactly and parse as a real calendar date — an invalid format returns HTTP 400 with message "date must be in YYYY-MM-DD format." A syntactically valid but impossible date (e.g. 2025-02-30) returns the same 400.
**Behavior:** Reads all `master_joined_table.parquet` rows for the given (`train_no`, `date`), ordered by `station_no`. Returns them as a time-ordered array for the frontend's Live-Replay mode.
**Safety checks:** if `train_no` exists but has zero rows for the given `date` (valid train, but didn't run that day, or date is out of the data's collection range), raises `NoActiveJourneyError` → HTTP 404 with message "Train {train_no} has no recorded journey on {date}." — distinct from `train_no` not existing at all.
**Response schema:**
```json
{
  "train_no": 12301,
  "date": "2025-09-15",
  "stops": [
    {"station_no": 1, "station_name": "HWH", "scheduled_time": "16:50", "actual_delay_min": 2, "lat": null, "lon": null},
    {"station_no": 2, "station_name": "CNB", "scheduled_time": "22:10", "actual_delay_min": 5, "lat": null, "lon": null}
  ]
}
```
`lat`/`lon` are filled in by the frontend at render time via the polyline-snapping function (see `06`), not by this endpoint — this endpoint only returns the time/delay sequence.
**Error responses:**
| Condition | Exception | Status |
|---|---|---|
| `train_no`/`date` malformed | input validation | 400 |
| `train_no` not in schedule | `InvalidTrainNumberError` | 404 |
| No journey recorded for that date | `NoActiveJourneyError` | 404 |

### `GET /health`
**Behavior:** Returns `{"status": "ok", "model_a_loaded": true, "last_scraper_update": "<timestamp>"}`. Used by deployment monitoring (see `08`).
**Safety checks:** if the model failed to load at startup, the service should already have refused to start (per `load_model()` below) — `/health` returning `"model_a_loaded": false` is therefore only ever observed in a race condition during startup, never in steady state. If `last_scraper_update` is older than a defined staleness threshold (default 2 hours), `/health` still returns `"status": "ok"` (the API itself is fine) but adds `"data_freshness_warning": true` so monitoring can distinguish "the API is down" from "the data pipeline upstream is stale."

### `GET /precedence`
**Query params:** `train_no: int` (required)
**Input validation:** `train_no` must parse as a positive integer; if non-positive or absent from schedule, raises `InvalidTrainNumberError` → HTTP 404.
**Behavior:** Evaluates confirmed historical precedence conflict events along this train's route against higher-priority trains (Rajdhani/Vande Bharat/Shatabdi/Superfast) crossing the same section.
**Response schema:**
```json
{
  "train_no": 1025,
  "train_name": "DR BALLIA SPL",
  "precedence_active": true,
  "precedence_risk_score": 0.95,
  "total_conflicts_count": 5,
  "conflicts": [
    {
      "section_id": "HD_ET",
      "role": "delayed",
      "interacting_train_no": 2131,
      "interacting_train_name": "PUNE JBP SF SPL",
      "confidence_score": 0.8,
      "total_crossings_observed": 6,
      "estimated_hold_min": 14.4,
      "description": "Subject to hold behind priority Train 2131 (PUNE JBP SF SPL) on section HD_ET"
    }
  ],
  "model_b_available": true
}
```
**Error responses:**
| Condition | Exception | Status |
|---|---|---|
| `train_no` not positive integer | `InvalidTrainNumberError` | 404 |
| `train_no` not in schedule | `InvalidTrainNumberError` | 404 |
| Service starting / model store unready | `ModelNotLoadedError` | 503 |

### `GET /trains`
**Query params:** None
**Behavior:** Returns the distinct list of all trains available in the historical model training set (`model_A_features.parquet`), along with their train number and commercial name.
**Response schema:**
```json
{
  "count": 415,
  "trains": [
    {"train_no": 961, "train_name": "VALLEY QUEEN SPL"},
    {"train_no": 1025, "train_name": "DR BALLIA SPL"}
  ]
}
```
**Error responses:**
| Condition | Exception | Status |
|---|---|---|
| Data store not loaded | `ModelNotLoadedError` | 503 |

---

## 2. Internal Functions

```
load_model(path: str) -> object
  Loads a trained model artifact (Model A, or Model B once Phase 2 exists) once at
  service startup.
  Safety checks: raises ModelNotLoadedError (FATAL — service refuses to start, per 10)
  if the file is missing, unreadable, or fails to deserialize. Also validates the
  loaded model exposes a .predict() method and a feature-importance/SHAP interface
  before accepting it — a loaded-but-incompatible artifact is treated the same as a
  missing one, not discovered later at first prediction time.

get_latest_reconciled_row(train_no: int) -> dict | None
  Reads the most recent row for this train from reconciled_positions.parquet.
  Returns None if no row exists (triggers baseline-only fallback in /predict) — this
  is a deliberate non-error return, not an exception, since "no live data yet" is an
  expected, handled state, not a failure.
  Safety checks: raises SchemaValidationError (logged, not returned to the caller as
  a 500 — caught internally and treated as "no row available") if the underlying
  parquet file itself is corrupt/unreadable, so a storage-layer problem degrades to
  the same safe fallback as "no data yet" rather than crashing the request.

apply_what_if_overrides(features: dict, overrides: dict) -> dict
  Returns a copy of the feature dict with specified fields replaced by hypothetical
  values.
  Safety checks: raises WhatIfOverrideInvalidError if a key in `overrides` is not one
  of the explicitly allowed what-if fields (03 Feature Dictionary — recommended
  allowlist: reported_delay_min, section_occupancy_count only, per 06). Raises the
  same exception if an allowed field's override value is outside its physically
  plausible range (e.g. reported_delay_min outside [-60, 3000]). Never silently
  clamps an out-of-range value and proceeds — the user must be told their scenario
  was rejected and why.

run_stage2_prediction(features: dict, model) -> float
  Returns the predicted residual (minutes) from the loaded model.
  Safety checks: raises OutOfRangeFeatureError (non-fatal, falls back to baseline for
  this one request) if the model's output is NaN, infinite, or exceeds ±2000 minutes
  — a broken prediction must never reach the passenger-facing response.

run_stage4_uncertainty(features: dict, model) -> tuple[float, float]
  Returns (lower_bound_minutes, upper_bound_minutes) around the point prediction.
  Safety checks: raises OutOfRangeFeatureError (non-fatal, falls back to baseline) if
  lower_bound > upper_bound (an inverted interval is a modeling bug, never shown to
  the user) or if either bound is NaN/infinite.

compute_final_eta(scheduled_time: datetime, baseline_delay: float,
                   predicted_residual: float) -> datetime
  scheduled_time + baseline_delay + predicted_residual.
  Safety checks: raises SchemaValidationError if scheduled_time is null (should be
  impossible given upstream validation, but this function must not silently produce
  a garbage datetime from a null input).

get_explanation(features: dict, model) -> list[str]
  Returns the top-3 human-readable delay factors (see 04's phrase-mapping table).
  Safety checks: if a feature name has no entry in the phrase-mapping lookup table,
  it is skipped (never shown to the user as a raw internal column name like
  "section_avg_delay_90d") and logged as a mapping-table gap to fix, rather than
  silently exposing implementation details.
```

---

## 3. Cross-Cutting Requirements

- **CORS:** must allow the Hostinger frontend domain explicitly (not wildcard `*` in production).
- **Model loading:** once at startup, never per-request (latency requirement); startup fails hard per `load_model()`'s safety checks above.
- **Fallback discipline:** every endpoint must degrade to baseline/partial data rather than returning HTTP 500 when the ML layer or live tracking data is unavailable — this is a hard requirement carried from the master plan's resilience design, not optional.
- **No PII, no login-gated data:** the backend never proxies or stores anything beyond public running-status data, per the scraping ethics rule established in this project.
- **Every response, success or error, uses a defined schema.** No endpoint may return an ad hoc shape not documented above or in `10`.
- **Rate limiting (recommended, not yet mandatory for the prototype):** consider a basic per-IP request cap on `/predict` and `/replay` to protect the model-serving process from accidental abuse during public demo access; not required for a controlled judge demo, worth adding before any wider public exposure.
