"""
Update Tool for Broker Productivity Agent.

Purpose:
    Update ONLY the actual editable insurance data in Broker_Productivity dataset.

Editable tables in Broker_Productivity:
    - Customer
    - Property
    - Policy
    - Risk
    - Claims
    - Audit (Automated audit logging table)
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from google.cloud import bigquery


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ID = "gcp-app-builder"
DATASET_ID = "Broker_Productivity"

client = bigquery.Client(project=PROJECT_ID)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ============================================================
# TABLE MAPPING
# ============================================================

TABLES = {
    "customer": "Customer",
    "property": "Property",
    "policy": "Policy1",
    "risk": "Risk",
    "claims": "Claims",
}


# ============================================================
# EDITABLE ENTITIES
# ============================================================

EDITABLE_ENTITIES = {
    "customer",
    "property",
    "policy",
}


# ============================================================
# READ-ONLY ENTITIES
# ============================================================

READ_ONLY_ENTITIES = {
    "risk",
    "claims",
    "claim",
    "audit",
}


# ============================================================
# CUSTOMER EDITABLE FIELDS
# ============================================================

CUSTOMER_FIELDS = {
    "full_name",
    "state",
    "email",
    "phone",
}


# ============================================================
# PROPERTY EDITABLE FIELDS
# ============================================================

PROPERTY_FIELDS = {
    "property_address",
    "zip_code",
    "property_type",
    "estimated_value",
    "year_built",
    "square_footage",
    "roof_age",
    "roof_material",
    "construction_type",
    "number_of_floors",
    "state",
}


# ============================================================
# POLICY EDITABLE FIELDS
# ============================================================

POLICY_FIELDS = {
    "policy_name",
    "policy_type",
    "policy_status",
    "effective_date",
    "expiration_date",
    "policy_term_months",
    "dwelling_coverage",
    "personal_property_coverage",
    "liability_limit",
    "deductible_amount",
    "add_ons",
    "annual_premium",
    "monthly_premium",
}


# ============================================================
# FIELD ALIASES
# ============================================================

FIELD_ALIASES = {

    # CUSTOMER
    "phone number": "phone",
    "mobile number": "phone",
    "telephone": "phone",
    "full name": "full_name",
    "name": "full_name",
    "email address": "email",

    # PROPERTY
    "home address": "property_address",
    "address": "property_address",
    "property address": "property_address",
    "home value": "estimated_value",
    "property value": "estimated_value",
    "estimated value": "estimated_value",
    "year built": "year_built",
    "square footage": "square_footage",
    "roof age": "roof_age",
    "roof material": "roof_material",
    "construction type": "construction_type",
    "floors": "number_of_floors",
    "number of floors": "number_of_floors",
    "zip": "zip_code",
    "zipcode": "zip_code",
    "zip code": "zip_code",

    # POLICY
    "policy number": "policy_number",
    "policy name": "policy_name",
    "policy type": "policy_type",
    "policy status": "policy_status",
    "status": "policy_status",
    "effective date": "effective_date",
    "expiration date": "expiration_date",
    "policy term": "policy_term_months",
    "term": "policy_term_months",
    "deductible": "deductible_amount",
    "deductible amount": "deductible_amount",
    "dwelling coverage": "dwelling_coverage",
    "dwelling": "dwelling_coverage",
    "coverage": "dwelling_coverage",
    "coverage amount": "dwelling_coverage",
    "personal property coverage": "personal_property_coverage",
    "personal property": "personal_property_coverage",
    "liability limit": "liability_limit",
    "liability": "liability_limit",
    "add ons": "add_ons",
    "add-ons": "add_ons",
    "addons": "add_ons",
    "add on": "add_ons",
    "premium": "annual_premium",
    "annual premium": "annual_premium",
    "monthly premium": "monthly_premium",

    # RISK
    "flood": "flood_risk",
    "flood risk": "flood_risk",
    "wildfire": "wildfire_risk",
    "wildfire risk": "wildfire_risk",
    "wind": "wind_risk",
    "wind risk": "wind_risk",
    "hail": "hail_risk",
    "hail risk": "hail_risk",
    "earthquake": "earthquake_risk",
    "earthquake risk": "earthquake_risk",
    "crime": "crime_score",
    "crime score": "crime_score",

    # CLAIMS
    "claim number": "claim_number",
    "claim type": "claim_type",
    "incident date": "incident_date",
    "reported date": "reported_date",
    "claim amount": "claim_amount",
    "approved amount": "approved_amount",
    "claim status": "claim_status",
}


# ============================================================
# RESPONSE HELPERS
# ============================================================

def success_response(data: Any) -> Dict:
    """
    Standard successful tool response.
    """

    return {
        "status": "SUCCESS",
        "data": data,
    }


def error_response(message: str) -> Dict:
    """
    Standard failed tool response.
    """

    return {
        "status": "FAILED",
        "message": message,
    }


# ============================================================
# SERIALIZATION
# ============================================================

def serialize_value(value: Any) -> Any:
    """
    Convert DATE / DATETIME / TIMESTAMP values into
    JSON-serializable strings.
    """

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return value


def serialize_row(row: Any) -> Dict:
    """
    Convert BigQuery Row into normal JSON-safe dictionary.
    """

    return {
        key: serialize_value(value)
        for key, value in dict(row).items()
    }


# ============================================================
# QUERY EXECUTION
# ============================================================

def execute_query(
    query: str,
    parameters: Optional[
        List[bigquery.ScalarQueryParameter]
    ] = None,
):
    """
    Execute BigQuery query.

    SELECT queries return serialized rows.

    UPDATE / INSERT / DELETE / MERGE return an empty list.
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=parameters or []
    )

    logger.info("Executing BigQuery query")

    job = client.query(
        query,
        job_config=job_config,
    )

    result = job.result()

    if query.strip().upper().startswith(
        ("UPDATE", "INSERT", "DELETE", "MERGE")
    ):
        return []

    return [
        serialize_row(row)
        for row in result
    ]


