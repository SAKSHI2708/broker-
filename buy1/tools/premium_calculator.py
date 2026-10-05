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
    property_type: str,
    square_footage: int,
    number_of_floors: int,
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
        area = int(square_footage)
        floors = int(number_of_floors)
    except (TypeError, ValueError):
        return {
            "status": "ERROR",
            "message": "Property value, year built, roof age, square footage, and floors must be integers.",
        }

    if coverage <= 0 or roof_years < 0 or area <= 0 or floors <= 0:
        return {
            "status": "ERROR",
            "message": "Property value, square footage, and floors must be positive; roof age cannot be negative.",
        }

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

    material = (roof_material or "").strip().lower()
    construction = (construction_type or "").strip().lower()
    property_kind = (property_type or "").strip().lower()
    property_factors = {
        "property_type": {
            "single family": 1.0,
            "single-family": 1.0,
            "condo": 0.65,
            "townhouse": 0.90,
        },
        "roof_material": {
            "metal": 0.925,
            "slate": 0.925,
            "wood": 1.20,
            "wood shingle": 1.20,
            "wood shake": 1.20,
            "shake": 1.20,
        },
        "construction_type": {
            "brick": 0.94,
            "concrete": 0.94,
            "stone": 0.94,
            "wood": 1.05,
            "wood frame": 1.05,
            "frame": 1.05,
        },
    }
    factors = {
        "property_type": property_factors["property_type"].get(property_kind, 1.0),
        "square_footage": max(0.80, min(1.20, 1 + (area - 2000) / 20000)),
        "number_of_floors": 1 + 0.03 * (floors - 1),
        "roof_material": property_factors["roof_material"].get(material, 1.0),
        "roof_age": 0.95 if roof_years <= 10 else 1.15 if roof_years >= 20 else 1.10 if roof_years >= 15 else 1.0,
        "construction_type": property_factors["construction_type"].get(construction, 1.0),
        "year_built": 0.97 if built >= 2015 else 1.10 if 0 < built < 1980 else 1.0,
    }
    property_factor = 1.0
    for factor in factors.values():
        property_factor *= factor

    risk_factor = 1 + total_points * 0.04
    deductible_rate = 0.02
    base_rate = 0.004
    ho3_premium = round(coverage * base_rate * property_factor * risk_factor)
    ho5_premium = round(ho3_premium * 1.20)

    def quote(
        policy_type: str, policy_factor: float, premium: int
    ) -> dict[str, Any]:
        return {
            "policy_type": policy_type,
            "coverage_amount": coverage,
            "policy_factor": policy_factor,
            "deductible": round(coverage * deductible_rate),
            "annual_premium": premium,
            "monthly_premium": round(premium / 12, 2),
        }

    quotes = [
        quote("HO-3", 1.00, ho3_premium),
        quote("HO-5", 1.20, ho5_premium),
    ]
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
        "base_rate": base_rate,
        "base_premium": round(coverage * base_rate),
        "adjustment_factors": {
            **factors,
            "verified_risk": risk_factor,
            "ho5_policy": 1.20,
            "deductible_rate": deductible_rate,
        },
        "recommendation": recommendation,
        "quotes": quotes,
    }