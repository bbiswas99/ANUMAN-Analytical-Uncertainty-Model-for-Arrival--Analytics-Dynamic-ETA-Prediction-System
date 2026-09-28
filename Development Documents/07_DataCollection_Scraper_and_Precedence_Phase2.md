# 07 — Data Collection: Phase 1 Live-Tracking API Polling + Phase 2 Precedence-Inference (marked)

> **Terminology note:** live tracking is done by polling public / reverse-engineered JSON API endpoints, not by HTML scraping. Function and file names below still use the word "scraper" for continuity with earlier documents.

---

## PART A — PHASE 1: Scraper Infrastructure (build now)

This expands on `02` Step 1 with the operational/infrastructure detail needed to actually run it continuously.

### Deployment
- Runs on a small always-on VPS (not the DGX/Mac Studio — this is I/O-bound, not compute-bound).
- Scheduled via cron, polling interval 10-15 minutes per active train.
- Scope limited to 2-3 target corridors (not national) — corridor list is a config value, not hardcoded.

### Function specs (beyond what's in `02` Step 1)
```
load_active_corridor_config() -> list[str]
  Reads the configured target corridors (e.g. ["Delhi-Mumbai-Kota", "Delhi-Howrah-GrandChord"])
  from a simple config file. Changing corridors requires only a config edit, not a code change.
  Safety checks: raises ConfigurationError (FATAL, service refuses to start — see 10)
  if the config file is missing or produces an empty corridor list — an empty list
  must never be silently treated as "scrape nothing" without an explicit alert.

check_source_health(source_name: str) -> bool
  Verifies the source's endpoint responded successfully in the last N polling cycles.
  Used by the monitoring alert (below).
  Safety checks: if source_name is not a recognized configured source, raises
  ConfigurationError rather than returning a misleading False.

alert_on_scraper_failure(source_name: str, failure_count: int) -> None
  Sends a simple notification (email/Slack webhook) if a source has failed more than
  a threshold number of consecutive polls, OR if the daily row count for
  parsed_snapshots.parquet drops to zero. This is the "catch a broken scraper in
  week 3, not month 3" requirement from the master plan.
  Safety checks: the notification call itself is wrapped so that a failure to send
  the alert (e.g. webhook down) is logged locally and never crashes the scraper
  process — monitoring must degrade gracefully, not become a second point of failure.
```

### Storage
- Raw responses: `raw/{date}/train_{train_no}_{source_name}_{timestamp}.json` — never overwritten, never deleted automatically.
- Parsed/reconciled tables: Parquet files, per `02` Steps 2-3 schemas.