# ============================================================
# ENTITY VALIDATION
# ============================================================

def validate_entity(entity: str) -> str:
    """
    Validate that the requested entity is editable.
    """

    if not entity:
        raise ValueError(
            "Entity is required."
        )

    entity = entity.lower().strip()

    if entity not in EDITABLE_ENTITIES:

        if entity in READ_ONLY_ENTITIES:
            raise ValueError(
                f"'{entity}' is read-only and cannot be updated."
            )

        raise ValueError(
            f"Unsupported update entity '{entity}'."
        )

    return entity


# ============================================================
# FIELD VALIDATION
# ============================================================

def validate_field(
    entity: str,
    field_name: str,
) -> str:
    """
    Normalize and validate the requested field.
    """

    if not field_name:
        raise ValueError(
            "Field name is required."
        )

    field_name = (
        field_name
        .lower()
        .strip()
    )

    # Convert user-friendly field name
    # into actual BigQuery column name.
    field_name = FIELD_ALIASES.get(
        field_name,
        field_name,
    )

    allowed_fields = {
        "customer": CUSTOMER_FIELDS,
        "property": PROPERTY_FIELDS,
        "policy": POLICY_FIELDS,
    }

    if field_name not in allowed_fields[entity]:

        raise ValueError(
            f"Field '{field_name}' is not editable "
            f"for {entity}."
        )

    return field_name


# ============================================================
# GET CUSTOMER ID FROM POLICY
# ============================================================

def get_customer_id(
    policy_id: str,
) -> str:
    """
    Find the customer associated with the policy.

    Only the Policy table is queried.
    """

    query = f"""
        SELECT customer_id
        FROM `{PROJECT_ID}.{DATASET_ID}.Policy1`
        WHERE policy_id = @policy_id
        LIMIT 1
    """

    rows = execute_query(
        query,
        [
            bigquery.ScalarQueryParameter(
                "policy_id",
                "STRING",
                policy_id,
            )
        ],
    )

    if not rows:
        raise ValueError(
            f"Policy '{policy_id}' was not found."
        )

    customer_id = rows[0].get(
        "customer_id"
    )

    if not customer_id:
        raise ValueError(
            f"No customer is linked to policy '{policy_id}'."
        )

    return customer_id


