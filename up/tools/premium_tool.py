"""
Dynamic Premium Calculation Tool for Broker Productivity Agent.

Used to dynamically recalculate annual and monthly premiums
whenever policy type, coverage amounts, deductibles, add-ons,
or property features (such as roof age & roof material) change.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def calculate_premium(
    policy_type: Optional[str] = "HO-3",
    dwelling_coverage: Optional[int] = 300000,
    personal_property_coverage: Optional[int] = 150000,
    liability_limit: Optional[int] = 100000,
    deductible_amount: Optional[int] = 1000,
    add_ons: Optional[str] = "",
    roof_age: Optional[int] = None,
    roof_material: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Dynamically calculate the annual and monthly insurance premium based on policy & property ratings.

    Parameters
    ----------
    policy_type:
        Policy type/form (e.g. "HO-3" = $1,000 base, "HO-5" = $1,500 base).
    dwelling_coverage:
        Dwelling coverage limit (INTEGER, e.g. 350000).
    personal_property_coverage:
        Personal property coverage limit (INTEGER, e.g. 175000).
    liability_limit:
        Liability limit amount (INTEGER, e.g. 300000).
    deductible_amount:
        Deductible amount (INTEGER, e.g. 1000, 1500, 2500).
    add_ons:
        Comma-separated string of active add-ons (e.g. "Water Backup, Service Line").
    roof_age:
        Age of property roof in years (INTEGER, e.g. 0, 5, 10, 18, 22).
    roof_material:
        Material of property roof (STRING, e.g. "Metal", "Tile", "Slate", "Asphalt", "Wood").

    Returns
    -------
    Dict:
        JSON response containing calculated annual_premium, monthly_premium, and cost breakdown.
    """
    logger.info("=" * 70)
    logger.info("CALCULATE PREMIUM")
    logger.info("Policy Type        : %s", policy_type)
    logger.info("Dwelling Coverage  : %s", dwelling_coverage)
    logger.info("Personal Property  : %s", personal_property_coverage)
    logger.info("Liability Limit    : %s", liability_limit)
    logger.info("Deductible Amount  : %s", deductible_amount)
    logger.info("Add-ons            : %s", add_ons)
    logger.info("Roof Age           : %s", roof_age)
    logger.info("Roof Material      : %s", roof_material)
    logger.info("=" * 70)

    try:
        # 1. Base Policy Form Rating
        pt_clean = str(policy_type).upper().replace("-", "").strip() if policy_type else "HO3"
        if "HO5" in pt_clean:
            base_premium = 1500.0
            form_name = "HO-5 Comprehensive Form"
        else:
            base_premium = 1000.0
            form_name = "HO-3 Special Form"

        # 2. Add-ons Rating
        addons_cost = 0.0
        active_addons = []
        if add_ons:
            addons_lower = str(add_ons).lower()
            if "water backup" in addons_lower or "water_backup" in addons_lower:
                addons_cost += 500.0
                active_addons.append("Water Backup ($500)")
            if "service line" in addons_lower or "service_line" in addons_lower:
                addons_cost += 700.0
                active_addons.append("Service Line ($700)")

        # 3. Dwelling Coverage Adjustment (Benchmark: $300,000)
        dwelling = int(dwelling_coverage) if dwelling_coverage else 300000
        dwelling_diff = dwelling - 300000
        dwelling_adj = (dwelling_diff / 50000.0) * 100.0

        # 4. Personal Property Coverage Adjustment (Benchmark: 50% of Dwelling)
        p_prop = int(personal_property_coverage) if personal_property_coverage else int(dwelling * 0.5)
        pp_benchmark = int(dwelling * 0.5)
        pp_diff = p_prop - pp_benchmark
        pp_adj = (pp_diff / 10000.0) * 25.0

        # 5. Liability Limit Adjustment (Benchmark: $100,000)
        liability = int(liability_limit) if liability_limit else 100000
        if liability >= 500000:
            liability_adj = 100.0
        elif liability >= 300000:
            liability_adj = 50.0
        else:
            liability_adj = 0.0

        # 6. Deductible Discount / Surcharge Adjustment (Benchmark: $1,000)
        deductible = int(deductible_amount) if deductible_amount else 1000
        if deductible <= 500:
            deductible_adj = 150.0  # Lower deductible = higher risk / surcharge
        elif deductible == 1500:
            deductible_adj = -100.0 # Higher deductible = discount
        elif deductible >= 2500:
            deductible_adj = -250.0
        elif deductible >= 5000:
            deductible_adj = -400.0
        else:
            deductible_adj = 0.0

        # 7. Roof Age Rating Tiers (New Roof Discount vs Aging Roof Surcharge)
        roof_age_adj = 0.0
        roof_age_tier_desc = "Standard Roof Age (8-15 yrs)"
        if roof_age is not None:
            rage = int(roof_age)
            if rage <= 3:
                roof_age_adj = -200.0  # Tier 1: Brand New Roof (0-3 yrs)
                roof_age_tier_desc = f"Brand New Roof ({rage} yrs): -$200.00 Discount (Ultra Low Risk)"
            elif rage <= 7:
                roof_age_adj = -100.0  # Tier 2: Preferred New Roof (4-7 yrs)
                roof_age_tier_desc = f"Preferred New Roof ({rage} yrs): -$100.00 Discount (Low Risk)"
            elif rage <= 15:
                roof_age_adj = 0.0     # Tier 3: Standard Roof (8-15 yrs)
                roof_age_tier_desc = f"Standard Roof ({rage} yrs): $0.00 Base Rating"
            elif rage <= 20:
                roof_age_adj = 150.0   # Tier 4: Aging Roof (16-20 yrs)
                roof_age_tier_desc = f"Aging Roof ({rage} yrs): +$150.00 Surcharge (Moderate Wear Risk)"
            else:
                roof_age_adj = 300.0   # Tier 5: Old Roof (> 20 yrs)
                roof_age_tier_desc = f"Old Roof ({rage} yrs): +$300.00 Surcharge (High Leak/Storm Risk)"

        # 8. Roof Material Rating Tiers (Durable Material Discount vs Wood Surcharge)
        roof_mat_adj = 0.0
        roof_mat_tier_desc = "Standard Roof Material (Asphalt)"
        if roof_material:
            rmat_lower = str(roof_material).lower().strip()
            if "metal" in rmat_lower:
                roof_mat_adj = -150.0  # Metal Roof (Wind & Hail Impact Resistant)
                roof_mat_tier_desc = "Metal Roof: -$150.00 Discount (High Wind/Hail Impact Resistance)"
            elif "tile" in rmat_lower:
                roof_mat_adj = -125.0  # Tile Roof (Fire & Storm Resistant)
                roof_mat_tier_desc = "Tile Roof: -$125.00 Discount (Fire & Storm Resistance)"
            elif "slate" in rmat_lower:
                roof_mat_adj = -100.0  # Slate Roof (Heavy Duty)
                roof_mat_tier_desc = "Slate Roof: -$100.00 Discount (Durable Heavy Duty Material)"
            elif "wood" in rmat_lower:
                roof_mat_adj = 150.0   # Wood Shake/Shingle (Fire Risk Surcharge)
                roof_mat_tier_desc = "Wood Roof: +$150.00 Surcharge (Higher Fire Hazard Risk)"
            else:
                roof_mat_adj = 0.0
                roof_mat_tier_desc = f"Standard {roof_material} Roof: $0.00 Base Rating"

        # Total Calculation
        total_annual = (
            base_premium
            + addons_cost
            + dwelling_adj
            + pp_adj
            + liability_adj
            + deductible_adj
            + roof_age_adj
            + roof_mat_adj
        )
        total_annual = max(500.0, round(total_annual, 2))
        total_monthly = round(total_annual / 12.0, 2)

        return {
            "status": "SUCCESS",
            "annual_premium": total_annual,
            "monthly_premium": total_monthly,
            "breakdown": {
                "base_policy_form": f"{form_name} (${base_premium})",
                "add_ons_cost": addons_cost,
                "active_addons": active_addons,
                "dwelling_adjustment": round(dwelling_adj, 2),
                "personal_property_adjustment": round(pp_adj, 2),
                "liability_adjustment": round(liability_adj, 2),
                "deductible_adjustment": round(deductible_adj, 2),
                "roof_age_adjustment": round(roof_age_adj, 2),
                "roof_age_rating_tier": roof_age_tier_desc,
                "roof_material_adjustment": round(roof_mat_adj, 2),
                "roof_material_rating_tier": roof_mat_tier_desc,
            },
            "message": f"Recalculated Annual Premium: ${total_annual:,.2f} (${total_monthly:,.2f}/month)",
        }

    except Exception as e:
        logger.exception("Premium calculation error")
        return {
            "status": "FAILED",
            "message": f"Calculation error: {str(e)}",
        }


__all__ = ["calculate_premium"]
