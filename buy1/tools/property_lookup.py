"""BigQuery-backed property lookup tool for the Buy Policy agent."""

from __future__ import annotations

import logging
import os
from typing import Any

from google.cloud import bigquery

logger = logging.getLogger(__name__)

# Fixed column name on the Property table that links to a Customer.
CUSTOMER_ID_COLUMN = "customer_id"


def _cfg() -> dict[str, str]:
    """Read BigQuery config from environment (with sensible defaults)."""
    return {
        "project": os.getenv("BQ_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "gcp-app-builder")),
        "dataset": os.getenv("BQ_DATASET", "Broker_Productivity"),
        "table": os.getenv("BQ_PROPERTY_TABLE", "Property"),
        "id_column": CUSTOMER_ID_COLUMN,
    }


def get_properties_by_customer(customer_id: str) -> dict[str, Any]:
    """Fetch all properties owned by a customer from BigQuery.

    Args:
        customer_id: The customer identifier whose properties to look up.

    Returns:
        A dict with:
          - status: "SUCCESS" | "NOT_FOUND" | "ERROR"
          - message: human-readable message
          - properties: list of dicts (column -> value) on SUCCESS
    """
    customer_id = (customer_id or "").strip()
    if not customer_id:
        return {
            "status": "ERROR",
            "message": "customer_id is required.",
        }

    cfg = _cfg()
    fq_table = f"`{cfg['project']}.{cfg['dataset']}.{cfg['table']}`"
    query = (
        f"SELECT * FROM {fq_table} "
        f"WHERE {cfg['id_column']} = @customer_id"
    )

    try:
        client = bigquery.Client(project=cfg["project"])
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("customer_id", "STRING", customer_id),
            ]
        )
        logger.info("Running BigQuery property lookup for customer_id=%s", customer_id)
        rows = list(client.query(query, job_config=job_config).result())

        if not rows:
            return {
                "status": "NOT_FOUND",
                "message": f"No properties found for customer ID '{customer_id}'.",
            }

        properties = [
            {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dict(r).items()}
            for r in rows
        ]

        return {
            "status": "SUCCESS",
            "message": f"Retrieved {len(properties)} property record(s).",
            "properties": properties,
        }

    except Exception as e:  # noqa: BLE001
        logger.exception("BigQuery property lookup failed")
        return {
            "status": "ERROR",
            "message": f"Failed to query BigQuery: {e}",
        }
