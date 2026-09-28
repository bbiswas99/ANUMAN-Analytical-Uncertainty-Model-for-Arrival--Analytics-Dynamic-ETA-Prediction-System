# backend/errors.py
"""
Single source of truth for error handling and custom exception taxonomy.
Implements: Development Plan/10_Error_Handling_and_Validation.md

Every API error returns the standardized schema:
{
  "error": true,
  "error_type": "<ExceptionClassName>",
  "message": "<human-readable message>",
  "status_code": <int>
}
"""

import logging
from typing import Any, Optional
from fastapi import Request
from fastapi.responses import JSONResponse

log = logging.getLogger("traineta.errors")


# ---------------------------------------------------------------------------
# Base Exception
# ---------------------------------------------------------------------------

class TrainETAError(Exception):
    """Base class for all application-defined errors."""
    http_status: int = 500
    error_code: str = "InternalError"

    def __init__(self, message: str, detail: Any = None):
        self.message = message
        self.detail = detail
        super().__init__(message)

    def to_response(self) -> dict:
        return {
            "error": True,
            "error_type": self.error_code,
            "message": self.message,
            "status_code": self.http_status,
            # Backwards compatibility aliases
            "error_code": self.error_code,
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# Section 2: Custom Exception Taxonomy
# ---------------------------------------------------------------------------

class InvalidTrainNumberError(TrainETAError):
    """train_no doesn't exist in train_details/combined_schedule. Clean 404."""
    http_status = 404
    error_code = "InvalidTrainNumberError"

    def __init__(self, message: Optional[str] = None, train_no: Optional[int] = None):
        if not message and train_no is not None:
            message = f"Train {train_no} not found in the schedule database."
        super().__init__(message or "Train not found in the schedule database.")


class NoActiveJourneyError(TrainETAError):
    """train_no exists but has no scheduled journey for requested date/time. Clean 404."""
    http_status = 404
    error_code = "NoActiveJourneyError"

    def __init__(self, message: Optional[str] = None, train_no: Optional[int] = None, date: Optional[str] = None):
        if not message and train_no is not None:
            date_str = f" for {date}" if date else ""
            message = f"Train {train_no} has no active journey{date_str}."
        super().__init__(message or "Train has no active journey for the requested date.")


class StaleDataError(TrainETAError):
    """Latest reconciled tracking row older than threshold (default 2h). Flag, not crash."""
    http_status = 200
    error_code = "StaleDataError"

    def __init__(self, message: Optional[str] = None, train_no: Optional[int] = None, age: Optional[str] = None):
        if not message and train_no is not None:
            message = f"Live tracking data for train {train_no} is {age or 'stale'}; showing last known state."
        super().__init__(message or "Live tracking data is stale; showing last known state.")


class SourceUnavailableError(TrainETAError):
    """A scraper source fails to respond after retry budget. Logged, scraper continues."""
    http_status = 200
    error_code = "SourceUnavailableError"

    def __init__(self, source_name: str, retries: int = 2, timestamp: Optional[str] = None):
        msg = f"Source '{source_name}' unreachable after {retries} retries at {timestamp or 'current time'}."
        super().__init__(msg)


class SchemaValidationError(TrainETAError):
    """Row or file missing required column or wrong type. Fatal for pipeline run."""
    http_status = 500
    error_code = "SchemaValidationError"

    def __init__(self, column: str, file: str, expected_type: str):
        msg = f"Column '{column}' missing or wrong type in {file}; expected {expected_type}."
        super().__init__(msg)


class ModelNotLoadedError(TrainETAError):
    """Model artifact missing or corrupt at startup. Fatal / 503."""
    http_status = 503
    error_code = "ModelNotLoadedError"

    def __init__(self, message: Optional[str] = None, path: Optional[str] = None):
        if not message and path:
            message = f"Model artifact at {path} could not be loaded; service will not start."
        super().__init__(message or "Model artifact could not be loaded; service will not start.")


class OutOfRangeFeatureError(TrainETAError):
    """Computed feature value falls outside plausible physical bounds. Flagged/clipped."""
    http_status = 200
    error_code = "OutOfRangeFeatureError"

    def __init__(self, feature: str, value: Any, min_val: Any, max_val: Any, train_no: Optional[int] = None):
        train_str = f" for train {train_no}" if train_no else ""
        msg = f"Feature '{feature}' value {value} outside plausible range [{min_val},{max_val}]{train_str}."
        super().__init__(msg, detail={"feature": feature, "value": value, "range": [min_val, max_val]})


class WhatIfOverrideInvalidError(TrainETAError):
    """What-if request contains unrecognized field or out-of-range value. Clean 422."""
    http_status = 422
    error_code = "WhatIfOverrideInvalidError"


class OSMGeometryMismatchError(TrainETAError):
    """Expected route path length deviates from scheduled distance beyond tolerance (>15%)."""
    http_status = 200
    error_code = "OSMGeometryMismatchError"

    def __init__(self, section_id: str, delta_km: float):
        msg = f"Expected route for section {section_id} is {delta_km:.1f} km off the scheduled distance; flagged for review."
        super().__init__(msg)


class InsufficientDataError(TrainETAError):
    """Phase 2: fewer than minimum required joint crossings to compute precedence score (returns 0.0)."""
    http_status = 200
    error_code = "InsufficientDataError"

    def __init__(self, n: int, min_n: int, train_a: int, train_b: int, section_id: str):
        msg = f"Only {n} joint crossings observed for ({train_a}, {train_b}, {section_id}); minimum {min_n} required — confidence set to 0."
        super().__init__(msg)


class ConfigurationError(TrainETAError):
    """Required environment variable or config value is missing/invalid. Fatal / 503."""
    http_status = 503
    error_code = "ConfigurationError"

    def __init__(self, message: Optional[str] = None, var: Optional[str] = None):
        if not message and var:
            message = f"Required environment variable '{var}' is not set."
        super().__init__(message or "Required configuration value is missing or invalid.")


# ---------------------------------------------------------------------------
# Section 3: Standard FastAPI Exception Handlers
# ---------------------------------------------------------------------------

async def traineta_error_handler(request: Request, exc: TrainETAError):
    """Handler for all typed TrainETA errors."""
    log.warning(f"TrainETAError on {request.method} {request.url}: [{exc.error_code}] {exc.message}")
    return JSONResponse(
        status_code=exc.http_status,
        content=exc.to_response(),
    )


async def generic_error_handler(request: Request, exc: Exception):
    """
    Catch-all unhandled exception handler per Section 1 Principle 2 & Section 3:
    Never expose internal stack traces or raw exception text externally.
    Internal details logged server-side only; response mapped to generic 500.
    """
    log.error(f"Unhandled internal exception on {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "error_type": "InternalError",
            "message": "An unexpected error occurred. Please try again.",
            "status_code": 500,
            "error_code": "InternalError",
            "detail": None,
        },
    )


def register_error_handlers(app):
    """Registers standard handlers on the FastAPI app instance."""
    app.add_exception_handler(TrainETAError, traineta_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)
