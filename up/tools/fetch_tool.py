"""
Generic Fetch Tool for Broker Productivity Agent.

Purpose:
    Fetch data from exactly one requested table.

IMPORTANT:
    This tool does NOT scan all tables.
    The agent must first identify the target entity/table.

Supported entities in Broker_Productivity:
    customer
    property
    policy
    risk
    claims
    audit
"""

import logging
from typing import Any, Dict, Optional

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

logging.basicConfig(
    level=logging.INFO
)


# ============================================================
# TABLE MAPPING
# ============================================================

TABLE_MAP = {

    "customer": "Customer",

    "property": "Property",

    "policy": "Policy1",

    "risk": "Risk",

    "claims": "Claims",

    "claim": "Claims",

}


# ============================================================
# ALIASES
# ============================================================

ENTITY_ALIASES = {

    "customers": "customer",

    "customer details": "customer",

    "homeowner": "customer",

    "homeowner details": "customer",

    "property details": "property",

    "home": "property",

    "home details": "property",

    "policies": "policy",

    "policy details": "policy",

    "risk": "risk",

    "risk details": "risk",

    "risk assessment": "risk",

    "claims": "claims",

    "claim": "claims",

    "claim details": "claims",

    "claims history": "claims",

}


# ============================================================
# SERIALIZATION
# ============================================================

def serialize_value(
    value: Any
) -> Any:
    """
    Convert BigQuery DATE / DATETIME / TIMESTAMP
    values into JSON serializable strings.
    """

    if value is None:
        return None

    if hasattr(
        value,
        "isoformat"
    ):
        return value.isoformat()

    return value


def serialize_row(
    row
) -> Dict[str, Any]:

    return {
        key: serialize_value(value)
        for key, value in dict(row).items()
    }


# ============================================================
# NORMALIZE ENTITY
# ============================================================

def normalize_entity(
    entity: str
) -> str:

    if not entity:
        raise ValueError(
            "Entity is required."
        )

    entity = (
        entity
        .strip()
        .lower()
    )

    entity = ENTITY_ALIASES.get(
        entity,
        entity
    )

    if entity not in TABLE_MAP:

        raise ValueError(
            f"Unsupported entity '{entity}'. "
            f"Supported entities: "
            f"{list(TABLE_MAP.keys())}"
        )

    return entity


# ============================================================
# GET ACTUAL TABLE SCHEMA
# ============================================================

def get_table_schema(
    table_name: str
) -> Dict[str, bigquery.SchemaField]:

    table_ref = (
        f"{PROJECT_ID}."
        f"{DATASET_ID}."
        f"{table_name}"
    )

    table = client.get_table(
        table_ref
    )

    return {
        field.name: field
        for field in table.schema
    }


# ============================================================
# RESOLVE POLICY -> CUSTOMER
# ============================================================

def resolve_customer_from_policy(
    policy_id: str
) -> str:

    query = f"""
        SELECT customer_id
        FROM `{PROJECT_ID}.{DATASET_ID}.Policy1`
        WHERE policy_id = @policy_id
        LIMIT 1
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "policy_id",
                "STRING",
                policy_id
            )
        ]
    )

    rows = list(
        client.query(
            query,
            job_config=job_config
        ).result()
    )

    if not rows:

        raise ValueError(
            f"Policy '{policy_id}' was not found."
        )

    customer_id = rows[0]["customer_id"]

    if not customer_id:

        raise ValueError(
            f"No customer is linked to policy "
            f"'{policy_id}'."
        )

    return customer_id


# ============================================================
# RESOLVE POLICY -> PROPERTY
# ============================================================

def resolve_property_from_policy(
    policy_id: str
) -> str:

    query = f"""
        SELECT property_id
        FROM `{PROJECT_ID}.{DATASET_ID}.Policy1`
        WHERE policy_id = @policy_id
        LIMIT 1
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "policy_id",
                "STRING",
                policy_id
            )
        ]
    )

    rows = list(
        client.query(
            query,
            job_config=job_config
        ).result()
    )

    if not rows:

        raise ValueError(
            f"Policy '{policy_id}' was not found."
        )

    property_id = rows[0]["property_id"]

    if not property_id:

        raise ValueError(
            f"No property is linked to policy "
            f"'{policy_id}'."
        )

    return property_id


# ============================================================
# BUILD FILTER
# ============================================================

