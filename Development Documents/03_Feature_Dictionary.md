# 03 — Feature Dictionary

Every column in `model_A_features.parquet` (see `02`, Step 6), fully defined. This is the single source of truth for what each feature means — no other document should be needed to understand the data.

| Column | Type | Definition | Range / Example | Notes |
|---|---|---|---|---|
| `train_no` | int | Indian Railways train number | e.g. 12301 | Join key throughout |
| `station_no` | int | This stop's sequence position on the train's route | 1, 2, 3… | Not a global station ID |
| `station_name` | string | Station code | "NDLS" | Misleadingly named in source files — it's a code, not a name |
| `station_full_name` | string | Human-readable station name | "New Delhi" | Display only, never used as a model feature directly (too high-cardinality; `station_zone` is the model-facing equivalent) |
| `station_zone` | categorical | One of 19 Indian Railways zones | "NR", "WR" | Used for zone-level model behavior and fallback priors |
| `date` | datetime | The journey date this record refers to | 2025-09-15 | |
| `distance_from_origin` | int (km) | Distance from the train's first station to this stop | 0–2500+ | |
| `arrival_day` | int | Day offset from departure day | 1, 2, 3… | Handles multi-day journeys |
| `arrival_time` | string (HH:MM) | Scheduled arrival at this stop | "14:32" | Displayed as `--:--` for the origin station |
| `departure_day` | int | | | |
| `departure_time` | string (HH:MM) | Scheduled departure from this stop | "14:37" | Displayed as `--:--` for the terminal station |
| `train_name` | string | Commercial train name | "Howrah Rajdhani Express" | |
| `type_code` | categorical | Train priority/class | PASS-TRAINS, EXP-TRAINS, SF-TRAINS, RAJ-TRAINS, SHT-TRAINS, GRB-TRAINS, T18-TRAINS, PRM-TRAINS | Direct proxy for `train_priority_class` used throughout project discussion |
| `is_special_train` | boolean | True if `train_name` contains "SPL" | | Special/festival trains behave differently; kept separate, not dropped |
| `reported_delay_min` | float (minutes) | Most recent reconciled delay reading for this train | Can be negative (early) | From live scraper, Step 3 |
| `platform_number` | string / null | Reported platform at last known station | "3" | Only available at major junctions; a deviation from a train's historical platform is treated as a corroborating signal in Phase 2, not noise |
| `source_agreement_score` | float (0-1) | How closely multiple scraped sources agreed on the last reading | 1.0 = perfect agreement | See `02` Step 3 |
| `data_confidence_score` | float (0-1) | Copy of `source_agreement_score`, exposed as the general-purpose confidence feature the model and API both reference | | Drives the "fall back to baseline when confidence is low" behavior |
| `section_id` | categorical | `{station_from}_{station_to}` identifier for the track segment this leg covers | "NDLS_GZB" | From OSM-derived geometry |
| `tracks` | int / null | Number of physical parallel tracks on this section, where OSM tag exists | 1, 2 | Null where OSM data incomplete — do not assume single-line by default |
| `electrified` | boolean / null | Whether this section is electrified | | |
| `usage` | categorical / null | OSM `usage` tag | "main", "branch" | Used as a junction tie-breaker when multiple candidate routes match the scheduled distance equally well |
| `expected_route_distance_km` | float | Total length of the OSM path selected as this section's "expected route" | | Should closely match `distance_from_origin` deltas; large mismatches indicate a bad OSM match and should be logged, not silently trusted |
| `section_occupancy_count` | int | Count of other trains scheduled through this same section within ±30 minutes of this train's scheduled time | 0, 1, 2… | The Phase 1 congestion proxy — stands in for the full network/GNN model described in the master plan |
| `hour_of_day_sin` / `hour_of_day_cos` | float | Cyclical encoding of the hour | | Never use raw hour integer — see master plan's encoding rule |
| `day_of_week_sin` / `day_of_week_cos` | float | Cyclical encoding of the day of week | | |
| `month` | int | Calendar month | 1–12 | |
| `is_fog_season_flag` | boolean | True if month is Dec/Jan/Feb | | Stand-in for real IMD weather integration |
| `stops_remaining_count` | int | Scheduled stops left on this train's route from here | | |
| `distance_remaining_total_km` | float | Distance left to final destination | | |
| `elapsed_journey_pct` | float (0-1) | Fraction of total scheduled distance already covered | | |
| `section_avg_delay_30d` | float (min) | Rolling 30-day average `delay` for this exact section | | |
| `section_avg_delay_90d` | float (min) | Rolling 90-day average | | |
| `section_avg_delay_365d` | float (min) | Rolling 365-day average | | |
| `train_number_avg_delay_30d` | float (min) | This specific train's own recent punctuality pattern | | |
| `zone_avg_punctuality_pct` | float (0-100) | Zone-level fallback prior | | Used for cold-start trains with little individual history |
| `delay_trend_last_3_points` | float | Slope of the last 3 delay readings for this train | Positive = worsening | |
| `recovery_margin_remaining_min` | float | Scheduled slack time built into the timetable between now and destination | | Derived from schedule padding |
| `baseline_delay_estimate` | float (min) | The naive "delay carries forward" estimate, adjusted by recovery margin | | This is the **Stage 1 baseline** referenced throughout the project |
| `baseline_eta` | datetime | Scheduled time + `baseline_delay_estimate` | | The fallback ETA shown when the ML layer is unavailable or low-confidence |
| `active_tsr_count_on_route` | int | Count of active temporary speed restrictions ahead | Always 0 in Phase 1 | Column exists now so Phase 2/production can populate it without a schema migration |
| `etrain_avg_delay` | float (min) | Historical average arrival delay for this train number at this station, from `etrain_delays.csv` (`average_delay_minutes`) | >= 0.0 | **Added beyond the original 45-column spec** during implementation; supplementary historical prior. Null where the train/station is not covered by that file |
| `etrain_pct_right_time` | float (0-100) | Percentage of historical runs arriving within the right-time threshold at this station, from `etrain_delays.csv` (`pct_right_time`) | 0.0 - 100.0 | **Added beyond the original spec**; supplementary historical prior |
| `delay` | float (min) | **Ground truth actual delay** at this station (from `combined_delay.csv`, outlier-capped) | | Not available at prediction time — training data only |
| `residual_target` | float (min) | `delay − baseline_delay_estimate` | | **The actual value Model A's Stage 2 tree ensemble is trained to predict** |

**Implemented column counts (audit-confirmed):** `model_A_features.parquet` = 47 columns (the 45 spec columns + `etrain_avg_delay` + `etrain_pct_right_time`); `model_B_features.parquet` = 49 columns (Model A's 47 + the precedence feature columns). The 4 OSM-derived section columns (`tracks`, `electrified`, `usage`, `expected_route_distance_km`) exist but are currently NaN until the section-geometry extraction (`02` Step 4) is run. `source_agreement_score` and `data_confidence_score` are currently NaN for all historical rows (no live API poller is populating them yet), and `platform_number` is 100% null in the historical data.

**Rule for any new feature added later:** it must be added to this table in the same turn it's added to the pipeline (`02`), with type, definition, and range/example filled in — no feature exists in this project without an entry here.
