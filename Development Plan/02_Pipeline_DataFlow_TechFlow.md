# 02 — Pipeline: Data Flow + Tech Flow (Phase 1)

Every step below states: **Technology**, **Function Specs** (signature + behavior, no implementation code per project decision), and the **FULL schema** of the table produced at that step — every column that exists in the file at that point, not just what was added. Schemas are cumulative on purpose so nothing has to be cross-referenced against an earlier step to know what a file contains.

---

## STEP 1 — Live Tracking (API Polling)

**Technology:** Python (`requests`) polling public / reverse-engineered JSON API endpoints (HTML scraping is deliberately avoided — it is fragile and higher-risk), scheduled via cron on an always-on host.

**Function specs:**
```
get_active_trains(schedule_df: DataFrame, corridor_list: list[str], as_of: datetime) -> list[int]
  Returns train numbers currently en route on the given corridors, based on scheduled
  departure/arrival windows in combined_schedule.csv.
  Safety checks: raises SchemaValidationError if schedule_df is missing any of its
  8 required columns (01, section 2.1). If corridor_list is empty, logs a warning
  and returns an empty list rather than raising — an empty corridor config is a
  configuration mistake to catch at startup (ConfigurationError, see 10), not here.

poll_train_source(train_no: int, source_name: str) -> dict | None
  Sends one HTTP request to the given source for the given train.
  Returns the raw parsed JSON/HTML response, or None on failure/timeout.
  Must not retry more than 2 times per call; must not touch any login/PNR-gated endpoint.
  Safety checks: on the 2nd consecutive failure for this source, raises
  SourceUnavailableError (non-fatal — logged, this source is skipped for this cycle,
  other sources/trains continue normally). Validates train_no is a positive integer
  before making the request; invalid input raises InvalidTrainNumberError rather than
  sending a malformed request.

save_raw_snapshot(train_no: int, source_name: str, timestamp: datetime, raw_response: dict) -> str
  Writes the raw response, unmodified, to raw/{date}/train_{train_no}_{source_name}_{timestamp}.json.
  Returns the file path written. Never parses or discards data at this step.
  Safety checks: if raw_response is None or empty, still writes an empty marker file
  (do not skip writing — a missing file must be distinguishable from "we never polled").
  If the disk write fails (permissions, full disk), raises and triggers
  alert_on_scraper_failure (07) rather than silently continuing.
```

**Output:** raw JSON files, one per (train, source, poll). No tabular schema yet — this is intentionally unstructured at this step.

**Goes to:** Step 2.

---

## STEP 2 — Parsing Raw Snapshots

**Technology:** Python (`pandas`, `json`).

**Function specs:**
```
parse_snapshot_file(filepath: str) -> dict
  Reads one raw JSON file and extracts the fixed field set below.
  Returns a flat dict ready to append as one row.
  Safety checks: if the file is missing, empty, or not valid JSON, raises
  SchemaValidationError and skips this snapshot (logged with the filepath) rather
  than crashing the batch — one bad file must never stop the rest from parsing.
  If a required field (train_no, poll_timestamp) is absent from the parsed JSON,
  the row is dropped and logged, never inserted with a null key.

append_parsed_row(row: dict, target_path: str = "parsed_snapshots.parquet") -> None
  Appends one parsed row to the growing parsed-snapshots table.
  Safety checks: validates row's keys exactly match the 6-column schema below
  before appending — raises SchemaValidationError on any mismatch rather than
  silently writing a misaligned row.
```

**Output schema — `parsed_snapshots.parquet` (full columns):**
| Column | Type | Description |
|---|---|---|
| `train_no` | int | |
| `source_name` | string | Which source this row came from (e.g. "NTES", "app_A") |
| `poll_timestamp` | datetime | When this snapshot was polled |
| `last_station_code` | string | Most recently reported station |
| `platform_number` | string / null | Where available |
| `reported_delay_min` | float | As reported by this one source |

**Goes to:** Step 3.

---

## STEP 3 — Multi-Source Reconciliation

**Technology:** Python (`pandas`).

