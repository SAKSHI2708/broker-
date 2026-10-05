from google.cloud import bigquery
from google.adk.tools import ToolContext
from datetime import date
import os
import uuid
import time
from google.api_core.exceptions import BadRequest

from decimal import Decimal
from datetime import date, datetime

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
DATASET = "Broker_Productivity"

client = bigquery.Client(project=PROJECT_ID)


def convert_to_json(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: convert_to_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_to_json(i) for i in obj]
    return obj


def parse_date_flexible(date_str: str) -> date:
    """
    Parse date from multiple formats:
    - ISO format: '2026-09-01'
    - MM/DD/YYYY format: '09/01/2026'
    """
    if not date_str:
        raise ValueError("Date string cannot be empty")

    # Try ISO format first (YYYY-MM-DD)
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        pass

    # Try MM/DD/YYYY format
    try:
        parts = date_str.split('/')
        if len(parts) == 3:
            month, day, year = parts
            return date(int(year), int(month), int(day))
    except (ValueError, IndexError):
        pass

    # If all else fails, raise error with helpful message
    raise ValueError(f"Invalid date format: '{date_str}'. Expected ISO format (YYYY-MM-DD) or MM/DD/YYYY")


def get_claim_context(policy_number: str, tool_context: ToolContext):
    """
    Fetch complete claim context from BigQuery.
    """
    query = f"""
    SELECT
        p.policy_id,
        p.policy_number,
        p.policy_status,
        p.coverage_amount,
        p.deductible_amount,
        p.effective_date,
        p.expiration_date,

        c.customer_id,
        c.full_name,
        c.email,
        c.phone,
        c.state AS customer_state,

        pr.property_id,
        pr.property_address,
        pr.property_type,
        pr.estimated_value,
        pr.roof_age,
        pr.roof_material,
        pr.year_built,
        pr.square_footage,
        # pr.width_ft,
        # pr.length_ft,
        pr.roof_area_sqft,
        pr.construction_type,
        pr.number_of_floors,
        pr.zip_code,
        pr.state AS property_state,

        r.flood_risk,
        r.wind_risk,
        r.hail_risk,
        r.wildfire_risk,
        r.earthquake_risk,
        r.crime_score

    FROM `{PROJECT_ID}.{DATASET}.Policy` p
    JOIN `{PROJECT_ID}.{DATASET}.Customer` c
        ON p.customer_id = c.customer_id
    JOIN `{PROJECT_ID}.{DATASET}.Property` pr
        ON p.property_id = pr.property_id
    LEFT JOIN `{PROJECT_ID}.{DATASET}.Risk` r
        ON pr.property_id = r.property_id

    WHERE p.policy_number = @policy_number
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("policy_number", "STRING", policy_number)
        ]
    )

    rows = list(client.query(query, job_config=job_config).result())

    if not rows:
        return {"status": "FAILED", "message": "Policy not found."}

    context = dict(rows[0])
    print("DEBUG context keys:", list(context.keys()))
    policy_id = context["policy_id"]

    previous_claims_query = f"""
    SELECT *
    FROM `{PROJECT_ID}.{DATASET}.Claims`
    WHERE policy_id = @policy_id
    ORDER BY incident_date DESC
    """

    claims_job = client.query(
        previous_claims_query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("policy_id", "STRING", policy_id)
            ]
        ),
    )

    previous_claims = [dict(row) for row in claims_job.result()]

    result = {
        "status": "SUCCESS",
        "policy": {
            "policy_id": context["policy_id"],
            "policy_number": context["policy_number"],
            "policy_status": context["policy_status"],
            "coverage_amount": context["coverage_amount"],
            "deductible_amount": context["deductible_amount"],
            "effective_date": context["effective_date"],
            "expiration_date": context["expiration_date"],
        },
        "customer": {
            "customer_id": context["customer_id"],
            "full_name": context["full_name"],
            "email": context["email"],
            "phone": context["phone"],
            "state": context["customer_state"],
        },
        "property": {
            "property_id": context["property_id"],
            "property_address": context["property_address"],
            "property_type": context["property_type"],
            "estimated_value": context["estimated_value"],
            "roof_age": context["roof_age"],
            "roof_material": context["roof_material"],
            "year_built": context["year_built"],
            "square_footage": context["square_footage"],
            # "width_ft": context["width_ft"],
            # "length_ft": context["length_ft"],
            "roof_area_sqft": context["roof_area_sqft"],
            "construction_type": context["construction_type"],
            "number_of_floors": context["number_of_floors"],
            "zip_code": context["zip_code"],
            "state": context["property_state"],
            # "state": context["state"],
        },
        "risk": {
            "flood_risk": context["flood_risk"],
            "wind_risk": context["wind_risk"],
            "hail_risk": context["hail_risk"],
            "wildfire_risk": context["wildfire_risk"],
            "earthquake_risk": context["earthquake_risk"],
            "crime_score": context["crime_score"],
        },
        "previous_claims": previous_claims,
    }
    result = convert_to_json(result)
    tool_context.state["claim_context"] = result
    tool_context.state["policy_number"] = policy_number
    return result


def create_claim(
    policy_id: str,
    customer_id: str,
    property_id: str,
    claim_type: str,
    incident_date: str,
    tool_context: ToolContext,
):
    """
    Inserts a new claim with status 'Submitted' and returns its IDs.

    Uses a DML INSERT query job (not the streaming insert API) so the
    row is immediately eligible for UPDATE — streaming inserts
    (insert_rows_json) place rows in a streaming buffer that blocks
    UPDATE/DELETE for an indeterminate period, which caused
    intermittent "streaming buffer still locked" errors when
    update_claim ran shortly after create_claim.
    """

    claim_id = str(uuid.uuid4())
    claim_number = f"CLM-{datetime.utcnow().strftime('%Y%m%d')}-{claim_id[:6].upper()}"
    reported_date = date.today().isoformat()

    try:
        incident_date_parsed = parse_date_flexible(incident_date).isoformat()
    except ValueError as e:
        return {"status": "ERROR", "message": str(e)}

    query = f"""
    INSERT INTO `{PROJECT_ID}.{DATASET}.Claims`
        (claim_id, policy_id, customer_id, property_id, claim_number,
         claim_type, incident_date, reported_date, claim_amount,
         approved_amount, claim_status)
    VALUES
        (@claim_id, @policy_id, @customer_id, @property_id, @claim_number,
         @claim_type, @incident_date, @reported_date, NULL, NULL, 'Submitted')
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("claim_id", "STRING", claim_id),
            bigquery.ScalarQueryParameter("policy_id", "STRING", policy_id),
            bigquery.ScalarQueryParameter("customer_id", "STRING", customer_id),
            bigquery.ScalarQueryParameter("property_id", "STRING", property_id),
            bigquery.ScalarQueryParameter("claim_number", "STRING", claim_number),
            bigquery.ScalarQueryParameter("claim_type", "STRING", claim_type),
            bigquery.ScalarQueryParameter("incident_date", "DATE", incident_date_parsed),
            bigquery.ScalarQueryParameter("reported_date", "DATE", reported_date),
        ]
    )

    try:
        client.query(query, job_config=job_config).result()
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

    tool_context.state["incident_date"] = incident_date_parsed
    tool_context.state["claim_id"] = claim_id
    tool_context.state["claim_number"] = claim_number
    tool_context.state["claim_type"] = claim_type

    return {
        "status": "SUCCESS",
        "claim_id": claim_id,
        "claim_number": claim_number,
        "claim_status": "Submitted",
    }


