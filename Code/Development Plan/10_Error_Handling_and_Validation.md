# 10 — Error Handling and Validation Framework

This is the single source of truth for error handling across the whole system. Every function/endpoint spec in files `02`, `05`, `06`, `07`, `08` references the exceptions and principles defined here rather than inventing its own error format.

---

## 1. General Safety Principles (apply everywhere, no exceptions)

1. **Fail fast at startup, fail soft at runtime.** Configuration errors, missing model artifacts, or bad environment variables must stop the service from starting at all — never start in a half-working state. Once running, a single bad request or one missing data point must never crash the whole service — degrade to a fallback and keep serving everything else.
2. **Never expose internal details externally.** Stack traces, file paths, raw exception text, and internal variable names never reach the frontend or an API response. Every external-facing error is a clean, mapped message from the taxonomy below; full detail goes to the server-side log only.
3. **Validate at every trust boundary.** Any time data crosses from one system to another (scraper → parser, API request → backend, backend response → frontend, CSV → pipeline), validate shape and type before using it. Never assume an upstream payload is well-formed.
4. **Range-check every numeric feature before it reaches the model.** Physically impossible values (negative distances, delay in the tens of thousands of minutes, a percentage outside 0-100) must be caught, not silently fed into a prediction.
5. **Log with context, never swallow silently.** Every caught exception logs at minimum: timestamp, function name, the identifying key involved (train_no, section_id, etc.), and the exception type. A `try/except: pass` with no logging is never acceptable anywhere in this system.
6. **The frontend never shows a raw error to the user.** Every possible failure state has a defined friendly message and a fallback UI state — never a blank screen, a browser console-only error, or an unstyled stack trace.

---

## 2. Custom Exception Taxonomy

| Exception | Raised when | Fatal? | Example message |
|---|---|---|---|
| `InvalidTrainNumberError` | `train_no` doesn't exist in `train_details`/`combined_schedule` | No — returns a clean 404 | "Train {train_no} not found in the schedule database." |
| `NoActiveJourneyError` | `train_no` exists but has no scheduled journey for the requested date/time | No — returns a clean 404 | "Train {train_no} has no active journey for the requested date." |
| `StaleDataError` | Latest reconciled tracking row for a train is older than the staleness threshold (default 2 hours) | No — not an error state, a flag | "Live tracking data for train {train_no} is {age} old; showing last known state." |
| `SourceUnavailableError` | A scraper source fails to respond after its retry budget | No — logged, scraper continues with other sources | "Source '{source_name}' unreachable after 2 retries at {timestamp}." |
| `SchemaValidationError` | A row or file is missing a required column, or a column has the wrong type | Yes, for that pipeline run — halts and alerts rather than processing bad data | "Column '{column}' missing or wrong type in {file}; expected {expected_type}." |
| `ModelNotLoadedError` | A model artifact is missing or corrupt at service startup | **Yes — service refuses to start** | "Model artifact at {path} could not be loaded; service will not start." |
| `OutOfRangeFeatureError` | A computed feature value falls outside its plausible physical bounds | No — the row is flagged and the offending feature is nulled/clipped, not silently used | "Feature '{feature}' value {value} outside plausible range [{min},{max}] for train {train_no}." |
| `WhatIfOverrideInvalidError` | A what-if request contains an unrecognized field or an out-of-range hypothetical value | No — returns a clean 422 | "Invalid what-if override: '{field}' is not a recognized feature." or "Invalid what-if override: '{field}' value {value} is outside allowed range [{min},{max}]." |
| `OSMGeometryMismatchError` | The selected "expected route" path length deviates from the scheduled distance beyond tolerance (default 15%) | No — logged and flagged for manual review, section still usable with a lowered confidence | "Expected route for section {section_id} is {delta_km} km off the scheduled distance; flagged for review." |
| `InsufficientDataError` | Phase 2 only: fewer than the minimum required joint crossings to compute a precedence confidence score | No — returns a confidence score of 0.0, not a crash | "Only {n} joint crossings observed for ({train_a}, {train_b}, {section_id}); minimum {min_n} required — confidence set to 0." |
| `ConfigurationError` | A required environment variable or config value is missing/invalid at startup | **Yes — service refuses to start** | "Required environment variable '{var}' is not set." |

---

## 3. Standard API Error Response Shape

Every FastAPI error response (see `05`) uses this exact shape, regardless of which exception triggered it:
```json
{
  "error": true,
  "error_type": "InvalidTrainNumberError",
  "message": "Train 99999 not found in the schedule database.",
  "status_code": 404
}
```

**HTTP status code mapping:**
| Exception | Status |
|---|---|
| `InvalidTrainNumberError`, `NoActiveJourneyError` | 404 |
| `WhatIfOverrideInvalidError` | 422 |
| `ModelNotLoadedError`, `ConfigurationError` (if surfaced via `/health`) | 503 |
| Any unhandled/unexpected exception | 500, with message forced to the generic string `"An unexpected error occurred. Please try again."` — the real exception is logged server-side only, never returned |

---

## 4. Frontend Error-State Convention

Every component in `06` that can fail must define, at minimum, these three states — this table is the checklist each component's spec is validated against:
| State | User-visible behavior |
|---|---|
| **Loading** | A visible loading indicator, never a blank area |
| **Recoverable failure** (API down, timeout) | Falls back to `demo-fallback.json`, with a small non-alarming label (e.g. "showing cached data") |
| **Unrecoverable/invalid input** (bad train number typed, no journey today) | A plain-language inline message near the input, never a popup/alert box, using the mapped message from the taxonomy above — never the raw API error text |
