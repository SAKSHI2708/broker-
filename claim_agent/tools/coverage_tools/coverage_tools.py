#new 1/9/26

from google.adk.tools import ToolContext
from datetime import date


def validate_coverage(tool_context: ToolContext):
    """
    Runs immediately after intake — before inspection or calculation.
    Checks policy status, date range, and whether this POC currently
    supports the reported peril (wind/hail roof claims only).
    Never calculates a cost figure — that happens two stages later.
    """

    claim_context = tool_context.state.get("claim_context")
    claim_type = tool_context.state.get("claim_type")

    if not claim_context:
        return {"status": "ERROR", "message": "Claim context not found."}

    policy = claim_context["policy"]
    notes = []

    # 1. Policy status
    policy_active = policy["policy_status"] == "Active"
    if not policy_active:
        notes.append(f"Policy status is '{policy['policy_status']}', not Active.")

    # 2. Date range
    incident_date_str = tool_context.state.get("incident_date")
    within_policy_period = True
    if incident_date_str:
        incident = date.fromisoformat(incident_date_str)
        effective = date.fromisoformat(str(policy["effective_date"]))
        expiration = date.fromisoformat(str(policy["expiration_date"]))
        within_policy_period = effective <= incident <= expiration
        if not within_policy_period:
            notes.append(
                f"Incident date {incident_date_str} falls outside the policy "
                f"period ({policy['effective_date']} to {policy['expiration_date']})."
            )
    else:
        notes.append("No incident date on record.")

    # 3. Peril supported — ONLY wind/hail roof claims for this POC
    if not claim_type:
        peril_supported = False
        notes.append("No claim type provided.")
    else:
        peril_supported = claim_type.strip().lower() in [
            "wind damage",
            "hail damage",
        ]
        if not peril_supported:
            notes.append(
                f"'{claim_type}' is not yet supported."
            )

    is_eligible = policy_active and within_policy_period and peril_supported

    result = {
        "status": "SUCCESS",
        "is_eligible": is_eligible,
        "policy_active": policy_active,
        "within_policy_period": within_policy_period,
        "peril_supported": peril_supported,
        "deductible_amount": policy["deductible_amount"],
        "coverage_amount": policy["coverage_amount"],
        "notes": notes,
        "coverage_status": "Potentially Covered" if is_eligible else "Not Eligible",
    }

    tool_context.state["coverage_validation"] = result
    return result