**Function specs:**
```
reconcile_snapshots(parsed_df: DataFrame, time_tolerance_min: int = 5) -> DataFrame
  Groups parsed_snapshots.parquet by (train_no, poll_timestamp rounded to time_tolerance_min).
  For each group: if all sources' reported_delay_min are within a small tolerance of each
  other, take the value from the highest-polling-frequency source and set
  source_agreement_score high (>=0.85). If they disagree beyond tolerance, keep the
  highest-frequency source's value but set source_agreement_score low (<0.5).
  Returns one reconciled row per (train_no, rounded timestamp).
  Safety checks: a group with only one source present gets source_agreement_score
  set to a fixed neutral value (0.6, not 1.0 — single-source agreement with itself
  is not the same as true cross-source confirmation) rather than an undefined/null
  score. Raises OutOfRangeFeatureError (non-fatal, row flagged) if a reported delay
  falls outside [-60, 3000] minutes — treated as a corrupted reading, not fed forward
  as-is.
```

**Output schema — `reconciled_positions.parquet` (full columns):**
| Column | Type | Description |
|---|---|---|
| `train_no` | int | |
| `timestamp` | datetime | Rounded reconciliation timestamp |
| `last_station_code` | string | |
| `platform_number` | string / null | |
| `reported_delay_min` | float | Reconciled value |
| `source_agreement_score` | float (0-1) | Confidence in the reconciled value |

**Goes to:** Step 5 (joining) and, in Phase 2 only, the precedence-inference pipeline (`07`).

---

## STEP 4 — Static Reference Data Cleaning (runs once, parallel to Steps 1-3)

**Technology:** Python (`pandas` for CSVs; `osmium` + `networkx` for OSM).

**Function specs:**
```
clean_schedule(raw_df: DataFrame) -> DataFrame
  Type-casts all columns; leaves nulls at origin/terminal stations as-is (expected, not errors).
  Safety checks: raises SchemaValidationError if any of the 8 required source columns
  (01, section 2.1) is absent. A null in arrival_time/departure_time is only valid at
  the actual first/last station_no for that train_no — a null anywhere else raises
  SchemaValidationError rather than being silently accepted, since that indicates a
  genuine data problem, not an expected origin/terminal gap.

clean_delay(raw_df: DataFrame, outlier_percentile: float = 99.5) -> DataFrame
  Caps `delay` at the given percentile; parses `date`; drops rows with entirely
  missing `delay` only if not recoverable from etrain_delays.csv fallback.
  Safety checks: logs the exact count and percentage of rows capped and rows dropped
  on every run — a silent, unlogged data-loss step is not acceptable. Raises
  OutOfRangeFeatureError (non-fatal, row dropped) for any `delay` value that is
  non-numeric after parsing.

clean_train_details(raw_df: DataFrame) -> DataFrame
  Adds derived boolean column is_special_train = train_name contains "SPL".
  Safety checks: raises SchemaValidationError if `type_code` contains a value outside
  the 8 known categories (01, section 2.3) — an unrecognized category must be surfaced,
  not silently treated as a ninth valid class.

clean_station_names(raw_df: DataFrame) -> DataFrame
  Drops station_address (not used downstream).
  Safety checks: raises SchemaValidationError if `station_zone` contains a value
  outside the 19 known zones.

build_section_geometry(osm_extract_path: str, schedule_df: DataFrame) -> DataFrame
  Implemented in backend/pipeline/build_section_geometry.py, scoped to the 2-3 target
  corridors only. Filters the OSM extract (osmium) to railway=rail/station tags and
  EXCLUDES ways tagged service=yard or service=siding before building the networkx graph.
  Station matching prefers the OSM node's ref= tag (the IR station code) and only falls
  back to fuzzy name-matching when ref= is absent. For each consecutive
  (station_no, station_no+1) pair per train, finds the "expected route" — the candidate
  OSM path whose total length best matches distance_from_origin's delta for that leg —
  rather than pure shortest path. Ties between equally-matching candidates are broken by
  preferring usage=main ways over usage=branch/unspecified.
  Assigns distance_match_confidence: "high" (within 10% of scheduled distance),
  "medium" (within 25%), "low" (beyond 25%). The count of low-confidence sections is
  logged at the end of every run and those sections are flagged for manual review.
  NOTE: the frontend map renders ONLY from this locally-extracted geometry — there is no
  runtime dependency on any external map-tile provider (OpenRailwayMap, Google, etc.).
  Safety checks: raises OSMGeometryMismatchError (non-fatal, logged + flagged) when the
  best-matching candidate path's length differs from the scheduled distance by more
  than 15% — the section is still usable but downstream code must treat its geometry
  as lower-confidence. If station-name fuzzy-matching produces no OSM match at all for
  a given station code, the section_geometry row is written with null coordinates
  rather than being silently omitted, so the gap is visible in the output.
```