# final claim_amount / approved_amount / claim_status.
# 23-09-26
def update_claim(
    claim_status: str,
    tool_context: ToolContext,
    claim_amount: int = None,
    approved_amount: int = None,
):
    """
    Updates the CURRENT claim's status and dollar amounts in BigQuery.
    claim_id is pulled automatically from session state (set by
    create_claim) — do not ask the user for it.

    Retry logic is kept as a safety net for genuinely transient
    BigQuery errors, but since create_claim now inserts via a DML
    query job instead of the streaming API, this should no longer
    need to retry due to streaming buffer locks.
    """
    claim_id = tool_context.state.get("claim_id")
    if not claim_id:
        return {"status": "ERROR", "message": "No claim_id in session state."}

    set_clauses = ["claim_status = @claim_status"]
    params = [bigquery.ScalarQueryParameter("claim_status", "STRING", claim_status)]

    if claim_amount is not None:
        set_clauses.append("claim_amount = @claim_amount")
        params.append(bigquery.ScalarQueryParameter("claim_amount", "INT64", int(round(claim_amount))))

    if approved_amount is not None:
        set_clauses.append("approved_amount = @approved_amount")
        params.append(bigquery.ScalarQueryParameter("approved_amount", "INT64", int(round(approved_amount))))

    params.append(bigquery.ScalarQueryParameter("claim_id", "STRING", claim_id))

    query = f"""
    UPDATE `{PROJECT_ID}.{DATASET}.Claims`
    SET {", ".join(set_clauses)}
    WHERE claim_id = @claim_id
    """

    # Retry logic kept as a safety net (exponential backoff)
    max_retries = 5
    retry_delay = 1  # Start with 1 second

    for attempt in range(max_retries):
        try:
            client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
            tool_context.state["claim_status"] = claim_status
            return {"status": "SUCCESS", "claim_id": claim_id, "claim_status": claim_status}

        except BadRequest as e:
            # Check if this is a streaming buffer error
            if "streaming buffer" in str(e):
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                    print(f"Streaming buffer delay detected. Retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    return {
                        "status": "ERROR",
                        "message": f"Failed to update claim after {max_retries} retries. BigQuery streaming buffer still locked. Please try again in a moment.",
                    }
            else:
                # Not a streaming buffer error, re-raise
                return {"status": "ERROR", "message": str(e)}


def check_duplicate_claim(
    claim_type: str,
    incident_date: str,
    tool_context: ToolContext,
):
    """
    Checks whether a similar claim already exists on this policy —
    same claim_type, incident date within 7 days, and not already
    rejected/cancelled. Uses previous_claims already loaded into
    session state by get_claim_context. Call this AFTER
    get_claim_context and BEFORE create_claim.
    """
    claim_context = tool_context.state.get("claim_context")
    if not claim_context:
        return {
            "status": "ERROR",
            "message": "Claim context not found. Call get_claim_context first.",
        }

    previous_claims = claim_context.get("previous_claims", [])
    incident = parse_date_flexible(incident_date)

    matches = []
    for c in previous_claims:
        existing_type = (c.get("claim_type") or "").strip().lower()
        existing_status = (c.get("claim_status") or "").strip().lower()
        existing_date_str = c.get("incident_date")

        if existing_type != claim_type.strip().lower():
            continue
        if existing_status in ("rejected", "denied", "cancelled"):
            continue
        if not existing_date_str:
            continue

        existing_date = parse_date_flexible(str(existing_date_str))
        if abs((incident - existing_date).days) <= 7:
            matches.append(c)

    result = {
        "status": "SUCCESS",
        "is_duplicate": len(matches) > 0,
        "matching_claims": matches,
    }
    tool_context.state["duplicate_check"] = result
    return result