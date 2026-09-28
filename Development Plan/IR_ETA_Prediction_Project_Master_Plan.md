# Indian Railways Dynamic ETA Prediction — Master Project Plan

> **Update note (latest audit):** this document predates several implementation decisions. Where it conflicts with `build_spec/`, the build spec wins. Key changes: live tracking uses public/reverse-engineered API polling (not HTML scraping); the map must render from locally-extracted OSM geometry with no live tile provider (current build still draws straight lines); Model B's conflict-subset result is a provisional ~3.2% MAE improvement (the earlier 34% figure was illustrative and is retired) pending wiring of the repetition-confidence gate; LightGBM is not used.

### Consolidated from full planning discussion — SIH Submission

---

## PART 1 — Problem Understanding

**Core ask (SIH problem statement):** Build a real-time, dynamic ETA prediction system for coaching trains that adapts to actual running conditions (delays, congestion, TSRs, weather, unscheduled stoppages), scales to thousands of trains across 17 zones, and exposes results via APIs to mobile apps, station displays, and control-room dashboards.

**Three sub-problems identified:**
1. **Point prediction** — ETA at the next station (easy, low uncertainty)
2. **Multi-hop prediction** — ETA at all remaining stations on multi-day routes (errors compound)
3. **Network-level prediction** — ETA accounting for *other* trains (precedence, crossing, congestion) — the true differentiator most competing teams will miss

**Key loopholes/edge cases to address in submission:** cold-start trains, GPS/data gaps, multi-source data disagreement, cascading delays, weather/seasonal systemic effects (fog Dec–Feb), unscheduled stops, long-haul multi-day error compounding, concept drift (timetable revisions twice/year), national scale (~13,000 trains/day), low-connectivity zones, explainability for control-room trust, confidence intervals instead of point estimates.

---

## PART 2 — Datasets (What We Actually Have, Verified by Direct Inspection)

### Real, usable data (uploaded and inspected):

| File | Rows × Cols | What it gives you | Quality notes |
|---|---|---|---|
| `combined_schedule.csv` | 172,112 × 8 | Timetable backbone: station sequence, arrival/departure day+time, distance from origin, per `train_no` | 8,673 unique trains; origin/terminal stations correctly show nulls for missing arrival/departure |
| `combined_delay.csv` | ~1.05M × 5 | **Only real per-journey delay label dataset** — `delay` per (train_no, station_no, date) | 466 unique trains, but **1,527 real distinct stations** (corrected — station_no is stop-sequence, not station identity); 6.5% missing; extreme outlier max (7,018 min) needs capping; date range Feb 2025–Feb 2026 |
| `train_details.csv` | 8,992 × 3 | `type_code` = train priority class (PASS/EXP/SF/RAJ/SHT/GRB/T18/PRM) | Some "SPL" (special) trains mixed in — flag/filter separately |
| `station_full_names.csv` | 8,963 × 4 | Station code → full name → **zone** (19 zones) | 94 missing addresses (not material) |
| `IRCTC_cleaned.csv` | 8,366 × 10 | Route strings w/ intermediate stops, `classes`, `days_of_week` | Redundant with `combined_schedule` except for `days_of_week`/`classes` fields |
| `etrain_delays.csv` (×2, duplicate upload) | 1,900 × 11 | Pre-aggregated 1-year delay summary per (train, station): avg delay, % on-time/slight/significant/cancelled | Good as a **prior/fallback feature**, not for granular temporal modeling (already aggregated) |

### Synthetic dataset (Kaggle competition — CONFIRMED NOT REAL DATA):
`ir_train.csv` / `ir_test.csv` / `ir_data_dictionary.csv` / `ir_sample_submission.csv` — this is the **"Indian Railways: Predict Train Delay"** Kaggle competition (binary target: late >15 min).

**Proof it's synthetic, not real IR operational data:**
- Zero missing values across 1.5M rows × 45 columns (impossible for real data)
- **Hard gap in `delay_minutes` distribution: zero rows between 15–36 minutes**, jumping from dense 10–14 min counts straight to 37+ — a generator fingerprint, real delays are continuous
- `is_overloaded` constant 0 despite `seat_utilisation_pct` hard-capped at exactly 100.0
- `route_historical_ontime_pct` only ~0.69 correlated with actual outcome — consistent with co-generation from the same formula as the label, not an independently computed historical stat
- `train_number` values are sequential auto-IDs (11100, 11101...) that only coincidentally numerically overlap with real IR train numbers (2,024/6,266 overlap checked directly) — **not the same trains**