**Output schemas (four separate cleaned tables + one geometry table):**

`cleaned_schedule` — same 8 columns as source (`01`, section 2.1), type-cast only.

`cleaned_delay` — same 5 columns as source (`01`, section 2.2), `delay` capped.

`cleaned_train_details`:
| Column | Type |
|---|---|
| `train_no` | int |
| `train_name` | string |
| `type_code` | string |
| `is_special_train` | boolean (new) |

`cleaned_station_names`:
| Column | Type |
|---|---|
| `station_name` | string |
| `station_full_name` | string |
| `station_zone` | string |

`section_geometry.json` (also mirrored to parquet for pipeline joins):
| Column | Type | Description |
|---|---|---|
| `section_id` | string | `{station_from}_{station_to}` |
| `station_from` | string | |
| `station_to` | string | |
| `coordinates` (`ordered_coords` in parquet) | list[(float,float)] | Lat/lon points along the expected route — the shape `snapPositionToRoute` consumes |
| `tracks` | int / null | Single=1, double=2, etc., where OSM tag present |
| `electrified` | boolean / null | |
| `usage` | string / null | main/branch/siding |
| `expected_route_distance_km` | float | Should closely match the schedule's distance delta |
| `scheduled_distance_km` | float | Distance delta taken from combined_schedule.csv |
| `distance_match_confidence` | string | `high` / `medium` / `low` (see above) |

**Current implementation status (audit-confirmed):** the geometry extraction has NOT yet been run — the built prototype still draws straight station-to-station lines and sets `tracks`/`electrified`/`usage`/`expected_route_distance_km` to NaN in the feature tables. The specification above is the agreed fix.

**Goes to:** Step 5.

---

## STEP 5 — The Master Join

**Technology:** Python (`pandas`).

**Function specs:**
```
build_master_table(cleaned_schedule, cleaned_delay, cleaned_train_details,
                    cleaned_station_names, reconciled_positions, section_geometry) -> DataFrame
  Sequential left-joins:
    cleaned_schedule
      LEFT JOIN cleaned_delay ON (train_no, station_no)
      LEFT JOIN cleaned_train_details ON (train_no)
      LEFT JOIN cleaned_station_names ON (station_name)
      LEFT JOIN reconciled_positions ON (train_no, nearest timestamp to date)
      LEFT JOIN section_geometry ON section_id built from (station_name, next station_name)
  Rows with no matching reconciled_positions entry get null tracking fields
  (handled downstream as low data_confidence_score, not dropped).
  Safety checks: raises SchemaValidationError before joining if any input DataFrame
  is missing its expected columns (per 01/Step 4 schemas) — never join against a
  malformed table and produce silently-wrong results. Logs the row count before and
  after each join; a join that unexpectedly drops rows (should never happen with
  LEFT JOIN, but a bug could turn one into an inner join) must raise, not pass silently.
```

**Output schema — `master_joined_table.parquet` (full columns):**
| Column | Type | Source |
|---|---|---|
| `train_no` | int | schedule |
| `station_no` | int | schedule |
| `station_name` | string | schedule (code) |
| `station_full_name` | string | station_names |
| `station_zone` | string | station_names |
| `distance_from_origin` | int | schedule |
| `arrival_day` | int | schedule |
| `arrival_time` | string | schedule |
| `departure_day` | int | schedule |
| `departure_time` | string | schedule |
| `date` | string | delay |
| `delay` | float | delay (capped) |
| `train_name` | string | train_details |
| `type_code` | string | train_details |
| `is_special_train` | boolean | train_details |
| `reported_delay_min` | float | reconciled tracking |
| `platform_number` | string / null | reconciled tracking |
| `source_agreement_score` | float | reconciled tracking |
| `section_id` | string | section_geometry |
| `tracks` | int / null | section_geometry |
| `electrified` | boolean / null | section_geometry |
| `usage` | string / null | section_geometry |
| `expected_route_distance_km` | float | section_geometry |

