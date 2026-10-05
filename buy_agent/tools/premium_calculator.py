"""Transparent homeowners quote calculator for HO-3 and HO-5 comparisons."""

from __future__ import annotations

from typing import Any


RISK_POINTS = {"low": 0, "medium": 1, "high": 2}
RISK_LABELS = {"low": "Low", "medium": "Medium", "high": "High"}


def _normalise_risk(value: str) -> str:
    risk = (value or "").strip().lower()
    return risk


def calculate_homeowners_quotes(
    estimated_value: int,
    year_built: int,
    roof_age: int,
    roof_material: str,
    construction_type: str,
    flood_risk: str,
    wind_risk: str,
    hail_risk: str,
    wildfire_risk: str,
    earthquake_risk: str,
    tornado_risk: str,
    lightning_risk: str,
    crime_risk: str,
) -> dict[str, Any]:
    """Return comparable HO-3 and HO-5 model estimates.

    This is a transparent estimate, not an insurer quote. The model deliberately
    excludes claims history and uses only the property and live risk inputs.
    """
    try:
        coverage = int(estimated_value)
        built = int(year_built)
        roof_years = int(roof_age)
    except (TypeError, ValueError):
        return {"status": "ERROR", "message": "Property value, year built, and roof age must be integers."}

    if coverage <= 0 or roof_years < 0:
        return {"status": "ERROR", "message": "Property value must be positive and roof age cannot be negative."}

    risks = {
        "Flood": _normalise_risk(flood_risk),
        "Wind": _normalise_risk(wind_risk),
        "Hail": _normalise_risk(hail_risk),
        "Wildfire": _normalise_risk(wildfire_risk),
        "Earthquake": _normalise_risk(earthquake_risk),
        "Tornado": _normalise_risk(tornado_risk),
        "Lightning": _normalise_risk(lightning_risk),
        "Crime": _normalise_risk(crime_risk),
    }
    invalid_risks = [name for name, risk in risks.items() if risk not in RISK_POINTS]
    if invalid_risks:
        return {
            "status": "ERROR",
            "message": f"Missing or invalid risk value(s): {', '.join(invalid_risks)}. Use Low, Medium, or High.",
        }
    points = {name: RISK_POINTS[level] for name, level in risks.items()}
    total_points = sum(points.values())
    overall_risk = "high" if total_points >= 10 else "medium" if total_points >= 5 else "low"

    # These transparent model factors are placeholders until an insurer-approved
    # rate table is connected. They must not be presented as a carrier quote.
    property_factor = 1.0
    if 0 < built < 1980:
        property_factor += 0.10
    if roof_years >= 15:
        property_factor += 0.10
    if (roof_material or "").strip().lower() in {"wood", "wood shingle", "shake"}:
        property_factor += 0.05
    if (construction_type or "").strip().lower() in {"wood", "wood frame"}:
        property_factor += 0.05

    risk_factor = 1 + total_points * 0.04
    deductible_rate = {"low": 0.01, "medium": 0.02, "high": 0.025}[overall_risk]
    deductible_factor = {"low": 1.0, "medium": 0.90, "high": 0.85}[overall_risk]
    base_rate = 0.004

    def quote(policy_type: str, policy_factor: float) -> dict[str, Any]:
        premium = round(coverage * base_rate * property_factor * risk_factor * policy_factor * deductible_factor)
        return {
            "policy_type": policy_type,
            "coverage_amount": coverage,
            "deductible": round(coverage * deductible_rate),
            "annual_premium": premium,
            "monthly_premium": round(premium / 12, 2),
        }

    quotes = [quote("HO-3", 1.00), quote("HO-5", 1.20)]
    recommendation = (
        "HO-5 is recommended because it generally provides broader coverage for personal property."
        if coverage >= 250000
        else "HO-3 is recommended as the lower-cost standard option for this property value."
    )
    return {
        "status": "SUCCESS",
        "quote_type": "MODEL_ESTIMATE",
        "message": "These are transparent model estimates, not insurer-approved quotes.",
        "risk_points": points,
        "total_risk_score": total_points,
        "overall_risk": RISK_LABELS[overall_risk],
        "recommendation": recommendation,
        "quotes": quotes,
    }