# ============================================================
# GET PROPERTY ID FROM POLICY
# ============================================================

def get_property_id(
    policy_id: str,
) -> str:
    """
    Find the property associated with the policy.

    Only the Policy table is queried.
    """

    query = f"""
        SELECT property_id
        FROM `{PROJECT_ID}.{DATASET_ID}.Policy1`
        WHERE policy_id = @policy_id
        LIMIT 1
    """

    rows = execute_query(
        query,
        [
            bigquery.ScalarQueryParameter(
                "policy_id",
                "STRING",
                policy_id,
            )
        ],
    )

    if not rows:
        raise ValueError(
            f"Policy '{policy_id}' was not found."
        )

    property_id = rows[0].get(
        "property_id"
    )

    if not property_id:
        raise ValueError(
            f"No property is linked to policy '{policy_id}'."
        )

    return property_id


# ============================================================
# GET CURRENT CUSTOMER RECORD
# ============================================================

def get_customer_record(
    policy_id: str,
) -> Dict:

    customer_id = get_customer_id(
        policy_id
    )

    query = f"""
        SELECT *
        FROM `{PROJECT_ID}.{DATASET_ID}.Customer`
        WHERE customer_id = @customer_id
        LIMIT 1
    """

    rows = execute_query(
        query,
        [
            bigquery.ScalarQueryParameter(
                "customer_id",
                "STRING",
                customer_id,
            )
        ],
    )

    if not rows:
        raise ValueError(
            f"No Customer record found for "
            f"policy '{policy_id}'."
        )

    return rows[0]


# ============================================================
# GET CURRENT PROPERTY RECORD
# ============================================================

def get_property_record(
    policy_id: str,
) -> Dict:

    property_id = get_property_id(
        policy_id
    )

    query = f"""
        SELECT *
        FROM `{PROJECT_ID}.{DATASET_ID}.Property`
        WHERE property_id = @property_id
        LIMIT 1
    """

    rows = execute_query(
        query,
        [
            bigquery.ScalarQueryParameter(
                "property_id",
                "STRING",
                property_id,
            )
        ],
    )

    if not rows:
        raise ValueError(
            f"No Property record found for "
            f"policy '{policy_id}'."
        )

    return rows[0]


# ============================================================
# GET CURRENT POLICY RECORD
# ============================================================

def get_policy_record(
    policy_id: str,
) -> Dict:

    query = f"""
        SELECT *
        FROM `{PROJECT_ID}.{DATASET_ID}.Policy1`
        WHERE policy_id = @policy_id
        LIMIT 1
    """

    rows = execute_query(
        query,
        [
            bigquery.ScalarQueryParameter(
                "policy_id",
                "STRING",
                policy_id,
            )
        ],
    )

    if not rows:
        raise ValueError(
            f"No Policy record found for "
            f"policy '{policy_id}'."
        )

    return rows[0]





# ============================================================
# GET CURRENT RECORD
# ============================================================

# ============================================================
# GET CURRENT RISK RECORD
# ============================================================

def get_risk_record(
    policy_id: str,
) -> Dict:

    property_id = get_property_id(
        policy_id
    )

    query = f"""
        SELECT *
        FROM `{PROJECT_ID}.{DATASET_ID}.Risk`
        WHERE property_id = @property_id
        LIMIT 1
    """

    rows = execute_query(
        query,
        [
            bigquery.ScalarQueryParameter(
                "property_id",
                "STRING",
                property_id,
            )
        ],
    )

    if not rows:
        raise ValueError(
            f"No Risk record found for "
            f"policy '{policy_id}'."
        )

    return rows[0]


# ============================================================
# GET CURRENT CLAIMS RECORD
# ============================================================

def get_claims_record(
    policy_id: str,
) -> Dict:

    query = f"""
        SELECT *
        FROM `{PROJECT_ID}.{DATASET_ID}.Claims`
        WHERE policy_id = @policy_id
    """

    rows = execute_query(
        query,
        [
            bigquery.ScalarQueryParameter(
                "policy_id",
                "STRING",
                policy_id,
            )
        ],
    )

    if not rows:
        raise ValueError(
            f"No Claims record found for "
            f"policy '{policy_id}'."
        )

    return {
        "records": rows
    }


