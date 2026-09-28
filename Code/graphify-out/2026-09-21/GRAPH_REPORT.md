# Graph Report - Code  (2026-09-21)

## Corpus Check
- 82 files · ~2,251,987 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 19 file(s) not represented in the graph (top: .css 13, (none) 4, .example 1)

## Summary
- 675 nodes · 884 edges · 51 communities (41 shown, 10 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 21 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- precedence_engine.py
- OpsView.jsx
- package.json
- Indian Railways Dynamic ETA Prediction — Master Project Plan
- What You Must Do When Invoked
- 3. Step-by-Step Implementation Record
- build_features.py
- extract_section_geometry
- train_model.py
- 2. Data Sources — Full Descriptions and Schemas
- PHASE 1 — Model A
- 2. Components
- PART A — PHASE 1: Scraper Infrastructure (build now)
- TrainETA Backend
- Prototype Technical Flow — Exact Technology + Data Transformation at Every Step
- 1. Endpoints
- graphify reference: extra exports and benchmark
- Ponytail
- 02 — Pipeline: Data Flow + Tech Flow (Phase 1)
- Ponytail Help
- Dynamic ETA Prediction System — Final Prototype Build Specification
- 08 — Deployment Specification
- graphify reference: query, path, explain
- 09 — Glossary and Appendix
- .oxlintrc.json
- ponytail-audit/SKILL.md
- Ponytail Gain
- ponytail-review/SKILL.md
- graphify reference: add a URL and watch a folder
- graphify reference: commit hook and native CLAUDE.md integration
- graphify reference: incremental update and cluster-only
- ponytail-debt/SKILL.md
- adaptive_polling.py
- generate_empirical_accuracy.py
- React + Vite
- graphify reference: GitHub clone and cross-repo merge
- graphify reference: transcribe video and audio
- main
- rules/graphify.md
- ponytail.md
- extraction-spec.md
- workflows/graphify.md
- 03_Feature_Dictionary.md
- errors.py
- train_model_b.py
- Full Data Flow Analysis — Indian Railways ETA Prediction System
- TrainETA: Dynamic Train ETA Prediction System for Indian Railways
- 10 — Error Handling and Validation Framework
- main.py

## God Nodes (most connected - your core abstractions)
1. `main()` - 21 edges
2. `TrainETAError` - 18 edges
3. `predict()` - 15 edges
4. `3. Step-by-Step Implementation Record` - 15 edges
5. `Prototype Technical Flow — Exact Technology + Data Transformation at Every Step` - 15 edges
6. `react` - 14 edges
7. `Full Data Flow Analysis — Indian Railways ETA Prediction System` - 14 edges
8. `Indian Railways Dynamic ETA Prediction — Master Project Plan` - 14 edges
9. `What You Must Do When Invoked` - 12 edges
10. `TrainETA: Dynamic Train ETA Prediction System for Indian Railways` - 12 edges

## Surprising Connections (you probably didn't know these)
- `replay()` --uses--> `NoActiveJourneyError`  [INFERRED]
  backend/main.py → backend/errors.py
- `startup_check_and_load_model()` --uses--> `ConfigurationError`  [INFERRED]
  backend/main.py → backend/errors.py
- `explain()` --uses--> `InvalidTrainNumberError`  [INFERRED]
  backend/main.py → backend/errors.py
- `precedence()` --uses--> `InvalidTrainNumberError`  [INFERRED]
  backend/main.py → backend/errors.py
- `predict()` --uses--> `InvalidTrainNumberError`  [INFERRED]
  backend/main.py → backend/errors.py

## Import Cycles
- None detected.

## Communities (51 total, 10 thin omitted)

### Community 0 - "precedence_engine.py"
Cohesion: 0.11
Nodes (24): Row or file missing required column or wrong type. Fatal for pipeline run., SchemaValidationError, add_precedence_features(), baseline_against_own_history(), compute_delay_picked_up(), cross_reference_priority(), get_priority_rank(), platform_deviation_signal() (+16 more)

### Community 1 - "OpsView.jsx"
Cohesion: 0.05
Nodes (52): App(), TABS, ConfidenceBar(), ErrorBoundary, ETACard(), ExplanationPanel(), LiveReplayControls(), handlePlayPause() (+44 more)

### Community 2 - "package.json"
Cohesion: 0.07
Nodes (26): dependencies, leaflet, react, react-dom, react-leaflet, devDependencies, oxlint, @types/react (+18 more)

### Community 3 - "Indian Railways Dynamic ETA Prediction — Master Project Plan"
Cohesion: 0.07
Nodes (27): Consolidated from full planning discussion — SIH Submission, Explicit risk mitigation & framing for judges:, Four-stage hybrid pipeline (within each model):, Full production architecture (data flow):, Indian Railways Dynamic ETA Prediction — Master Project Plan, Multi-source cross-validation design:, PART 10 — 30-Hour Hackathon/Prototype Build Plan (4-person team), PART 11 — Cost & Scalability Notes (Production) (+19 more)

### Community 4 - "What You Must Do When Invoked"
Cohesion: 0.07
Nodes (26): For /graphify add and --watch, For /graphify query, For the commit hook and native CLAUDE.md integration, For --update and --cluster-only, /graphify, Honesty Rules, Interpreter guard for subcommands, Part A - Structural extraction for code files (+18 more)

### Community 5 - "3. Step-by-Step Implementation Record"
Cohesion: 0.07
Nodes (26): 1. Executive Summary & Problem Context, 2. Architecture Overview & Technology Stack, 3. Step-by-Step Implementation Record, 4. File & Asset Registry, 5. Data Dictionary & Interface Schemas, 6. Roadmap & Pending Milestones, 7. Metric & Visual Artifact Veracity Disclosure, Prediction Response Schema (`/predict` & Dynamic Baseline) (+18 more)

### Community 6 - "build_features.py"
Cohesion: 0.15
Nodes (23): add_stub_features(), build_baseline(), build_delay_trend(), build_journey_features(), build_recovery_margin(), build_rolling_delay_features(), build_section_id(), build_section_occupancy() (+15 more)

### Community 7 - "extract_section_geometry"
Cohesion: 0.16
Nodes (17): build_track_graph(), extract_section_geometry(), find_expected_route(), haversine_km(), main(), match_stations_to_graph(), DataFrame, Path (+9 more)

### Community 8 - "train_model.py"
Cohesion: 0.29
Nodes (10): chronological_split(), encode_categoricals(), evaluate(), load_and_prepare(), main(), # NOTE: 'date' is intentionally NOT here -- kept for chronological_split(),, Split by date, oldest 80% → train, newest 20% → test., Frequency + label encode categoricals. Save mapping for inference. (+2 more)

### Community 9 - "2. Data Sources — Full Descriptions and Schemas"
Cohesion: 0.14
Nodes (13): 01 — Architecture Overview and Data Sources, 1. System Architecture (Phase 1, the closed-loop prototype), 2.10 Excluded from the pipeline entirely (documented decision, not an oversight), 2.1 `combined_schedule.csv` (already have — Phase 1), 2.2 `combined_delay.csv` (already have — Phase 1), 2.3 `train_details.csv` (already have — Phase 1), 2.4 `station_full_names.csv` (already have — Phase 1), 2.5 `etrain_delays.csv` (already have — Phase 1, supplementary) (+5 more)

### Community 10 - "PHASE 1 — Model A"
Cohesion: 0.14
Nodes (13): 04 — ML Model Specification, Evaluation metrics (required, report all of these), Explainability, PHASE 1 — Model A, PHASE 2 — Model B (do not build until the data-collection go/no-go checkpoint passes), Required comparison methodology (this is the actual deliverable of Phase 2, not just "a better model"), Retraining, Serving fallback requirement (+5 more)

### Community 11 - "2. Components"
Cohesion: 0.14
Nodes (13): 06 — Frontend / Dashboard Specification (React + Vite + Leaflet), 06 — Frontend / Dashboard Specification (React + Vite + Leaflet), 1. Application Structure, 2. Components, 3. Fallback Behavior (mandatory, applies app-wide), 4. State Management, 5. Build/Deploy Note, `<ETACard />` (+5 more)

### Community 12 - "PART A — PHASE 1: Scraper Infrastructure (build now)"
Cohesion: 0.15
Nodes (12): 07 — Data Collection: Phase 1 Scraper Infrastructure + Phase 2 Precedence-Inference (marked), Deployment, Ethics/scope guardrails (hard requirements, not preferences), Feeding into Model B (see `04` Phase 2 section), Function specs, Function specs (beyond what's in `02` Step 1), Output schema — `precedence_events.parquet`, PART A — PHASE 1: Scraper Infrastructure (build now) (+4 more)

### Community 13 - "TrainETA Backend"
Cohesion: 0.17
Nodes (11): API Endpoints, Environment Variables, Error Response Shape, File Structure, How it works, How to generate the file (example, on the scraper machine), Optional Columns (used if present, silently ignored if absent), Quick Start (+3 more)

### Community 14 - "Prototype Technical Flow — Exact Technology + Data Transformation at Every Step"
Cohesion: 0.12
Nodes (15): Full Concrete Walkthrough (One Train, One Request), Prototype Technical Flow — Exact Technology + Data Transformation at Every Step, STEP 10 — Frontend (React + Vite, on Hostinger), STEP 11 — Deployment Mechanics, STEP 1 — Data Collection (Scraper), STEP 2 — Parsing Raw Snapshots, STEP 3 — Multi-Source Reconciliation, STEP 4 — Static Reference Data Preparation (runs once, in parallel with Steps 1–3) (+7 more)

### Community 15 - "1. Endpoints"
Cohesion: 0.17
Nodes (11): 05 — Backend API Specification (FastAPI), 05 — Backend API Specification (FastAPI), 1. Endpoints, 2. Internal Functions, 3. Cross-Cutting Requirements, `GET /explain`, `GET /health`, `GET /precedence` (+3 more)

### Community 16 - "graphify reference: extra exports and benchmark"
Cohesion: 0.22
Nodes (8): graphify reference: extra exports and benchmark, Step 6b - Wiki (only if --wiki flag), Step 7 - Neo4j export (only if --neo4j or --neo4j-push flag), Step 7a - FalkorDB export (only if --falkordb or --falkordb-push flag), Step 7b - SVG export (only if --svg flag), Step 7c - GraphML export (only if --graphml flag), Step 7d - MCP server (only if --mcp flag), Step 8 - Token reduction benchmark (only if total_words > 5000)

### Community 17 - "Ponytail"
Cohesion: 0.22
Nodes (8): Boundaries, Intensity, Output, Persistence, Ponytail, Rules, The ladder, When NOT to be lazy

### Community 18 - "02 — Pipeline: Data Flow + Tech Flow (Phase 1)"
Cohesion: 0.22
Nodes (8): 02 — Pipeline: Data Flow + Tech Flow (Phase 1), STEP 1 — Live Tracking Scraper, STEP 2 — Parsing Raw Snapshots, STEP 3 — Multi-Source Reconciliation, STEP 4 — Static Reference Data Cleaning (runs once, parallel to Steps 1-3), STEP 5 — The Master Join, STEP 6 — Feature Engineering, STEP 7 — Live Single-Train Feature Computation (serving time)

### Community 19 - "Ponytail Help"
Cohesion: 0.25
Nodes (7): Configure Default Mode, Deactivate, Levels, More, Ponytail Help, Skills, Update

### Community 20 - "Dynamic ETA Prediction System — Final Prototype Build Specification"
Cohesion: 0.29
Nodes (6): 0. Purpose of This Document Set, 1. File Index, 2. Recommended Build Order, 3. Problem Statement Coverage Matrix (Closed-Loop Proof), Dynamic ETA Prediction System — Final Prototype Build Specification, Team SteamX · PS 26028 · Master Index

### Community 21 - "08 — Deployment Specification"
Cohesion: 0.29
Nodes (6): 08 — Deployment Specification, 1. Backend (FastAPI → Render/Railway), 2. Frontend (React/Vite → Hostinger), 3. Local Development / Testing, 4. Monitoring (minimum viable, Phase 1), 5. Pre-Demo Checklist

### Community 22 - "graphify reference: query, path, explain"
Cohesion: 0.33
Nodes (5): For /graphify explain, For /graphify path, graphify reference: query, path, explain, Step 0 — Constrained query expansion (REQUIRED before traversal), Step 1 — Traversal

### Community 23 - "09 — Glossary and Appendix"
Cohesion: 0.33
Nodes (5): 09 — Glossary and Appendix, 1. Glossary, 2. Appendix A — Synthetic Dataset (excluded from the pipeline), 3. Appendix B — Open Action Items (carried from the master plan, current status), 4. Cross-References to Other Project Documents

### Community 24 - ".oxlintrc.json"
Cohesion: 0.33
Nodes (5): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema

### Community 25 - "ponytail-audit/SKILL.md"
Cohesion: 0.40
Nodes (4): Boundaries, Hunt, Output, Tags

### Community 26 - "Ponytail Gain"
Cohesion: 0.40
Nodes (4): Boundaries, Honesty boundary, Ponytail Gain, Scoreboard

### Community 27 - "ponytail-review/SKILL.md"
Cohesion: 0.40
Nodes (4): Boundaries, Examples, Format, Scoring

### Community 28 - "graphify reference: add a URL and watch a folder"
Cohesion: 0.50
Nodes (3): For /graphify add, For --watch, graphify reference: add a URL and watch a folder

### Community 29 - "graphify reference: commit hook and native CLAUDE.md integration"
Cohesion: 0.50
Nodes (3): For git commit hook, For native CLAUDE.md integration, graphify reference: commit hook and native CLAUDE.md integration

### Community 30 - "graphify reference: incremental update and cluster-only"
Cohesion: 0.50
Nodes (3): For --cluster-only, For --update (incremental re-extraction), graphify reference: incremental update and cluster-only

### Community 31 - "ponytail-debt/SKILL.md"
Cohesion: 0.50
Nodes (3): Boundaries, Output, Scan

### Community 32 - "adaptive_polling.py"
Cohesion: 0.50
Nodes (3): adjust_polling_interval(), backend/adaptive_polling.py Phase 2 Enhancement: Adaptive Polling Frequency…, Computes optimal next polling interval (in minutes) for a specific train. Rules…

### Community 33 - "generate_empirical_accuracy.py"
Cohesion: 0.67
Nodes (3): main(), Fully empirical, zero-approximation accuracy and residual evaluation script.…, set_dark_theme()

### Community 34 - "React + Vite"
Cohesion: 0.50
Nodes (3): Expanding the Oxlint configuration, React Compiler, React + Vite

### Community 45 - "errors.py"
Cohesion: 0.09
Nodes (26): Any, ConfigurationError, generic_error_handler(), InsufficientDataError, NoActiveJourneyError, OSMGeometryMismatchError, OutOfRangeFeatureError, Computed feature value falls outside plausible physical bounds. Flagged/clipped. (+18 more)

### Community 46 - "train_model_b.py"
Cohesion: 0.33
Nodes (9): chronological_split(), encode_categoricals(), evaluate(), load_and_prepare(), main(), Split by date: oldest 80% -> train, newest 20% -> test., Frequency + label encode categoricals. Save mapping for inference., save_artifacts() (+1 more)

### Community 47 - "Full Data Flow Analysis — Indian Railways ETA Prediction System"
Cohesion: 0.13
Nodes (14): Full Data Flow Analysis — Indian Railways ETA Prediction System, One-Page Summary Diagram, STAGE 10 — FRONTEND / DASHBOARD (API response → what the user sees), STAGE 11 — FEEDBACK LOOP (actual outcomes become future training input), STAGE 1 — DATA SOURCES (origin of every piece of data), STAGE 2 — INGESTION (how each source physically enters the system), STAGE 3 — CLEANING & TRANSFORMATION (per-source processing), STAGE 4 — JOINING (where separate sources become one dataset) (+6 more)

### Community 48 - "TrainETA: Dynamic Train ETA Prediction System for Indian Railways"
Cohesion: 0.06
Nodes (32): 10. Key Engineering Problems Solved, 1.1 The Challenge (PS 26028), 1.2 The TrainETA Solution, 1. Executive Summary & Problem Statement, 2. End-to-End System Architecture, 3. Dataset Specifications, 4.1 Section & Track Dynamics, 4.2 Temporal & Cyclical Features (+24 more)

### Community 50 - "10 — Error Handling and Validation Framework"
Cohesion: 0.33
Nodes (5): 10 — Error Handling and Validation Framework, 1. General Safety Principles (apply everywhere, no exceptions), 2. Custom Exception Taxonomy, 3. Standard API Error Response Shape, 4. Frontend Error-State Convention

### Community 66 - "main.py"
Cohesion: 0.05
Nodes (60): InvalidTrainNumberError, ModelNotLoadedError, Model artifact missing or corrupt at startup. Fatal / 503., What-if request contains unrecognized field or out-of-range value. Clean 422., train_no doesn't exist in train_details/combined_schedule. Clean 404., WhatIfOverrideInvalidError, apply_what_if_overrides(), compute_station_schedule_times() (+52 more)

## Knowledge Gaps
- **285 isolated node(s):** `ModelStore`, `$schema`, `plugins`, `react/rules-of-hooks`, `react/only-export-components` (+280 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 416 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `react` connect `OpsView.jsx` to `package.json`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **Why does `SchemaValidationError` connect `precedence_engine.py` to `main.py`, `errors.py`?**
  _High betweenness centrality (0.006) - this node is a cross-community bridge._
- **Why does `TrainETAError` connect `errors.py` to `precedence_engine.py`, `main.py`?**
  _High betweenness centrality (0.005) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `predict()` (e.g. with `InvalidTrainNumberError` and `ModelNotLoadedError`) actually correct?**
  _`predict()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ModelStore`, `$schema`, `plugins` to the rest of the system?**
  _285 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `precedence_engine.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11076923076923077 - nodes in this community are weakly interconnected._
- **Should `OpsView.jsx` be split into smaller, more focused modules?**
  _Cohesion score 0.05067920585161965 - nodes in this community are weakly interconnected._