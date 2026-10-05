"""BigQuery-backed insert tool for the query-time property table.

Query-time property details are stored in ``query_property_details``
and are NOT the same as a real Property record. A row is promoted to
the ``Property`` table only when the user actually purchases a policy.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from google.cloud import bigquery

logger = logging.getLogger(__name__)


def _cfg() -> dict[str, str]:
    return {
        "project": os.getenv("BQ_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "gcp-app-builder")),
        "dataset": os.getenv("BQ_DATASET", "Broker_Productivity"),
        "table": os.getenv("BQ_QUERY_PROPERTY_TABLE", "query_property_details"),
    }


def create_query_property(
    query_id: str,
    property_id: str,
    property_address: str,
    city: str,
    state: str,
    zip_code: int,
    property_type: str,
    estimated_value: int,
    year_built: int,
    square_footage: int,
    roof_age: int,
    roof_material: str,
    construction_type: str,
    number_of_floors: int,
) -> dict[str, Any]:
    """Insert a new row into the ``query_property_details`` table.

    Args:
        query_id:          Query ID this property belongs to.
        property_id:       User-supplied plot number.
        property_address:  Street address.
        city:              City the property is located in.
        state:             US state (2-letter code or full name).
        zip_code:          5-digit ZIP code (integer).
        property_type:     e.g. "Single Family", "Condo".
        estimated_value:   Estimated value in USD (integer).
        year_built:        4-digit year the property was built.
        square_footage:    Total square footage.
        roof_age:          Age of the roof in years.
        roof_material:     e.g. "Asphalt Shingle", "Tile", "Metal".
        construction_type: e.g. "Wood Frame", "Brick", "Concrete".
        number_of_floors:  Number of floors / stories.

    Returns:
        A dict with:
          - status: "SUCCESS" | "ERROR"
          - message: human-readable message
          - query_id: the query_id stored (on SUCCESS)
          - property_id: the plot number stored (on SUCCESS)
          - query_property: dict of the inserted row (on SUCCESS)
    """
    query_id = (query_id or "").strip()
    property_id = (property_id or "").strip()

    if not query_id:
        return {"status": "ERROR", "message": "query_id is required."}
    if not property_id:
        return {"status": "ERROR", "message": "property_id (plot number) is required."}

    cfg = _cfg()
    fq_table = f"{cfg['project']}.{cfg['dataset']}.{cfg['table']}"

    row = {
        "query_id": query_id,
        "property_id": property_id,
        "property_address": (property_address or "").strip(),
        "city": (city or "").strip(),
        "state": (state or "").strip(),
        "zip_code": int(zip_code) if zip_code is not None else None,
        "property_type": (property_type or "").strip(),
        "estimated_value": int(estimated_value) if estimated_value is not None else None,
        "year_built": int(year_built) if year_built is not None else None,
        "square_footage": int(square_footage) if square_footage is not None else None,
        "roof_age": int(roof_age) if roof_age is not None else None,
        "roof_material": (roof_material or "").strip(),
        "construction_type": (construction_type or "").strip(),
        "number_of_floors": int(number_of_floors) if number_of_floors is not None else None,
    }

    try:
        client = bigquery.Client(project=cfg["project"])
        logger.info("Inserting new query_property_details row: query_id=%s property_id=%s", query_id, property_id)
        errors = client.insert_rows_json(fq_table, [row])
        if errors:
            logger.error("BigQuery insert returned errors: %s", errors)
            return {"status": "ERROR", "message": f"BigQuery insert failed: {errors}"}

        return {
            "status": "SUCCESS",
            "message": "Query-time property details saved.",
            "query_id": query_id,
            "property_id": property_id,
            "query_property": row,
        }

    except Exception as e:  # noqa: BLE001
        logger.exception("BigQuery query_property insert failed")
        return {"status": "ERROR", "message": f"Failed to insert query_property: {e}"}
