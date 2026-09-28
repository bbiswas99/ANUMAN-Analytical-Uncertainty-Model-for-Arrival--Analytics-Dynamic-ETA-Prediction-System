# precedence_engine.py

> 22 nodes · cohesion 0.11

## Key Concepts

- **precedence_engine.py** (12 connections) — `backend/precedence_engine.py`
- **run_precedence_pipeline()** (6 connections) — `backend/precedence_engine.py`
- **add_precedence_features()** (5 connections) — `backend/precedence_engine.py`
- **cross_reference_priority()** (5 connections) — `backend/precedence_engine.py`
- **DataFrame** (5 connections)
- **compute_delay_picked_up()** (4 connections) — `backend/precedence_engine.py`
- **get_priority_rank()** (4 connections) — `backend/precedence_engine.py`
- **baseline_against_own_history()** (3 connections) — `backend/precedence_engine.py`
- **require_repetition_confidence()** (3 connections) — `backend/precedence_engine.py`
- **platform_deviation_signal()** (2 connections) — `backend/precedence_engine.py`
- **systemic_cause_filter()** (2 connections) — `backend/precedence_engine.py`
- **Series** (1 connections)
- **backend/precedence_engine.py Phase 2: Precedence-Inference Pipeline & Feature…** (1 connections) — `backend/precedence_engine.py`
- **Returns True (systemic cause, DISCARD as precedence candidate) if most/all…** (1 connections) — `backend/precedence_engine.py`
- **Returns the train_no of any higher-priority train present in/near the same…** (1 connections) — `backend/precedence_engine.py`
- **Returns confidence_score = (occurrences where precedence held) / (total…** (1 connections) — `backend/precedence_engine.py`
- **Returns a confidence boost (+0.15) if observed_platform differs from historical…** (1 connections) — `backend/precedence_engine.py`
- **Left-joins precedence_events onto model_A_features producing model_B_features.…** (1 connections) — `backend/precedence_engine.py`
- **Executes full Phase 2 Precedence-Inference pipeline on…** (1 connections) — `backend/precedence_engine.py`
- **Map type_code to operational priority class (1=highest, 5=lowest).** (1 connections) — `backend/precedence_engine.py`
- **Computes delay_picked_up = delay_at_exit - delay_at_entry for each train…** (1 connections) — `backend/precedence_engine.py`
- **Returns (mean, std) of this train's own historical delay_picked_up at this…** (1 connections) — `backend/precedence_engine.py`

## Relationships

- [main.py](main.py.md) (5 shared connections)
- [errors.py](errors.py.md) (1 shared connections)

## Source Files

- `backend/precedence_engine.py`

## Audit Trail

- EXTRACTED: 34 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*