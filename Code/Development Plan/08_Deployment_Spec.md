# 08 — Deployment Specification

---

## 1. Backend (FastAPI → Render/Railway)

**Build requirements:**
- `requirements.txt` must pin exact versions of: `fastapi`, `uvicorn`, `pandas`, `scikit-learn`, `xgboost`, `numpy`.
- Entry point: a standard `uvicorn main:app` start command.
- Model artifact file(s) (`model_a.pkl`/`.json`, and `model_b.*` once Phase 2 exists) must be committed to the deployed repo or fetched from a storage bucket at startup — never trained at deploy time.

**Startup safety checks (all fatal — service must refuse to start on failure, per `10`):**
1. Every required environment variable below is present and non-empty → else `ConfigurationError`.
2. `MODEL_A_PATH` resolves to a loadable, compatible model artifact → else `ModelNotLoadedError` (see `05`'s `load_model()`).
3. `RECONCILED_DATA_PATH` is reachable (even if currently empty — an unreachable *path* is a config error, an empty *table* is a normal early-stage data state and not fatal).
4. `ALLOWED_ORIGINS` is non-empty and does not contain a bare wildcard `*` — a wildcard CORS origin in a deployed environment is treated as a configuration error to catch at startup, not a runtime security incident later.

**Required environment variables:**
| Variable | Purpose | Required? |
|---|---|---|
| `ALLOWED_ORIGINS` | CORS allowlist — must include the Hostinger frontend domain | Yes |
| `MODEL_A_PATH` | Path to the trained Model A artifact | Yes |
| `MODEL_B_PATH` | Path to Model B artifact (Phase 2 only; absent/null in Phase 1) | No (Phase 1) |
| `DATA_CONFIDENCE_THRESHOLD` | Fallback-to-baseline threshold, default `0.3` | No (has default) |
| `RECONCILED_DATA_PATH` | Path/connection string to `reconciled_positions.parquet`'s live store | Yes |

**Health check:** deployment platform should poll `GET /health` (see `05`) and restart the service if it stops returning `"status": "ok"`. A restart loop (3+ failed health checks in a row) should trigger the same alert channel as `alert_on_scraper_failure()` (`07`) — a backend that can't stay up is exactly as urgent as a broken scraper.

---

## 2. Frontend (React/Vite → Hostinger)

**Build command:** `npm run build` → produces static `dist/` folder.
**Deploy method:** upload `dist/` contents to Hostinger via its file manager or FTP/Git integration (Hostinger's Business/Cloud plan supports this for Node-built static output, per the team's confirmed plan type).
**Required build-time environment variable:**
| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | The deployed Render/Railway backend's public HTTPS URL |

**Build-time safety checks (the build should fail, not produce a broken deploy artifact):**
1. `VITE_API_BASE_URL` is set and is a valid HTTPS URL → else the build fails with an explicit error, rather than shipping a frontend that silently calls a blank/relative URL.
2. `section_geometry.json` export produces at least one section (per `06`, section 5's build-time check).
3. `demo-fallback.json` is present and contains at least one valid entry — a build with an empty or missing fallback file must fail, since the mandatory offline-fallback path (see section 3 below) would otherwise be silently broken.

**Static assets to bundle at build time (not fetched live):**
- `section_geometry.json` — exported once from `section_geometry.parquet` (see `06`, section 5)
- `demo-fallback.json` — precomputed predictions for the fixed demo train set (see `06`, section 3)
- Train list for `<TrainSelector />` — derived once from `train_details.csv`

---

## 3. Local Development / Testing

- Backend runnable locally on `localhost:8000` as the mandatory offline-fallback path for demo day (per the master plan's backup-plan requirement) — test this explicitly, including via a laptop hotspot, before any live demo.
- Frontend `.env.local` should point `VITE_API_BASE_URL` at `localhost:8000` for local testing, and the deployed Render URL for production builds.

---

## 4. Monitoring (minimum viable, Phase 1)

- `GET /health` polled by the hosting platform (see section 1).
- Scraper's `alert_on_scraper_failure()` (see `07`) as the data-pipeline-side monitoring.
- No dedicated observability stack (Grafana/Prometheus) required at prototype scale — that belongs to the production architecture described in the master plan, not this build.
- **All logged errors (per `10`'s "log with context" principle) should be written to a location the team can actually check before a demo** — even a simple log file reviewed manually the morning of a demo is sufficient at this scale; the requirement is that nothing fails silently and unobserved, not that it requires a dashboard.

---

## 5. Pre-Demo Checklist

1. Confirm `/health` returns `"status": "ok"` on the deployed backend.
2. Confirm the frontend loads and renders with the network disconnected (fallback path).
3. Confirm at least one full Live-Replay run completes without errors.
4. Confirm the local backup (`localhost:8000` + hotspot) starts successfully.
5. Confirm CORS is correctly scoped (not wildcarded) and the deployed frontend can actually reach the deployed backend.
6. **Deliberately trigger each error state at least once** — an invalid train number, a date with no recorded journey, an out-of-range what-if value — and confirm each shows its defined friendly message (per `10`/`06`), not a raw error or a blank screen.
7. Confirm the backend genuinely refuses to start when a required environment variable is deliberately unset (proves the fail-fast startup checks in section 1 actually work, rather than assuming they do).
