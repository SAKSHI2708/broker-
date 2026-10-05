"""BigQuery-backed policy insert tool.

Creates a new row in the ``Policy`` table and auto-generates a
``policy_id`` in the form ``POL0100``, ``POL0101``, ...
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta
from typing import Any

from google.cloud import bigquery

logger = logging.getLogger(__name__)

POLICY_ID_START = 46
POLICY_ID_PREFIX = "POL"
POLICY_ID_WIDTH = 3
POLICY_NUMBER_PREFIX = "HO"
POLICY_NUMBER_START = 45
POLICY_NUMBER_WIDTH = 5

US_STATE_CODES = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE",
    "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI", "IDAHO": "ID",
    "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS",
    "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS",
    "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ", "NEW MEXICO": "NM", "NEW YORK": "NY",
    "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK",
    "OREGON": "OR", "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT",
    "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA", "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI", "WYOMING": "WY", "DISTRICT OF COLUMBIA": "DC",
}
VALID_STATE_CODES = set(US_STATE_CODES.values())


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


def _normalise_state_code(state: str) -> str | None:
    value = (state or "").strip().upper()
    if value in VALID_STATE_CODES:
        return value
    return US_STATE_CODES.get(value)


def _format_policy_number(state_code: str, sequence: int) -> str:
    return f"{POLICY_NUMBER_PREFIX}-{state_code}-{sequence:0{POLICY_NUMBER_WIDTH}d}"


def _next_policy_number(
    client: bigquery.Client, fq_table: str, state_code: str
) -> str:
    query = f"""
        SELECT MAX(CAST(REGEXP_EXTRACT(policy_number, r'^HO-{state_code}-([0-9]+)$') AS INT64)) AS max_num
        FROM `{fq_table}`
        WHERE REGEXP_CONTAINS(policy_number, r'^HO-{state_code}-[0-9]+$')
    """
    rows = list(client.query(query).result())
    max_num = rows[0].max_num if rows and rows[0].max_num is not None else None
    next_num = (
        max(POLICY_NUMBER_START - 1, int(max_num)) + 1
        if max_num is not None
        else POLICY_NUMBER_START
    )
    return _format_policy_number(state_code, next_num)


def create_policy(
    customer_id: str,
    property_id: str,
    coverage_amount: int,
    deductible: int,
    annual_premium: int,
    term_months: int = 12,
    policy_id: str = "",
    policy_type: str = "",
    state: str = "",
    selected_addons: str = "[]",
) -> dict[str, Any]:
    """Insert a policy row with separate internal and customer-facing IDs.

    Args:
        customer_id:     Owner customer ID.
        property_id:     Insured property ID.
        coverage_amount: Coverage amount in USD.
        deductible:      Deductible amount in USD.
        annual_premium:  Annual premium in USD.
        term_months:     Policy term in months (default 12).
        policy_id:       Optional internal policy_id; generated if empty.
        policy_type:     Selected homeowners policy (HO-3 or HO-5).
        state:           Insured property's state name or two-letter code.
        selected_addons: JSON list returned by ``calculate_final_premium``.

    Returns:
        A dict with:
          - status: "SUCCESS" | "ERROR"
          - message: human-readable message
          - policy_id: the newly generated ID (on SUCCESS)
          - policy_number: customer-facing number such as HO-TX-00045
          - policy: dict of the inserted row (on SUCCESS)
    """
    customer_id = (customer_id or "").strip()
    property_id = (property_id or "").strip()
    policy_id = (policy_id or "").strip().upper()
    policy_type = (policy_type or "").strip().upper()
    state_code = _normalise_state_code(state)

    if not customer_id:
        return {"status": "ERROR", "message": "customer_id is required."}
    if not property_id:
        return {"status": "ERROR", "message": "property_id is required."}
    if policy_type not in {"HO-3", "HO-5"}:
        return {"status": "ERROR", "message": "policy_type must be HO-3 or HO-5."}
    if state_code is None:
        return {"status": "ERROR", "message": "state must be a valid US state name or two-letter code."}
    if int(term_months) != 12:
        return {"status": "ERROR", "message": "Homeowners policies must have a 12-month term."}
    try:
        addons = json.loads(selected_addons or "[]")
    except (TypeError, json.JSONDecodeError):
        return {"status": "ERROR", "message": "selected_addons must be a JSON list."}
    if not isinstance(addons, list) or any(
        not isinstance(addon, dict)
        or not isinstance(addon.get("name"), str)
        or not addon["name"].strip()
        or not isinstance(addon.get("annual_price"), int)
        or addon["annual_price"] < 0
        for addon in addons
    ):
        return {
            "status": "ERROR",
            "message": "Each selected add-on must have a name and non-negative integer annual_price.",
        }
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
        policy_number = _next_policy_number(client, fq_table, state_code)

        effective_date = date.today()
        expiration_date = _one_year_later(effective_date)

        row = {
            "policy_id": policy_id,
            "policy_number": policy_number,
            "customer_id": customer_id,
            "property_id": property_id,
            "policy_type": policy_type,
            "policy_status": "ACTIVE",
            "effective_date": effective_date.isoformat(),
            "expiration_date": expiration_date.isoformat(),
            "policy_term_months": 12,
            "deductible_amount": int(deductible) if deductible is not None else None,
            "annual_premium": int(annual_premium) if annual_premium is not None else None,
            "coverage_amount": int(coverage_amount) if coverage_amount is not None else None,
            "selected_addons": json.dumps(addons, separators=(",", ":")),
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
            "policy_number": policy_number,
            "policy": row,
        }

    except Exception as e:  # noqa: BLE001
        logger.exception("BigQuery policy insert failed")
        return {"status": "ERROR", "message": f"Failed to insert policy: {e}"}
