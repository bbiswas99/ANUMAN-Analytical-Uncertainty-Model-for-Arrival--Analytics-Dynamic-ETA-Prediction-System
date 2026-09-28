# train_model.py

> 19 nodes · cohesion 0.18

## Key Concepts

- **train_model.py** (8 connections) — `backend/train_model.py`
- **train_model_b.py** (7 connections) — `backend/train_model_b.py`
- **main()** (7 connections) — `backend/train_model_b.py`
- **main()** (7 connections) — `backend/train_model.py`
- **chronological_split()** (3 connections) — `backend/train_model_b.py`
- **encode_categoricals()** (3 connections) — `backend/train_model_b.py`
- **chronological_split()** (3 connections) — `backend/train_model.py`
- **encode_categoricals()** (3 connections) — `backend/train_model.py`
- **evaluate()** (2 connections) — `backend/train_model_b.py`
- **load_and_prepare()** (2 connections) — `backend/train_model_b.py`
- **save_artifacts()** (2 connections) — `backend/train_model_b.py`
- **train_xgboost()** (2 connections) — `backend/train_model_b.py`
- **evaluate()** (2 connections) — `backend/train_model.py`
- **load_and_prepare()** (2 connections) — `backend/train_model.py`
- **save_artifacts()** (2 connections) — `backend/train_model.py`
- **train_xgboost()** (2 connections) — `backend/train_model.py`
- **# NOTE: 'date' is intentionally NOT here -- kept for chronological_split(),** (1 connections) — `backend/train_model.py`
- **Split by date, oldest 80% → train, newest 20% → test.** (1 connections) — `backend/train_model.py`
- **Frequency + label encode categoricals. Save mapping for inference.** (1 connections) — `backend/train_model.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `backend/train_model.py`
- `backend/train_model_b.py`

## Audit Trail

- EXTRACTED: 31 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*