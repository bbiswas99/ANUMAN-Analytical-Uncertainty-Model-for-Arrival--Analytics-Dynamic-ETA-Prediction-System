# 06 — Frontend / Dashboard Specification (React + Vite + Leaflet)

Function/component-level specs only (props, signature, behavior) — no implementation code, per project decision.

---

# 06 — Frontend / Dashboard Specification (React + Vite + Leaflet)

Function/component-level specs only (props, signature, behavior) — no implementation code, per project decision. Every component below is checked against the three required error states defined in `10_Error_Handling_and_Validation.md` §4 (Loading / Recoverable failure / Unrecoverable-invalid-input) — a component spec that doesn't define all three is incomplete.

---

## 1. Application Structure

Single-page app with three modes accessible from one dashboard view, plus an always-present map (per the decision that the map is core to the final prototype, not a stretch goal):
1. **Simple Dashboard** — pick a train, see current ETA + confidence band + explanation.
2. **Live-Replay** — pick a train + historical date, watch its journey replay on a simulated clock.
3. **What-If** — pick a train + a hypothetical scenario, see the recomputed ETA instantly.

All three share the same map component, which shows the train's position (real or replayed).

---

## 2. Components

### `<TrainSelector />`
**Props:** `onSelect: (trainNo: number) => void`
**Behavior:** Autocomplete/search input over the known train list (fetched once at app load from a static bundled list derived from `train_details.csv`, not a live API call). Emits the selected train number.
**Error states:**
| State | Behavior |
|---|---|
| Loading | Input is disabled with a subtle spinner until the bundled train list finishes loading |
| Recoverable failure | If the bundled list somehow fails to load (corrupt build asset), falls back to a plain numeric text input with the message "Train list unavailable — enter a train number directly" |
| Unrecoverable/invalid input | If the user types a number not present in the list, shows inline "No matching train found" rather than silently emitting an invalid `trainNo` upward — `onSelect` is never called with an unvalidated value |

### `<ETACard />`
**Props:** `trainNo: number`
**Behavior on mount/trainNo change:**
1. Calls `GET /predict?train_no={trainNo}`.
2. Displays `eta`, a confidence band (visualized as a shaded range between `confidence_interval_lower` and `confidence_interval_upper`), and `model_used` (shown subtly, e.g. "baseline estimate" vs "ML prediction", so a low-confidence fallback is visible to the user, not hidden).
3. On fetch failure or timeout (>5s): falls back to reading the bundled `demo-fallback.json` for this `trainNo`, and shows a small non-alarming indicator that this is cached/demo data.
**Function spec:**
```
fetchPrediction(trainNo: number): Promise<PredictionResponse>
  Wraps the /predict call with a timeout and the demo-fallback catch described above.
  Safety checks: validates trainNo is a positive integer BEFORE making the network
  call — an invalid value never reaches the API, it fails locally with the
  Unrecoverable state below. If the API returns one of the mapped error responses
  from 10 (404/422/500), the exact `message` field from that response is shown
  in the Unrecoverable state — never the raw HTTP status code or a generic
  "Something went wrong" with no explanation.
```
**Error states:**
| State | Behavior |
|---|---|
| Loading | A skeleton/placeholder card, not a blank space, shown for up to the 5s timeout |
| Recoverable failure | Falls back to `demo-fallback.json`; if `trainNo` isn't in the fallback set either, shows "Live prediction unavailable for this train right now" rather than a broken card |
| Unrecoverable/invalid input | If `trainNo` fails local validation, or the API returns 404 (`InvalidTrainNumberError`/`NoActiveJourneyError`), shows the API's mapped message inline (e.g. "Train {trainNo} has no active journey today") |

