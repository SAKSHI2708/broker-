"""BigQuery-backed policy insert tool.

Creates a new row in the ``Policy`` table and auto-generates a
``policy_id`` in the form ``POL0100``, ``POL0101``, ...
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Any

from google.cloud import bigquery

logger = logging.getLogger(__name__)

POLICY_ID_START = 46
POLICY_ID_PREFIX = "POL"
POLICY_ID_WIDTH = 3


def _one_year_later(effective_date: date) -> date:
    """Return the calendar anniversary, using February 28 for leap-day policies."""
    try:
        return effective_date.replace(year=effective_date.year + 1)
    except ValueError:
        return effective_date.replace(year=effective_date.year + 1, day=28)


def _cfg() -> dict[str, str]:
    return {
        "project": os.getenv("BQ_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "gcp-app-builder")),
        "dataset": os.getenv("BQ_DATASET", "Broker_Productivity"),
        "table": os.getenv("BQ_POLICY_TABLE", "Policy"),
    }


def _next_policy_id(client: bigquery.Client, fq_table: str) -> str:
    query = f"""
        SELECT MAX(CAST(SUBSTR(policy_id, {len(POLICY_ID_PREFIX) + 1}) AS INT64)) AS max_num
        FROM `{fq_table}`
        WHERE REGEXP_CONTAINS(policy_id, r'^{POLICY_ID_PREFIX}[0-9]+$')
    """
    rows = list(client.query(query).result())
    max_num = rows[0].max_num if rows and rows[0].max_num is not None else 0
    next_num = max(int(max_num), POLICY_ID_START - 1) + 1
    return f"{POLICY_ID_PREFIX}{next_num:0{POLICY_ID_WIDTH}d}"


def create_policy(
    customer_id: str,
    property_id: str,
    coverage_amount: int,
    deductible: int,
    annual_premium: int,
    term_months: int = 12,
    policy_id: str = "",
) -> dict[str, Any]:
    """Insert a new policy row and auto-generate a policy_id.

    Args:
        customer_id:     Owner customer ID.
        property_id:     Insured property ID.
        coverage_amount: Coverage amount in USD.
        deductible:      Deductible amount in USD.
        annual_premium:  Annual premium in USD.
        term_months:     Policy term in months (default 12).
        policy_id:       Optional pre-reserved policy ID for uploaded photos.

    Returns:
        A dict with:
          - status: "SUCCESS" | "ERROR"
          - message: human-readable message
          - policy_id: the newly generated ID (on SUCCESS)
          - policy: dict of the inserted row (on SUCCESS)
    """
    customer_id = (customer_id or "").strip()
    property_id = (property_id or "").strip()
    policy_id = (policy_id or "").strip().upper()

    if not customer_id:
        return {"status": "ERROR", "message": "customer_id is required."}
    if not property_id:
        return {"status": "ERROR", "message": "property_id is required."}
    if policy_id and (
        not policy_id.startswith(POLICY_ID_PREFIX)
        or not policy_id[len(POLICY_ID_PREFIX) :].isdigit()
    ):
        return {"status": "ERROR", "message": "policy_id must use the POL number format."}

    cfg = _cfg()
    fq_table = f"{cfg['project']}.{cfg['dataset']}.{cfg['table']}"

    try:
        client = bigquery.Client(project=cfg["project"])
        if not policy_id:
            policy_id = _next_policy_id(client, fq_table)

        effective_date = date.today()
        expiration_date = _one_year_later(effective_date)

        row = {
            "policy_id": policy_id,
            "customer_id": customer_id,
            "property_id": property_id,
            "coverage_amount": int(coverage_amount) if coverage_amount is not None else None,
            "deductible": int(deductible) if deductible is not None else None,
            "annual_premium": int(annual_premium) if annual_premium is not None else None,
            "effective_date": effective_date.isoformat(),
            "expiration_date": expiration_date.isoformat(),
            "status": "ACTIVE",
        }

        logger.info("Inserting new policy into BigQuery: %s", policy_id)
        errors = client.insert_rows_json(fq_table, [row])
        if errors:
            logger.error("BigQuery insert returned errors: %s", errors)
            return {"status": "ERROR", "message": f"BigQuery insert failed: {errors}"}

        return {
            "status": "SUCCESS",
            "message": "Policy created.",
            "policy_id": policy_id,
            "policy": row,
        }

    except Exception as e:  # noqa: BLE001
        logger.exception("BigQuery policy insert failed")
        return {"status": "ERROR", "message": f"Failed to insert policy: {e}"}