# ============================================================
# GET CURRENT RECORD
# ============================================================

def get_current_record(
    entity: str,
    policy_id: str,
) -> Dict:
    """
    Fetch ONLY the target entity.

    No searching across all tables.
    """

    if entity == "customer":

        return get_customer_record(
            policy_id
        )

    if entity == "property":

        return get_property_record(
            policy_id
        )

    if entity == "policy":

        return get_policy_record(
            policy_id
        )

    if entity == "risk":

        return get_risk_record(
            policy_id
        )

    if entity == "claims":

        return get_claims_record(
            policy_id
        )

    raise ValueError(
        f"Unsupported entity '{entity}'."
    )


# ============================================================
# BIGQUERY PARAMETER
# ============================================================

def get_parameter(
    field_name: str,
    value: Any,
):
    """
    Create a correctly typed BigQuery parameter
    according to the target column.
    """

    # --------------------------------------------------------
    # INTEGER FIELDS
    # --------------------------------------------------------

    INTEGER_FIELDS = {
        "zip_code",
        "estimated_value",
        "year_built",
        "square_footage",
        "roof_age",
        "number_of_floors",
        "policy_term_months",
        "deductible_amount",
        "coverage_amount",
        "dwelling_coverage",
        "personal_property_coverage",
        "liability_limit",
        "claim_amount",
        "approved_amount",
    }

    # --------------------------------------------------------
    # FLOAT FIELDS
    # --------------------------------------------------------

    FLOAT_FIELDS = {
        "annual_premium",
        "monthly_premium",
    }

    # --------------------------------------------------------
    # BOOLEAN FIELDS
    # --------------------------------------------------------

    BOOLEAN_FIELDS = set()

    # --------------------------------------------------------
    # DATE FIELDS
    # --------------------------------------------------------

    DATE_FIELDS = {
        "effective_date",
        "expiration_date",
        "incident_date",
        "reported_date",
    }

    # --------------------------------------------------------
    # INTEGER
    # --------------------------------------------------------

    if field_name in INTEGER_FIELDS:

        try:
            clean_str = str(value).replace("$", "").replace(",", "").strip()
            integer_value = int(float(clean_str))

        except (TypeError, ValueError):

            raise ValueError(
                f"Value '{value}' must be an integer "
                f"for field '{field_name}'."
            )

        return bigquery.ScalarQueryParameter(
            "new_value",
            "INT64",
            integer_value,
        )

    # --------------------------------------------------------
    # FLOAT
    # --------------------------------------------------------

    if field_name in FLOAT_FIELDS:

        try:
            clean_str = str(value).replace("$", "").replace(",", "").strip()
            float_value = float(clean_str)

        except (TypeError, ValueError):

            raise ValueError(
                f"Value '{value}' must be numeric "
                f"for field '{field_name}'."
            )

        return bigquery.ScalarQueryParameter(
            "new_value",
            "FLOAT64",
            float_value,
        )

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    if field_name in DATE_FIELDS:

        try:
            date_value = date.fromisoformat(
                str(value)
            )

        except ValueError:

            raise ValueError(
                f"Value '{value}' must be in "
                f"YYYY-MM-DD format for "
                f"field '{field_name}'."
            )

        return bigquery.ScalarQueryParameter(
            "new_value",
            "DATE",
            date_value,
        )

    # --------------------------------------------------------
    # BOOLEAN
    # --------------------------------------------------------

    if field_name in BOOLEAN_FIELDS:

        if isinstance(value, bool):

            bool_value = value

        elif str(value).strip().lower() in {
            "true",
            "yes",
            "1",
        }:

            bool_value = True

        elif str(value).strip().lower() in {
            "false",
            "no",
            "0",
        }:

            bool_value = False

        else:

            raise ValueError(
                f"Invalid boolean value '{value}' "
                f"for field '{field_name}'. "
                f"Use true/false."
            )

        return bigquery.ScalarQueryParameter(
            "new_value",
            "BOOL",
            bool_value,
        )

    # --------------------------------------------------------
    # STRING
    # --------------------------------------------------------

    return bigquery.ScalarQueryParameter(
        "new_value",
        "STRING",
        str(value),
    )