### Ethics/scope guardrails (hard requirements, not preferences)
- Never poll login-gated or PNR-requiring endpoints.
- Prefer reverse-engineered NTES JSON endpoints over HTML scraping where found (check the source's Network tab before writing an HTML parser).
- No IP rotation/proxy evasion — if a source throttles the scraper, slow down or drop that source, don't route around the throttle.

**Polling interval in Phase 1 is flat (10-15 min for every active train, regardless of activity).** See Part B below for the adaptive version, which is a Phase 2 enhancement — do not build it until Phase 1's flat-interval scraper is stable and validated.

---

## PART B — PHASE 2 ENHANCEMENT: Adaptive Polling Frequency (do not build until Phase 1 scraper is stable)

**Why this is deferred, not part of Phase 1:** the flat 10-15 minute interval is sufficient to prove the closed-loop prototype works end-to-end. Adaptive polling is an accuracy refinement — it doesn't change the pipeline's shape (`02` and `05`/`06` don't need to know the polling interval), so it can be added later purely inside the scraper without touching any other component. Building it now would add complexity before Phase 1 is even validated.

**What it does:** once a train's delay reading starts changing, poll it more frequently for a short window to capture the exact moment and magnitude of the change more precisely, then relax back to the flat interval once the reading stabilizes again.

**Function spec:**
```
adjust_polling_interval(train_no: int, recent_delay_readings: list[float],
                         base_interval_min: int = 12, fast_interval_min: int = 4,
                         change_threshold_min: float = 3.0) -> int
  Compares the most recent reading to the one before it. If the absolute
  difference exceeds change_threshold_min, returns fast_interval_min for this
  train's next poll. If the last 2-3 readings have been stable (below threshold),
  returns base_interval_min. This is evaluated per train, independently — one
  train speeding up its own polling never affects any other train's interval.
  Safety checks: if recent_delay_readings has fewer than 2 entries (train just
  started being tracked), returns base_interval_min rather than raising or
  comparing against a nonexistent prior reading. Clamps its own return value to
  never go below fast_interval_min or above base_interval_min regardless of input,
  so a bad threshold config can't accidentally produce a runaway polling rate.
```

**Integration point:** `get_active_trains()` (Part A) would call this once per cycle per train to decide its next poll time, rather than using a single fixed interval for every active train uniformly. No other function in this document changes.

---

## PART C — PHASE 2: Precedence-Inference Pipeline (DO NOT BUILD until the data-collection go/no-go checkpoint in the master plan has passed)

### Function specs
```
compute_delay_picked_up(reconciled_df: DataFrame, section_id: str) -> DataFrame
  For each train's crossing of the given section, computes
  delay_picked_up = delay_at_exit − delay_at_entry (using scheduled times, which
  already net out planned dwell — confirmed non-issue during project review).
  Safety checks: raises SchemaValidationError if reconciled_df lacks the columns
  this depends on. Rows where either entry or exit delay is missing produce a
  null delay_picked_up (excluded from downstream analysis) rather than a
  fabricated value from a partial reading.

baseline_against_own_history(train_no: int, section_id: str,
                              delay_picked_up_series: Series) -> tuple[float, float]
  Returns (mean, std) of this train's own historical delay_picked_up at this exact
  section — the per-train, per-section baseline used to flag anomalies, rather than
  a fixed absolute threshold.
  Safety checks: raises InsufficientDataError-equivalent behavior (returns
  (null, null), non-fatal) if fewer than 5 historical crossings exist for this
  exact (train_no, section_id) pair — too few points to establish a meaningful
  baseline, and this must be visibly distinguishable from "delay is always exactly
  average" rather than silently returning a baseline computed from 1-2 points.

systemic_cause_filter(section_id: str, date: str,
                       all_trains_delay_picked_up: dict[int, float]) -> bool
  Returns True (systemic cause, DISCARD as precedence candidate) if most/all trains
  crossing this section on this date show an anomalous delay_picked_up; returns
  False (proceed) if only one train is anomalous while others are normal.
  Section granularity must be the finest station-pair available, not a wide
  multi-station corridor — a coarse granularity will miss real systemic events.
  Safety checks: if all_trains_delay_picked_up contains only one train (no other
  trains crossed this section that day), returns False (cannot rule out systemic
  cause, but also cannot confirm it) and the calling pipeline must treat this as
  lower-confidence, not silently equivalent to "confirmed not systemic."

cross_reference_priority(delayed_train_no: int, section_id: str, date: str,
                          nearby_trains: list[int], train_details_df: DataFrame) -> int | None
  Returns the train_no of any higher-priority train (by type_code) present in/near
  the same section at the same time, or None if no such train is found.
  Safety checks: raises SchemaValidationError if any train_no in nearby_trains is
  absent from train_details_df — every train observed by the scraper must resolve
  to a known priority class, or the comparison is meaningless; an unresolvable
  train_no is logged and excluded from this comparison, not assumed lowest-priority
  by default.

require_repetition_confidence(delayed_train_no: int, priority_train_no: int,
                               section_id: str, all_observed_crossings: DataFrame,
                               min_occurrences: int = 6, min_total_crossings: int = 10) -> float
  Returns a confidence_score = (occurrences where the pattern held) / (total observed
  joint crossings). A single instance is NEVER trusted — this function is the gate
  that converts a coincidence into a defensible signal. Returns 0.0 if
  total_crossings < min_total_crossings (not enough data yet to judge).
  Safety checks: raises InsufficientDataError (non-fatal, per 10 — returns 0.0
  rather than propagating) explicitly rather than letting a division by
  total_crossings=0 raise an unhandled arithmetic error.

platform_deviation_signal(train_no: int, station_code: str,
                           observed_platform: str, historical_platform_mode: str) -> float
  Returns a confidence BOOST (not a penalty/filter) if observed_platform differs
  from this train's historical norm at this station — platform reassignment during
  congestion is a real operational pattern and corroborates a precedence event,
  per the project's explicit decision to treat this as signal, not noise.
  Safety checks: if historical_platform_mode is null (this train has never been
  observed at this station before), returns a neutral 0.0 boost rather than
  treating "no history" the same as "confirmed deviation."
```

### Output schema — `precedence_events.parquet`
| Column | Type | Description |
|---|---|---|
| `delayed_train_no` | int | |
| `priority_train_no` | int | |
| `section_id` | string | |
| `confidence_score` | float (0-1) | From `require_repetition_confidence`, optionally boosted by `platform_deviation_signal` |
| `first_observed_date` | date | |
| `last_observed_date` | date | |
| `total_crossings_observed` | int | |

### Feeding into Model B (see `04` Phase 2 section)
```
add_precedence_features(model_A_features_df: DataFrame,
                         precedence_events_df: DataFrame) -> DataFrame
  Left-joins precedence_events onto model_A_features by (train_no ≈ delayed_train_no,
  section_id, date near first/last_observed_date range), producing:
    precedence_risk_score_next_section = confidence_score for the upcoming section, or null
    historical_precedence_rate_vs_known_priority_trains = total_crossings_observed-weighted
      rate for this train/section pair, or null
  Returns model_A_features_df with these 2 columns appended = model_B_features.parquet.
  Safety checks: raises SchemaValidationError if model_A_features_df doesn't already
  contain all 45 Model A columns (03) — this function only ever adds to a complete
  Model A table, never operates on a partial one. Rows with no matching precedence
  event get null (not 0.0) for both new columns — null means "no known conflict
  data," which is a different, less certain state than a confirmed 0.0 risk score,
  and the model/serving layer must treat them differently (see 05's fallback rule).
```

### Validation requirement (human-in-the-loop, not automated)
Before trusting any output of this pipeline in a reported result: spot-check the top-confidence `precedence_events` rows against enthusiast forums, news coverage, or an RTI request, per the master plan's validation plan. This validation step is manual and does not feed back into the pipeline automatically.


---

## IMPLEMENTATION STATUS (audit-confirmed)

| Item | Status | Detail |
|---|---|---|
| Live API poller (Steps 1-3) | **Not built** | Only the consumer side exists (`backend/reconciled_reader.py`, with caching and staleness detection). Nothing yet generates `reconciled_positions.parquet`. Blocked on choosing and testing an actual API source (the RapidAPI hostname previously suggested did not verify; RailRadar.in is an unevaluated lead). |
| `require_repetition_confidence()` | **Defined, NOT wired — flagged in three consecutive audits** | The function exists in `precedence_engine.py`, but `run_precedence_pipeline()` still uses `if total_crossings >= 4: confidence = min(0.95, round(0.50 + total_crossings*0.05, 2))`. That formula depends only on how many times two trains crossed, not on how often the hold pattern actually occurred, so two pairs with identical crossing counts get the same confidence regardless of how consistently the pattern held. **Fix: replace the inline formula with a call to `require_repetition_confidence()` (6+ occurrences out of 10+ joint crossings), confirming that the grouped rows represent all joint crossings and not only hold-days; then regenerate `precedence_events.parquet` and `model_B_features.parquet`, re-train Model B, and re-run the evaluation.** |
| `platform_deviation_signal()` | Defined, not called | `platform_number` is 100% null in the historical data; becomes usable once live data provides platforms. |
| Multi-source reconciliation (`source_agreement_score`) | Not built (column is NaN) | Needs at least two live sources running together. |
| `adjust_polling_interval()` (Part B) | Not built | Phase 2 by design. |
| Precedence events (as generated today) | 189 events | Derived by back-testing the rules over one year of historical schedule/delay data (not from live-scraped data). Crossing counts per pair: min 4, median 8, mean 19.3, max 228; 148 of 189 pairs have >= 6 crossings, 83 have >= 10. |

**Congestion proxy discrepancy (belongs to `02` Step 6):** `section_occupancy_count` is currently computed as a per-day, per-section train count (`groupby(["date","section_id"]).transform("count")`), not the specified +/-30-minute self-join on scheduled time. Replacing it is a ~1-hour task, followed by regenerating both feature parquets.
