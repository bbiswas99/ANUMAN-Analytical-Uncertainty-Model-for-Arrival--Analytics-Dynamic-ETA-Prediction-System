# 01 — Architecture Overview and Data Sources

---

## 1. System Architecture (Phase 1, the closed-loop prototype)

```
┌────────────────────────────────────────────────────────────────────┐
│                          PHASE 1 SOURCES                            │
│  combined_schedule.csv · combined_delay.csv · train_details.csv     │
│  station_full_names.csv · etrain_delays.csv · OSM (Overpass/        │
│  Geofabrik) · Live public train-tracking scraper (NTES/apps)        │
└───────────────────────────────┬───────────────────────────────────┘
                                 ▼
                    DATA PIPELINE (see 02_Pipeline_DataFlow_TechFlow.md)
                    Scrape → Parse → Reconcile → Clean → Join →
                    Feature Engineering → model_A_features table
                                 ▼
                    MODEL A (see 04_ML_Model_Spec.md)
                    Baseline + Random Forest / XGBoost / Extra Trees
                    residual model + uncertainty layer
                                 ▼
                    BACKEND API — FastAPI (see 05_Backend_API_Spec.md)
                    /predict  /explain  /replay
                                 ▼
                    FRONTEND — React + Vite + Leaflet (see 06)
                    Dashboard · Live-Replay · What-If · Map
                                 ▼
                    Deployed: Backend → Render/Railway
                              Frontend → Hostinger
                    (see 08_Deployment_Spec.md)
                                 ▲
                    FEEDBACK: actual arrivals write back into
                    combined_delay-equivalent storage → nightly retrain
```

**PHASE 2 (not built in this pass)** attaches at exactly one point: a weekly precedence-inference batch job reads the same scraper output used above, produces `precedence_events`, and those get joined into a second feature table (`model_B_features`) used only by Model B. See `07` and `04` Model B sections. Nothing above changes when Phase 2 is added.

---

## 2. Data Sources — Full Descriptions and Schemas

### 2.1 `combined_schedule.csv` (already have — Phase 1)
**Description:** The timetable backbone. One row per (train, stop) giving the scheduled sequence, timing, and distance.
**Exact columns (verified):**
| Column | Type | Notes |
|---|---|---|
| `station_no` | int | Sequence position of this stop on the train's route (1, 2, 3…) |
| `station_name` | string | **Actually a station CODE**, not a full name (e.g. "MJ") — do not rename in code, but never display raw to the user |
| `distance_from_origin` | int | Kilometers from the train's first station |
| `arrival_day` | int | Day offset from departure (1 = same day, 2 = next day, etc.) |
| `arrival_time` | string (HH:MM) | Displayed as `--:--` for the origin station |
| `departure_day` | int | |
| `departure_time` | string (HH:MM) | Displayed as `--:--` for the terminal station |
| `train_no` | int | Join key |

### 2.2 `combined_delay.csv` (already have — Phase 1)
**Description:** The only real per-journey delay label dataset. One row per (train, station, date).
**Exact columns (verified):**
| Column | Type | Notes |
|---|---|---|
| `date` | string | Range: 8 Feb 2025 – 7 Feb 2026 |
| `station_no` | int | Same sequence-position meaning as above |
| `station_name` | string | Station code (same caveat as above) |
| `delay` | float | Minutes; **cap outliers above the 99.5th percentile before use** (raw max observed: 7,018 min, a data artifact); negative values are valid (early arrival) |
| `train_no` | int | Join key |

### 2.3 `train_details.csv` (already have — Phase 1)
**Description:** Train priority/class lookup.
**Exact columns (verified):**
| Column | Type | Notes |
|---|---|---|
| `train_no` | int | Join key |
| `train_name` | string | Some contain "SPL" (special train) — flag these with a boolean derived column, do not drop |
| `type_code` | string (categorical) | One of: PASS-TRAINS, EXP-TRAINS, SF-TRAINS, RAJ-TRAINS, SHT-TRAINS, GRB-TRAINS, T18-TRAINS, PRM-TRAINS |

