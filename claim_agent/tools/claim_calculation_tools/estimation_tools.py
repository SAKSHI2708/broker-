import os
from google.adk.tools import ToolContext


# ============================================================
# POC PRICING & REGIONAL CONFIGURATION
# ============================================================
# Baseline trade rates per square foot (USD) by state and roof material.
# ============================================================

US_ROOF_RATES = {
    # Texas
    "TX": {
        "asphalt_shingle": 5.25,
        "metal": 9.00,
        "tile": 11.00,
        "slate": 15.00,
    },
    # California
    "CA": {
        "asphalt_shingle": 7.50,
        "metal": 11.00,
        "tile": 14.00,
        "slate": 18.00,
    },
    # Florida
    "FL": {
        "asphalt_shingle": 6.00,
        "metal": 10.00,
        "tile": 12.00,
        "slate": 17.00,
    },
    # New York
    "NY": {
        "asphalt_shingle": 7.00,
        "metal": 11.00,
        "tile": 13.00,
        "slate": 17.00,
    },
    # Default for other U.S. states
    "DEFAULT": {
        "asphalt_shingle": 5.50,
        "metal": 9.50,
        "tile": 12.00,
        "slate": 16.00,
    },
}


# ============================================================
# LABOR VS. MATERIAL COST RATIOS BY STATE
# ============================================================
# Represents regional trade labor cost weightings vs. materials.
# ============================================================

LABOR_MATERIAL_SPLIT = {
    "TX": {"labor_ratio": 0.45, "material_ratio": 0.55},
    "CA": {"labor_ratio": 0.60, "material_ratio": 0.40},
    "FL": {"labor_ratio": 0.45, "material_ratio": 0.55},
    "NY": {"labor_ratio": 0.55, "material_ratio": 0.45},
    "DEFAULT": {"labor_ratio": 0.50, "material_ratio": 0.50},
}


# ============================================================
# METRO / ZIP CODE MULTIPLIERS (3-Digit ZIP Prefix)
# ============================================================
# Adjusts state baseline rates for high-cost urban/metro zones.
# ============================================================

ZIP_METRO_MULTIPLIERS = {
    # California High-Cost Urban (LA, Bay Area, SF)
    "900": 1.15, "901": 1.15, "902": 1.15, "941": 1.25, "940": 1.25, "943": 1.25,
    # New York Metro (Westchester, Long Island, NYC)
    "100": 1.20, "101": 1.20, "106": 1.12, "115": 1.10, "117": 1.10,
    # Florida High-Cost Coastal (Miami, Tampa)
    "331": 1.12, "332": 1.12, "336": 1.08,
    # Texas High-Cost Metro (Houston, Dallas)
    "770": 1.05, "752": 1.05,
}


# ------------------------------------------------------------
# Other Estimating Assumptions
# ------------------------------------------------------------

ROOF_REMOVAL_RATE = 1.25
DEBRIS_DISPOSAL_RATE = 0.40
DECKING_RATE = 2.50
REPAIR_FACTOR = 1.35

# Baseline Roof Lifespan (Years)
DEFAULT_ROOF_USEFUL_LIFE_YEARS = 20

PERMIT_COST = 0.0
CURRENCY = "USD"

