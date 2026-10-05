"""BigQuery-backed lookup for the query-time property table."""

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
        "table": os.getenv("BQ_QUERY_PROPERTY_TABLE", "query_property_details"),
    }


def get_query_property_by_query_id(query_id: str) -> dict[str, Any]:
    """Fetch all query-time property rows for a given Query ID.

    Returns:
        A dict with:
          - status: "SUCCESS" | "NOT_FOUND" | "ERROR"
          - message: human-readable message
          - properties: list of dicts (column -> value) on SUCCESS
    """
    query_id = (query_id or "").strip()
    if not query_id:
        return {"status": "ERROR", "message": "query_id is required."}

    cfg = _cfg()
    fq_table = f"`{cfg['project']}.{cfg['dataset']}.{cfg['table']}`"
    query = f"SELECT * FROM {fq_table} WHERE {QUERY_ID_COLUMN} = @query_id"

    try:
        client = bigquery.Client(project=cfg["project"])
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("query_id", "STRING", query_id),
            ]
        )
        logger.info("Running query_property_details lookup for query_id=%s", query_id)
        rows = list(client.query(query, job_config=job_config).result())

        if not rows:
            return {
                "status": "NOT_FOUND",
                "message": f"No query-time property found for Query ID '{query_id}'.",
            }

        properties = [
            {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dict(r).items()}
            for r in rows
        ]

        return {
            "status": "SUCCESS",
            "message": f"Retrieved {len(properties)} query-time property record(s).",
            "properties": properties,
        }

    except Exception as e:  # noqa: BLE001
        logger.exception("BigQuery query_property lookup failed")
        return {"status": "ERROR", "message": f"Failed to query BigQuery: {e}"}