# ============================================================
# UPDATE CUSTOMER
# ============================================================

def update_customer(
    policy_id: str,
    field_name: str,
    new_value: Any,
):

    customer_id = get_customer_id(
        policy_id
    )

    query = f"""
        UPDATE `{PROJECT_ID}.{DATASET_ID}.Customer`
        SET
            {field_name} = @new_value
        WHERE customer_id = @customer_id
    """

    execute_query(
        query,
        [
            get_parameter(
                field_name,
                new_value,
            ),
            bigquery.ScalarQueryParameter(
                "customer_id",
                "STRING",
                customer_id,
            ),
        ],
    )

    return get_current_record(
        "customer",
        policy_id,
    )


# ============================================================
# UPDATE PROPERTY
# ============================================================

def update_property(
    policy_id: str,
    field_name: str,
    new_value: Any,
):

    property_id = get_property_id(
        policy_id
    )

    query = f"""
        UPDATE `{PROJECT_ID}.{DATASET_ID}.Property`
        SET
            {field_name} = @new_value
        WHERE property_id = @property_id
    """

    execute_query(
        query,
        [
            get_parameter(
                field_name,
                new_value,
            ),
            bigquery.ScalarQueryParameter(
                "property_id",
                "STRING",
                property_id,
            ),
        ],
    )

    return get_current_record(
        "property",
        policy_id,
    )


# ============================================================
# UPDATE POLICY
# ============================================================

def update_policy(
    policy_id: str,
    field_name: str,
    new_value: Any,
):

    query = f"""
        UPDATE `{PROJECT_ID}.{DATASET_ID}.Policy1`
        SET
            {field_name} = @new_value
        WHERE policy_id = @policy_id
    """

    execute_query(
        query,
        [
            get_parameter(
                field_name,
                new_value,
            ),
            bigquery.ScalarQueryParameter(
                "policy_id",
                "STRING",
                policy_id,
            ),
        ],
    )

    return get_current_record(
        "policy",
        policy_id,
    )


# ============================================================
# UPDATE RISK
# ============================================================

def update_risk(
    policy_id: str,
    field_name: str,
    new_value: Any,
):

    property_id = get_property_id(
        policy_id
    )

    query = f"""
        UPDATE `{PROJECT_ID}.{DATASET_ID}.Risk`
        SET
            {field_name} = @new_value
        WHERE property_id = @property_id
    """

    execute_query(
        query,
        [
            get_parameter(
                field_name,
                new_value,
            ),
            bigquery.ScalarQueryParameter(
                "property_id",
                "STRING",
                property_id,
            ),
        ],
    )

    return get_current_record(
        "risk",
        policy_id,
    )


# ============================================================
# UPDATE CLAIMS
# ============================================================

def update_claims(
    policy_id: str,
    field_name: str,
    new_value: Any,
):

    query = f"""
        UPDATE `{PROJECT_ID}.{DATASET_ID}.Claims`
        SET
            {field_name} = @new_value
        WHERE policy_id = @policy_id
    """

    execute_query(
        query,
        [
            get_parameter(
                field_name,
                new_value,
            ),
            bigquery.ScalarQueryParameter(
                "policy_id",
                "STRING",
                policy_id,
            ),
        ],
    )

    return get_current_record(
        "claims",
        policy_id,
    )


# ============================================================
# MAIN UPDATE TABLE DATA TOOL
# ============================================================