**Goes to:** Step 6.

---

## STEP 6 — Feature Engineering

**Technology:** Python (`pandas`, `numpy`).

**Function specs:**
```
add_temporal_features(df) -> DataFrame
  hour_of_day_sin/cos, day_of_week_sin/cos from `date`; month; is_fog_season_flag
  (True if month in [12,1,2]).
  Safety checks: raises SchemaValidationError if `date` fails to parse for any row
  (never silently coerce an unparseable date to a default like 1970-01-01, which
  would corrupt every downstream cyclical feature for that row).

add_journey_progress_features(df) -> DataFrame
  stops_remaining_count (max station_no for this train_no − current station_no),
  distance_remaining_total_km (max distance_from_origin − current),
  elapsed_journey_pct (current distance_from_origin / max distance_from_origin).
  Safety checks: raises OutOfRangeFeatureError (non-fatal, row flagged) if
  elapsed_journey_pct falls outside [0, 1] — indicates a corrupted distance value
  upstream. Guards the division by max distance_from_origin against a zero value
  (single-station edge case) by returning null rather than raising a division error.

add_historical_features(df) -> DataFrame
  section_avg_delay_30d/90d/365d (rolling mean of `delay` grouped by section_id,
  windowed by `date`); train_number_avg_delay_30d (grouped by train_no);
  zone_avg_punctuality_pct (grouped by station_zone);
  delay_trend_last_3_points (slope of the last 3 delay readings for this train_no).
  Safety checks: when fewer than 3 historical points exist for a train (cold start),
  delay_trend_last_3_points is set to null, never computed from fewer points and
  presented as if it were a full 3-point trend. Rolling averages with zero
  observations in the window return null, not zero — a section with no history is
  not the same as a section with a confirmed zero average delay.

add_congestion_proxy(df, schedule_df) -> DataFrame
  section_occupancy_count = count of OTHER train_no values whose scheduled
  arrival/departure at the same section falls within ±30 minutes of this row's
  scheduled time (self-join on cleaned_schedule, filtered by section_id and time window).
  Safety checks: raises SchemaValidationError if schedule_df lacks section_id
  (i.e., section_geometry wasn't joined before this step runs) — this function must
  never run against an incomplete master table.

add_baseline_and_target(df) -> DataFrame
  baseline_delay_estimate = reported_delay_min (carried forward as the naive
  "delay stays constant" baseline) + recovery_margin_remaining_min adjustment.
  recovery_margin_remaining_min = scheduled slack time between now and destination
  (derived from schedule padding — difference between cumulative scheduled running
  time and cumulative minimum historical running time for the same distance).
  baseline_eta = departure_time/arrival_time + baseline_delay_estimate.
  residual_target = delay − baseline_delay_estimate   [THIS IS THE MODEL A TRAINING LABEL]
  Safety checks: raises OutOfRangeFeatureError (non-fatal, row excluded from training
  set but kept for serving) if `residual_target` has an absolute value greater than
  2000 minutes — almost certainly a data artifact, not a real residual, and must not
  silently poison model training the way the uncapped 7,018-minute outlier did
  before this project's original outlier-capping decision.

add_data_confidence(df) -> DataFrame
  data_confidence_score = source_agreement_score, carried through unchanged
  (renamed for feature-table clarity).
  Safety checks: raises SchemaValidationError if source_agreement_score is absent
  from the input (indicates Step 3/5 was skipped or misconfigured upstream).

add_tsr_placeholder(df) -> DataFrame
  active_tsr_count_on_route = 0 for all rows in Phase 1 (TSR parsing not yet built;
  column exists so Phase-2/production can populate it without a schema change).
  Safety checks: none beyond confirming the column doesn't already exist with
  different values — if it does, this indicates Phase 2's real TSR parser is
  already wired in and this placeholder function must not silently overwrite it.
```

**Output schema — `model_A_features.parquet` (FULL final columns — this is what Model A actually trains and predicts on):**

