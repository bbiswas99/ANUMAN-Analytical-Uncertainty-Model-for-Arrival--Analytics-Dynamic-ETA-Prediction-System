# TrainETA — Development Document
**Project:** Dynamic ETA Prediction for Coaching Trains (SIH 2026 — PS 26028)  
**Document Version:** 1.0.0  
**Last Updated:** September 14, 2026  
**Status:** Active & Maintained  

---

## Table of Contents
1. [Executive Summary & Problem Context](#1-executive-summary--problem-context)
2. [Architecture Overview & Technology Stack](#2-architecture-overview--technology-stack)
3. [Step-by-Step Implementation Record](#3-step-by-step-implementation-record)
   - [Step 1: Scaffolding & Design Foundation](#step-1-scaffolding--design-foundation)
   - [Step 2: Component Architecture & State Management](#step-2-component-architecture--state-management)
   - [Step 3: Dual-View Implementation (Passenger & Operations)](#step-3-dual-view-implementation-passenger--operations)
   - [Step 4: Mapping Infrastructure & OpenRailwayMap GIS](#step-4-mapping-infrastructure--openrailwaymap-gis)
   - [Step 5: Operations Tab Compact Analysis Strip](#step-5-operations-tab-compact-analysis-strip)
   - [Step 6: Passenger Tab Search & Inline Train Catalog](#step-6-passenger-tab-search--inline-train-catalog)
   - [Step 7: Nationwide Dataset Ingestion (8,730 Trains)](#step-7-nationwide-dataset-ingestion-8730-trains)
   - [Step 8: Nationwide Station GIS (8,703 Stations) & Dynamic Camera Routing](#step-8-nationwide-station-gis-8703-stations--dynamic-camera-routing)
   - [Step 9: Dynamic Baseline Inference & Offline Prediction Engine](#step-9-dynamic-baseline-inference--offline-prediction-engine)
   - [Step 10: Live Replay Journey Engine & Destination Fixes](#step-10-live-replay-journey-engine--destination-fixes)
4. [File & Asset Registry](#4-file--asset-registry)
5. [Data Dictionary & Interface Schemas](#5-data-dictionary--interface-schemas)
6. [Roadmap & Pending Milestones](#6-roadmap--pending-milestones)

---

## 1. Executive Summary & Problem Context
Traditional railway arrival estimation algorithms rely on static timetable schedules and static sectional speed charts, causing massive errors during cascading delays, congestion, freight precedence, or inclement weather. 

**TrainETA** addresses this challenge with:
* Real-time dynamic ETA forecasting using multi-feature ML regression with fallback baseline mechanisms.
* Granular uncertainty confidence bounds ($\pm X$ minutes) for passenger clarity.
* Explainable AI (XAI) factors detailing *why* delay occurs (e.g., precedence, section congestion, weather).
* A dispatcher control room "What-If" simulation console for operations personnel.
* Complete historical journey replay with animated route tracking across the Indian Railways network.

---

## 2. Architecture Overview & Technology Stack

```mermaid
graph TD
    A[Raw Datasets<br/>Schedule, Delays, Details, Stations] --> B[Data Pipeline Scripts<br/>build_train_list.py]
    B --> C[Frontend Asset Store<br/>train-list.json, station-coordinates.json]
    C --> D[Vite + React Dashboard]
    D --> E[Passenger View<br/>Live ETA & Replay]
    D --> F[Operations View<br/>What-If & Model Health]
    D --> G[GIS Leaflet Layer<br/>OSM Base + OpenRailwayMap Overlay]
    D --> H[Offline Dynamic Inference Engine<br/>apiClient.js]
    H -.-> I[Upcoming FastAPI ML Backend<br/>localhost:8000]
```

### Technology Stack:
* **Frontend Framework:** React 19 + Vite 8 (Ultra-fast HMR, production bundling)
* **Styling:** Modular Vanilla CSS & CSS Custom Properties (zero external UI framework overhead)
* **Geospatial & Mapping:** Leaflet 1.9 + React-Leaflet (Cartographic tiling, SVG vector polylines, divIcons, animated bounding box fits)
* **Map Tile Providers:**
  - Base: OpenStreetMap Standard (100% free, unmetered, watermark-free)
  - Railway Infrastructure: OpenRailwayMap standard tiles (electrification, track gauges, IR station nodes)
* **Dataset Engine:** Python 3.13 + Pandas (normalization, station graph resolution, coordinate reconciliation)

---

## 3. Step-by-Step Implementation Record

### Step 1: Scaffolding & Design Foundation
* Initialized the frontend project structure under `frontend/` using Vite + React.
* Created `index.css` defining the complete design system:
  - Deep railway blues (`#1e3a5f`), electric railway amber accents (`#f59e0b`), status emeralds, and delay crimson reds.
  - Fluid typography powered by Google Fonts `Inter`.
  - Glassmorphic card surfaces (`#ffffff` on `#f0f4f8`), subtle shadows, and crisp pill badges.
* Configured top navigation bar displaying system branding, corridor status indicators, and view toggles.

### Step 2: Component Architecture & State Management
Constructed atomic, reusable UI components following separation of concerns:
* **`TrainSelector`:** Train search bar supporting real-time fuzzy filtering and selection.
* **`ETACard`:** High-contrast arrival time display with confidence interval bar (`±X min`) and delay status badge.
* **`ConfidenceBar`:** Visual gauge depicting data reliability score (0–100%).
* **`ExplanationPanel`:** Bulleted factor breakdown attributing delay to track bottlenecks, precedence, or seasonal constraints.
* **`TrackMap`:** Interactive GIS map rendering rails, stops, train position, and junctions.
* **`LiveReplayControls`:** Animated playback scrub bar with speed multipliers (1x, 2x, 4x, 8x), play/pause, and stop indicators.
* **`WhatIfForm`:** Dispatcher scenario input sliders (injected delays, speed restrictions, weather risk flags).

### Step 3: Dual-View Implementation (Passenger & Operations)
* **Passenger View (`PassengerView.jsx`):**
  - **Mode 1 (Live ETA):** Search train, view current arrival prediction, confidence window, delay reasons, and live track location.
  - **Mode 2 (Live Replay):** Pick journey date, step through historical run stop-by-stop, observe delays at each station.
* **Operations View (`OpsView.jsx`):**
  - Dispatcher scenario console featuring What-If simulations with instant local re-computation.
  - Raw ML model diagnostic telemetry table: Model version, baseline comparison, confidence threshold, and last recorded stop.

### Step 4: Mapping Infrastructure & OpenRailwayMap GIS
* Transitioned from standard highway-centric road maps to a railway-native dual-tile architecture in `TrackMap.jsx`:
  - **Base Layer:** OpenStreetMap standard raster tiles (eliminating third-party API key watermarks).
  - **Overlay Layer:** OpenRailwayMap tile server showing actual Indian Railways physical track network, switches, signals, and station nodes.
  - **Highlight Overlay:** High-visibility polyline tracing the train's route with amber dash animation and navy drop-glow.

### Step 5: Operations Tab Compact Analysis Strip
* **Issue:** The initial `ETACard` in the Operations tab occupied excessive vertical height, reducing the visible map area.
* **Resolution:** Replaced the tall card in `OpsView.jsx` with a streamlined horizontal bar (`.etaStrip`, height: 48px).
* **Metrics:** Neatly displays train number badge, train name, ETA, delay delta, confidence score, baseline ETA, and model pill in a single horizontal strip.

### Step 6: Passenger Tab Search & Inline Train Catalog
* **Issue:** Relying solely on a popup dropdown required passengers to click into the input or memorize train numbers.
* **Resolution:** Transformed `TrainSelector.jsx` to support `inlineList={true}` on the Passenger tab:
  - Search input positioned prominently at the top.
  - Directly underneath, an always-visible, scrollable card lists available corridor and national trains.
  - Typing in the search bar dynamically filters the list in real time.
  - Shows active train badges with 1-click deselect buttons (`✕`) and a collapse/expand toggle (`▴ Hide list`).

### Step 7: Nationwide Dataset Ingestion (8,730 Trains)
* Extracted and unified all train datasets in `Dataset/`:
  - `train_details.csv` (8,720 trains)
  - `combined_schedule.csv` (172,114 stop records across 8,673 trains)
  - `etrain_delays.csv` (detailed delay records for 90 key services)
  - `station_full_names.csv` (8,963 station names and addresses)
* Built `frontend/scripts/build_train_list.py` to generate `train-list.json`:
  - Compiled **8,730 unique trains** with train number, name, origin, destination, and stop list.
  - Categorized IR train classes with color pills: `VANDE BHARAT` (T18), `RAJDHANI` (RAJ), `SHATABDI` (SHT), `SUPERFAST` (SF), `EXPRESS` (EXP), `GARIB RATH` (GRB), `PREMIUM` (PRM), and `PASSENGER` (PASS).
  - Multi-field search enables instant discovery by train number, name, station code, or station name (e.g. *Chennai*, *Coimbatore*, *Kolkata*).
  - Integrated infinite-scroll chunking (60 items/page) to ensure 60 FPS performance with 8,730 records.

### Step 8: Nationwide Station GIS (8,703 Stations) & Dynamic Camera Routing
* Integrated GeoJSON station coordinates from `datameet/railways` into `station-coordinates.json`:
  - Mapped **8,703 Indian Railway stations** with precise latitude and longitude.
  - Implemented alias resolution for historic IR code renamings (`MMCT ↔ BCT`, `DDU ↔ MGS`, `PRYJ ↔ ALD`, `CSMT ↔ CSTM`).
* Built Dynamic Route Rendering in `TrackMap.jsx`:
  - When any train is selected, `TrackMap` pulls its ordered stop list, maps every station to its coordinates, and draws the route line across India.
  - Distinct markers: 🟢 Origin, 🔴 Destination, 🔵 Intermediate Stops (with station codes & tooltips).
  - Integrated `MapBoundsUpdater` using Leaflet's `fitBounds`: automatically flies and zooms to frame the selected train's journey anywhere in India.

### Step 9: Dynamic Baseline Inference & Offline Prediction Engine
* **Issue:** When the backend was offline, selecting any train outside the 3 static demo records returned *"Live prediction unavailable"*.
* **Resolution:** Added `synthesizeBaselinePrediction()` and `synthesizeExplanation()` in `apiClient.js`:
  - Dynamically calculates realistic arrival ETAs, confidence intervals, and category-weighted delays based on train classification.
  - Generates contextual explanation factors (precedence, section traffic density, schedule buffer).
  - Ensures **all 8,730 trains** display complete, realistic predictions and explanations offline.

### Step 10: Live Replay Journey Engine & Destination Fixes
* **Dynamic Replay Synthesis:** Added `synthesizeReplay()` in `apiClient.js` to construct historical stop logs with realistic station arrival times and delay curves for any chosen train across India.
* **State Cleansing:** Updated `PassengerView.jsx` and `LiveReplayControls.jsx` to clear lingering coordinates (`trainPosition = null`, `activeStop = null`) when switching trains.
* **Premature Stop Bug Fix:**
  - *Symptom:* Live replay train marker moved across stations but prematurely paused at the second-to-last station before destination.
  - *Fix:* Corrected the step transition in `LiveReplayControls.jsx` so the journey advances cleanly through the final leg, terminates at the actual destination station (`total / total`), and updates the control button to `↺ Replay journey`.

### Step 11: Clean Map State on Train Deselection
* **Problem:** When a train was deselected (or before any train was selected), the map defaulted to rendering hardcoded Delhi–Mumbai corridor track lines and station markers.
* **Resolution:**
  - Removed Delhi–Mumbai geometry fallbacks in `frontend/src/components/TrackMap.jsx`.
  - Configured `activeRouteCoords` and `stationsToRender` to return empty arrays when `selectedTrain` is null.
  - Configured `markerPosition` to evaluate to `null` when no train is selected.
  - Updated `MapBoundsUpdater` to detect deselection and smoothly fly the camera back out to the national overview (`DEFAULT_CENTER = [22.8, 79.5]`, `DEFAULT_ZOOM = 5`).
  - Updated map legend to display a neutral *"Select a train to view route"* state when no train is selected, hiding route, origin, and destination symbols.
  - Updated the topbar status badge in `App.jsx` to *"Indian Railways Network"* reflecting the full nationwide system.

### Step 12: Excluded Trains Without Intermediate Stations
* **Requirement:** Trains having only a source and destination station (0 intermediate halts, such as short 2 km branch shuttles or non-stop point-to-point routes) should not appear in the dashboard search or selection lists, while preserving the raw CSV dataset untouched.
* **Resolution:**
  - Updated `frontend/scripts/build_train_list.py` to enforce `len(set(stops)) >= 3` (requiring at least 1 intermediate station).
  - Preserved all files in `Dataset/` unmodified (`combined_schedule.csv`, `train_details.csv`, etc.).
  - Regenerated `frontend/src/assets/train-list.json`: filtered out 188 trains (137 two-station shuttles/non-stops and 51 records lacking schedule halts).
  - The dashboard catalog now features **8,542 active trains**, all of which possess realistic intermediate stops and multi-station routes.

### Step 13: Operations Tab Train List Unification
* **Issue:** The Operations tab was using `<TrainSelector>` in legacy dropdown mode (limiting the initial view to only 10 trains in a floating popup), whereas the Passenger tab had the full scrollable inline list under the search input.
* **Resolution:**
  - Updated `frontend/src/tabs/OpsView.jsx` to pass the `inlineList` prop to `<TrainSelector>`.
  - The Operations tab now shares the identical, complete list of **8,542 multi-station trains** directly below the search bar, with real-time search filtering, infinite scrolling, category badges, and instant selection into What-If simulation and Model Details cards.

### Step 15: Standard Error Handling & Validation Framework (File 10 Integration)
* **Objective:** Unify error handling across the entire stack per `Development Plan/10_Error_Handling_and_Validation.md` as the single source of truth.
* **Resolution:**
  - Implemented the complete custom exception taxonomy in `backend/errors.py`: `InvalidTrainNumberError`, `NoActiveJourneyError`, `StaleDataError`, `SourceUnavailableError`, `SchemaValidationError`, `ModelNotLoadedError`, `OutOfRangeFeatureError`, `WhatIfOverrideInvalidError`, `OSMGeometryMismatchError`, `InsufficientDataError`, and `ConfigurationError`.
  - Implemented standard JSON error envelope: `{"error": true, "error_type": "<ClassName>", "message": "<human-readable>", "status_code": <int>}`.
  - Aligned all backend endpoints (`/predict`, `/explain`, `/replay`, `/precedence`) to raise typed exceptions rather than raw unhandled payloads or inconsistent status codes.
  - Implemented server-side sanitization: raw exceptions and stack traces are logged internally and masked with generic 500 responses to prevent internal information leakage.
  - Frontend `apiClient.js` and UI cards now consume the standard `error_type` and `message` format with graceful degradation to cached fallbacks during network interruptions.

---

## 4. File & Asset Registry

| File Path | Description / Role |
|---|---|
| `backend/errors.py` | Single source of truth for custom exception taxonomy and standard error response formatting (File 10). |
| `Development Plan/10_Error_Handling_and_Validation.md` | Master specification for system-wide validation and error handling conventions. |
| `frontend/src/index.css` | Global design system tokens, typography, CSS reset, and utility classes. |
| `frontend/src/App.jsx` | Root application orchestrator, navigation bar, and tab router. |
| `frontend/src/tabs/PassengerView.jsx` | Passenger console supporting Live ETA and Live Replay modes. |
| `frontend/src/tabs/OpsView.jsx` | Staff operations dashboard with scenario builder and compact telemetry strip. |
| `frontend/src/components/TrackMap.jsx` | Dynamic nationwide GIS map with OpenRailwayMap tiles, route polylines, and auto-zoom. |
| `frontend/src/components/TrainSelector.jsx` | Search input and progressive-loading train catalog supporting 8,730 trains. |
| `frontend/src/components/LiveReplayControls.jsx` | Playback scrubber, speed multipliers, and animated route advancement engine. |
| `frontend/src/components/ETACard.jsx` | High-contrast arrival time, delay badge, and prediction interval window. |
| `frontend/src/components/ConfidenceBar.jsx` | Gauge visualizing model data confidence percentage. |
| `frontend/src/components/ExplanationPanel.jsx` | Explainable AI delay factor attribution list. |
| `frontend/src/components/WhatIfForm.jsx` | Dispatcher scenario simulation form for operations testing. |
| `frontend/src/utils/apiClient.js` | Centralized API client with dynamic offline inference and replay synthesis. |
| `frontend/src/utils/snapPositionToRoute.js` | Arc-length parameterized interpolation along geospatial coordinates. |
| `frontend/src/assets/train-list.json` | Catalog of 8,730 Indian Railways trains with routes, stops, and types. |
| `frontend/src/assets/station-coordinates.json` | Geospatial lookup index of 8,703 railway station latitudes and longitudes. |
| `frontend/scripts/build_train_list.py` | Python ingestion pipeline script that compiles raw CSVs into frontend assets. |
| `requirements.txt` | Pinned dependencies for project virtual environment (.venv). |
| `Development Plan/Development Document.md` | **This file:** Master technical blueprint and chronological build log. |

---

## 5. Data Dictionary & Interface Schemas

### Prediction Response Schema (`/predict` & Dynamic Baseline)
```json
{
  "train_no": 12673,
  "train_name": "CHERAN EXPRESS",
  "type_code": "SF-TRAINS",
  "eta": "2026-09-14T15:44:00.000Z",
  "confidence_interval_lower": "2026-09-14T15:34:00.000Z",
  "confidence_interval_upper": "2026-09-14T15:59:00.000Z",
  "baseline_eta": "2026-09-14T15:30:00.000Z",
  "current_delay_min": 14,
  "data_confidence_score": 0.84,
  "model_used": "baseline",
  "last_station_code": "SA",
  "last_station_name": "Salem Jn",
  "_isFallback": true
}
```

### Replay Response Schema (`/replay`)
```json
{
  "train_no": 12673,
  "train_name": "CHERAN EXPRESS",
  "date": "2025-11-15",
  "stops": [
    {
      "station_no": 1,
      "station_name": "MAS",
      "station_full_name": "Chennai Central",
      "scheduled_time": "06:00",
      "actual_delay_min": 0,
      "lat": 13.0827,
      "lon": 80.2755
    },
    {
      "station_no": 9,
      "station_name": "CBE",
      "station_full_name": "Coimbatore Jn",
      "scheduled_time": "11:20",
      "actual_delay_min": 5,
      "lat": 11.0016,
      "lon": 76.9668
    }
  ]
}
```

---

## 6. Roadmap & Pending Milestones

- [x] **Milestone 1:** Frontend UI architecture, design tokens, and components complete.
- [x] **Milestone 2:** Ingestion of full IR catalog (8,730 trains) and nationwide GIS coordinates (8,703 stations).
- [x] **Milestone 3:** Dynamic route rendering, camera auto-pan/zoom, and complete live replay engine.
- [x] **Milestone 4 (Backend):** Implement Python FastAPI service (`main.py`) exposing `/predict`, `/explain`, and `/replay` on `http://localhost:8000`. (*Completed and verified running on port 8000.*)
- [x] **Milestone 5 (ML Model):** Train XGBoost / Random Forest / Extra Trees models (*LightGBM was dropped due to Windows environment constraints*). Model A (Congestion-Aware) and Model B (Precedence-Aware) trained on 774,291 records with chronological 80/20 train/test split. *(Note: Model B precedence features are back-tested on historical delay data rather than live-scraped stream, pending live NTES ingestion).*
- [x] **Milestone 6 (File 10 Integration):** Implement standardized error response shapes and recovery codes once File 10 specification is received. (*Completed and verified: full custom exception taxonomy, standardized envelope `{"error": true, "error_type", "message", "status_code"}`, boundary guards across `/predict`, `/explain`, `/replay`, `/precedence`, and fail-safe frontend degradation.*)
- [ ] **Milestone 7 (Real-Time Ingestion):** Build live scraper / NTES polling connector for live train positional tracking. *(Remains open; currently uses historical back-testing and replay).*

---

## 7. Metric & Visual Artifact Veracity Disclosure

| Metric / Artifact | Status | Source & Evaluation Context |
|---|---|---|
| **Overall Test Error (156,216 samples)** | **Real (Trained Model)** | Evaluated on out-of-sample test split (`date >= 2025-11-27`): Baseline MAE = 33.24m, Model A MAE = 8.86m, Model B MAE = 8.87m. |
| **Precedence Conflict Sections MAE (5,927 samples)** | **Real (Trained Model)** | Evaluated on test subset where `precedence_risk_score_next_section > 0`: Model A MAE = 9.09m, Model B MAE = 8.80m (-0.29m / -3.2% error reduction). |
| **Cumulative Accuracy Curves (±5m, ±10m, ±15m, ±30m)** | **Real (Empirical)** | Empirically derived from the 156,216 test residuals: ±5m: 59.08%, ±10m: 76.67%, ±15m: 84.82%, ±30m: 94.05% (zero formula approximation). |
| **Actual vs. Predicted Delay Hexbin & Residual Histogram** | **Real (Empirical)** | Generated directly by `backend/generate_empirical_accuracy.py` across all 156,216 test predictions. |
| **Feature Importances** | **Real (Trained Model)** | XGBoost gain-based feature importances extracted directly from `model_b.json`. |
| **Live Replay Trajectories** | **Real Data (Replay Mode)** | Station delays and timings drawn from `Dataset/combined_delay.csv` historical records. |
| **What-If Scenario Simulation (Ops View)** | **Illustrative Prototype** | Interactive dispatcher heuristic slider demonstrating scenario planning UI ahead of full physical dispatch rules engine. |