def build_filter(
    field_name: str,
    value: Any,
    schema: Dict[str, bigquery.SchemaField],
    parameter_name: str,
):

    if field_name not in schema:

        raise ValueError(
            f"Column '{field_name}' does not exist "
            f"in the requested table."
        )

    field = schema[field_name]

    field_type = field.field_type.upper()

    if field_type in (
        "INTEGER",
        "INT64",
    ):

        parameter = bigquery.ScalarQueryParameter(
            parameter_name,
            "INT64",
            int(value)
        )

    elif field_type in (
        "FLOAT",
        "FLOAT64",
    ):

        parameter = bigquery.ScalarQueryParameter(
            parameter_name,
            "FLOAT64",
            float(value)
        )

    elif field_type == "BOOL":

        parameter = bigquery.ScalarQueryParameter(
            parameter_name,
            "BOOL",
            bool(value)
        )

    elif field_type == "DATE":

        parameter = bigquery.ScalarQueryParameter(
            parameter_name,
            "DATE",
            str(value)
        )

    elif field_type in (
        "TIMESTAMP",
        "DATETIME",
    ):

        parameter = bigquery.ScalarQueryParameter(
            parameter_name,
            field_type,
            str(value)
        )

    else:

        parameter = bigquery.ScalarQueryParameter(
            parameter_name,
            "STRING",
            str(value)
        )

    return (
        f"`{field_name}` = @{parameter_name}",
        parameter,
    )


# ============================================================
# MAIN FETCH TOOL
# ============================================================

