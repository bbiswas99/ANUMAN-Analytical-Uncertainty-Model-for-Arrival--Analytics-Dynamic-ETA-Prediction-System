# reconciled_reader.py

> 12 nodes · cohesion 0.26

## Key Concepts

- **reconciled_reader.py** (6 connections) — `backend/reconciled_reader.py`
- **get_cached_reconciled()** (6 connections) — `backend/reconciled_reader.py`
- **get_data_freshness()** (6 connections) — `backend/reconciled_reader.py`
- **get_latest_reconciled_row()** (5 connections) — `backend/reconciled_reader.py`
- **_get_reconciled_path()** (5 connections) — `backend/reconciled_reader.py`
- **_load_from_disk()** (4 connections) — `backend/reconciled_reader.py`
- **DataFrame** (2 connections)
- **Path** (1 connections)
- **Returns freshness metadata for the /health endpoint. {…** (1 connections) — `backend/reconciled_reader.py`
- **Read path from env var. Returns None if not configured.** (1 connections) — `backend/reconciled_reader.py`
- **Return the cached reconciled dataframe, refreshing if TTL expired.** (1 connections) — `backend/reconciled_reader.py`
- **Return the most recent scraped position row for train_no, or None. None means…** (1 connections) — `backend/reconciled_reader.py`

## Relationships

- [main.py](main.py.md) (5 shared connections)

## Source Files

- `backend/reconciled_reader.py`

## Audit Trail

- EXTRACTED: 22 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*