### 2.4 `station_full_names.csv` (already have — Phase 1)
**Description:** Station code → name → zone lookup.
**Exact columns (verified):**
| Column | Type | Notes |
|---|---|---|
| `station_name` | string | This is the code (join key against other files' `station_name`) |
| `station_full_name` | string | Human-readable name |
| `station_zone` | string (categorical) | 19 zones: NER, ECR, NR, CR, SECR, NCR, SR, WR, NWR, SER, NFR, ER, SWR, SCR, KR, WCR, ECOR, BR, SCOR |
| `station_address` | string | 94 rows null; not used as a model feature |

### 2.5 `etrain_delays.csv` (already have — Phase 1, supplementary)
**Description:** Pre-aggregated 1-year delay summary per (train, station) — used as a fallback prior, not for granular temporal features.
**Exact columns (verified):**
| Column | Type | Notes |
|---|---|---|
| `train_number` | int | Join key (note: different column name than other files' `train_no` — rename to `train_no` during ingestion) |
| `train_name` | string | |
| `station_code` | string | Join key |
| `station_name` | string | Full name in this file (unlike other files) |
| `average_delay_minutes` | float | 236 rows null |
| `pct_right_time` | float | |
| `pct_slight_delay` | float | |
| `pct_significant_delay` | float | |
| `pct_cancelled_unknown` | float | |
| `scraped_at` | string (timestamp) | All rows scraped 2025-09-27 |
| `source_url` | string | Traceability only, not a feature |

### 2.6 `IRCTC_cleaned.csv` (already have — Phase 1, low priority / reference only)
**Description:** Redundant with `combined_schedule.csv` except for two unique fields. **Do not join into the main pipeline** — only extract `days_of_week` and `classes` if a later feature needs them.
**Exact columns (verified):** `train_no`, `train_name`, `source_station`, `departure_time`, `arrival_time`, `distance`, `destination_station`, `days_of_week`, `classes`, `intermediate_stops`.

### 2.7 OpenStreetMap track geometry (to build — Phase 1)
**Description:** Real track geometry and station coordinates, via a one-time Geofabrik India extract filtered with `osmium` for `railway=rail` and `railway=station` tags.
**Fields extracted:** way ID, ordered list of (lat, lon) points per way, `tracks` tag (single/double/multi, where present), `electrified` tag, `usage` tag (main/branch/siding), station node (lat, lon) + OSM name (needs fuzzy-matching to `station_name` codes).
**Processing decision (per prior review):** station-pair connections are resolved by finding the candidate path whose total length matches the **scheduled distance** (`distance_from_origin` deltas from `combined_schedule.csv`) — the "expected route" — not the pure geometric shortest path, since junctions can have multiple physical lines between the same two named stations.

### 2.8 Live public train-tracking scraper (to build — Phase 1)
**Description:** Polls NTES and/or third-party running-status sources for active trains on the target corridor(s). See `07` for full function specs. Produces the raw snapshot fields: `train_no`, `source_name`, `poll_timestamp`, `last_station_code`, `platform_number` (where available), `reported_delay_min`.

### 2.9 Not built in Phase 1 (named for honesty, not hidden)
| Source | Status | Phase 1 stand-in |
|---|---|---|
| IMD weather API | Not integrated | Static `is_fog_season_flag` (Dec–Feb boolean) computed from date |
| TSR/PSR notices (division PDFs) | Not integrated | Feature `active_tsr_count_on_route` defaults to 0 / null until built |
| CRIS/ISRO RTIS (real GPS) | Not available — enterprise-only access via Pravah API, pending data-sharing agreement | Live scraper (2.8) + OSM interpolation (2.7) |

### 2.10 Excluded from the pipeline entirely (documented decision, not an oversight)
The Kaggle "Indian Railways: Predict Train Delay" synthetic competition dataset (`ir_train.csv`, `ir_test.csv`, etc.) is **never joined into any table in this pipeline** — confirmed synthetic (see `09` Appendix A for evidence). It is referenced only as an isolated sandbox for pipeline-code stress-testing, never as a source of training labels or accuracy claims.
