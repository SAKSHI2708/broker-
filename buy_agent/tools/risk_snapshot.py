"""Stable, source-backed risk snapshots for a property address."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

from google.cloud import storage


RISK_LEVELS = {"Low", "Medium", "High"}
RISK_NAMES = (
    "flood",
    "wind",
    "hail",
    "wildfire",
    "earthquake",
    "tornado",
    "lightning",
    "crime",
)


def _bucket_name() -> str:
    return os.getenv("POLICY_PHOTOS_BUCKET", "").removeprefix("gs://").rstrip("/")


def _snapshot_name(property_address: str, city: str, state: str, zip_code: str) -> str:
    location = "|".join(
        value.strip().upper() for value in (property_address, city, state, str(zip_code))
    )
    location_hash = hashlib.sha256(location.encode("utf-8")).hexdigest()
    return f"risk_snapshots/{location_hash}.json"


def get_risk_snapshot(
    property_address: str, city: str, state: str, zip_code: str
) -> dict[str, Any]:
    """Return the previously verified risk snapshot for a property, if one exists."""
    bucket_name = _bucket_name()
    if not bucket_name:
        return {"status": "ERROR", "message": "POLICY_PHOTOS_BUCKET is not configured."}

    object_name = _snapshot_name(property_address, city, state, zip_code)
    try:
        blob = storage.Client().bucket(bucket_name).blob(object_name)
        if not blob.exists():
            return {"status": "NOT_FOUND", "message": "No saved risk snapshot for this property."}
        return {
            "status": "SUCCESS",
            "message": "Using the saved risk snapshot for this property.",
            "snapshot": json.loads(blob.download_as_text()),
        }
    except Exception as error:  # noqa: BLE001
        return {"status": "ERROR", "message": f"Failed to load risk snapshot: {error}"}


def save_risk_snapshot(
    property_address: str,
    city: str,
    state: str,
    zip_code: str,
    flood_risk: str,
    wind_risk: str,
    hail_risk: str,
    wildfire_risk: str,
    earthquake_risk: str,
    tornado_risk: str,
    lightning_risk: str,
    crime_risk: str,
    flood_source_url: str,
    wind_source_url: str,
    hail_source_url: str,
    wildfire_source_url: str,
    earthquake_source_url: str,
    tornado_source_url: str,
    lightning_source_url: str,
    crime_source_url: str,
) -> dict[str, Any]:
    """Save the first verified risk result and preserve it for future quote runs."""
    bucket_name = _bucket_name()
    if not bucket_name:
        return {"status": "ERROR", "message": "POLICY_PHOTOS_BUCKET is not configured."}

    risks = {
        "flood": flood_risk,
        "wind": wind_risk,
        "hail": hail_risk,
        "wildfire": wildfire_risk,
        "earthquake": earthquake_risk,
        "tornado": tornado_risk,
        "lightning": lightning_risk,
        "crime": crime_risk,
    }
    source_urls = {
        "flood": flood_source_url,
        "wind": wind_source_url,
        "hail": hail_source_url,
        "wildfire": wildfire_source_url,
        "earthquake": earthquake_source_url,
        "tornado": tornado_source_url,
        "lightning": lightning_source_url,
        "crime": crime_source_url,
    }
    invalid = [name for name in RISK_NAMES if risks[name].strip().title() not in RISK_LEVELS or not source_urls[name].strip()]
    if invalid:
        return {
            "status": "ERROR",
            "message": f"Each risk needs Low, Medium, or High plus a source URL. Invalid: {', '.join(invalid)}.",
        }

    snapshot = {
        "location": {
            "property_address": property_address.strip(),
            "city": city.strip(),
            "state": state.strip(),
            "zip_code": str(zip_code).strip(),
        },
        "risks": {name: risks[name].strip().title() for name in RISK_NAMES},
        "source_urls": {name: source_urls[name].strip() for name in RISK_NAMES},
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "version": 1,
    }
    object_name = _snapshot_name(property_address, city, state, zip_code)
    try:
        blob = storage.Client().bucket(bucket_name).blob(object_name)
        blob.upload_from_string(
            json.dumps(snapshot), content_type="application/json", if_generation_match=0
        )
        return {"status": "SUCCESS", "message": "Risk snapshot saved.", "snapshot": snapshot}
    except Exception as error:  # noqa: BLE001
        if "PreconditionFailed" in type(error).__name__:
            return get_risk_snapshot(property_address, city, state, zip_code)
        return {"status": "ERROR", "message": f"Failed to save risk snapshot: {error}"}