# TrainETA Backend

FastAPI service providing `/predict`, `/explain`, `/replay`, `/health`, and `/trains` endpoints.

---

## Quick Start

```bash
# From the project root (e:\SIH 2026\Code)
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000 --reload
```

Or in production mode (no reload):
```bash
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000 --host 0.0.0.0
```

---

## File Structure

```
backend/
  main.py                    — FastAPI app, all endpoints
  errors.py                  — Standard exception classes (10_Error_Handling)
  reconciled_reader.py       — Reader for live scraper output (see below)
  train_model.py             — Model A training script (run once)
  models/
    model_a.json             — XGBoost Model A artifact
    label_encoders.json      — Categorical feature encoders
    feature_importance.json  — Feature weights for /explain
  pipeline/
    build_features.py        — Feature engineering pipeline (run once)
  model_A_features.parquet   — Training/inference feature table
```

---

## Scraper Integration — `reconciled_positions.parquet`

The prediction backend can consume **live delay data** from the remote scraper machine.
The scraper drops a parquet file at the path configured by `RECONCILED_DATA_PATH` (see `.env.example`).

### How it works
1. **Remote machine** polls NTES every 10–15 minutes and writes `reconciled_positions.parquet`.
2. **This machine** reads that file at most once per 60 seconds (cached).
3. If the file is absent or stale, `/predict` silently falls back to historical-baseline mode — **no crash, no 500 error**.
4. `/health` reports `"data_freshness_warning": true` if the newest row is older than 2 hours.

### Required Parquet Schema

| Column | Type | Description |
|---|---|---|
| `train_no` | `int64` | Indian Railways train number |
| `station_no` | `int64` | Stop sequence on the route |
| `station_name` | `str` | Station code (e.g. `"NDLS"`) |
| `delay` | `float64` | Current delay in minutes (negative = early) |
| `date` | `datetime64[UTC]` | Journey date (UTC) |
| `scraped_at` | `datetime64[UTC]` | Timestamp when this row was scraped (UTC) |
| `source_agreement_score` | `float64` | 0–1 multi-source confidence |

### Optional Columns (used if present, silently ignored if absent)
| Column | Type | Description |
|---|---|---|
| `platform_number` | `str` | Platform assignment |
| `reported_speed_kmh` | `float64` | Reported loco speed |

### How to generate the file (example, on the scraper machine)

```python
import pandas as pd

rows = []  # ... populated from NTES polling
df = pd.DataFrame(rows)

# CRITICAL: scraped_at must be UTC timezone-aware
df["scraped_at"] = pd.Timestamp.utcnow()
df.to_parquet("reconciled_positions.parquet", index=False)
```

Then **copy** (rsync / shared drive / any mechanism) to `RECONCILED_DATA_PATH` on this machine.
The backend will auto-reload it within 60 seconds.

---

## Environment Variables

See [`.env.example`](../.env.example) in the project root.

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Service status, model loaded, scraper freshness |
| `/predict?train_no=12301` | GET | ML ETA prediction |
| `/predict?train_no=12301&what_if={"reported_delay_min":30}` | GET | What-If scenario |
| `/explain?train_no=12301` | GET | Top delay factors |
| `/replay?train_no=12301&date=2025-11-15` | GET | Historical journey replay |
| `/trains` | GET | List all trains with data |
| `/docs` | GET | Interactive Swagger UI |

### Error Response Shape

All errors return this standard JSON shape:
```json
{
  "error_code": "InvalidTrainNumberError",
  "message": "Train 99999 not found in the dataset",
  "detail": null
}
```

| `error_code` | HTTP | Meaning |
|---|---|---|
| `ValidationError` | 400 | Bad input (invalid train_no, date format) |
| `InvalidTrainNumberError` | 404 | Train not in dataset |
| `NoActiveJourneyError` | 404 | No journey data for that date |
| `WhatIfOverrideInvalidError` | 422 | Invalid what-if field or out-of-range value |
| `ModelNotLoadedError` | 503 | Model artifact failed to load |
| `InternalError` | 500 | Unexpected error (details logged server-side) |