**Decision: DO NOT MERGE with real data.** Different granularity (whole-journey vs per-station) and no valid join key. **Use only as:** (a) a fast sandbox for pipeline-testing code at scale, (b) source for `primary_delay_cause` taxonomy to design the explainability layer's delay-cause categories. Never report headline accuracy numbers from this dataset as real-world performance — clearly label it as a synthetic benchmark if mentioned at all.

### Track/infrastructure data:
**OpenStreetMap (OSM) Overpass API** — provides real track geometry (`railway=rail` ways), station nodes, and tags (`tracks=`, `electrified=`, `maxspeed=`, `usage=main/branch`). Solves part of the "track ambiguity" problem (real single/double-line info) but NOT real-time occupancy/signalling.

**Implementation notes:**
- Verify tag completeness on target corridors manually first (via `overpass-turbo.eu`) before building
- Do a **one-time bulk extract** (Geofabrik India OSM extract + `osmium` filtering) — don't hit the live Overpass API repeatedly
- OSM station names need fuzzy-matching to your station codes — not automatic
- Building the actual path between two named stations requires graph construction (`networkx`) + shortest-path, not a single query

### What's genuinely NOT publicly available (named explicitly, for honesty in the pitch):
- COIS/FOIS real-time train control data
- Interlocking/signalling logs (real block-section occupancy)
- TMS precedence/crossing decision data
- Crew/maintenance scheduling internals

---

## PART 3 — Novel Data Collection Idea: Precedence-Inference from Public Tracking

