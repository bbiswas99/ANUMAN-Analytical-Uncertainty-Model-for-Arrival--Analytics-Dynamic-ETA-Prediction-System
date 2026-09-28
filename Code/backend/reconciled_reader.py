# backend/reconciled_reader.py
# Reads reconciled_positions.parquet produced by the remote scraper machine.
# This file is the ONLY interface between the scraper and the prediction backend.
#
# Expected schema (columns the remote scraper must provide):
#   train_no          int      — Indian Railways train number
#   station_no        int      — Stop sequence on the route
#   station_name      str      — Station code (e.g. "NDLS")
#   delay             float    — Current reported delay in minutes (negative = early)
#   date              datetime — Journey date (UTC)
#   scraped_at        datetime — Timestamp when this row was scraped (UTC)
#   source_agreement_score  float  — 0-1, how consistent multiple sources were
#
# Optional columns (used if present, ignored if absent):
#   platform_number   str | null
#   reported_speed_kmh  float | null
#
# The file can be dropped / replaced atomically by the remote machine at any time.
# This reader caches the loaded dataframe for CACHE_TTL_SECONDS to avoid re-reading
# on every prediction request.

import os
import time
import logging
import threading
from pathlib import Path
from typing import Optional
import pandas as pd

log = logging.getLogger("traineta.reconciled")

CACHE_TTL_SECONDS = 60          # Re-read the file at most once per minute
STALE_WARNING_HOURS = 2         # Warn if newest row is older than this

REQUIRED_COLUMNS = {"train_no", "station_no", "station_name", "delay", "date", "scraped_at"}

_cache_lock = threading.Lock()
_cached_df: Optional[pd.DataFrame] = None
_cache_loaded_at: float = 0.0


def _get_reconciled_path() -> Optional[Path]:
    """Read path from env var. Returns None if not configured."""
    raw = os.environ.get("RECONCILED_DATA_PATH", "").strip()
    if not raw:
        return None
    return Path(raw)


def _load_from_disk() -> Optional[pd.DataFrame]:
    path = _get_reconciled_path()
    if path is None:
        log.debug("RECONCILED_DATA_PATH not set — live data disabled")
        return None

    if not path.exists():
        log.warning(f"reconciled_positions file not found at {path} — using static fallback")
        return None

    try:
        df = pd.read_parquet(path)
    except Exception as e:
        log.error(f"Failed to read reconciled_positions at {path}: {e}")
        return None

    # Validate required columns
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        log.error(f"reconciled_positions is missing required columns: {missing}")
        return None

    # Parse timestamps
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce")
    df["train_no"] = pd.to_numeric(df["train_no"], errors="coerce").astype("Int64")
    df["delay"] = pd.to_numeric(df["delay"], errors="coerce")

    log.info(f"Loaded reconciled_positions: {len(df):,} rows, "
             f"{df['train_no'].nunique()} trains, "
             f"newest scraped_at={df['scraped_at'].max()}")
    return df


def get_cached_reconciled() -> Optional[pd.DataFrame]:
    """Return the cached reconciled dataframe, refreshing if TTL expired."""
    global _cached_df, _cache_loaded_at

    with _cache_lock:
        now = time.monotonic()
        if now - _cache_loaded_at > CACHE_TTL_SECONDS:
            _cached_df = _load_from_disk()
            _cache_loaded_at = now

    return _cached_df


def get_latest_reconciled_row(train_no: int) -> Optional[dict]:
    """
    Return the most recent scraped position row for train_no, or None.
    None means 'no live data' — caller falls back to static historical snapshot.
    This is a deliberate non-error return per 05_Backend_API_Spec.md.
    """
    df = get_cached_reconciled()
    if df is None:
        return None

    sub = df[df["train_no"] == train_no]
    if sub.empty:
        return None

    # Most recent scraped row
    row = sub.sort_values("scraped_at").iloc[-1]
    return row.to_dict()


def get_data_freshness() -> dict:
    """
    Returns freshness metadata for the /health endpoint.
    {
        "reconciled_data_configured": bool,
        "last_scraper_update": str | null,
        "data_freshness_warning": bool,
        "live_trains_count": int
    }
    """
    path = _get_reconciled_path()
    if path is None:
        return {
            "reconciled_data_configured": False,
            "last_scraper_update": None,
            "data_freshness_warning": False,
            "live_trains_count": 0,
        }

    df = get_cached_reconciled()
    if df is None:
        return {
            "reconciled_data_configured": True,
            "last_scraper_update": None,
            "data_freshness_warning": True,
            "live_trains_count": 0,
        }

    newest = df["scraped_at"].max()
    import pandas as pd
    age_hours = (pd.Timestamp.utcnow() - newest).total_seconds() / 3600
    stale = age_hours > STALE_WARNING_HOURS

    return {
        "reconciled_data_configured": True,
        "last_scraper_update": str(newest),
        "data_freshness_warning": stale,
        "live_trains_count": int(df["train_no"].nunique()),
    }
