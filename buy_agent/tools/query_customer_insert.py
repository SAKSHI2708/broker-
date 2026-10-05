"""BigQuery-backed insert tool for the query-time customer table.

Query-time customer details are stored in the ``query_customer`` table
and are NOT the same as a real Customer record. A row is promoted to
the ``Customer`` table only when the user actually purchases a policy.
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
        "table": os.getenv("BQ_QUERY_CUSTOMER_TABLE", "query_customer"),
    }


def create_query_customer(
    query_id: str,
    full_name: str,
    gender: str,
    state: str,
    email: str,
    phone: str,
) -> dict[str, Any]:
    """Insert a new row into the ``query_customer`` table.

    This is the *query-time* customer capture. No ``customer_id`` is
    assigned here — that only happens when the user actually buys a
    policy (see ``create_customer``).

    Args:
        query_id:  Query ID issued to this user (must already exist).
        full_name: User's full name.
        gender:    User's gender.
        state:     US state.
        email:     Email address.
        phone:     Phone number.

    Returns:
        A dict with:
          - status: "SUCCESS" | "ERROR"
          - message: human-readable message
          - query_id: the query_id stored (on SUCCESS)
          - query_customer: dict of the inserted row (on SUCCESS)
    """
    query_id = (query_id or "").strip()
    full_name = (full_name or "").strip()
    gender = (gender or "").strip()
    state = (state or "").strip()
    email = (email or "").strip()
    phone = (phone or "").strip()

    missing = [
        name
        for name, value in [
            ("query_id", query_id),
            ("full_name", full_name),
            ("gender", gender),
            ("state", state),
            ("email", email),
            ("phone", phone),
        ]
        if not value
    ]
    if missing:
        return {
            "status": "ERROR",
            "message": f"Missing required field(s): {', '.join(missing)}.",
        }

    cfg = _cfg()
    fq_table = f"{cfg['project']}.{cfg['dataset']}.{cfg['table']}"

    row = {
        "query_id": query_id,
        "full_name": full_name,
        "gender": gender,
        "state": state,
        "email": email,
        "phone": phone,
    }

    try:
        client = bigquery.Client(project=cfg["project"])
        logger.info("Inserting new query_customer row: query_id=%s", query_id)
        errors = client.insert_rows_json(fq_table, [row])
        if errors:
            logger.error("BigQuery insert returned errors: %s", errors)
            return {
                "status": "ERROR",
                "message": f"BigQuery insert failed: {errors}",
            }

        return {
            "status": "SUCCESS",
            "message": "Query-time customer details saved.",
            "query_id": query_id,
            "query_customer": row,
        }

    except Exception as e:  # noqa: BLE001
        logger.exception("BigQuery query_customer insert failed")
        return {
            "status": "ERROR",
            "message": f"Failed to insert query_customer: {e}",
        }