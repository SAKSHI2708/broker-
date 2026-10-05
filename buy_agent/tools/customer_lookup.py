"""BigQuery-backed customer lookup tool for the Buy Policy agent."""

from __future__ import annotations

import logging
import os
from typing import Any

from google.cloud import bigquery

logger = logging.getLogger(__name__)

# Fixed column name used to look up a customer in BigQuery.
CUSTOMER_ID_COLUMN = "customer_id"


def _cfg() -> dict[str, str]:
    """Read BigQuery config from environment (with sensible defaults)."""
    return {
        "project": os.getenv("BQ_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "gcp-app-builder")),
        "dataset": os.getenv("BQ_DATASET", "Broker_Productivity"),
        "table": os.getenv("BQ_CUSTOMER_TABLE", "Customer"),
        "id_column": CUSTOMER_ID_COLUMN,
    }


def get_customer_by_id(customer_id: str) -> dict[str, Any]:
    """Fetch a customer profile from BigQuery by customer ID.

    Args:
        customer_id: The customer identifier supplied by the user.

    Returns:
        A dict with:
          - status: "SUCCESS" | "NOT_FOUND" | "ERROR"
          - message: human-readable message
          - customer: dict of column -> value (only on SUCCESS)
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
        f"WHERE {cfg['id_column']} = @customer_id LIMIT 1"
    )

    try:
        client = bigquery.Client(project=cfg["project"])
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("customer_id", "STRING", customer_id),
            ]
        )
        logger.info("Running BigQuery customer lookup for id=%s", customer_id)
        rows = list(client.query(query, job_config=job_config).result())

        if not rows:
            return {
                "status": "NOT_FOUND",
                "message": f"No customer found for ID '{customer_id}'.",
            }

        # Convert Row -> JSON-safe dict
        row = rows[0]
        customer = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dict(row).items()}

        return {
            "status": "SUCCESS",
            "message": "Customer profile retrieved.",
            "customer": customer,
        }

    except Exception as e:  # noqa: BLE001
        logger.exception("BigQuery lookup failed")
        return {
            "status": "ERROR",
            "message": f"Failed to query BigQuery: {e}",
        }


QUERY_ID_COLUMN = "query_id"


def get_customer_by_query_id(query_id: str) -> dict[str, Any]:
    """Fetch a customer profile from BigQuery by their Query ID.

    Args:
        query_id: The query identifier issued when the customer first
                  registered as a new user.

    Returns:
        A dict with:
          - status: "SUCCESS" | "NOT_FOUND" | "ERROR"
          - message: human-readable message
          - customer: dict of column -> value (only on SUCCESS)
    """
    query_id = (query_id or "").strip()
    if not query_id:
        return {
            "status": "ERROR",
            "message": "query_id is required.",
        }

    cfg = _cfg()
    fq_table = f"`{cfg['project']}.{cfg['dataset']}.{cfg['table']}`"
    query = (
        f"SELECT * FROM {fq_table} "
        f"WHERE {QUERY_ID_COLUMN} = @query_id LIMIT 1"
    )

    try:
        client = bigquery.Client(project=cfg["project"])
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("query_id", "STRING", query_id),
            ]
        )
        logger.info("Running BigQuery customer lookup for query_id=%s", query_id)
        rows = list(client.query(query, job_config=job_config).result())

        if not rows:
            return {
                "status": "NOT_FOUND",
                "message": f"No customer found for Query ID '{query_id}'.",
            }

        row = rows[0]
        customer = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dict(row).items()}

        return {
            "status": "SUCCESS",
            "message": "Customer profile retrieved.",
            "customer": customer,
        }

    except Exception as e:  # noqa: BLE001
        logger.exception("BigQuery lookup by query_id failed")
        return {
            "status": "ERROR",
            "message": f"Failed to query BigQuery: {e}",
        }