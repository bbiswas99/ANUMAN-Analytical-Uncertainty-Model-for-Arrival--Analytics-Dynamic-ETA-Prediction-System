# Graph Report - Code  (2026-09-16)

## Corpus Check
- 73 files · ~513,836 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 16 file(s) not represented in the graph (top: .css 12, (none) 3, .example 1)

## Summary
- 510 nodes · 675 edges · 45 communities (35 shown, 10 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 19 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- main.py
- What You Must Do When Invoked
- package.json
- apiClient.js
- build_features.py
- OpsView.jsx
- reconciled_reader.py
- train_model.py
- .oxlintrc.json
- 3. Step-by-Step Implementation Record
- main
- precedence_engine.py
- 2. Data Sources — Full Descriptions and Schemas
- PHASE 1 — Model A
- 2. Components
- PART A — PHASE 1: Scraper Infrastructure (build now)
- TrainETA Backend
- train_model_b.py
- 1. Endpoints
- graphify reference: extra exports and benchmark
- Ponytail
- 02 — Pipeline: Data Flow + Tech Flow (Phase 1)
- Ponytail Help
- Dynamic ETA Prediction System — Final Prototype Build Specification
- 08 — Deployment Specification
- graphify reference: query, path, explain
- 09 — Glossary and Appendix
- ponytail-audit/SKILL.md
- Ponytail Gain
- ponytail-review/SKILL.md
- graphify reference: add a URL and watch a folder
- graphify reference: commit hook and native CLAUDE.md integration
- graphify reference: incremental update and cluster-only
- ponytail-debt/SKILL.md
- adaptive_polling.py
- React + Vite
- graphify reference: GitHub clone and cross-repo merge
- graphify reference: transcribe video and audio
- rules/graphify.md
- ponytail.md
- extraction-spec.md
- workflows/graphify.md
- 03_Feature_Dictionary.md

## God Nodes (most connected - your core abstractions)
1. `main()` - 21 edges
2. `predict()` - 15 edges
3. `3. Step-by-Step Implementation Record` - 15 edges
4. `TrainETAError` - 14 edges
5. `react` - 13 edges
6. `What You Must Do When Invoked` - 12 edges
7. `/graphify` - 11 edges
8. `2. Data Sources — Full Descriptions and Schemas` - 11 edges
9. `safe_float()` - 9 edges
10. `LiveReplayControls()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `explain()` --uses--> `InvalidTrainNumberError`  [INFERRED]
  backend/main.py → backend/errors.py
- `precedence()` --uses--> `InvalidTrainNumberError`  [INFERRED]
  backend/main.py → backend/errors.py
- `predict()` --uses--> `InvalidTrainNumberError`  [INFERRED]
  backend/main.py → backend/errors.py
- `replay()` --uses--> `InvalidTrainNumberError`  [INFERRED]
  backend/main.py → backend/errors.py
- `predict()` --uses--> `WhatIfOverrideInvalidError`  [INFERRED]
  backend/main.py → backend/errors.py

## Import Cycles
- None detected.

## Communities (45 total, 10 thin omitted)

### Community 0 - "main.py"
Cohesion: 0.06
Nodes (57): ConfigurationError, generic_error_handler(), InvalidTrainNumberError, ModelNotLoadedError, NoActiveJourneyError, OutOfRangeFeatureError, Call this in main.py after creating the FastAPI app., Base class for all application-defined errors. (+49 more)

### Community 1 - "What You Must Do When Invoked"
Cohesion: 0.07
Nodes (26): For /graphify add and --watch, For /graphify query, For the commit hook and native CLAUDE.md integration, For --update and --cluster-only, /graphify, Honesty Rules, Interpreter guard for subcommands, Part A - Structural extraction for code files (+18 more)

### Community 2 - "package.json"
Cohesion: 0.07
Nodes (26): dependencies, leaflet, react, react-dom, react-leaflet, devDependencies, oxlint, @types/react (+18 more)

### Community 3 - "apiClient.js"
Cohesion: 0.15
Nodes (21): LiveReplayControls(), handlePlayPause(), handleRestart(), SPEED_OPTIONS, WhatIfForm(), handleSubmit(), validate(), useReplay() (+13 more)

### Community 4 - "build_features.py"
Cohesion: 0.15
Nodes (23): add_stub_features(), build_baseline(), build_delay_trend(), build_journey_features(), build_recovery_margin(), build_rolling_delay_features(), build_section_id(), build_section_occupancy() (+15 more)

### Community 5 - "OpsView.jsx"
Cohesion: 0.07
Nodes (26): App(), TABS, ConfidenceBar(), ErrorBoundary, ETACard(), ExplanationPanel(), DEFAULT_CENTER, TrackMap() (+18 more)

### Community 6 - "reconciled_reader.py"
Cohesion: 0.26
Nodes (11): get_cached_reconciled(), get_data_freshness(), get_latest_reconciled_row(), _get_reconciled_path(), _load_from_disk(), DataFrame, Path, Returns freshness metadata for the /health endpoint. {… (+3 more)

### Community 7 - "train_model.py"
Cohesion: 0.29
Nodes (10): chronological_split(), encode_categoricals(), evaluate(), load_and_prepare(), main(), # NOTE: 'date' is intentionally NOT here -- kept for chronological_split(),, Split by date, oldest 80% → train, newest 20% → test., Frequency + label encode categoricals. Save mapping for inference. (+2 more)

### Community 8 - ".oxlintrc.json"
Cohesion: 0.33
Nodes (5): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema

### Community 9 - "3. Step-by-Step Implementation Record"
Cohesion: 0.08
Nodes (25): 1. Executive Summary & Problem Context, 2. Architecture Overview & Technology Stack, 3. Step-by-Step Implementation Record, 4. File & Asset Registry, 5. Data Dictionary & Interface Schemas, 6. Roadmap & Pending Milestones, Prediction Response Schema (`/predict` & Dynamic Baseline), Replay Response Schema (`/replay`) (+17 more)

### Community 11 - "precedence_engine.py"
Cohesion: 0.11
Nodes (22): add_precedence_features(), baseline_against_own_history(), compute_delay_picked_up(), cross_reference_priority(), get_priority_rank(), platform_deviation_signal(), DataFrame, Path (+14 more)

### Community 12 - "2. Data Sources — Full Descriptions and Schemas"
Cohesion: 0.14
Nodes (13): 01 — Architecture Overview and Data Sources, 1. System Architecture (Phase 1, the closed-loop prototype), 2.10 Excluded from the pipeline entirely (documented decision, not an oversight), 2.1 `combined_schedule.csv` (already have — Phase 1), 2.2 `combined_delay.csv` (already have — Phase 1), 2.3 `train_details.csv` (already have — Phase 1), 2.4 `station_full_names.csv` (already have — Phase 1), 2.5 `etrain_delays.csv` (already have — Phase 1, supplementary) (+5 more)

### Community 13 - "PHASE 1 — Model A"
Cohesion: 0.14
Nodes (13): 04 — ML Model Specification, Evaluation metrics (required, report all of these), Explainability, PHASE 1 — Model A, PHASE 2 — Model B (do not build until the data-collection go/no-go checkpoint passes), Required comparison methodology (this is the actual deliverable of Phase 2, not just "a better model"), Retraining, Serving fallback requirement (+5 more)

### Community 14 - "2. Components"
Cohesion: 0.14
Nodes (13): 06 — Frontend / Dashboard Specification (React + Vite + Leaflet), 06 — Frontend / Dashboard Specification (React + Vite + Leaflet), 1. Application Structure, 2. Components, 3. Fallback Behavior (mandatory, applies app-wide), 4. State Management, 5. Build/Deploy Note, `<ETACard />` (+5 more)

### Community 15 - "PART A — PHASE 1: Scraper Infrastructure (build now)"
Cohesion: 0.15
Nodes (12): 07 — Data Collection: Phase 1 Scraper Infrastructure + Phase 2 Precedence-Inference (marked), Deployment, Ethics/scope guardrails (hard requirements, not preferences), Feeding into Model B (see `04` Phase 2 section), Function specs, Function specs (beyond what's in `02` Step 1), Output schema — `precedence_events.parquet`, PART A — PHASE 1: Scraper Infrastructure (build now) (+4 more)

### Community 16 - "TrainETA Backend"
Cohesion: 0.17
Nodes (11): API Endpoints, Environment Variables, Error Response Shape, File Structure, How it works, How to generate the file (example, on the scraper machine), Optional Columns (used if present, silently ignored if absent), Quick Start (+3 more)

### Community 17 - "train_model_b.py"
Cohesion: 0.33
Nodes (9): chronological_split(), encode_categoricals(), evaluate(), load_and_prepare(), main(), Split by date: oldest 80% -> train, newest 20% -> test., Frequency + label encode categoricals. Save mapping for inference., save_artifacts() (+1 more)

### Community 18 - "1. Endpoints"
Cohesion: 0.20
Nodes (9): 05 — Backend API Specification (FastAPI), 05 — Backend API Specification (FastAPI), 1. Endpoints, 2. Internal Functions, 3. Cross-Cutting Requirements, `GET /explain`, `GET /health`, `GET /predict` (+1 more)

### Community 19 - "graphify reference: extra exports and benchmark"
Cohesion: 0.22
Nodes (8): graphify reference: extra exports and benchmark, Step 6b - Wiki (only if --wiki flag), Step 7 - Neo4j export (only if --neo4j or --neo4j-push flag), Step 7a - FalkorDB export (only if --falkordb or --falkordb-push flag), Step 7b - SVG export (only if --svg flag), Step 7c - GraphML export (only if --graphml flag), Step 7d - MCP server (only if --mcp flag), Step 8 - Token reduction benchmark (only if total_words > 5000)

### Community 20 - "Ponytail"
Cohesion: 0.22
Nodes (8): Boundaries, Intensity, Output, Persistence, Ponytail, Rules, The ladder, When NOT to be lazy

### Community 21 - "02 — Pipeline: Data Flow + Tech Flow (Phase 1)"
Cohesion: 0.22
Nodes (8): 02 — Pipeline: Data Flow + Tech Flow (Phase 1), STEP 1 — Live Tracking Scraper, STEP 2 — Parsing Raw Snapshots, STEP 3 — Multi-Source Reconciliation, STEP 4 — Static Reference Data Cleaning (runs once, parallel to Steps 1-3), STEP 5 — The Master Join, STEP 6 — Feature Engineering, STEP 7 — Live Single-Train Feature Computation (serving time)

### Community 22 - "Ponytail Help"
Cohesion: 0.25
Nodes (7): Configure Default Mode, Deactivate, Levels, More, Ponytail Help, Skills, Update

### Community 23 - "Dynamic ETA Prediction System — Final Prototype Build Specification"
Cohesion: 0.29
Nodes (6): 0. Purpose of This Document Set, 1. File Index, 2. Recommended Build Order, 3. Problem Statement Coverage Matrix (Closed-Loop Proof), Dynamic ETA Prediction System — Final Prototype Build Specification, Team SteamX · PS 26028 · Master Index

### Community 24 - "08 — Deployment Specification"
Cohesion: 0.29
Nodes (6): 08 — Deployment Specification, 1. Backend (FastAPI → Render/Railway), 2. Frontend (React/Vite → Hostinger), 3. Local Development / Testing, 4. Monitoring (minimum viable, Phase 1), 5. Pre-Demo Checklist

### Community 25 - "graphify reference: query, path, explain"
Cohesion: 0.33
Nodes (5): For /graphify explain, For /graphify path, graphify reference: query, path, explain, Step 0 — Constrained query expansion (REQUIRED before traversal), Step 1 — Traversal

### Community 26 - "09 — Glossary and Appendix"
Cohesion: 0.33
Nodes (5): 09 — Glossary and Appendix, 1. Glossary, 2. Appendix A — Synthetic Dataset (excluded from the pipeline), 3. Appendix B — Open Action Items (carried from the master plan, current status), 4. Cross-References to Other Project Documents

### Community 27 - "ponytail-audit/SKILL.md"
Cohesion: 0.40
Nodes (4): Boundaries, Hunt, Output, Tags

### Community 28 - "Ponytail Gain"
Cohesion: 0.40
Nodes (4): Boundaries, Honesty boundary, Ponytail Gain, Scoreboard

### Community 29 - "ponytail-review/SKILL.md"
Cohesion: 0.40
Nodes (4): Boundaries, Examples, Format, Scoring

### Community 30 - "graphify reference: add a URL and watch a folder"
Cohesion: 0.50
Nodes (3): For /graphify add, For --watch, graphify reference: add a URL and watch a folder

### Community 31 - "graphify reference: commit hook and native CLAUDE.md integration"
Cohesion: 0.50
Nodes (3): For git commit hook, For native CLAUDE.md integration, graphify reference: commit hook and native CLAUDE.md integration

### Community 32 - "graphify reference: incremental update and cluster-only"
Cohesion: 0.50
Nodes (3): For --cluster-only, For --update (incremental re-extraction), graphify reference: incremental update and cluster-only

### Community 33 - "ponytail-debt/SKILL.md"
Cohesion: 0.50
Nodes (3): Boundaries, Output, Scan

### Community 34 - "adaptive_polling.py"
Cohesion: 0.50
Nodes (3): adjust_polling_interval(), backend/adaptive_polling.py Phase 2 Enhancement: Adaptive Polling Frequency…, Computes optimal next polling interval (in minutes) for a specific train. Rules…

### Community 35 - "React + Vite"
Cohesion: 0.50
Nodes (3): Expanding the Oxlint configuration, React Compiler, React + Vite

## Knowledge Gaps
- **204 isolated node(s):** `ModelStore`, `$schema`, `plugins`, `react/rules-of-hooks`, `react/only-export-components` (+199 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 304 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `react` connect `OpsView.jsx` to `package.json`, `apiClient.js`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Why does `SchemaValidationError` connect `main.py` to `precedence_engine.py`?**
  _High betweenness centrality (0.007) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `predict()` (e.g. with `InvalidTrainNumberError` and `ModelNotLoadedError`) actually correct?**
  _`predict()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ModelStore`, `$schema`, `plugins` to the rest of the system?**
  _204 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06393442622950819 - nodes in this community are weakly interconnected._
- **Should `What You Must Do When Invoked` be split into smaller, more focused modules?**
  _Cohesion score 0.07407407407407407 - nodes in this community are weakly interconnected._
- **Should `package.json` be split into smaller, more focused modules?**
  _Cohesion score 0.07142857142857142 - nodes in this community are weakly interconnected._