**The core idea (user's):** Instead of needing IR's internal signalling data, infer track-precedence conflicts by observing which trains pick up delay near a higher-priority train, using only public running-status data.

### Refined algorithm (final version after review):
1. **Delay signal per train per section** — `delay_picked_up = delay_exit − delay_entry` (scheduled times already net out planned dwell — confirmed non-issue)
2. **Baseline against the train's OWN historical pattern** at that exact section (not an absolute threshold)
3. **Systemic-cause filter** — check if ALL trains in that section (at finest station-pair granularity) show the same anomaly that day → discard as weather/signal-failure, not precedence
4. **Priority cross-reference** — check `train_details.csv` priority class of any train present nearby
5. **Require repetition before trusting a label** — e.g., 6+/10 observed joint crossings, not a single coincidence — gives a natural confidence score
6. **Platform-number change treated as a POSITIVE signal** (not noise to discard) — congestion-driven platform reassignment is a real operational pattern, so a deviation from a train's normal platform raises confidence rather than being filtered out

### Multi-source cross-validation design:
- Poll NTES + multiple third-party apps (RailYatri/Trainman/Where Is My Train etc.)
- Reconcile per (train, timestamp) into one value + a `source_agreement_score`
- Disagreement between sources = low-confidence flag, not just averaged away

### Validation plan (must-do, not optional):
- Spot-check top-confidence flagged events against IRFCA/enthusiast forums, news coverage, or a targeted RTI request for a small sample of dates/trains
- Start validation in **week 3–4**, not at the end

### Explicit risk mitigation & framing for judges:
- State clearly: "original CRIS/ISRO data wasn't available, so we built this self-supervised inference method instead"
- Never scrape login-gated/PNR endpoints — public running-status only
- Scraping is a network/legal risk, not a compute problem — local hardware (DGX/Mac Studio) doesn't reduce ToS/rate-limit risk

---

## PART 4 — Time-Based Polyline Snapping (Map Visualization Only)

**What it is:** Linear interpolation of train position between two known station timestamps, snapped onto real OSM track geometry (arc-length parameterized, not point-index) — same technique used by "Where Is My Train."

**Strict scope decision:** **Display-layer approximation ONLY.** Never used as input to the ETA-prediction or precedence-inference pipelines, because:
- Assumes constant speed — cannot represent a real mid-section signal halt (looks identical to normal progress)
- Adds zero new information beyond what's already known from the two schedule/delay numbers

**Legitimate secondary use:** cheap candidate-generation filter — interpolate multiple trains' positions at the same timestamp to flag which train pairs are plausibly near each other, narrowing which pairs to run the full precedence-inference algorithm on.

**OSM static signal/junction positions + real delay-spike data** → used to place an approximate "delay spike near this junction" marker on the map. **Labeling discipline for the PPT:** caption as *"delay spike observed near this junction (interpolated)"* — never claim a specific signal/cause was detected (that would be an overclaim).

**Finale-round pitch framing (before/after CRIS table):**

| Now (prototype, public data only) | With CRIS/ISRO access (production) |
|---|---|
| Delay spike + nearest OSM junction → approximate marker | Exact signal ID, real block-section occupancy, control-office halt reason |
| Time-interpolated position between stations | True continuous GPS/RTIS position |

*(Verified, sourced RTIS specifications — NavIC+GAGAN positioning, 30s updates, confirmed use-cases — are documented in the Data Flow Analysis doc's "Sources for the verified RTIS facts" section; do not use unsourced field-level schemas that may surface elsewhere in research.)*
| Inferred precedence from public delay correlation | Ground-truth precedence from dispatch records |

Map can be scoped as authority-only, public, or both — explicitly left as an operator decision, not something the prototype forces.

---

## PART 5 — Feature Set (Final, by Category)

**Train state (real-time):** current_delay_min, last_reported_lat/lon, last_reported_timestamp, time_since_last_update_sec, current_speed_kmph, scheduled_speed_kmph, speed_ratio, distance_to_next_station_km, scheduled_time_to_next_station_min, stops_remaining_count, distance_remaining_total_km, elapsed_journey_pct, delay_trend_last_3_points, delay_rate_per_100km, train_priority_class, train_number, rake_type, coach_composition_count, is_running_late_flag, origin_departure_delay_min

**Section/network (spatial, feeds precedence layer):** section_id, line_type (single/double/multi — from OSM), electrification_status, gradient_category, max_permissible_speed_kmph, section_occupancy_count, precedence_conflict_flag, conflict_score, upstream_delay_min, historical_avg_crossing_time_min, junction_complexity_score, platform_availability_flag

**Temporal:** hour_of_day (cyclical sin/cos), day_of_week (cyclical), month, is_holiday_flag, is_festival_rush_flag, is_fog_season_flag, days_since_timetable_revision, time_to_destination_horizon_hr

**Environmental:** visibility_m, rainfall_intensity_mm, temperature_c, cyclone_alert_flag, weather_severity_score (composite)

**Speed restriction/maintenance:** active_tsr_count_on_route, tsr_severity_avg, psr_flag, maintenance_block_scheduled_flag, level_crossing_count_remaining

**Historical/statistical priors:** section_avg_delay_30d/90d/365d, train_number_avg_delay_30d, zone_avg_punctuality_pct, seasonal_decomposition_residual, station_avg_dwell_time_min

**Derived/composite:** recovery_margin_remaining_min, baseline_eta, predicted_residual_min, network_adjustment_min, final_eta, confidence_interval_lower/upper, data_confidence_score

**New (from precedence-inference work):** precedence_risk_score_next_section, historical_precedence_rate_vs_known_priority_trains

**Encoding rules:** high-cardinality categoricals (train_number, section_id, station_code) → target/frequency encoding, not one-hot; time features always cyclical sin/cos, never raw integer; TSR/PSR notices need a dedicated NLP/regex parser (messiest source).

---

## PART 6 — Model Architecture (Final)

### Two-model comparison strategy (final decision):
- **Model A** — baseline + LightGBM residual, using ONLY publicly available features (schedule, historical stats, priority, temporal, schedule-based congestion proxy). Deployable immediately, guaranteed to exist regardless of scraping outcome.
- **Model B** — Model A's exact pipeline + additional precedence-inference features bolted on (`precedence_risk_score_next_section`, etc.) from the scraping/inference work. Research extension, upside case.

**Evaluation methodology:** same train/test split and date range for both; report overall MAE AND MAE specifically on the subset where a precedence conflict was flagged (isolates where Model B should help); guard against data leakage (precedence features must only use data available before the test date).

**Serving resilience:** if Model B's features are missing for a given train/section, fall back to Model A rather than failing.

### Four-stage hybrid pipeline (within each model):
1. **Stage 1 — Deterministic baseline:** schedule + current delay + recovery margin. Always computed, always available (ultimate fallback).
2. **Stage 2 — Random Forest / XGBoost / Extra Trees residual model** (per zone or section-cluster), predicts deviation from baseline, not absolute time. Retrained nightly. *(Model choice finalized — team is using tree-ensemble methods, not gradient-boosted-only or deep learning, for this stage. XGBoost is the natural pick if a single best-performer is needed; Random Forest/Extra Trees are good baselines/ensembling partners and are notably easier to bootstrap confidence intervals from via inter-tree variance.)*
3. **Stage 3 — Network/congestion layer:** full production version = GNN (graph = stations/sections, inspired by the published RSTGCN architecture for Indian Railways, 4,735 stations/17 zones) or Temporal Fusion Transformer. **30-hour/hackathon-scoped version = engineered proxy feature** (count of other trains scheduled through same station-pair within ±30 min, computable from `combined_schedule.csv` alone, no graph library needed) — explicitly labeled in the pitch as a lightweight stand-in for the full GNN.
4. **Stage 4 — Ensemble + uncertainty:** stacked meta-learner or Bayesian averaging; for confidence intervals, either **XGBoost quantile objective** (`reg:quantileerror`, e.g. alpha 0.1/0.9) or **Random Forest/Extra Trees inter-tree prediction variance** (a natural fit since these are bagged ensembles — spread across trees gives an uncertainty estimate with no extra loss function needed) — critical for multi-day trains where far-future stations should show a widening range, not false precision.

**Explainability requirement:** feature importances / SHAP values on the Stage-2 tree ensemble for control-room trust ("why" this ETA) — directly serves the SIH's "reliable, up-to-date information for decision-making" requirement. All three candidate models (RF, XGBoost, Extra Trees) support SHAP natively, so this doesn't constrain the final pick.

**Note on scope:** actual model training/tuning (feature selection refinement, hyperparameter search, RF vs. XGBoost vs. Extra Trees comparison) is being handled by a dedicated team member — this document tracks the architectural decision, not the implementation.

**Delay-cause taxonomy** (borrowed from synthetic Kaggle set's `primary_delay_cause` categories) — used to structure the explainability output even though that dataset itself isn't used for training.

### Prior academic work to cite (found during research, strengthens literature review):
- **RSTGCN** (railway-centric spatio-temporal GNN, Indian Railways, 4,735 stations/17 zones) — direct precedent for Stage 3's full production design
- **Zero-Shot Markov Model** for Mughalsarai (MGS) junction delay propagation, 135 trains, 2 years — India-specific precedent for network/congestion effects, simpler baseline your hybrid approach improves on
- **XGBoost + dispatcher commands** (2024, ~1.9M records, 38 months, high-speed rail) — supports gradient-boosted-tree choice for Stage 2

---

## PART 7 — System Architecture

### Full production architecture (data flow):
```
DATA SOURCES (COIS/FOIS, NTES/GPS, RFID, signalling logs, IMD weather,
TSR/PSR notices, static timetable, OSM track geometry, scraped precedence data)
        ↓
INGESTION/ETL (Kafka event bus, Kafka Connect/custom adapters for legacy
COIS/FOIS SOAP/flat-file systems, NLP parser microservice for TSR/PSR PDFs)
        ↓
STREAM PROCESSING (Spark Structured Streaming or Flink — GPS/position
reconciliation via Kalman filter + multi-source fusion/confidence scoring,
real-time feature computation → Feast online store (Redis) + offline (Delta Lake/S3))
        ↓
ML SERVING (K8s) — Stage 1 baseline (stateless) → Stage 2 LightGBM per-zone
(BentoML/FastAPI) → Stage 3 GNN/TFT (TorchServe, batched inference every
30-60s per zone) → Stage 4 ensemble+conformal → MLflow model registry,
canary deployment
        ↓
CACHING/API (Redis cache, Kong/NGINX gateway, FastAPI/Node.js REST+WebSocket:
/eta/train/{no}, /eta/station/{code}, /eta/stream, /explain/{train_no})
        ↓
CONSUMERS: Mobile app/NTES integration | Station display boards (IoT,
low-bandwidth fallback to cached baseline) | Control room dashboard
(React + Grafana + explainability panel)

MLOps: Airflow/Kubeflow nightly (Stage 2) / weekly (Stage 3) retraining,
ground-truth feedback loop from COIS, shadow deployment 3-7 days before
promotion, drift monitoring (Evidently AI), A/B eval vs current NTES baseline
```

### Prototype architecture (30-hour build / SIH demo, decided given Hostinger + team constraints):
```
React (Vite) on Hostinger  ──HTTPS──►  FastAPI (Render/Railway free tier)
    │                                    - baseline engine
    │◄── fallback: bundled                - LightGBM point + quantile models
    │    demo-fallback.json               - /predict, /explain, /replay endpoints
    │    (if API unreachable)
    ▼
Live-replay mode (historical journey replayed on a simulated clock)
+ Manual what-if mode (pick train + scenario, instant prediction)
```

**Decision rationale:** Python needed for LightGBM/pandas — reimplementing in Node/ONNX under time pressure is unnecessary risk; decouple FastAPI (ML) from Hostinger (frontend, static Vite build) via HTTPS/CORS. Backup plan (mandatory): bundled fallback JSON + locally runnable FastAPI via laptop hotspot, in case of bad venue Wi-Fi.

---

## PART 8 — Full Technology List (Everything Named Across This Project)

**Data ingestion/streaming:** Apache Kafka, Kafka Connect, MQTT (alt.), AWS Kinesis (alt.)

**Stream processing:** Apache Spark Structured Streaming, Apache Flink (alt.)

**Feature store:** Feast (Redis-backed online store), Delta Lake/S3 (offline store)

**ML/modeling:** Python, pandas, scikit-learn (Random Forest, Extra Trees), XGBoost, PyTorch (for GNN/TFT, production-stage only), H2O.ai AutoML (alt.) — *(LightGBM/CatBoost dropped from final tech list; RF/XGBoost/Extra Trees are the finalized Stage-2 model candidates)*

**Model serving:** FastAPI, MLflow (model registry), BentoML, TorchServe, Seldon Core (alt.)

**Orchestration/MLOps:** Apache Airflow, Kubeflow Pipelines, Prefect (alt.), Evidently AI / WhyLabs (drift monitoring)

**Time-series/storage:** TimescaleDB, InfluxDB (alt.), PostgreSQL, Redis, AWS S3/Athena or HDFS (data lake), BigQuery (alt.)

**Containers/infra:** Docker, Kubernetes, NIC Cloud/MeghRaj (govt data residency) or AWS/Azure India regions

**API/Gateway:** Kong, NGINX, AWS API Gateway (alt.)

**Auth:** OAuth2/JWT, Keycloak

**Frontend/dashboard:** React + Vite, D3.js/Recharts, Grafana, Streamlit (rapid-demo alt.), Leaflet/Mapbox (map viz)

**Mobile:** React Native, Flutter (alt.)

**Geographic/track data:** OpenStreetMap Overpass API, Geofabrik OSM extracts, `osmium` (local filtering), `networkx` (graph/shortest-path construction)

**Scraping/data collection infra:** cheap always-on VPS, scheduled cron/orchestrator with retries, raw-response-first storage (Parquet/Postgres), NTES reverse-engineered JSON endpoints (preferred over HTML scraping)

**Weather:** IMD (India Meteorological Department) API

**Deployment (this project's actual choice):** Hostinger (React/Vite static frontend), Render/Railway (FastAPI backend, free tier)

---

## PART 9 — Data Collection Plan Timeline (Sept → December)

| Phase | Weeks | Milestone |
|---|---|---|
| 0 | Week 1 | Legal/ToS check on all sources; find reverse-engineered NTES JSON endpoints (prefer over HTML scraping); confirm platform-number field availability at target junctions; lock 2-3 target corridors (e.g. Delhi-Mumbai via Kota, Delhi-Howrah Grand Chord) |
| 1 | Week 2 | VPS provisioned, scraper live, raw-storage schema running, monitoring/alerts wired |
| 2 | Weeks 3-4 | Monitoring proven stable; first weekly precedence-inference batch run; FIRST validation spot-check against enthusiast forums/news/RTI |
| 3 | Weeks 5-12 (Oct-Nov) | Continuous collection + weekly inference runs + periodic re-validation |
| 4 | Late Nov | Freeze data collection; finalize Model B training; run Model A vs B comparison |
| 5 | Early Dec | Finalize results; build finale presentation/demo |

**Team role split (2-4 people):** Scraper/infra owner (VPS, uptime, monitoring) · Data pipeline owner (reconciliation, precedence-inference algorithm) · Model owner (Model A now, Model B once features ready) · Validation/docs owner (spot-checks, CRIS/mentor request, pitch narrative)

**Parallel institutional track (start immediately, longest lead time):** faculty mentor/SPOC formally requests NTES/CRIS data access or API partnership — status: not yet identified, flagged as most urgent open action item.

---

## PART 10 — 30-Hour Hackathon/Prototype Build Plan (4-person team)

| Hours | Data/ML | Backend | Frontend | Integration/Docs |
|---|---|---|---|---|
| 0-4 | Join/clean 6 CSVs, feature table | Scaffold FastAPI, endpoint contracts | Scaffold React/Vite, layout skeleton | Draft problem-statement-to-feature mapping |
| 4-10 | Train baseline + RF/XGBoost/Extra Trees point model | Build `/predict` | Train-select UI, dummy data | Architecture diagram slide |
| 10-16 | Uncertainty (quantile/inter-tree variance), congestion proxy, SHAP | Build `/explain` | Wire real API, confidence-band UI | What-if scenario spec |
| 16-20 | Live-replay data generator | Build `/replay/{train_no}` | Live-replay view | Build fallback demo-fallback.json, test offline mode |
| 20-24 | Finalize model, record metrics | Deploy to Render/Railway | Polish styling, what-if UI | Deploy React to Hostinger, e2e test |
| 24-28 | Model card: features, MAE, CI coverage, limitations | Error handling, CORS, fallback logic | Finish both modes, responsive check | Slide deck: problem→data→architecture→results→future |
| 28-30 | Bug bash, all hands | Bug bash, all hands | Bug bash, all hands | Rehearse pitch, test offline fallback twice |

**Explicit SIH "Expected Solution" coverage check:**
- Live location → live-replay simulation
- Historical trends/network conditions → historical stats + congestion proxy feature
- Dynamic updates → replay recalculates ETA at each checkpoint
- ML/improve over time → LightGBM residual + documented retraining approach
- APIs for mobile/displays/dashboards → `/predict`, `/explain`, `/replay` endpoints
- Reliable/up-to-date info → confidence interval + explainability

**What to state explicitly as simplified (builds credibility, not weakness):** GNN → engineered congestion proxy; live GPS/COIS → historical replay simulation; live weather → static seasonal flag.

---

## PART 11 — Cost & Scalability Notes (Production)

- Biggest recurring cost: streaming infra (Kafka/Spark) at national scale → mitigate by batching updates (30-60s cadence, not per-second)
- GNN/deep model inference needs GPU only for batched, periodic inference — not per-request
- Boosted-tree (Stage 2) inference is CPU-only, negligible cost
- Storage: tiered — hot (Redis/Timescale) for recent, cold (S3/Glacier-equivalent) for archival
- Government data-sovereignty likely mandates NIC/MeghRaj cloud or on-prem — frame as capex on existing IR infra, not recurring commercial cloud spend
- **Key selling point for the pitch:** this is an analytics/ML layer on top of data IR already collects (COIS/NTES/GPS) — no new trackside sensor network required
- Scale for ~2,000-4,000 concurrently active trains (not all 13,000/day at once); per-zone model sharding isolates regional spikes (e.g. fog season in North doesn't degrade other zones)

---

## PART 12 — Open Action Items (Not Yet Resolved)

1. **Identify faculty mentor/SPOC** and send formal CRIS/NTES data-access request — highest priority, longest lead time
2. **Manually verify** platform-number field is actually present on target corridor's major junctions (30-min check)
3. **Manually verify** OSM tag completeness (`tracks=`, `electrified=`) on target corridor via overpass-turbo.eu before building the graph pipeline
4. **Decide final 2-3 target corridors** for focused data collection (candidates raised: Delhi-Mumbai via Kota, Delhi-Howrah Grand Chord)
5. **Line up 5-10 face-validity spot-checks** (enthusiast forums, news, or RTI) for precedence-inference validation — start this in weeks 3-4, not November
6. Confirm exact PPT (due before Sept 14) content scope — deferred by team, ideation-focused for now
7. **ML model development (RF/XGBoost/Extra Trees training, tuning, comparison) is owned by a separate team member** — this plan covers architecture/data/backend/deployment; not the model code itself
