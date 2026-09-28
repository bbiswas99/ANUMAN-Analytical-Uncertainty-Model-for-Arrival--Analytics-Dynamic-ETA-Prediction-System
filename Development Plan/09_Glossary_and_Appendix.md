# 09 — Glossary and Appendix

---

## 1. Glossary

| Term | Definition |
|---|---|
| **ETA** | Expected Time of Arrival — the core prediction this system produces, at every upcoming station, not just the final destination |
| **Baseline (Stage 1)** | The deterministic, non-ML estimate: scheduled time + current delay + recovery margin. Always computable, used as the fallback when confidence is low |
| **Residual** | `actual delay − baseline delay estimate` — the quantity Model A's Stage 2 tree ensemble is actually trained to predict, rather than predicting the absolute delay directly |
| **Model-Stage vs. document Step/Stage** | The model's own internal architecture (Stage 1 baseline, Stage 2 tree ensemble, Stage 3 network layer, Stage 4 uncertainty) is a separate numbering system from any document's own pipeline step numbers — always disambiguated as "Model-Stage N" when there's risk of confusion |
| **Section** | A station-pair track segment (`section_id` = `{station_from}_{station_to}`), the finest granularity used for congestion and precedence analysis |
| **Congestion proxy** | The Phase 1 engineered feature (`section_occupancy_count`) standing in for a full network/GNN model — counts other trains scheduled through the same section within a time window |
| **Precedence event** | An inferred instance of one train being held up to let a higher-priority train pass, detected from public delay-pattern correlation (Phase 2 only) |
| **Data confidence score** | A 0-1 score reflecting how much multiple scraped sources agreed on a train's latest position/delay reading; drives the fallback-to-baseline behavior |
| **Expected route** | The OSM-derived path between two stations selected by matching total track length to the known scheduled distance, rather than pure geometric shortest path |
| **Polyline snapping** | The time-based interpolation technique used only for map visualization — never used as a model input; assumes constant speed and cannot represent a real mid-section halt |
| **SHAP** | SHapley Additive exPlanations — a method for explaining individual model predictions by attributing contribution to each input feature; used for the `/explain` endpoint |
| **What-if mode** | A dashboard feature letting a user override specific feature values (e.g. hypothetical current delay) and see the recomputed prediction instantly |
| **Live-replay mode** | A dashboard feature that replays a historical journey's actual data on a simulated clock, to demonstrate dynamic ETA updates without a true live feed |
| **Phase 1 / Phase 2** | Phase 1 = buildable now with available data; Phase 2 = the precedence-inference pipeline and Model B, gated on months of data collection with an explicit go/no-go checkpoint |
| **Graphify** | Development-time codebase knowledge-graph tool used inside Antigravity: code files are parsed deterministically (tree-sitter AST); Markdown docs go through an LLM semantic pass. Edges are tagged EXTRACTED (read from source) or INFERRED (guessed by the tool) — an INFERRED edge is never to be treated as a verified fact. Not part of the shipped system |
| **Residual target** | `delay - baseline_delay_estimate` — the actual value the tree ensemble is trained to predict |
| **RTIS** | Real-Time Train Information System — CRIS/ISRO's actual production GPS tracking infrastructure (NavIC+GAGAN-based); not accessible to this project, and not built by this project — see the Data Flow Analysis document's verified-sources section for exactly what is and isn't confirmed about it |

---

## 2. Appendix A — Synthetic Dataset (excluded from the pipeline)

The Kaggle "Indian Railways: Predict Train Delay" competition dataset (`ir_train.csv`, `ir_test.csv`, `ir_data_dictionary.csv`, `ir_sample_submission.csv`) is confirmed synthetic, not real operational data. Evidence: zero missing values across 1.5M rows/45 columns; a hard gap in the delay distribution between 15-36 minutes; `is_overloaded` constant despite `seat_utilisation_pct` hard-capped at 100; train numbers that only coincidentally numerically overlap with real IR train numbers (sequential synthetic IDs vs. scattered real ones).

**Permitted uses only:** (a) stress-testing pipeline code at scale before running on real data, (b) borrowing its `primary_delay_cause` category taxonomy as a template for the `/explain` endpoint's human-readable factor list.
**Never permitted:** joining any of its rows into `master_joined_table` or any downstream table; reporting any accuracy metric derived from it as real-world performance.

---

## 3. Appendix B — Open Action Items (current)

**Resolved since the last version**
- Train-count gap (466 vs 415) explained: 2 trains missing from the schedule + 49 dropped by the strict 3-key join.
- Model-family drift fixed: LightGBM removed; project uses Random Forest / XGBoost / Extra Trees.
- Fabricated evaluation charts replaced by fully empirical plots; the 34.1% figure is retired.
- Feature Dictionary and API spec updated for `etrain_*` columns and the `/precedence`, `/trains` endpoints.

**Open — fix first**
1. Wire `require_repetition_confidence()` into the precedence event loop (flagged in three audits), regenerate precedence events and Model B, re-run the conflict-subset evaluation, and report the new subset size.
2. Run the section-geometry extraction (`02` Step 4) and feed real coordinates to the map; local offline map is being built separately.
3. Replace the daily-count congestion proxy with the +/-30-minute self-join.

**Open — smaller**
4. Raise (instead of only logging) the 5 unraised exceptions; add loading/retry states to `<TrainSelector />`.
5. Hyperparameter tuning (Optuna/GridSearchCV).

**Open — blocked on external decisions/access**
6. Choose and verify a live-tracking API source (RapidAPI listing unverified; RailRadar.in unevaluated), then build the poller and reconciliation; this unblocks the retraining loop, platform-deviation signal, and populated confidence scores.
7. Faculty mentor/SPOC and formal CRIS/NTES data-access request (still unassigned).
8. Cloud deployment (Render/Railway backend, Hostinger frontend); decide where the poller runs (VPS vs dedicated machine).
9. Confirm the 2-3 target corridors; verify platform-number availability and OSM tag completeness (`tracks=`, `electrified=`) on them via overpass-turbo (note: Overpass bounding boxes are written `(south,west,north,east)` with no angle brackets).
10. Line up 5-10 face-validity spot-checks for precedence events once re-generated.

**Pending from SIH:** Team ID and Theme.

## 4. Cross-References to Other Project Documents

| Document | What it covers that this build spec doesn't repeat |
|---|---|
| `IR_ETA_Prediction_Project_Master_Plan.md` | Full project history, decision rationale, cost/scalability analysis, production-scale architecture |
| `IR_ETA_Data_Flow_Analysis.md` | Source-to-consumption narrative including verified RTIS sourcing detail |
| `IR_ETA_Prototype_Technical_Flow.md` | An earlier, narrative version of the pipeline — this build spec (`02`) supersedes it for implementation purposes; kept for historical/pitch reference |
| `SIH_Dynamic_ETA_Deck.pptx` | The 5-slide pitch presentation |

**Within this build spec set:** `10_Error_Handling_and_Validation.md` is the shared error-handling reference for every other file — it is not repeated here since it's already its own document.
