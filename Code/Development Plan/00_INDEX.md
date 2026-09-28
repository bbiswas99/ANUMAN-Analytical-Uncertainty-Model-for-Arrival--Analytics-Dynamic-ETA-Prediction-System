# Dynamic ETA Prediction System — Final Prototype Build Specification
### Team SteamX · PS 26028 · Master Index

---

## 0. Purpose of This Document Set

This is the **definitive build reference** for the final prototype. It is written so an AI coding agent (or any developer) can build the system section by section without needing to ask what a function should do, what a file's schema is at any pipeline stage, or how a component should behave. Every section defines **inputs, outputs, and behavior** — not narrative explanation.

**Two build phases, clearly separated throughout every document in this set:**
- **PHASE 1 (build now):** everything using data we already have or can collect immediately — the real CSV files, live public train-tracking scraping, OSM track geometry, the baseline + Model A (Random Forest / XGBoost / Extra Trees), the full API, and the full dashboard (including the map). This is a complete, closed-loop, demonstrable system on its own.
- **PHASE 2 (build later, marked explicitly wherever it appears):** the precedence-inference pipeline and Model B, which depend on months of scraped data (per the September→December collection timeline). Do not build Phase 2 components until Phase 1 is complete and the data collection go/no-go checkpoint has passed.

Wherever this document set contradicts the original SIH problem statement's exact wording, **what we decided in this project takes precedence** — the problem statement is the origin of the requirement, not a constraint on implementation choices already made.

---

## 1. File Index

| # | File | Contents |
|---|---|---|
| 00 | `00_INDEX.md` (this file) | Purpose, build order, PS coverage matrix |
| 01 | `01_Architecture_and_Sources.md` | System architecture diagram; every data source with full description |
| 02 | `02_Pipeline_DataFlow_TechFlow.md` | Step-by-step pipeline: technology, function specs, and **full CSV schema at every step** |
| 03 | `03_Feature_Dictionary.md` | Every feature/column in the final model-ready table, defined |
| 04 | `04_ML_Model_Spec.md` | Model A specification (Phase 1) + Model B specification (Phase 2, marked) |
| 05 | `05_Backend_API_Spec.md` | Every FastAPI endpoint + every internal function, signatures and behavior |
| 06 | `06_Frontend_Dashboard_Spec.md` | Every dashboard screen/component/mode, behavior and API contracts |
| 07 | `07_DataCollection_Scraper_and_Precedence_Phase2.md` | Phase 1 scraper function specs; Phase 2 adaptive-polling enhancement and precedence-inference specs (marked) |
| 08 | `08_Deployment_Spec.md` | Exact deployment steps, environment variables, build commands |
| 09 | `09_Glossary_and_Appendix.md` | Glossary of every term; synthetic-dataset appendix; open action items |
| 10 | `10_Error_Handling_and_Validation.md` | Custom exception taxonomy, safety-check principles, and standard error formats referenced by every function/endpoint/component across `02`, `05`, `06`, `07`, `08` |

**Related prior documents** (referenced, not duplicated, throughout this set): `IR_ETA_Prediction_Project_Master_Plan.md`, `IR_ETA_Data_Flow_Analysis.md`, `IR_ETA_Prototype_Technical_Flow.md`, `SIH_Dynamic_ETA_Deck.pptx`.

**Visual diagrams:** `diagrams/` contains 8 flowchart images (system architecture, pipeline detail, ML model spec, backend API flow, frontend component flow, scraper + Phase 2 adaptive polling, deployment, glossary/appendix) — visual companions to the text specs above, covering files `01` through `09`. Cross-check against the text spec if a diagram and its source file ever appear to disagree; the markdown files are authoritative.

---

## 2. Recommended Build Order

1. `01` (understand sources) → 2. **`10` (read the error-handling framework once, before writing any function — every subsequent file assumes it)** → 3. `02` (build the data pipeline, Phase 1 steps only) → 4. `03` (lock the feature dictionary) → 5. `04` Model A section (hand to ML teammate) → 6. `05` (build backend once features + model artifact exist) → 7. `06` (build frontend against backend contracts) → 8. `07` Phase 1 scraper section (can be built in parallel with steps 3-7, since it only feeds Step 2 of the pipeline) → 9. `08` (deploy) → 10. Revisit `04`/`07` Phase 2 sections only once scraped data volume clears the go/no-go checkpoint in the master plan.

---

## 3. Problem Statement Coverage Matrix (Closed-Loop Proof)

Every clause of the original SIH problem statement, mapped to the exact section of this document set that satisfies it. This table is the closed-loop proof that nothing in the PS is left unaddressed.

| PS Requirement (verbatim clause) | Satisfied by |
|---|---|
| "ETA... using static schedules, current delays and in-built recovery times... may not reflect real-time ground realities" | `02` Step 1-3 (live tracking replaces static-only input); `04` Stage 1 baseline explicitly defined as the static component being improved upon |
| "speed restrictions, congestion, unscheduled stoppages or historical patterns" | `03` Feature Dictionary: `active_tsr_count_on_route`, `section_occupancy_count` (congestion proxy), `delay_trend_last_3_points` (stoppage signal), `section_avg_delay_30d/90d/365d` (historical patterns) |
| "passengers, station staff, and downstream logistics services face uncertainty" | `06` Dashboard (passenger-facing) + `05` `/explain` endpoint (staff-facing reasoning) + confidence intervals throughout `04` |
| "real-time data feeds... GPS-based location data, signal aspects, average sectional running times, weather conditions, historical delay patterns, congestion levels on downstream tracks" | `07` Phase 1 scraper (GPS-proxy location); `01` OSM source (sectional geometry/running distances); weather named as not-yet-built in `01` (static seasonal flag used instead, documented honestly); `03` historical + congestion features |
| "scalable to cover thousands of trains simultaneously... adaptable to... diverse operational zones" | `05` API designed stateless/per-request (horizontally scalable); `03` `station_zone` feature; scaling path documented in `08` and cross-referenced to the master plan's production architecture |
| "account for temporal and spatial variability... continuously refine its predictions using machine learning" | `03` cyclical temporal features + `section_id` spatial features; `04` nightly retraining loop defined |
| "dynamically update ETAs in response to real-time events and delays" | `06` Live-Replay mode recomputes ETA at every simulated checkpoint; `05` `/predict` always reflects latest scraped position |
| "Machine learning or statistical forecasting techniques... improve accuracy over time" | `04` full retraining/feedback loop specification |
| "APIs for integration with mobile apps, station displays, and control room dashboards" | `05` full API spec — endpoints are channel-agnostic, consumable by any client |
| "reliable, up-to-date information to support decision-making and planning" | `04` confidence intervals + `05` `/explain` (SHAP/feature-importance reasoning) |

**Explicitly out of scope for Phase 1** (named honestly, not hidden): true signal-aspect data, real weather API integration, real CRIS/ISRO GPS feed, network/GNN-based congestion modeling. Each has a documented stand-in (scraped tracking + OSM interpolation, static seasonal flag, single swappable data-source slot, engineered congestion proxy respectively) — see `01` and the master plan's "swap point" section for the exact production upgrade path.
