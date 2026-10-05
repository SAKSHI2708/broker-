"""Dedicated Pre-Renewal tool for the Broker Productivity Agent.

Purpose:
- Checks if an active policy is expiring within 10 days.
- Offers a pre-renewal incentive with a loyalty discount on premium.
- Automatically calculates an enhanced claim limit (max claim amount capacity) 
  when pre-renewing with a slight coverage/premium boost.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from google.cloud import bigquery

PROJECT_ID = "gcp-app-builder"
DATASET_ID = "Broker_Productivity"
client = bigquery.Client(project=PROJECT_ID)
logger = logging.getLogger(__name__)

PRE_RENEWAL_DISCOUNT_PCT = 0.08  # 8% loyalty discount for pre-renewing early
CLAIM_LIMIT_BOOST_MULTIPLIER = 1.15  # 15% extra claim capacity boost on pre-renewal


def _num(v: Any, default: Optional[float] = None) -> Optional[float]:
    if v is None or v == "":
        return default
    try:
        return float(Decimal(str(v)))
    except Exception as exc:
        raise ValueError(f"Invalid numeric value: {v!r}") from exc


def _money(v: float) -> float:
    return round(float(v), 2)


def calculate_max_claim_capacity(dwelling_coverage: float, personal_property: float, deductible: float) -> Dict[str, Any]:
    """
    Calculates the maximum claim payout capacity and out-of-pocket breakdown 
    for a given policy structure during pre-renewal.
    """
    dwelling = float(dwelling_coverage or 0.0)
    contents = float(personal_property or (dwelling * 0.50))
    ded = float(deductible or 1000.0)
    
    total_coverage_pool = dwelling + contents
    net_max_payout = max(0.0, total_coverage_pool - ded)

    return {
        "dwelling_coverage_limit": dwelling,
        "personal_property_limit": contents,
        "deductible_out_of_pocket": ded,
        "total_coverage_pool": total_coverage_pool,
        "net_max_payout_capacity": net_max_payout,
        "explanation": (
            f"With a Dwelling limit of ${dwelling:,.0f} and Personal Property of ${contents:,.0f}, "
            f"your total coverage pool is ${total_coverage_pool:,.0f}. After accounting for your "
            f"${ded:,.0f} deductible, your maximum net claim payout capacity is up to ${net_max_payout:,.0f}."
        )
    }


def _fetch_policy_for_pre_renewal(policy_id: str) -> Dict[str, Any]:
    query = f"""
    SELECT
        p.policy_id, p.policy_number, p.policy_name, p.policy_type,
        p.policy_status, p.effective_date, p.expiration_date,
        p.dwelling_coverage, p.personal_property_coverage,
        p.liability_limit, p.deductible_amount, p.annual_premium, p.monthly_premium
    FROM `{PROJECT_ID}.{DATASET_ID}.Policy1` p
    WHERE p.policy_id = @policy_id
    LIMIT 1
    """
    config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("policy_id", "STRING", policy_id.strip())]
    )
    rows = list(client.query(query, job_config=config).result())
    if not rows:
        raise ValueError(f"Policy '{policy_id}' was not found.")
    return dict(rows[0])


def calculate_pre_renewal(policy_id: str) -> Dict[str, Any]:
    """
    Checks if a policy is expiring within 10 days and generates a pre-renewal offer
    with discounted premium and boosted max claim capacity.
    """
    try:
        if not policy_id or not str(policy_id).strip():
            raise ValueError("policy_id is required.")

        row = _fetch_policy_for_pre_renewal(str(policy_id).strip())
        
        status = str(row.get("policy_status") or "").upper()
        if status != "ACTIVE":
            return {
                "status": "INELIGIBLE",
                "message": f"Policy '{policy_id}' status is '{status}'. Pre-renewal is only available for active policies nearing expiration."
            }

        exp_date_raw = row.get("expiration_date")
        if not exp_date_raw:
            raise ValueError("Policy expiration date is missing.")

        if isinstance(exp_date_raw, str):
            exp_date = datetime.strptime(exp_date_raw[:10], "%Y-%m-%d").date()
        elif isinstance(exp_date_raw, datetime):
            exp_date = exp_date_raw.date()
        else:
            exp_date = exp_date_raw

        days_remaining = (exp_date - date.today()).days

        if days_remaining > 10:
            return {
                "status": "NOT_YET_ELIGIBLE",
                "days_remaining": days_remaining,
                "message": f"Policy is active and expires in {days_remaining} days. Pre-renewal offers become available 10 days prior to expiration."
            }

        current_annual = _num(row.get("annual_premium"), 1500.0)
        current_dwelling = _num(row.get("dwelling_coverage"), 300000.0)
        current_pp = _num(row.get("personal_property_coverage"), current_dwelling * 0.50)
        current_deductible = _num(row.get("deductible_amount"), 1000.0)

        # Apply pre-renewal discount to annual premium
        discounted_annual = _money(current_annual * (1.0 - PRE_RENEWAL_DISCOUNT_PCT))
        discounted_monthly = _money(discounted_annual / 12)

        # Calculate standard vs boosted max claim capacity
        standard_claim_capacity = calculate_max_claim_capacity(current_dwelling, current_pp, current_deductible)
        
        # Boosted dwelling/coverage pool on pre-renewal
        boosted_dwelling = current_dwelling * CLAIM_LIMIT_BOOST_MULTIPLIER
        boosted_pp = current_pp * CLAIM_LIMIT_BOOST_MULTIPLIER
        boosted_claim_capacity = calculate_max_claim_capacity(boosted_dwelling, boosted_pp, current_deductible)

        return {
            "status": "SUCCESS",
            "policy_id": str(policy_id).strip(),
            "pre_renewal_eligible": True,
            "days_remaining": days_remaining,
            "current_terms": {
                "annual_premium": current_annual,
                "claim_capacity": standard_claim_capacity,
            },
            "pre_renewal_offer": {
                "discount_applied_pct": PRE_RENEWAL_DISCOUNT_PCT * 100,
                "proposed_annual_premium": discounted_annual,
                "proposed_monthly_premium": discounted_monthly,
                "enhanced_claim_capacity": boosted_claim_capacity,
                "benefit_note": (
                    f"By pre-renewing early, you receive an {int(PRE_RENEWAL_DISCOUNT_PCT * 100)}% loyalty discount "
                    f"(${discounted_annual:,.2f}/yr instead of ${current_annual:,.2f}/yr) and your maximum net "
                    f"claim payout capacity gets boosted up to ${boosted_claim_capacity['net_max_payout_capacity']:,.2f}."
                )
            },
            "message": f"Your policy is expiring in {days_remaining} day(s). You are eligible for our pre-renewal discount offer!"
        }

    except Exception as exc:
        logger.exception("Pre-renewal calculation failed")
        return {
            "status": "FAILED",
            "policy_id": str(policy_id).strip() if policy_id else None,
            "message": str(exc),
        }


__all__ = ["calculate_pre_renewal", "calculate_max_claim_capacity"]