PRICING_BASIS = (
    "Preliminary U.S. public-market Replacement Cost Value (RCV) estimate. "
    "Calculated using state base rates, ZIP code metro adjustments, and "
    "regional trade labor/materials splits."
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _normalize_roof_material(roof_material: str) -> str:
    """Converts different roof material names into configuration keys."""
    if not roof_material:
        return "asphalt_shingle"

    material = roof_material.strip().lower()

    replacements = {
        "asphalt shingle": "asphalt_shingle",
        "asphalt shingles": "asphalt_shingle",
        "composition shingle": "asphalt_shingle",
        "composition shingles": "asphalt_shingle",
        "metal roof": "metal",
        "metal roofing": "metal",
        "tile roof": "tile",
        "tile roofing": "tile",
        "slate roof": "slate",
        "slate roofing": "slate",
    }

    return replacements.get(material, material.replace(" ", "_"))


def _get_zip_multiplier(zip_code: str) -> float:
    """Looks up a 3-digit ZIP prefix factor to adjust for local metro costs."""
    if not zip_code:
        return 1.00
    
    clean_zip = str(zip_code).strip()[:3]
    return ZIP_METRO_MULTIPLIERS.get(clean_zip, 1.00)


def _get_us_roof_rate(state: str, roof_material: str, zip_code: str = ""):
    """
    Returns state-specific POC roof rate adjusted for ZIP code metro factor.
    """
    state = (state or "").strip().upper()
    roof_material = _normalize_roof_material(roof_material)

    if not state:
        return {
            "status": "ERROR",
            "message": "Property state is missing.",
            "human_review_required": True,
        }

    state_rates = US_ROOF_RATES.get(state, US_ROOF_RATES["DEFAULT"])
    base_rate = state_rates.get(
        roof_material,
        state_rates.get("asphalt_shingle", US_ROOF_RATES["DEFAULT"]["asphalt_shingle"])
    )

    # Apply ZIP Metro Multiplier
    zip_multiplier = _get_zip_multiplier(zip_code)
    final_rate = float(base_rate) * zip_multiplier

    pricing_region = state if state in US_ROOF_RATES else "US_DEFAULT"

    return {
        "status": "SUCCESS",
        "state": state,
        "zip_code": zip_code,
        "roof_material": roof_material,
        "base_rate_per_sqft": float(base_rate),
        "zip_multiplier": zip_multiplier,
        "rate_per_sqft": final_rate,
        "pricing_region": pricing_region,
    }


def _get_float(value, default=0.0):
    """Safely converts numeric values into float."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ============================================================
# MAIN CLAIM ESTIMATION TOOL
# ============================================================

def calculate_claim_from_damage(tool_context: ToolContext):
    """
    Calculates Replacement Cost Value (RCV), Actual Cash Value (ACV),
    Labor/Material splits, and Net Payable Claim Amount based on 
    Vision Agent damage assessments and policy parameters.
    """

    # --------------------------------------------------------
    # 1. Get claim context
    # --------------------------------------------------------
    claim_context = tool_context.state.get("claim_context")
    if not claim_context:
        return {"status": "ERROR", "message": "Claim context not found."}

    # --------------------------------------------------------
    # 2. Get damage assessment
    # --------------------------------------------------------
    damage = tool_context.state.get("damage_assessment")
    if not damage:
        return {"status": "ERROR", "message": "Damage assessment not found."}

    policy = claim_context.get("policy", {})
    property_details = claim_context.get("property", {})

    # --------------------------------------------------------
    # 3. Validate Location (State & ZIP)
    # --------------------------------------------------------
    property_state = (property_details.get("state") or "").strip().upper()
    zip_code = str(property_details.get("zip_code") or "").strip()

    if not property_state:
        return {
            "status": "ERROR",
            "message": "Property state is missing.",
            "human_review_required": True
        }

    # --------------------------------------------------------
    # 4. Get Roof Square Footage
    # --------------------------------------------------------
    roof_area_sqft = _get_float(property_details.get("roof_area_sqft"))
    if roof_area_sqft <= 0:
        return {
            "status": "ERROR",
            "message": "Roof area square footage is missing or invalid.",
            "human_review_required": True
        }

    # --------------------------------------------------------
    # 5. Get Roof Material
    # --------------------------------------------------------
    roof_material = _normalize_roof_material(property_details.get("roof_material"))

    # --------------------------------------------------------
    # 6. Get Damage Measurement from Vision Agent
    # --------------------------------------------------------
    measurable = damage.get("measurable", False)
    raw_percent = damage.get("affected_area_percent")

    if not measurable or raw_percent is None:
        return {
            "status": "ERROR",
            "message": (
                "Damage assessment could not measure the affected area. "
                "Human review is required before calculating a cost estimate."
            ),
            "human_review_required": True
        }

    damage_percent = max(0.0, min(_get_float(raw_percent), 100.0))

    # --------------------------------------------------------
    # 7. Get Affected Roof Area
    # --------------------------------------------------------
    affected_area_sqft = damage.get("affected_area_sqft")
    if affected_area_sqft is None:
        affected_area_sqft = roof_area_sqft * damage_percent / 100.0
    else:
        affected_area_sqft = _get_float(affected_area_sqft)

    if affected_area_sqft <= 0:
        return {
            "status": "ERROR",
            "message": "Affected roof area is invalid.",
            "human_review_required": True
        }

    # --------------------------------------------------------
    # 8. Get Adjusted Pricing Rate (State + ZIP)
    # --------------------------------------------------------
    rate_result = _get_us_roof_rate(property_state, roof_material, zip_code)
    if rate_result["status"] != "SUCCESS":
        return rate_result

    rate_per_sqft = rate_result["rate_per_sqft"]
    base_rate_per_sqft = rate_result["base_rate_per_sqft"]
    zip_multiplier = rate_result["zip_multiplier"]
    pricing_region = rate_result["pricing_region"]

    # --------------------------------------------------------
    # 9. Determine Repair vs. Replacement
    # --------------------------------------------------------
    severity = damage.get("severity", "Unknown")
    determination = (damage.get("repair_or_replace", "uncertain") or "uncertain").strip().lower()

    if determination not in {"repair", "replace"}:
        return {
            "status": "ERROR",
            "message": (
                "Vision assessment could not determine whether the damaged roof "
                "should be repaired or replaced."
            ),
            "human_review_required": True
        }

    # --------------------------------------------------------
    # 10. Calculate Direct Damage Cost Components
    # --------------------------------------------------------
    roofing_cost = 0.0
    removal_cost = 0.0
    disposal_cost = 0.0
    decking_cost = 0.0

    if determination == "replace":
        roofing_cost = affected_area_sqft * rate_per_sqft
        removal_cost = affected_area_sqft * ROOF_REMOVAL_RATE
        disposal_cost = affected_area_sqft * DEBRIS_DISPOSAL_RATE

        # Decking replacement (only if specified by Vision tool)
        damaged_components = damage.get("damaged_components", [])
        normalized_components = [str(c).strip().lower() for c in damaged_components]
        decking_damaged = any("decking" in c or "sheathing" in c for c in normalized_components)

        if decking_damaged:
            decking_cost = affected_area_sqft * DECKING_RATE

    elif determination == "repair":
        roofing_cost = affected_area_sqft * rate_per_sqft * REPAIR_FACTOR

    permit_and_inspection = PERMIT_COST

    direct_cost = (
        roofing_cost
        + removal_cost
        + disposal_cost
        + decking_cost
        + permit_and_inspection
    )

    # --------------------------------------------------------
    # 11. Calculate Labor vs. Material Split
    # --------------------------------------------------------
    split_info = LABOR_MATERIAL_SPLIT.get(
        property_state,
        LABOR_MATERIAL_SPLIT["DEFAULT"]
    )
    labor_ratio = split_info["labor_ratio"]
    material_ratio = split_info["material_ratio"]

    labor_cost = direct_cost * labor_ratio
    material_cost = direct_cost * material_ratio

    # --------------------------------------------------------
    # 12. Replacement Cost Value (RCV)
    # --------------------------------------------------------
    # Replacement Cost Value is equivalent to the direct construction cost.
    rcv = direct_cost

    # --------------------------------------------------------
    # 13. Depreciation & Actual Cash Value (ACV)
    # --------------------------------------------------------
    roof_age = _get_float(property_details.get("roof_age"))
    useful_life = DEFAULT_ROOF_USEFUL_LIFE_YEARS

    depreciation_rate = min(roof_age / useful_life, 1.0)
    depreciation_amount = rcv * depreciation_rate
    acv = max(rcv - depreciation_amount, 0.0)

    # --------------------------------------------------------
    # 14. Policy Limits & Deductible Application
    # --------------------------------------------------------
    deductible = _get_float(policy.get("deductible_amount"))
    coverage_amount = _get_float(policy.get("coverage_amount"))

    # Net Preliminary Payment (ACV - Deductible, capped at Coverage Limit)
    preliminary_claim_payment = min(
        max(acv - deductible, 0.0),
        coverage_amount
    )

    # --------------------------------------------------------
    # 15. Build Result Dictionary
    # --------------------------------------------------------
    result = {
        "status": "SUCCESS",
        "claim_type": "roof",
        "damage_type": damage.get("damage_type"),
        "severity": severity,
        "repair_or_replace": determination,
        "damaged_components": damage.get("damaged_components", []),

        # Property & Geographic Details
        "state": property_state,
        "zip_code": zip_code,
        "pricing_region": pricing_region,
        "zip_metro_multiplier": round(zip_multiplier, 2),
        "roof_material": roof_material,
        "roof_area_square_feet": round(roof_area_sqft, 2),

        # Damage Quantities
        "affected_area_percent": round(damage_percent, 2),
        "affected_area_square_feet": round(affected_area_sqft, 2),

        # Rate Metrics
        "base_rate_per_square_foot": round(base_rate_per_sqft, 2),
        "rate_per_square_foot": round(rate_per_sqft, 2),

        # Line-Item Cost Breakdown
        "roofing_cost": round(roofing_cost, 2),
        "removal_cost": round(removal_cost, 2),
        "debris_disposal": round(disposal_cost, 2),
        "decking_allowance": round(decking_cost, 2),
        "permit_and_inspection": round(permit_and_inspection, 2),
        "direct_damage_cost": round(direct_cost, 2),

        # Trade Cost Allocation
        "labor_ratio_percent": round(labor_ratio * 100, 2),
        "material_ratio_percent": round(material_ratio * 100, 2),
        "estimated_labor_cost": round(labor_cost, 2),
        "estimated_material_cost": round(material_cost, 2),

        # Core Valuation Figures (RCV vs ACV)
        "replacement_cost_value_rcv": round(rcv, 2),
        "roof_age": round(roof_age, 2),
        "useful_life_years": useful_life,
        "depreciation_rate_percent": round(depreciation_rate * 100, 2),
        "depreciation_amount": round(depreciation_amount, 2),
        "actual_cash_value_acv": round(acv, 2),

        # Policy & Settlement Breakdown
        "deductible": round(deductible, 2),
        "coverage_amount": round(coverage_amount, 2),
        "preliminary_claim_payment": round(preliminary_claim_payment, 2),
        "currency": CURRENCY,

        # Audit & Methodological Notes
        "pricing_basis": PRICING_BASIS,
        "human_review_required": False,
    }

    # Save output into session state for downstream processing/BigQuery updates
    tool_context.state["cost_estimate"] = result

    return result