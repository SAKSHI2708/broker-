"""BigQuery-backed lookup for the query-time customer table."""

from __future__ import annotations

import logging
import os
from typing import Any

from google.cloud import bigquery

logger = logging.getLogger(__name__)

QUERY_ID_COLUMN = "query_id"


def _cfg() -> dict[str, str]:
    return {
        "project": os.getenv("BQ_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "gcp-app-builder")),
        "dataset": os.getenv("BQ_DATASET", "Broker_Productivity"),
        "table": os.getenv("BQ_QUERY_CUSTOMER_TABLE", "query_customer"),
    }


def get_query_customer_by_query_id(query_id: str) -> dict[str, Any]:
    """Fetch a query-time customer record by Query ID.

    Returns:
        A dict with:
          - status: "SUCCESS" | "NOT_FOUND" | "ERROR"
          - message: human-readable message
          - query_customer: dict of column -> value (only on SUCCESS)
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
        logger.info("Running query_customer lookup for query_id=%s", query_id)
        rows = list(client.query(query, job_config=job_config).result())

        if not rows:
            return {
                "status": "NOT_FOUND",
                "message": f"No query-time customer found for Query ID '{query_id}'.",
            }

        row = rows[0]
        customer = {
            k: (v.isoformat() if hasattr(v, "isoformat") else v)
            for k, v in dict(row).items()
        }

        return {
            "status": "SUCCESS",
            "message": "Query-time customer details retrieved.",
            "query_customer": customer,
        }

    except Exception as e:  # noqa: BLE001
        logger.exception("BigQuery query_customer lookup failed")
        return {
            "status": "ERROR",
            "message": f"Failed to query BigQuery: {e}",
        }