def update_table_data(
    entity: str,
    policy_id: str,
    field_name: str,
    new_value: Any,
) -> Dict:
    """
    Update one editable field in the correct source table.

    Parameters
    ----------
    entity:
        customer
        property
        policy
        risk
        claims

    policy_id:
        Policy identifier used to locate the related record.

    field_name:
        Actual column name or supported user-friendly alias.

    new_value:
        New value for the field.

    Returns
    -------
    Dict:
        JSON-safe response containing:
        - entity
        - table
        - policy_id
        - field
        - old_value
        - new_value
        - updated_record
    """

    logger.info("=" * 70)
    logger.info("UPDATE TABLE DATA")
    logger.info("Entity      : %s", entity)
    logger.info("Policy ID   : %s", policy_id)
    logger.info("Field       : %s", field_name)
    logger.info("New Value   : %s", new_value)
    logger.info("=" * 70)

    try:

        # ====================================================
        # 1. VALIDATE POLICY ID
        # ====================================================

        if not policy_id:
            raise ValueError(
                "Policy ID is required."
            )

        policy_id = str(
            policy_id
        ).strip()

        # ====================================================
        # 2. IDENTIFY EXACT ENTITY
        # ====================================================

        entity = validate_entity(
            entity
        )

        # ====================================================
        # 3. IDENTIFY EXACT FIELD
        # ====================================================

        field_name = validate_field(
            entity,
            field_name,
        )

        logger.info(
            "Validated target: %s.%s",
            TABLES[entity],
            field_name,
        )

        # ====================================================
        # 4. FETCH ONLY TARGET TABLE
        # ====================================================

        current_record = get_current_record(
            entity,
            policy_id,
        )

        # ====================================================
        # 5. GET CURRENT VALUE
        # ====================================================

        if entity == "claims":

            records = current_record.get(
                "records",
                []
            )

            if not records:
                raise ValueError(
                    "No claims record found."
                )

            current_value = records[0].get(
                field_name
            )

        else:

            if field_name not in current_record:

                raise ValueError(
                    f"Field '{field_name}' does not exist "
                    f"in {TABLES[entity]}."
                )

            current_value = current_record.get(
                field_name
            )

        # ====================================================
        # 6. VALIDATE NEW VALUE TYPE BEFORE UPDATE
        # ====================================================

        # This does not change the database.
        # It only validates conversion.
        parameter = get_parameter(
            field_name,
            new_value,
        )

        # ====================================================
        # 7. PREVENT UNNECESSARY UPDATE
        # ====================================================

        if (
            current_value is not None
            and str(current_value) == str(new_value)
        ):

            return error_response(
                f"{field_name} already has "
                f"the value '{new_value}'."
            )

        # ====================================================
        # 8. ROUTE TO EXACT UPDATE FUNCTION
        # ====================================================

        ROUTE_MAP = {

            "customer":
                update_customer,

            "property":
                update_property,

            "policy":
                update_policy,
        }

        update_function = ROUTE_MAP[
            entity
        ]

        # ====================================================
        # 9. PERFORM ACTUAL SOURCE TABLE UPDATE
        # ====================================================

        updated_record = update_function(
            policy_id,
            field_name,
            new_value,
        )

        # ====================================================
        # 9.5 AUTO-INSERT AUDIT LOG RECORD
        # ====================================================
        try:
            from .insert_tool import log_audit_entry
            log_audit_entry(
                policy_id=policy_id,
                table_name=TABLES[entity],
                column_name=field_name,
                old_value=current_value,
                new_value=new_value,
            )
        except Exception as audit_err:
            logger.warning("Failed to log audit entry: %s", audit_err)

        # ====================================================
        # 10. RETURN RESULT
        # ====================================================

        return success_response({

            "entity":
                entity,

            "table":
                TABLES[entity],

            "policy_id":
                policy_id,

            "field":
                field_name,

            "old_value":
                current_value,

            "new_value":
                new_value,

            "updated_record":
                updated_record,

            "message":
                (
                    f"Successfully updated "
                    f"{TABLES[entity]}.{field_name}."
                ),
        })

    except ValueError as e:

        logger.error(
            "Update validation error: %s",
            e,
        )

        return error_response(
            str(e)
        )

    except Exception as e:

        logger.exception(
            "Update failed"
        )

        return error_response(
            f"Unexpected error occurred: {str(e)}"
        )

    finally:

        logger.info(
            "UPDATE TABLE DATA COMPLETED"
        )


# ============================================================
# EXPORT
# ============================================================

__all__ = [
    "update_table_data",
]