| # | Column | Type | Category |
|---|---|---|---|
| 1 | `train_no` | int | identifier |
| 2 | `station_no` | int | identifier |
| 3 | `station_name` | string | identifier |
| 4 | `station_full_name` | string | identifier |
| 5 | `station_zone` | string (categorical) | identifier |
| 6 | `date` | datetime | identifier |
| 7 | `distance_from_origin` | int | schedule |
| 8 | `arrival_day` | int | schedule |
| 9 | `arrival_time` | string | schedule |
| 10 | `departure_day` | int | schedule |
| 11 | `departure_time` | string | schedule |
| 12 | `train_name` | string | train |
| 13 | `type_code` | string (categorical) | train |
| 14 | `is_special_train` | boolean | train |
| 15 | `reported_delay_min` | float | live tracking |
| 16 | `platform_number` | string / null | live tracking |
| 17 | `source_agreement_score` | float | live tracking |
| 18 | `data_confidence_score` | float | derived |
| 19 | `section_id` | string (categorical) | section |
| 20 | `tracks` | int / null | section |
| 21 | `electrified` | boolean / null | section |
| 22 | `usage` | string / null | section |
| 23 | `expected_route_distance_km` | float | section |
| 24 | `section_occupancy_count` | int | congestion proxy |
| 25 | `hour_of_day_sin` | float | temporal |
| 26 | `hour_of_day_cos` | float | temporal |
| 27 | `day_of_week_sin` | float | temporal |
| 28 | `day_of_week_cos` | float | temporal |
| 29 | `month` | int | temporal |
| 30 | `is_fog_season_flag` | boolean | temporal |
| 31 | `stops_remaining_count` | int | journey progress |
| 32 | `distance_remaining_total_km` | float | journey progress |
| 33 | `elapsed_journey_pct` | float | journey progress |
| 34 | `section_avg_delay_30d` | float | historical |
| 35 | `section_avg_delay_90d` | float | historical |
| 36 | `section_avg_delay_365d` | float | historical |
| 37 | `train_number_avg_delay_30d` | float | historical |
| 38 | `zone_avg_punctuality_pct` | float | historical |
| 39 | `delay_trend_last_3_points` | float | historical |
| 40 | `recovery_margin_remaining_min` | float | baseline |
| 41 | `baseline_delay_estimate` | float | baseline |
| 42 | `baseline_eta` | datetime | baseline |
| 43 | `active_tsr_count_on_route` | int | placeholder (always 0 in Phase 1) |
| 44 | `delay` | float | **ground truth (actual)** |
| 45 | `residual_target` | float | **TRAINING LABEL for Model A Stage 2** |

**Goes to:** `04_ML_Model_Spec.md` (Model A training) directly. In Phase 2 only, also goes to the precedence-feature join described in `07`, producing `model_B_features.parquet` (= this exact table + 2 additional columns, see `07`).

---

## STEP 7 — Live Single-Train Feature Computation (serving time)

**Technology:** Python, inside the FastAPI process (see `05`).

**Function specs:**
```
compute_live_features(train_no: int, current_time: datetime,
                       static_tables: dict, latest_reconciled_row: dict) -> dict
  Recomputes exactly the Step 6 logic (add_temporal_features through
  add_tsr_placeholder) for a SINGLE train's current situation, using the latest
  reconciled tracking row instead of historical rows.
  Returns a dict with the same 43 input columns as model_A_features.parquet,
  EXCLUDING `delay` and `residual_target` (unknown at prediction time).
  Safety checks: raises InvalidTrainNumberError if train_no is not present in
  static_tables' schedule. Raises NoActiveJourneyError if train_no exists but has
  no scheduled stop at or after current_time today. If latest_reconciled_row is
  None, proceeds with data_confidence_score forced to 0.0 (never raises — this is
  the expected, handled path that triggers the API's baseline-only fallback, not
  an error condition).
```

**Output schema:** identical to `model_A_features.parquet` columns 1–43 (identifiers through `active_tsr_count_on_route`), for exactly one train at one point in time. This single-row feature vector is what gets passed into the trained model at prediction time.

**Goes to:** `05_Backend_API_Spec.md`'s `/predict` endpoint.