### `<ExplanationPanel />`
**Props:** `trainNo: number`
**Behavior:** Calls `GET /explain?train_no={trainNo}`, renders the returned `top_delay_factors` list as plain-language bullet points (e.g. "Likely factors: historical delays on this route, congestion at this section").
**Error states:**
| State | Behavior |
|---|---|
| Loading | Text placeholder ("Loading explanation…") |
| Recoverable failure | If `/explain` fails but `/predict` succeeded (via `<ETACard />`), shows "Detailed reasoning unavailable right now" rather than hiding the whole panel — the ETA itself is still shown elsewhere |
| Unrecoverable/invalid input | Same 404 handling as `<ETACard />`; if `top_delay_factors` returns fewer than 3 items (per `05`'s safety check), renders however many are present rather than showing empty bullet placeholders |

### `<LiveReplayControls />`
**Props:** `trainNo: number`, `date: string`
**Behavior:**
1. Calls `GET /replay?train_no={trainNo}&date={date}` once on mount.
2. Steps through the returned `stops` array on a simulated clock (configurable speed, default: 1 real second = several simulated minutes, tunable).
3. At each tick, computes the train's interpolated position via `snapPositionToRoute()` (below) and updates `<TrackMap />`.
4. Exposes play/pause/speed controls.
**Function spec:**
```
snapPositionToRoute(sectionGeometry: {lat,lon}[], progressRatio: number) -> {lat, lon}
  Arc-length-parameterized interpolation: walks the ordered coordinate array,
  computing cumulative distance at each point, and returns the point at
  progressRatio (0 to 1) of the TOTAL distance — not the point at that fractional
  INDEX in the array (points are not evenly spaced).
  progressRatio is computed as (elapsed_time_since_last_stop / scheduled_time_for_this_leg),
  clamped to [0, 1]. This is a DISPLAY-LAYER APPROXIMATION ONLY — it is never used
  as input to any prediction; see the master plan's explicit scope note on this technique.
  Safety checks: if sectionGeometry is empty or null (OSM match failed for this
  section, per 02 Step 4's OSMGeometryMismatchError path), returns null rather than
  throwing — the caller (<TrackMap />) must handle a null position by simply not
  rendering a marker for that leg, not crashing the whole map.
```
**Error states:**
| State | Behavior |
|---|---|
| Loading | Playback controls disabled with a loading indicator until `/replay` resolves |
| Recoverable failure | If `/replay` times out, retries once automatically before showing the Unrecoverable state — replay is a lower-urgency demo feature than live `/predict`, so a slightly longer retry tolerance is acceptable |
| Unrecoverable/invalid input | 404 (`NoActiveJourneyError` — "no recorded journey on this date") shown inline with a suggestion to pick a different date; playback controls remain disabled rather than attempting to play an empty sequence |

### `<WhatIfForm />`
**Props:** `trainNo: number`, `onResult: (result: PredictionResponse) => void`
**Behavior:** Lets the user set hypothetical override values for fields in the Feature Dictionary (`03`) that make sense to expose as user-editable — recommended minimal set: `reported_delay_min` (simulate "assume train is currently N minutes late"), `section_occupancy_count` (simulate "assume heavier congestion ahead"). On submit, calls `GET /predict?train_no={trainNo}&what_if={...}` and passes the result up.
**Safety checks:** input fields are constrained client-side to the same plausible ranges enforced server-side by `apply_what_if_overrides()` (`05`) — e.g. the delay input has a min/max on the number field itself — so an out-of-range value is caught before submission, not only after a round trip to the API. If the server still rejects it (`WhatIfOverrideInvalidError`, HTTP 422), the exact returned message is shown next to the offending field, not as a generic form-wide error.
**Error states:**
| State | Behavior |
|---|---|
| Loading | Submit button shows a spinner and is disabled to prevent duplicate submissions |
| Recoverable failure | If the request times out, the form re-enables and shows "Could not compute scenario — try again" without losing the user's entered values |
| Unrecoverable/invalid input | 422 response shown inline next to the specific invalid field |

### `<TrackMap />`
**Props:** `trainPosition: {lat, lon} | null`, `sectionGeometry: GeoJSON`, `delaySpikeMarkers: DelayMarker[]`
**Behavior:**
1. Renders the OSM-derived track geometry (bundled static JSON, from `section_geometry.parquet` exported at build time) as polylines using Leaflet.
2. Renders `trainPosition` as a moving marker.
3. Renders `delaySpikeMarkers` (Phase 2 feature — see `07`) as static markers near the nearest OSM junction, captioned exactly as **"Delay spike observed near this junction (interpolated)"** — never captioned as a confirmed cause, per the labeling-discipline decision made during this project.
**Note:** in Phase 1, `delaySpikeMarkers` is an empty array — this prop exists now so Phase 2 doesn't require a component rewrite.
**Error states:**
| State | Behavior |
|---|---|
| Loading | Map renders with the base track geometry immediately (it's bundled, always available) while `trainPosition` is still null — never blocks the whole map on live data |
| Recoverable failure | If `trainPosition` is null (per `snapPositionToRoute()`'s safety check above), the map simply shows no marker for that train rather than erroring |
| Unrecoverable/invalid input | If `sectionGeometry` itself is malformed/missing (corrupt bundled asset), the map shows a plain message "Track map unavailable" in place of the Leaflet canvas, rather than a broken/blank map area |

---

## 3. Fallback Behavior (mandatory, applies app-wide)

A bundled `demo-fallback.json` (built into the app at build time, containing precomputed predictions for a fixed demo train set) is the fallback for **every** API-calling component (`<ETACard />`, `<ExplanationPanel />`, `<LiveReplayControls />`) whenever the live backend is unreachable or times out. This must be tested explicitly (disconnect the network, confirm the dashboard still shows something sensible) before any demo.

**Global safety net:** wrap the entire application in a top-level React error boundary. If any component throws an unhandled exception (a bug, not one of the defined error states above), the error boundary shows a single friendly message ("Something went wrong — please refresh") instead of a blank white screen — this is the last line of defense, not a substitute for the per-component error states above.

---

## 4. State Management

No global state library required at this scale — React `useState`/`useContext` for the selected train number (shared across `<ETACard />`, `<ExplanationPanel />`, `<TrackMap />`) is sufficient. Do not introduce Redux or similar for this prototype.

---

## 5. Build/Deploy Note

`section_geometry.parquet` is exported once (not fetched live) to a static JSON file bundled into the frontend build, since track geometry rarely changes — see `08` for the exact export/build step. **Safety check at build time:** the build process should fail (not silently produce an empty bundle) if this export step produces zero sections — an empty map is a build-time bug to catch immediately, not a runtime surprise during a demo.
