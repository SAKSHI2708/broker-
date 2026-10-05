"""BigQuery-backed customer insert tool for the Buy Policy agent."""

from __future__ import annotations

import logging
import os
from typing import Any

from google.cloud import bigquery

logger = logging.getLogger(__name__)

# First customer ID to hand out if the table currently has none higher.
CUSTOMER_ID_START = 100
CUSTOMER_ID_PREFIX = "CUST"
CUSTOMER_ID_WIDTH = 4


def _cfg() -> dict[str, str]:
    """Read BigQuery config from environment (with sensible defaults)."""
    return {
        "project": os.getenv("BQ_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "gcp-app-builder")),
        "dataset": os.getenv("BQ_DATASET", "Broker_Productivity"),
        "table": os.getenv("BQ_CUSTOMER_TABLE", "Customer"),
    }


def _next_customer_id(client: bigquery.Client, fq_table: str) -> str:
    """Return the next auto-incremented customer ID (e.g. CUST0100, CUST0101)."""
    query = f"""
        SELECT MAX(CAST(SUBSTR(customer_id, {len(CUSTOMER_ID_PREFIX) + 1}) AS INT64)) AS max_num
        FROM `{fq_table}`
        WHERE REGEXP_CONTAINS(customer_id, r'^{CUSTOMER_ID_PREFIX}[0-9]+$')
    """
    rows = list(client.query(query).result())
    max_num = rows[0].max_num if rows and rows[0].max_num is not None else 0
    next_num = max(int(max_num), CUSTOMER_ID_START - 1) + 1
    return f"{CUSTOMER_ID_PREFIX}{next_num:0{CUSTOMER_ID_WIDTH}d}"


def create_customer(
    full_name: str,
    gender: str,
    state: str,
    email: str,
    phone: str,
    query_id: str,
    customer_id: str = "",
) -> dict[str, Any]:
    """Insert a new customer record into BigQuery.

    Args:
        full_name:   Customer's full name.
        gender:      Customer's gender (e.g. "Male", "Female", "Other").
        state:       US state the customer resides in.
        email:       Customer's email address.
        phone:       Customer's phone number.
        query_id:    Query ID issued to this customer at the start of
                     the new-user registration flow. Stored alongside
                     the customer so they can later retrieve their
                     profile by Query ID.
        customer_id: Optional pre-supplied customer ID. If empty, a new
                     unique ID (CUST + 8 hex chars) is generated.

    Returns:
        A dict with:
          - status: "SUCCESS" | "ERROR"
          - message: human-readable message
          - customer_id: the ID of the newly created customer (on SUCCESS)
          - query_id: the Query ID stored on the row (on SUCCESS)
          - customer: dict of the inserted row (on SUCCESS)
    """
    full_name = (full_name or "").strip()
    gender = (gender or "").strip()
    state = (state or "").strip()
    email = (email or "").strip()
    phone = (phone or "").strip()
    query_id = (query_id or "").strip()
    customer_id = (customer_id or "").strip()

    missing = [
        name
        for name, value in [
            ("full_name", full_name),
            ("gender", gender),
            ("state", state),
            ("email", email),
            ("phone", phone),
            ("query_id", query_id),
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

    try:
        client = bigquery.Client(project=cfg["project"])
        if not customer_id:
            customer_id = _next_customer_id(client, fq_table)

        row = {
            "customer_id": customer_id,
            "query_id": query_id,
            "full_name": full_name,
            "gender": gender,
            "state": state,
            "email": email,
            "phone": phone,
        }

        logger.info("Inserting new customer into BigQuery: %s (query_id=%s)", customer_id, query_id)
        errors = client.insert_rows_json(fq_table, [row])
        if errors:
            logger.error("BigQuery insert returned errors: %s", errors)
            return {
                "status": "ERROR",
                "message": f"BigQuery insert failed: {errors}",
            }

        return {
            "status": "SUCCESS",
            "message": "Customer profile created.",
            "customer_id": customer_id,
            "query_id": query_id,
            "customer": row,
        }

    except Exception as e:  # noqa: BLE001
        logger.exception("BigQuery customer insert failed")
        return {
            "status": "ERROR",
            "message": f"Failed to insert customer: {e}",
        }