def fetch_table_data(
    entity: str,
    policy_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    property_id: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Fetch data from exactly one requested table.

    Parameters
    ----------
    entity:
        Target entity/table.

    policy_id:
        Policy identifier.

    customer_id:
        Customer identifier.

    property_id:
        Property identifier.

    filters:
        Additional column/value filters.

    limit:
        Maximum number of rows.

    Returns
    -------
    JSON-safe dictionary.
    """

    logger.info("=" * 70)
    logger.info("FETCH TABLE DATA")
    logger.info(
        "Entity      : %s",
        entity
    )
    logger.info(
        "Policy ID   : %s",
        policy_id
    )
    logger.info(
        "Customer ID : %s",
        customer_id
    )
    logger.info(
        "Property ID : %s",
        property_id
    )
    logger.info(
        "Filters     : %s",
        filters
    )
    logger.info("=" * 70)

    try:

        # ----------------------------------------------------
        # 1. Normalize entity
        # ----------------------------------------------------

        entity = normalize_entity(
            entity
        )

        table_name = TABLE_MAP[
            entity
        ]

        # ----------------------------------------------------
        # 2. Get ONLY requested table schema
        # ----------------------------------------------------

        schema = get_table_schema(
            table_name
        )

        # ----------------------------------------------------
        # 3. Resolve identifier
        # ----------------------------------------------------

        if entity == "customer":

            if not customer_id:

                if not policy_id:

                    raise ValueError(
                        "customer_id or policy_id "
                        "is required for customer lookup."
                    )

                customer_id = (
                    resolve_customer_from_policy(
                        policy_id
                    )
                )

            if "customer_id" not in schema:

                raise ValueError(
                    "Customer table does not contain "
                    "'customer_id'."
                )

            where_clause = (
                "`customer_id` = @customer_id"
            )

            parameters = [
                bigquery.ScalarQueryParameter(
                    "customer_id",
                    "STRING",
                    customer_id
                )
            ]

        # ----------------------------------------------------
        # PROPERTY
        # ----------------------------------------------------

        elif entity == "property":

            if not property_id:

                if not policy_id:

                    raise ValueError(
                        "property_id or policy_id "
                        "is required for property lookup."
                    )

                property_id = (
                    resolve_property_from_policy(
                        policy_id
                    )
                )

            if "property_id" not in schema:

                raise ValueError(
                    "Property table does not contain "
                    "'property_id'."
                )

            where_clause = (
                "`property_id` = @property_id"
            )

            parameters = [
                bigquery.ScalarQueryParameter(
                    "property_id",
                    "STRING",
                    property_id
                )
            ]

        # ----------------------------------------------------
        # POLICY
        # ----------------------------------------------------

        elif entity == "policy":

            if policy_id:

                where_clause = (
                    "`policy_id` = @policy_id"
                )

                parameters = [
                    bigquery.ScalarQueryParameter(
                        "policy_id",
                        "STRING",
                        policy_id
                    )
                ]

            elif customer_id:

                where_clause = (
                    "`customer_id` = @customer_id"
                )

                parameters = [
                    bigquery.ScalarQueryParameter(
                        "customer_id",
                        "STRING",
                        customer_id
                    )
                ]

            else:

                raise ValueError(
                    "policy_id or customer_id is required "
                    "for policy lookup."
                )

        # ----------------------------------------------------
        # RISK
        # ----------------------------------------------------

        elif entity == "risk":

            if property_id:

                where_clause = "`property_id` = @property_id"

                parameters = [

                    bigquery.ScalarQueryParameter(

                        "property_id",

                        "STRING",

                        property_id

                    )

                ]

            elif policy_id:

                property_id = resolve_property_from_policy(policy_id)

                where_clause = "`property_id` = @property_id"

                parameters = [

                    bigquery.ScalarQueryParameter(

                        "property_id",

                        "STRING",

                        property_id

                    )

                ]

            else:

                raise ValueError(

                    "property_id or policy_id is required for risk lookup."

                )

        # ----------------------------------------------------
        # CLAIMS
        # ----------------------------------------------------

        elif entity == "claims":

            if policy_id:

                where_clause = "`policy_id` = @policy_id"

                parameters = [

                    bigquery.ScalarQueryParameter(

                        "policy_id",

                        "STRING",

                        policy_id

                    )

                ]

            elif customer_id:

                where_clause = "`customer_id` = @customer_id"

                parameters = [

                    bigquery.ScalarQueryParameter(

                        "customer_id",

                        "STRING",

                        customer_id

                    )

                ]

            elif property_id:

                where_clause = "`property_id` = @property_id"

                parameters = [

                    bigquery.ScalarQueryParameter(

                        "property_id",

                        "STRING",

                        property_id

                    )

                ]

            else:

                raise ValueError(

                    "policy_id, customer_id, or property_id is required for claims lookup."

                )

        # ----------------------------------------------------
        # OTHER TABLES
        # ----------------------------------------------------

        else:

            where_conditions = []

            parameters = []

            if filters:

                for index, (
                    field_name,
                    value
                ) in enumerate(
                    filters.items()
                ):

                    condition, parameter = (
                        build_filter(
                            field_name,
                            value,
                            schema,
                            f"filter_{index}"
                        )
                    )

                    where_conditions.append(
                        condition
                    )

                    parameters.append(
                        parameter
                    )

            if not where_conditions:

                raise ValueError(
                    f"A filter is required when "
                    f"fetching '{table_name}'. "
                    f"Broad table scans are not allowed."
                )

            where_clause = " AND ".join(
                where_conditions
            )

        # ----------------------------------------------------
        # 4. Additional filters
        # ----------------------------------------------------

        if filters:

            for index, (
                field_name,
                value
            ) in enumerate(
                filters.items()
            ):

                condition, parameter = (
                    build_filter(
                        field_name,
                        value,
                        schema,
                        f"extra_filter_{index}"
                    )
                )

                where_clause += (
                    f" AND {condition}"
                )

                parameters.append(
                    parameter
                )

        # ----------------------------------------------------
        # 5. Safe limit
        # ----------------------------------------------------

        try:

            limit = int(limit)

        except (
            TypeError,
            ValueError,
        ):

            limit = 20

        limit = max(
            1,
            min(limit, 100)
        )

        # ----------------------------------------------------
        # 6. Query ONLY target table
        # ----------------------------------------------------

        query = f"""
            SELECT *
            FROM `{PROJECT_ID}.{DATASET_ID}.{table_name}`
            WHERE {where_clause}
            LIMIT {limit}
        """

        logger.info(
            "Executing query on ONLY table: %s",
            table_name
        )

        # ----------------------------------------------------
        # 7. Execute query
        # ----------------------------------------------------

        job_config = (
            bigquery.QueryJobConfig(
                query_parameters=parameters
            )
        )

        rows = list(
            client.query(
                query,
                job_config=job_config
            ).result()
        )

        # ----------------------------------------------------
        # 8. Convert to JSON-safe output
        # ----------------------------------------------------

        records = [
            serialize_row(row)
            for row in rows
        ]

        logger.info(
            "Rows returned: %s",
            len(records)
        )

        # ----------------------------------------------------
        # 9. Return
        # ----------------------------------------------------

        return {
            "status": "SUCCESS",

            "entity": entity,

            "table": table_name,

            "record_count": len(records),

            "data": records,
        }

    except ValueError as e:

        logger.error(
            "Fetch validation error: %s",
            e
        )

        return {
            "status": "FAILED",

            "error_type": "VALIDATION_ERROR",

            "message": str(e),
        }

    except Exception as e:

        logger.exception(
            "Fetch failed"
        )

        return {
            "status": "FAILED",

            "error_type": "FETCH_ERROR",

            "message": str(e),
        }

    finally:

        logger.info(
            "FETCH TABLE DATA COMPLETED"
        )


__all__ = [
    "fetch_table_data",
]