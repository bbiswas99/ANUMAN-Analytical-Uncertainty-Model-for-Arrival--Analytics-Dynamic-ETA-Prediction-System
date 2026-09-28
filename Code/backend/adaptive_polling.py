"""
backend/adaptive_polling.py
Phase 2 Enhancement: Adaptive Polling Frequency Engine.
Per Development Plan 07_DataCollection_Scraper_and_Precedence_Phase2.md (Part B).

Adjusts scraper polling frequency per train based on delay volatility:
- Accelerates to fast_interval_min (default 4m) when delay delta exceeds change_threshold_min (default 3m).
- Relaxes to base_interval_min (default 12m) when readings stabilize.
- Fully guarded against cold starts, single-reading edge cases, and boundary violations.
"""

from typing import List, Optional
import logging

log = logging.getLogger("traineta.adaptive_polling")


def adjust_polling_interval(
    train_no: int,
    recent_delay_readings: Optional[List[float]],
    base_interval_min: int = 12,
    fast_interval_min: int = 4,
    change_threshold_min: float = 3.0,
) -> int:
    """
    Computes optimal next polling interval (in minutes) for a specific train.

    Rules & Safety Checks:
    1. If recent_delay_readings has fewer than 2 entries (cold start/newly tracked train),
       returns base_interval_min rather than raising or comparing against nonexistent prior.
    2. Compares the most recent reading to the reading immediately before it.
    3. If abs(delta) >= change_threshold_min -> returns fast_interval_min (acceleration).
    4. If stable over recent readings -> returns base_interval_min.
    5. Always clamps the return value to [fast_interval_min, base_interval_min].
    """
    # Safety Check 1: Cold start / insufficient history
    if not recent_delay_readings or len(recent_delay_readings) < 2:
        return base_interval_min

    try:
        # Sanitize entries (filter out NaNs/Nones if any slipped through)
        valid_readings = [
            float(r) for r in recent_delay_readings 
            if r is not None and not (isinstance(r, float) and (r != r))
        ]
        if len(valid_readings) < 2:
            return base_interval_min

        latest = valid_readings[-1]
        prior = valid_readings[-2]
        delta = abs(latest - prior)

        # Acceleration trigger: significant delay surge or recovery
        if delta >= change_threshold_min:
            chosen_interval = fast_interval_min
            log.debug(
                f"Train {train_no}: delta {delta:.1f}m >= threshold {change_threshold_min}m -> "
                f"fast poll {fast_interval_min}m"
            )
        else:
            # Check stability over last 3 points if available
            if len(valid_readings) >= 3:
                prior_delta = abs(valid_readings[-2] - valid_readings[-3])
                if prior_delta < change_threshold_min:
                    chosen_interval = base_interval_min
                else:
                    # Still transitioning from recent disturbance
                    chosen_interval = int((base_interval_min + fast_interval_min) / 2)
            else:
                chosen_interval = base_interval_min

        # Safety Check 2: Clamping bounds
        return max(fast_interval_min, min(base_interval_min, chosen_interval))

    except Exception as e:
        log.warning(f"Train {train_no}: adaptive polling calculation error ({e}); using base interval.")
        return base_interval_min


if __name__ == "__main__":
    # Self-validation check
    print("Testing adjust_polling_interval...")
    assert adjust_polling_interval(12951, []) == 12, "Empty readings must return base"
    assert adjust_polling_interval(12951, [10.0]) == 12, "Single reading must return base"
    assert adjust_polling_interval(12951, [10.0, 11.0]) == 12, "Small change (1m) must return base"
    assert adjust_polling_interval(12951, [10.0, 15.0]) == 4, "Large surge (5m) must return fast"
    assert adjust_polling_interval(12951, [25.0, 20.0]) == 4, "Large recovery (5m) must return fast"
    assert adjust_polling_interval(12951, [10.0, 18.0, 18.2]) == 8, "Mid stabilization must yield stepped interval"
    print("All adaptive polling tests passed successfully!")
