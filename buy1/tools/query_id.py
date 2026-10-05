"""Query ID generator tool for the Buy Policy agent."""

from __future__ import annotations

import logging
import os
from typing import Any

from google.cloud import bigquery

logger = logging.getLogger(__name__)

QUERY_ID_START = 100
QUERY_ID_PREFIX = "QUERY"
QUERY_ID_WIDTH = 4


def _cfg() -> dict[str, str]:
    """Read BigQuery config from environment (with sensible defaults)."""
    return {
        "project": os.getenv("BQ_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "gcp-app-builder")),
        "dataset": os.getenv("BQ_DATASET", "Broker_Productivity"),
        "table": os.getenv("BQ_QUERY_CUSTOMER_TABLE", "query_customer"),
    }


def generate_query_id() -> dict[str, Any]:
    """Generate the next auto-incremented Query ID for a new-user registration.

    Format: ``QUERY0100``, ``QUERY0101``, ``QUERY0102``, ...

    The generator queries the ``query_customer`` table's ``query_id``
    column for the highest existing sequence number and returns
    ``max + 1``. If no matching IDs exist yet, it starts at
    ``QUERY0100``.

    Returns:
        A dict with:
          - status: "SUCCESS" | "ERROR"
          - message: human-readable message
          - query_id: newly generated ID (on SUCCESS)
    """
    cfg = _cfg()
    fq_table = f"`{cfg['project']}.{cfg['dataset']}.{cfg['table']}`"

    query = f"""
        SELECT MAX(CAST(SUBSTR(query_id, {len(QUERY_ID_PREFIX) + 1}) AS INT64)) AS max_num
        FROM {fq_table}
        WHERE REGEXP_CONTAINS(query_id, r'^{QUERY_ID_PREFIX}[0-9]+$')
    """

    try:
        client = bigquery.Client(project=cfg["project"])
        rows = list(client.query(query).result())
        max_num = rows[0].max_num if rows and rows[0].max_num is not None else 0
        next_num = max(int(max_num), QUERY_ID_START - 1) + 1
        query_id = f"{QUERY_ID_PREFIX}{next_num:0{QUERY_ID_WIDTH}d}"
        logger.info("Generated next query_id=%s (previous max=%s)", query_id, max_num)
        return {
            "status": "SUCCESS",
            "message": "Query ID generated.",
            "query_id": query_id,
        }

    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to generate next query_id")
        return {
            "status": "ERROR",
            "message": f"Failed to generate query_id: {e}",
        }
