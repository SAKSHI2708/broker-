"""
Insert Tool for Broker Productivity Agent.

Used for inserting audit logs into the 'Audit' table in Broker_Productivity dataset.

Audit Table Schema:
    - policy_id (STRING)
    - table_name (STRING)
    - column_name (STRING)
    - old_value (STRING)
    - new_value (STRING)
    - performed_at (TIMESTAMP)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from google.cloud import bigquery


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ID = "gcp-app-builder"
DATASET_ID = "Broker_Productivity"

client = bigquery.Client(
    project=PROJECT_ID
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ============================================================
# ALLOWED INSERT TABLES
# ============================================================

ALLOWED_INSERT_TABLES = {
    "audit": "Audit",
    "audit_log": "Audit",
    "claims": "Claims",
    "claim": "Claims",
}


# ============================================================
# RESPONSE HELPERS
# ============================================================

def success_response(
    data: Any,
) -> Dict:
    return {
        "status": "SUCCESS",
        "data": data,
    }


def error_response(
    message: str,
) -> Dict:
    return {
        "status": "FAILED",
        "message": message,
    }


# ============================================================
# JSON SERIALIZATION
# ============================================================

def serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


# ============================================================
# INSERT AUDIT LOG HELPER
# ============================================================

def log_audit_entry(
    policy_id: str,
    table_name: str,
    column_name: str,
    old_value: Any,
    new_value: Any,
) -> Dict:
    """
    Direct helper to insert audit records into the Audit table.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    
    row = {
        "policy_id": str(policy_id) if policy_id else None,
        "table_name": str(table_name) if table_name else None,
        "column_name": str(column_name) if column_name else None,
        "old_value": str(old_value) if old_value is not None else None,
        "new_value": str(new_value) if new_value is not None else None,
        "performed_at": now_iso,
    }

    table_ref = f"{PROJECT_ID}.{DATASET_ID}.Audit"

    try:
        errors = client.insert_rows_json(table_ref, [row])
        if errors:
            logger.error("Audit log insertion errors: %s", errors)
            return error_response(f"Audit insert failed: {errors}")
        
        logger.info("Audit log inserted successfully: %s", row)
        return success_response({"inserted_row": row})
    except Exception as e:
        logger.exception("Failed to insert audit log")
        return error_response(f"Audit log insertion failed: {str(e)}")


# ============================================================
# INSERT TABLE DATA TOOL
# ============================================================

def insert_table_data(
    entity: str,
    data: Dict,
) -> Dict:
    """
    Insert record into supported table (e.g. Audit).

    Parameters
    ----------
    entity:
        Target table ('audit' or 'claims').
    data:
        Dictionary containing field values to insert.
    """
    logger.info("=" * 70)
    logger.info("INSERT TABLE DATA")
    logger.info("Entity : %s", entity)
    logger.info("Data   : %s", data)
    logger.info("=" * 70)

    try:
        entity = entity.lower().strip()

        if entity not in ALLOWED_INSERT_TABLES:
            raise ValueError(f"Insert into '{entity}' is not allowed.")

        table_name = ALLOWED_INSERT_TABLES[entity]

        if table_name == "Audit":
            policy_id = data.get("policy_id")
            tbl = data.get("table_name")
            col = data.get("column_name")
            old_v = data.get("old_value")
            new_v = data.get("new_value")
            return log_audit_entry(policy_id, tbl, col, old_v, new_v)

        # General insert for other tables
        table_ref = f"{PROJECT_ID}.{DATASET_ID}.{table_name}"
        row = {k: serialize_value(v) for k, v in data.items()}

        errors = client.insert_rows_json(table_ref, [row])
        if errors:
            raise ValueError(f"BigQuery insert failed: {errors}")

        logger.info("Insert successful into %s", table_name)
        return success_response({
            "table": table_name,
            "entity": entity,
            "inserted_data": row,
        })

    except ValueError as e:
        logger.error(str(e))
        return error_response(str(e))
    except Exception as e:
        logger.exception("Insert failed")
        return error_response(f"Unexpected error: {str(e)}")


__all__ = [
    "insert_table_data",
    "log_audit_entry",
]
