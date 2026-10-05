"""Dedicated renewal premium rating tool for the Broker Productivity Agent.

Updated with realistic US-based rating factors, deductible relativity bands,
and comprehensive state catastrophe loads aligned with the BigQuery properties.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from google.cloud import bigquery

PROJECT_ID = "gcp-app-builder"
DATASET_ID = "Broker_Productivity"

client = bigquery.Client(project=PROJECT_ID)
logger = logging.getLogger(__name__)

ANNUAL_TREND_RATE = 0.055  # Realistic annual renewal trend rate (5.5%)

FORM_BASE = {
    "HO-3": 1450.0,
    "HO-5": 1780.0,
}

DEDUCTIBLE_FACTORS = {
    500: 1.12,
    1000: 1.00,
    2000: 0.92,
    5000: 0.78,
}

ROOF_AGE_FACTORS = [
    (0, 5, 0.88, "0-5 years"),
    (6, 10, 0.94, "6-10 years"),
    (11, 15, 1.00, "11-15 years"),
    (16, 20, 1.18, "16-20 years"),
    (21, 25, 1.35, "21-25 years"),
    (26, 999, 1.55, "26+ years"),
]

ROOF_MATERIAL_FACTORS = {
    "asphalt shingle": 1.00,
    "asphalt": 1.00,
    "metal": 0.94,
    "tile": 1.06,
    "wood shake": 1.18,
    "wood shake/shingle": 1.18,
    "wood": 1.18,
    "slate": 1.00,
}

LIABILITY_FACTORS = {
    100_000: 1.00,
    300_000: 1.04,
    500_000: 1.09,
    1_000_000: 1.18,
}

ADDON_PRICE = {
    "water backup": 350.0,
    "coverage line": 450.0,
}

DWELLING_ELASTICITY = 0.60
PERSONAL_PROPERTY_ELASTICITY = 0.20

CONSTRUCTION_ADJ = {
    "fire resistive": -150.0, "masonry veneer": -35.0, "masonry": -85.0,
    "steel": -60.0, "frame": 85.0, "wood": 85.0, "brick": -40.0, "concrete": -100.0, "concrete block": -90.0,
}
COINSURANCE_MIN_PCT = 0.80          
COINSURANCE_PENALTY_SCALE = 300.0   

RISK_RATE_TABLE = {
    "flood_risk":      {"low": 0.0, "moderate": 120.0, "medium": 120.0, "high": 350.0, "very high": 650.0, "extreme": 650.0},
    "earthquake_risk": {"low": 0.0, "moderate": 90.0,  "medium": 90.0,  "high": 280.0, "very high": 500.0, "extreme": 500.0},
    "wildfire_risk":   {"low": 0.0, "moderate": 90.0,  "medium": 90.0,  "high": 320.0, "very high": 580.0, "extreme": 580.0},
    "wind_risk":       {"low": 0.0, "moderate": 60.0,  "medium": 60.0,  "high": 180.0, "very high": 320.0, "extreme": 320.0},
    "hail_risk":       {"low": 0.0, "moderate": 40.0,  "medium": 40.0,  "high": 130.0, "very high": 220.0, "extreme": 220.0},
}
CRIME_SCORE_RATE = {"low": 0.0, "moderate": 20.0, "medium": 20.0, "high": 60.0, "very high": 110.0, "extreme": 110.0}

CLAIMS_FREQUENCY_SURCHARGE = {0: 0.0, 1: 120.0, 2: 320.0}
CLAIMS_FREQUENCY_SURCHARGE_3PLUS = 650.0
CLAIMS_EXCLUDED_STATUSES = {"denied", "rejected", "withdrawn", "cancelled"}
LARGE_CLAIM_THRESHOLD = 10_000.0
LARGE_CLAIM_SURCHARGE = 275.0
LARGE_CLAIM_SURCHARGE_CAP_COUNT = 2

STATE_TERRITORY_LOAD_PCT = {
    "FL": 0.35, "LA": 0.30, "TX": 0.18, "CA": 0.22, "OK": 0.20, 
    "CO": 0.12, "NC": 0.15, "SC": 0.15, "AZ": 0.08, "NV": 0.05, 
    "OR": 0.05, "WA": 0.08, "MA": 0.10, "VA": 0.08, "IN": 0.02, 
    "OH": 0.02, "WI": 0.02, "ID": 0.03, "UT": 0.05, "default": 0.05,
}

RATING_FIELDS = {
    "policy_name",
    "policy_type",
    "dwelling_coverage",
    "personal_property_coverage",
    "liability_limit",
    "deductible_amount",
    "add_ons",
    "roof_age",
    "roof_material",
}


def _num(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None or value == "":
        return default
    try:
        return float(Decimal(str(value)))
    except Exception as exc:
        raise ValueError(f"Invalid numeric value: {value!r}") from exc


def _money(value: float) -> float:
    return round(float(value), 2)


def _normalize_form(name: Any, policy_type: Any) -> str:
    for value in (name, policy_type):
        if not value:
            continue
        text = str(value).upper().replace(" ", "").replace("_", "")
        if "HO5" in text or "HO-5" in text:
            return "HO-5"
        if "HO3" in text or "HO-3" in text:
            return "HO-3"
    raise ValueError("Policy form must be HO-3 or HO-5.")


def _normalize_addons(value: Any) -> list[str]:
    if value is None or value == "" or str(value).strip().lower() == "none":
        return []

    raw = list(value) if isinstance(value, (list, tuple, set)) else str(value).split(",")
    result = []

    for item in raw:
        text = " ".join(str(item).lower().replace("_", " ").split())
        if text == "none":
            continue
        if text == "water backup":
            name = "Water Backup"
        elif text == "coverage line":
            name = "coverage line"
        else:
            raise ValueError(
                f"Unsupported add-on '{item}'. "
                "Supported add-ons: Water Backup, coverage line."
            )

        if name not in result:
            result.append(name)

    return result


def _addon_cost(addons: list[str]) -> float:
    return sum(ADDON_PRICE[a.lower()] for a in addons)


def _deductible_factor(value: float) -> tuple[float, str]:
    if value < 500 or value > 5000:
        raise ValueError("Deductible must be between $500 and $5,000 for this POC.")

    tiers = sorted(DEDUCTIBLE_FACTORS.items())

    if value in DEDUCTIBLE_FACTORS:
        return DEDUCTIBLE_FACTORS[int(value)], f"${value:,.0f} deductible tier"

    for (low_value, low_factor), (high_value, high_factor) in zip(tiers, tiers[1:]):
        if low_value < value < high_value:
            ratio = (value - low_value) / (high_value - low_value)
            factor = low_factor + ratio * (high_factor - low_factor)
            return factor, (
                f"${low_value:,.0f}-${high_value:,.0f} deductible band "
                f"(interpolated factor)"
            )

    raise ValueError("Unable to determine deductible rating factor.")


def _liability_factor(value: float) -> tuple[float, str]:
    if value not in LIABILITY_FACTORS:
        supported = ", ".join(f"${v:,.0f}" for v in sorted(LIABILITY_FACTORS))
        raise ValueError(f"Liability limit must be one of: {supported}.")
    return LIABILITY_FACTORS[int(value)], f"${value:,.0f} liability tier"


def _roof_age_factor(value: Any) -> tuple[float, str]:
    if value is None or value == "":
        return 1.0, "Roof age not provided"

    age = int(_num(value))
    if age < 0:
        raise ValueError("roof_age cannot be negative.")

    for minimum, maximum, factor, label in ROOF_AGE_FACTORS:
        if minimum <= age <= maximum:
            return factor, f"{label} roof-age tier"

    raise ValueError("Unable to determine roof-age rating factor.")


def _roof_material_factor(value: Any) -> tuple[float, str]:
    if not value:
        return 1.0, "Roof material not provided"

    text = " ".join(str(value).lower().replace("_", " ").split())

    for material, factor in ROOF_MATERIAL_FACTORS.items():
        if material in text:
            return factor, f"{value} roof-material tier"

    raise ValueError(
        f"Unsupported roof material '{value}'. "
        "Supported values include Asphalt, Asphalt Shingle, Metal, "
        "Tile, Wood, and Slate."
    )


def _coverage_factor(current: float, proposed: float, elasticity: float) -> float:
    if current <= 0 or proposed <= 0:
        raise ValueError("Coverage values must be positive.")
    return 1.0 + elasticity * ((proposed / current) - 1.0)


def _one_year_later(start: date) -> date:
    try:
        return start.replace(year=start.year + 1)
    except ValueError:
        return start.replace(year=start.year + 1, day=28)


def _construction_adjustment(value: Any) -> Tuple[float, str]:
    if not value:
        return 0.0, "Construction type not provided"
    text = str(value).lower()
    for key, adj in CONSTRUCTION_ADJ.items():
        if key in text:
            return adj, f"{value} Construction"
    return 0.0, f"{value} (standard construction)"


def _home_age_adjustment(year_built: Any) -> Tuple[float, str]:
    if year_built is None or year_built == "":
        return 0.0, "Year built not provided"
    year = int(_num(year_built))
    age = date.today().year - year
    if age < 0:
        raise ValueError("year_built cannot be in the future.")
    if age <= 10:
        return -80.0, f"New Home ({age} yrs)"
    if age <= 30:
        return 0.0, f"Standard Age Home ({age} yrs)"
    if age <= 50:
        return 130.0, f"Older Home ({age} yrs)"
    return 290.0, f"Vintage Home ({age} yrs)"


def _floors_adjustment(value: Any) -> Tuple[float, str]:
    if value is None or value == "":
        return 0.0, "Number of floors not provided"
    n = int(_num(value))
    if n <= 1:
        return 0.0, "Single-story"
    if n == 2:
        return 35.0, "Two-story"
    return 70.0, f"{n}-story (multi-level)"


def _coverage_adequacy_adjustment(dwelling_coverage: float, estimated_value: Any) -> Tuple[float, str]:
    ev = _num(estimated_value)
    if not ev or ev <= 0:
        return 0.0, "Estimated property value not available - adequacy not evaluated"
    required = ev * COINSURANCE_MIN_PCT
    if dwelling_coverage >= required:
        return 0.0, "Dwelling coverage meets 80% replacement-cost adequacy guideline"
    shortfall_pct = (required - dwelling_coverage) / required
    penalty = _money(shortfall_pct * COINSURANCE_PENALTY_SCALE)
    return penalty, f"Underinsured - dwelling coverage is {shortfall_pct * 100:.0f}% below the 80% adequacy guideline"


def _risk_adjustment(risk_key: str, value: Any) -> Tuple[float, str]:
    label = risk_key.replace("_", " ").title()
    if not value:
        return 0.0, f"{label} not provided"
    tier = str(value).strip().lower()
    adj = RISK_RATE_TABLE[risk_key].get(tier)
    if adj is None:
        return 0.0, f"{label}: {value} (unrecognized tier, no adjustment applied)"
    return adj, f"{label}: {value}"


def _crime_adjustment(value: Any) -> Tuple[float, str]:
    if not value:
        return 0.0, "Crime score not provided"
    tier = str(value).strip().lower()
    adj = CRIME_SCORE_RATE.get(tier)
    if adj is None:
        return 0.0, f"Crime Score: {value} (unrecognized tier, no adjustment applied)"
    return adj, f"Crime Score: {value}"


def _claims_surcharge(claims_rows: List[Dict[str, Any]]) -> Tuple[float, str, Dict[str, Any]]:
    counted = [c for c in claims_rows if str(c.get("claim_status") or "").strip().lower() not in CLAIMS_EXCLUDED_STATUSES]
    n = len(counted)
    freq_adj = CLAIMS_FREQUENCY_SURCHARGE.get(n, CLAIMS_FREQUENCY_SURCHARGE_3PLUS if n >= 3 else 0.0)

    large = [c for c in counted if (_num(c.get("approved_amount")) or _num(c.get("claim_amount")) or 0.0) > LARGE_CLAIM_THRESHOLD]
    large_counted = min(len(large), LARGE_CLAIM_SURCHARGE_CAP_COUNT)
    large_adj = large_counted * LARGE_CLAIM_SURCHARGE

    total = _money(freq_adj + large_adj)
    tier = f"{n} claim(s) on record"
    if large:
        tier += f", {len(large)} large loss(es) over ${LARGE_CLAIM_THRESHOLD:,.0f}"
    return total, tier, {"claim_count": n, "large_claim_count": len(large)}


def _territory_load(state: Any) -> Tuple[float, str]:
    if not state:
        return 0.0, "State/territory not available - no territory load applied"
    code = str(state).strip().upper()
    pct = STATE_TERRITORY_LOAD_PCT.get(code, STATE_TERRITORY_LOAD_PCT["default"])
    if pct:
        return pct, f"{code} territory load (+{pct * 100:.0f}%)"
    return 0.0, f"{code} territory (no load)"


def _trend(effective_date: Any) -> Tuple[float, float, str]:
    if not effective_date:
        return 0.0, 1.0, "Effective date not available - no renewal trend applied"
    try:
        if isinstance(effective_date, str):
            parsed = datetime.strptime(effective_date[:10], "%Y-%m-%d").date()
        elif isinstance(effective_date, datetime):
            parsed = effective_date.date()
        else:
            parsed = effective_date
        years = (date.today() - parsed).days / 365.25
    except Exception:
        return 0.0, 1.0, "Could not parse effective date - no renewal trend applied"
    years = max(0.0, years)
    mult = round((1 + ANNUAL_TREND_RATE) ** years, 6)
    return round(years, 2), mult, f"{years:.1f} yr(s) since inception @ {ANNUAL_TREND_RATE * 100:.1f}%/yr trend"


def _fetch(policy_id: str) -> Dict[str, Any]:
    query = f"""
    SELECT
        p.policy_id,
        p.policy_name,
        p.policy_type,
        p.policy_status,
        p.effective_date,
        p.expiration_date,
        p.dwelling_coverage,
        p.personal_property_coverage,
        p.liability_limit,
        p.deductible_amount,
        p.add_ons,
        p.annual_premium,
        p.monthly_premium,
        pr.roof_age,
        pr.roof_material,
        pr.year_built,
        pr.construction_type,
        pr.number_of_floors,
        pr.estimated_value,
        pr.state AS property_state,
        pr.city,
        pr.zip_code,
        r.flood_risk,
        r.wildfire_risk,
        r.wind_risk,
        r.hail_risk,
        r.earthquake_risk,
        r.crime_score
    FROM `{PROJECT_ID}.{DATASET_ID}.Policy1` p
    LEFT JOIN `{PROJECT_ID}.{DATASET_ID}.Property` pr
      ON p.property_id = pr.property_id
    LEFT JOIN `{PROJECT_ID}.{DATASET_ID}.Risk` r
      ON p.property_id = r.property_id
    WHERE p.policy_id = @policy_id
    LIMIT 1
    """

    config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "policy_id", "STRING", policy_id.strip()
            )
        ]
    )

    rows = list(client.query(query, job_config=config).result())

    if not rows:
        raise ValueError(f"Policy '{policy_id}' was not found.")

    return dict(rows[0])


def _fetch_claims(policy_id: str) -> List[Dict[str, Any]]:
    query = f"""
    SELECT claim_amount, approved_amount, claim_status, incident_date
    FROM `{PROJECT_ID}.{DATASET_ID}.Claims`
    WHERE policy_id = @policy_id
    """
    config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("policy_id", "STRING", policy_id.strip())
        ]
    )
    return [dict(r) for r in client.query(query, job_config=config).result()]


def _field_alias(raw: str) -> str:
    aliases = {
        "policy form": "policy_name",
        "form": "policy_name",
        "policy": "policy_name",
        "policy type": "policy_type",
        "type": "policy_type",
        "policy_type": "policy_type",
        "deductible": "deductible_amount",
        "deductible amount": "deductible_amount",
        "deductible_amount": "deductible_amount",
        "dwelling": "dwelling_coverage",
        "dwelling coverage": "dwelling_coverage",
        "dwelling_coverage": "dwelling_coverage",
        "personal property": "personal_property_coverage",
        "personal property coverage": "personal_property_coverage",
        "personal_property_coverage": "personal_property_coverage",
        "liability": "liability_limit",
        "liability limit": "liability_limit",
        "liability_limit": "liability_limit",
        "addons": "add_ons",
        "add-ons": "add_ons",
        "add ons": "add_ons",
        "add_ons": "add_ons",
        "roof age": "roof_age",
        "roof-age": "roof_age",
        "roof_age": "roof_age",
        "roof material": "roof_material",
        "roof-material": "roof_material",
        "roof_material": "roof_material",
    }
    normalized = str(raw).strip().lower()
    return aliases.get(normalized, normalized)


def calculate_renewal_premium(
    policy_id: str,
    proposed_changes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    try:
        if not policy_id or not str(policy_id).strip():
            raise ValueError("policy_id is required.")

        row = _fetch(str(policy_id).strip())
        claims_rows = _fetch_claims(str(policy_id).strip())

        status = str(row.get("policy_status") or "").upper()
        if status != "EXPIRED":
            if status == "ACTIVE":
                raise ValueError("Active policies do not require renewal.")
            raise ValueError("Only expired policies are eligible for this renewal flow.")

        stored_annual = _num(row.get("annual_premium"))
        if stored_annual is None or stored_annual <= 0:
            raise ValueError(
                "A valid current annual premium is required to calculate the renewal quote."
            )

        current = {
            "policy_name": row.get("policy_name"),
            "policy_type": row.get("policy_type"),
            "dwelling_coverage": _num(row.get("dwelling_coverage")),
            "personal_property_coverage": _num(row.get("personal_property_coverage")),
            "liability_limit": _num(row.get("liability_limit")),
            "deductible_amount": _num(row.get("deductible_amount")),
            "add_ons": row.get("add_ons"),
            "roof_age": _num(row.get("roof_age")),
            "roof_material": row.get("roof_material"),
        }

        proposed = dict(current)
        normalized_changes = {}

        for raw_field, value in (proposed_changes or {}).items():
            field = _field_alias(raw_field)

            if field not in RATING_FIELDS:
                raise ValueError(
                    f"'{raw_field}' is not supported for renewal rating. "
                    f"Supported fields: {sorted(RATING_FIELDS)}"
                )

            normalized_changes[field] = value

            if field in {
                "dwelling_coverage",
                "personal_property_coverage",
                "liability_limit",
                "deductible_amount",
                "roof_age",
            }:
                proposed[field] = _num(value)
            elif field == "add_ons":
                proposed[field] = _normalize_addons(value)
            else:
                proposed[field] = value

        current_form = _normalize_form(
            current.get("policy_name"), current.get("policy_type")
        )
        proposed_form = _normalize_form(
            proposed.get("policy_name"), proposed.get("policy_type")
        )

        current_addons = _normalize_addons(current.get("add_ons"))
        proposed_addons = _normalize_addons(proposed.get("add_ons"))

        current_dwelling = float(current["dwelling_coverage"] or 0)
        proposed_dwelling = float(proposed["dwelling_coverage"] or 0)
        current_pp = float(current["personal_property_coverage"] or 0)
        proposed_pp = float(proposed["personal_property_coverage"] or 0)
        current_liability = float(current["liability_limit"] or 0)
        proposed_liability = float(proposed["liability_limit"] or 0)
        current_deductible = float(current["deductible_amount"] or 0)
        proposed_deductible = float(proposed["deductible_amount"] or 0)

        trend_years, trend_mult, trend_note = _trend(row.get("effective_date"))
        renewal_rate_amount = _money(stored_annual * (trend_mult - 1.0))
        renewal_baseline = stored_annual + renewal_rate_amount

        construction_adj, construction_tier = _construction_adjustment(row.get("construction_type"))
        home_age_adj, home_age_tier = _home_age_adjustment(row.get("year_built"))
        floors_adj, floors_tier = _floors_adjustment(row.get("number_of_floors"))
        flood_adj, flood_tier = _risk_adjustment("flood_risk", row.get("flood_risk"))
        wildfire_adj, wildfire_tier = _risk_adjustment("wildfire_risk", row.get("wildfire_risk"))
        wind_adj, wind_tier = _risk_adjustment("wind_risk", row.get("wind_risk"))
        hail_adj, hail_tier = _risk_adjustment("hail_risk", row.get("hail_risk"))
        eq_adj, eq_tier = _risk_adjustment("earthquake_risk", row.get("earthquake_risk"))
        crime_adj, crime_tier = _crime_adjustment(row.get("crime_score"))
        claims_adj, claims_tier, claims_detail = _claims_surcharge(claims_rows)

        risk_data_refresh_amount = _money(
            construction_adj + home_age_adj + floors_adj + flood_adj +
            wildfire_adj + wind_adj + hail_adj + eq_adj + crime_adj + claims_adj
        )

        territory_pct, territory_tier = _territory_load(row.get("property_state"))
        baseline_with_risk_refresh = renewal_baseline + risk_data_refresh_amount
        territory_load_amount = _money(baseline_with_risk_refresh * territory_pct)
        pre_factor_total = baseline_with_risk_refresh + territory_load_amount

        current_ded_factor, current_ded_tier = _deductible_factor(current_deductible)
        proposed_ded_factor, proposed_ded_tier = _deductible_factor(proposed_deductible)

        current_liab_factor, current_liab_tier = _liability_factor(current_liability)
        proposed_liab_factor, proposed_liab_tier = _liability_factor(proposed_liability)

        current_roof_age_factor, current_roof_age_tier = _roof_age_factor(
            current.get("roof_age")
        )
        proposed_roof_age_factor, proposed_roof_age_tier = _roof_age_factor(
            proposed.get("roof_age")
        )

        current_roof_material_factor, current_roof_material_tier = _roof_material_factor(
            current.get("roof_material")
        )
        proposed_roof_material_factor, proposed_roof_material_tier = _roof_material_factor(
            proposed.get("roof_material")
        )

        current_form_factor = FORM_BASE[current_form]
        proposed_form_factor = FORM_BASE[proposed_form]

        form_relative = proposed_form_factor / current_form_factor
        deductible_relative = proposed_ded_factor / current_ded_factor
        liability_relative = proposed_liab_factor / current_liab_factor
        roof_age_relative = proposed_roof_age_factor / current_roof_age_factor
        roof_material_relative = (
            proposed_roof_material_factor / current_roof_material_factor
        )

        dwelling_relative = _coverage_factor(
            current_dwelling,
            proposed_dwelling,
            DWELLING_ELASTICITY,
        )
        personal_property_relative = _coverage_factor(
            current_pp,
            proposed_pp,
            PERSONAL_PROPERTY_ELASTICITY,
        )

        rating_multiplier = (
            form_relative
            * deductible_relative
            * liability_relative
            * roof_age_relative
            * roof_material_relative
            * dwelling_relative
            * personal_property_relative
        )

        factor_adjusted_premium = pre_factor_total * rating_multiplier

        current_addon_cost = _addon_cost(current_addons)
        proposed_addon_cost = _addon_cost(proposed_addons)
        addon_delta = proposed_addon_cost - current_addon_cost

        current_adequacy_adj, current_adequacy_tier = _coverage_adequacy_adjustment(
            current_dwelling, row.get("estimated_value")
        )
        proposed_adequacy_adj, proposed_adequacy_tier = _coverage_adequacy_adjustment(
            proposed_dwelling, row.get("estimated_value")
        )
        adequacy_delta = _money(proposed_adequacy_adj - current_adequacy_adj)

        proposed_annual = max(
            500.0,
            _money(factor_adjusted_premium + addon_delta + adequacy_delta),
        )
        proposed_monthly = _money(proposed_annual / 12)

        annual_change = _money(proposed_annual - stored_annual)
        monthly_change = _money(
            proposed_monthly - _money(stored_annual / 12)
        )

        percentage_change = (
            _money((annual_change / stored_annual) * 100)
            if stored_annual
            else 0.0
        )

        direction = (
            "INCREASE"
            if annual_change > 0
            else "DECREASE"
            if annual_change < 0
            else "NO_CHANGE"
        )

        reasons = [
            {
                "factor": "Renewal trend",
                "current": f"${stored_annual:,.2f}",
                "proposed": f"${renewal_baseline:,.2f}",
                "impact": _money(renewal_rate_amount),
                "reason": (
                    f"The new policy term applies an {ANNUAL_TREND_RATE * 100:.1f}%/yr "
                    f"renewal trend, compounded over the {trend_years:.1f} year(s) "
                    "since the policy's effective date."
                ),
            }
        ]

        if risk_data_refresh_amount != 0.0:
            reasons.append(
                {
                    "factor": "Risk data refresh (property, hazard, claims)",
                    "current": "Not previously priced",
                    "proposed": f"${risk_data_refresh_amount:,.2f}",
                    "impact": risk_data_refresh_amount,
                    "reason": (
                        "Construction type, home age, floor count, hazard risk tiers, "
                        "crime score, and claims loss history are factored into the renewal."
                    ),
                }
            )

        if territory_load_amount != 0.0:
            reasons.append(
                {
                    "factor": "Territory rating",
                    "current": row.get("property_state") or "Unknown",
                    "proposed": row.get("property_state") or "Unknown",
                    "impact": territory_load_amount,
                    "reason": territory_tier,
                }
            )

        def add_factor_reason(
            factor: str,
            current_value: Any,
            proposed_value: Any,
            relative_factor: float,
            reason: str,
        ):
            if current_value != proposed_value:
                reasons.append(
                    {
                        "factor": factor,
                        "current": current_value,
                        "proposed": proposed_value,
                        "impact": relative_factor,
                        "reason": reason,
                    }
                )

        add_factor_reason("Policy form", current_form, proposed_form, form_relative, "HO-5 has broader coverage than HO-3.")
        add_factor_reason("Dwelling coverage", f"${current_dwelling:,.0f}", f"${proposed_dwelling:,.0f}", dwelling_relative, "Dwelling coverage adjustment.")
        add_factor_reason("Personal property coverage", f"${current_pp:,.0f}", f"${proposed_pp:,.0f}", personal_property_relative, "Personal property coverage adjustment.")
        add_factor_reason("Liability limit", f"${current_liability:,.0f}", f"${proposed_liability:,.0f}", liability_relative, "Liability limit adjustment.")
        add_factor_reason("Deductible", f"${current_deductible:,.0f}", f"${proposed_deductible:,.0f}", deductible_relative, "Deductible factor adjustment.")
        add_factor_reason("Roof age", current.get("roof_age"), proposed.get("roof_age"), roof_age_relative, "Roof age factor.")
        add_factor_reason("Roof material", current.get("roof_material"), proposed.get("roof_material"), roof_material_relative, "Roof material factor.")

        if current_addons != proposed_addons:
            reasons.append(
                {
                    "factor": "Add-ons",
                    "current": current_addons or ["None"],
                    "proposed": proposed_addons or ["None"],
                    "impact": _money(addon_delta),
                    "reason": "Optional endorsements change.",
                }
            )

        if adequacy_delta != 0.0:
            reasons.append(
                {
                    "factor": "Coverage adequacy",
                    "current": current_adequacy_tier,
                    "proposed": proposed_adequacy_tier,
                    "impact": adequacy_delta,
                    "reason": "80% replacement-cost adequacy guideline check.",
                }
            )

        today = date.today()
        renewal_expiration = _one_year_later(today)

        changed_fields = {}
        for field in normalized_changes:
            old_value = current.get(field)
            new_value = proposed.get(field)
            if isinstance(old_value, Decimal):
                old_value = float(old_value)
            if isinstance(new_value, Decimal):
                new_value = float(new_value)
            changed_fields[field] = {
                "current": old_value,
                "proposed": new_value,
                "changed": old_value != new_value,
            }

        return {
            "status": "SUCCESS",
            "policy_id": str(policy_id).strip(),
            "location_context": {
                "state": row.get("property_state"),
                "city": row.get("city"),
                "zip_code": row.get("zip_code"),
            },
            "renewal_eligibility": "ELIGIBLE",
            "renewal_dates": {
                "effective_date": today.isoformat(),
                "expiration_date": renewal_expiration.isoformat(),
            },
            "current": {
                "policy_name": current_form,
                "dwelling_coverage": current_dwelling,
                "personal_property_coverage": current_pp,
                "liability_limit": current_liability,
                "deductible_amount": current_deductible,
                "add_ons": current_addons,
                "roof_age": current.get("roof_age"),
                "roof_material": current.get("roof_material"),
                "annual_premium": _money(stored_annual),
                "monthly_premium": _money(stored_annual / 12),
            },
            "proposed": {
                "policy_name": proposed_form,
                "dwelling_coverage": proposed_dwelling,
                "personal_property_coverage": proposed_pp,
                "liability_limit": proposed_liability,
                "deductible_amount": proposed_deductible,
                "add_ons": proposed_addons,
                "roof_age": proposed.get("roof_age"),
                "roof_material": proposed.get("roof_material"),
                "annual_premium": proposed_annual,
                "monthly_premium": proposed_monthly,
            },
            "renewal_trend": {
                "annual_trend_rate": ANNUAL_TREND_RATE,
                "years_since_inception": trend_years,
                "trend_multiplier": trend_mult,
                "trend_amount": renewal_rate_amount,
                "note": trend_note,
            },
            "renewal_rating": {
                "renewal_baseline": _money(renewal_baseline),
                "risk_data_refresh_amount": risk_data_refresh_amount,
                "territory_state": row.get("property_state"),
                "territory_load_pct": territory_pct,
                "territory_load_amount": territory_load_amount,
                "pre_factor_total": _money(pre_factor_total),
                "rating_multiplier": _money(rating_multiplier),
            },
            "premium_impact": {
                "annual_change": annual_change,
                "monthly_change": monthly_change,
                "percentage_change": percentage_change,
                "direction": direction,
            },
            "changed_fields": changed_fields,
            "reasons": reasons,
            "message": (
                f"Renewal premium changes from ${stored_annual:,.2f}/yr "
                f"to ${proposed_annual:,.2f}/yr "
                f"({direction.lower()}: ${abs(annual_change):,.2f}/yr)."
            ),
        }

    except Exception as exc:
        logger.exception("Renewal premium calculation failed")
        return {
            "status": "FAILED",
            "policy_id": str(policy_id).strip() if policy_id else None,
            "message": str(exc),
        }

def calculate_max_claim_capacity(dwelling_coverage: float, personal_property: float, deductible: float, add_ons_list: list) -> Dict[str, Any]:
    """
    Calculates the maximum claim payout capacity and out-of-pocket breakdown 
    for a given policy structure.
    """
    dwelling = float(dwelling_coverage or 0.0)
    contents = float(personal_property or (dwelling * 0.50))
    ded = float(deductible or 1000.0)
    
    # Total structural and contents protection limit (Max claimable aggregate pool)
    total_coverage_pool = dwelling + contents
    
    # Net maximum payout after factoring out the deductible minimum responsibility
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

__all__ = ["calculate_renewal_premium"]









# """Dedicated renewal premium rating tool for the Broker Productivity Agent.

# This tool is intentionally separate from the mid-term policy-change calculator.

# Renewal POC model:
# - Starts from the policy's stored annual premium.
# - Applies a configurable renewal rate-level adjustment.
# - Applies relative rating-factor changes for policy form, deductible, liability,
#   roof age, roof material, dwelling coverage, and personal-property coverage.
# - Adds/removes configured add-on charges.
# - Returns a transparent factor/reason breakdown for the agent to explain.

# IMPORTANT:
# These are POC rating assumptions, not carrier-approved rates. In production,
# the renewal rate level and rating factors must come from the applicable
# carrier/state-approved rating plan.
# """

# import logging
# from datetime import date
# from decimal import Decimal
# from typing import Any, Dict, Optional

# from google.cloud import bigquery

# PROJECT_ID = "gcp-app-builder"
# DATASET_ID = "Broker_Productivity"

# client = bigquery.Client(project=PROJECT_ID)
# logger = logging.getLogger(__name__)

# # ---------------------------------------------------------------------------
# # POC renewal assumptions
# # ---------------------------------------------------------------------------

# # This is NOT a universal US insurance rate. It is a configurable POC
# # renewal rate-level assumption used to demonstrate a new policy term.
# RENEWAL_RATE_LEVEL = 0.08

# # Rules supplied in the project's Premium_Rating_Rules file, effective 2026.
# FORM_BASE = {
#     "HO-3": 2400.0,
#     "HO-5": 2880.0,
# }

# DEDUCTIBLE_FACTORS = {
#     500: 1.15,
#     1000: 1.00,
#     2000: 0.90,
#     5000: 0.75,
# }

# ROOF_AGE_FACTORS = [
#     (0, 5, 0.90, "0-5 years"),
#     (6, 10, 0.95, "6-10 years"),
#     (11, 15, 1.00, "11-15 years"),
#     (16, 20, 1.15, "16-20 years"),
#     (21, 25, 1.30, "21-25 years"),
#     (26, 999, 1.50, "26+ years"),
# ]

# ROOF_MATERIAL_FACTORS = {
#     "asphalt shingle": 1.00,
#     "asphalt": 1.00,
#     "metal": 0.95,
#     "tile": 1.05,
#     "wood shake": 1.15,
#     "wood shake/shingle": 1.15,
#     "wood": 1.15,
#     "slate": 1.00,
# }

# LIABILITY_FACTORS = {
#     100_000: 1.00,
#     300_000: 1.05,
#     500_000: 1.10,
#     1_000_000: 1.20,
# }

# # Existing project POC add-on prices.
# ADDON_PRICE = {
#     "water backup": 500.0,
#     "coverage line": 700.0,
# }

# # Coverage does not normally move premium dollar-for-dollar with the limit.
# # These elasticities are POC assumptions:
# # 10% more dwelling coverage -> approximately 6% rating movement.
# DWELLING_ELASTICITY = 0.60
# PERSONAL_PROPERTY_ELASTICITY = 0.20

# RATING_FIELDS = {
#     "policy_name",
#     "policy_type",
#     "dwelling_coverage",
#     "personal_property_coverage",
#     "liability_limit",
#     "deductible_amount",
#     "add_ons",
#     "roof_age",
#     "roof_material",
# }


# def _num(value: Any, default: Optional[float] = None) -> Optional[float]:
#     if value is None or value == "":
#         return default
#     try:
#         return float(Decimal(str(value)))
#     except Exception as exc:
#         raise ValueError(f"Invalid numeric value: {value!r}") from exc


# def _money(value: float) -> float:
#     return round(float(value), 2)


# def _normalize_form(name: Any, policy_type: Any) -> str:
#     for value in (name, policy_type):
#         if not value:
#             continue
#         text = str(value).upper().replace(" ", "").replace("_", "")
#         if "HO5" in text or "HO-5" in text:
#             return "HO-5"
#         if "HO3" in text or "HO-3" in text:
#             return "HO-3"
#     raise ValueError("Policy form must be HO-3 or HO-5.")


# def _normalize_addons(value: Any) -> list[str]:
#     if value is None or value == "" or str(value).strip().lower() == "none":
#         return []

#     raw = list(value) if isinstance(value, (list, tuple, set)) else str(value).split(",")
#     result = []

#     for item in raw:
#         text = " ".join(str(item).lower().replace("_", " ").split())
#         if text == "none":
#             continue
#         if text == "water backup":
#             name = "Water Backup"
#         elif text == "coverage line":
#             name = "coverage line"
#         else:
#             raise ValueError(
#                 f"Unsupported add-on '{item}'. "
#                 "Supported add-ons: Water Backup, coverage line."
#             )

#         if name not in result:
#             result.append(name)

#     return result


# def _addon_cost(addons: list[str]) -> float:
#     return sum(ADDON_PRICE[a.lower()] for a in addons)


# def _deductible_factor(value: float) -> tuple[float, str]:
#     if value < 500 or value > 5000:
#         raise ValueError("Deductible must be between $500 and $5,000 for this POC.")

#     tiers = sorted(DEDUCTIBLE_FACTORS.items())

#     # Exact tier.
#     if value in DEDUCTIBLE_FACTORS:
#         return DEDUCTIBLE_FACTORS[int(value)], f"${value:,.0f} deductible tier"

#     # Linear interpolation between the two configured POC tiers.
#     for (low_value, low_factor), (high_value, high_factor) in zip(tiers, tiers[1:]):
#         if low_value < value < high_value:
#             ratio = (value - low_value) / (high_value - low_value)
#             factor = low_factor + ratio * (high_factor - low_factor)
#             return factor, (
#                 f"${low_value:,.0f}-${high_value:,.0f} deductible band "
#                 f"(interpolated POC factor)"
#             )

#     raise ValueError("Unable to determine deductible rating factor.")


# def _liability_factor(value: float) -> tuple[float, str]:
#     if value not in LIABILITY_FACTORS:
#         supported = ", ".join(f"${v:,.0f}" for v in sorted(LIABILITY_FACTORS))
#         raise ValueError(f"Liability limit must be one of: {supported}.")
#     return LIABILITY_FACTORS[int(value)], f"${value:,.0f} liability tier"


# def _roof_age_factor(value: Any) -> tuple[float, str]:
#     if value is None or value == "":
#         return 1.0, "Roof age not provided"

#     age = int(_num(value))
#     if age < 0:
#         raise ValueError("roof_age cannot be negative.")

#     for minimum, maximum, factor, label in ROOF_AGE_FACTORS:
#         if minimum <= age <= maximum:
#             return factor, f"{label} roof-age tier"

#     raise ValueError("Unable to determine roof-age rating factor.")


# def _roof_material_factor(value: Any) -> tuple[float, str]:
#     if not value:
#         return 1.0, "Roof material not provided"

#     text = " ".join(str(value).lower().replace("_", " ").split())

#     for material, factor in ROOF_MATERIAL_FACTORS.items():
#         if material in text:
#             return factor, f"{value} roof-material tier"

#     raise ValueError(
#         f"Unsupported roof material '{value}'. "
#         "Supported POC values include Asphalt, Asphalt Shingle, Metal, "
#         "Tile, Wood, and Slate."
#     )


# def _coverage_factor(current: float, proposed: float, elasticity: float) -> float:
#     if current <= 0 or proposed <= 0:
#         raise ValueError("Coverage values must be positive.")
#     return 1.0 + elasticity * ((proposed / current) - 1.0)


# def _one_year_later(start: date) -> date:
#     try:
#         return start.replace(year=start.year + 1)
#     except ValueError:
#         # Handles Feb 29 safely.
#         return start.replace(year=start.year + 1, day=28)


# def _fetch(policy_id: str) -> Dict[str, Any]:
#     query = f"""
#     SELECT
#         p.policy_id,
#         p.policy_name,
#         p.policy_type,
#         p.policy_status,
#         p.effective_date,
#         p.expiration_date,
#         p.dwelling_coverage,
#         p.personal_property_coverage,
#         p.liability_limit,
#         p.deductible_amount,
#         p.add_ons,
#         p.annual_premium,
#         p.monthly_premium,
#         pr.roof_age,
#         pr.roof_material
#     FROM `{PROJECT_ID}.{DATASET_ID}.Policy1` p
#     LEFT JOIN `{PROJECT_ID}.{DATASET_ID}.Property` pr
#       ON p.property_id = pr.property_id
#     WHERE p.policy_id = @policy_id
#     LIMIT 1
#     """

#     config = bigquery.QueryJobConfig(
#         query_parameters=[
#             bigquery.ScalarQueryParameter(
#                 "policy_id", "STRING", policy_id.strip()
#             )
#         ]
#     )

#     rows = list(client.query(query, job_config=config).result())

#     if not rows:
#         raise ValueError(f"Policy '{policy_id}' was not found.")

#     return dict(rows[0])


# def _field_alias(raw: str) -> str:
#     aliases = {
#         "policy form": "policy_name",
#         "form": "policy_name",
#         "deductible": "deductible_amount",
#         "deductible amount": "deductible_amount",
#         "dwelling": "dwelling_coverage",
#         "dwelling coverage": "dwelling_coverage",
#         "personal property": "personal_property_coverage",
#         "personal property coverage": "personal_property_coverage",
#         "liability": "liability_limit",
#         "liability limit": "liability_limit",
#         "addons": "add_ons",
#         "add-ons": "add_ons",
#         "add ons": "add_ons",
#         "roof age": "roof_age",
#         "roof material": "roof_material",
#     }
#     normalized = str(raw).strip().lower()
#     return aliases.get(normalized, normalized)


# def calculate_renewal_premium(
#     policy_id: str,
#     proposed_changes: Optional[Dict[str, Any]] = None,
# ) -> Dict[str, Any]:
#     """Calculate a renewal quote for an expired policy.

#     proposed_changes is optional. If omitted or empty, the current policy
#     terms are used for the renewal quote.

#     Example:
#         calculate_renewal_premium("POL033", {})

#     User-requested renewal changes can be combined:
#         calculate_renewal_premium(
#             "POL033",
#             {
#                 "policy_name": "HO-5",
#                 "deductible_amount": 2500,
#                 "add_ons": ["Water Backup"],
#             },
#         )
#     """
#     try:
#         if not policy_id or not str(policy_id).strip():
#             raise ValueError("policy_id is required.")

#         row = _fetch(str(policy_id).strip())

#         status = str(row.get("policy_status") or "").upper()
#         if status != "EXPIRED":
#             if status == "ACTIVE":
#                 raise ValueError("Active policies do not require renewal.")
#             raise ValueError("Only expired policies are eligible for this renewal flow.")

#         stored_annual = _num(row.get("annual_premium"))
#         if stored_annual is None or stored_annual <= 0:
#             raise ValueError(
#                 "A valid current annual premium is required to calculate the renewal quote."
#             )

#         current = {
#             "policy_name": row.get("policy_name"),
#             "policy_type": row.get("policy_type"),
#             "dwelling_coverage": _num(row.get("dwelling_coverage")),
#             "personal_property_coverage": _num(row.get("personal_property_coverage")),
#             "liability_limit": _num(row.get("liability_limit")),
#             "deductible_amount": _num(row.get("deductible_amount")),
#             "add_ons": row.get("add_ons"),
#             "roof_age": _num(row.get("roof_age")),
#             "roof_material": row.get("roof_material"),
#         }

#         proposed = dict(current)
#         normalized_changes = {}

#         for raw_field, value in (proposed_changes or {}).items():
#             field = _field_alias(raw_field)

#             if field not in RATING_FIELDS:
#                 raise ValueError(
#                     f"'{raw_field}' is not supported for renewal rating. "
#                     f"Supported fields: {sorted(RATING_FIELDS)}"
#                 )

#             normalized_changes[field] = value

#             if field in {
#                 "dwelling_coverage",
#                 "personal_property_coverage",
#                 "liability_limit",
#                 "deductible_amount",
#                 "roof_age",
#             }:
#                 proposed[field] = _num(value)
#             elif field == "add_ons":
#                 proposed[field] = _normalize_addons(value)
#             else:
#                 proposed[field] = value

#         # Normalize current values too, so comparisons are consistent.
#         current_form = _normalize_form(
#             current.get("policy_name"), current.get("policy_type")
#         )
#         proposed_form = _normalize_form(
#             proposed.get("policy_name"), proposed.get("policy_type")
#         )

#         current_addons = _normalize_addons(current.get("add_ons"))
#         proposed_addons = _normalize_addons(proposed.get("add_ons"))

#         current_dwelling = float(current["dwelling_coverage"] or 0)
#         proposed_dwelling = float(proposed["dwelling_coverage"] or 0)
#         current_pp = float(current["personal_property_coverage"] or 0)
#         proposed_pp = float(proposed["personal_property_coverage"] or 0)
#         current_liability = float(current["liability_limit"] or 0)
#         proposed_liability = float(proposed["liability_limit"] or 0)
#         current_deductible = float(current["deductible_amount"] or 0)
#         proposed_deductible = float(proposed["deductible_amount"] or 0)

#         # -------------------------
#         # Renewal baseline
#         # -------------------------
#         renewal_rate_amount = stored_annual * RENEWAL_RATE_LEVEL
#         renewal_baseline = stored_annual + renewal_rate_amount

#         # -------------------------
#         # Relative rating factors
#         # -------------------------
#         current_ded_factor, current_ded_tier = _deductible_factor(current_deductible)
#         proposed_ded_factor, proposed_ded_tier = _deductible_factor(proposed_deductible)

#         current_liab_factor, current_liab_tier = _liability_factor(current_liability)
#         proposed_liab_factor, proposed_liab_tier = _liability_factor(proposed_liability)

#         current_roof_age_factor, current_roof_age_tier = _roof_age_factor(
#             current.get("roof_age")
#         )
#         proposed_roof_age_factor, proposed_roof_age_tier = _roof_age_factor(
#             proposed.get("roof_age")
#         )

#         current_roof_material_factor, current_roof_material_tier = _roof_material_factor(
#             current.get("roof_material")
#         )
#         proposed_roof_material_factor, proposed_roof_material_tier = _roof_material_factor(
#             proposed.get("roof_material")
#         )

#         current_form_factor = FORM_BASE[current_form]
#         proposed_form_factor = FORM_BASE[proposed_form]

#         form_relative = proposed_form_factor / current_form_factor
#         deductible_relative = proposed_ded_factor / current_ded_factor
#         liability_relative = proposed_liab_factor / current_liab_factor
#         roof_age_relative = proposed_roof_age_factor / current_roof_age_factor
#         roof_material_relative = (
#             proposed_roof_material_factor / current_roof_material_factor
#         )

#         dwelling_relative = _coverage_factor(
#             current_dwelling,
#             proposed_dwelling,
#             DWELLING_ELASTICITY,
#         )
#         personal_property_relative = _coverage_factor(
#             current_pp,
#             proposed_pp,
#             PERSONAL_PROPERTY_ELASTICITY,
#         )

#         rating_multiplier = (
#             form_relative
#             * deductible_relative
#             * liability_relative
#             * roof_age_relative
#             * roof_material_relative
#             * dwelling_relative
#             * personal_property_relative
#         )

#         factor_adjusted_premium = renewal_baseline * rating_multiplier

#         current_addon_cost = _addon_cost(current_addons)
#         proposed_addon_cost = _addon_cost(proposed_addons)
#         addon_delta = proposed_addon_cost - current_addon_cost

#         proposed_annual = max(
#             500.0,
#             _money(factor_adjusted_premium + addon_delta),
#         )
#         proposed_monthly = _money(proposed_annual / 12)

#         annual_change = _money(proposed_annual - stored_annual)
#         monthly_change = _money(
#             proposed_monthly - _money(stored_annual / 12)
#         )

#         percentage_change = (
#             _money((annual_change / stored_annual) * 100)
#             if stored_annual
#             else 0.0
#         )

#         direction = (
#             "INCREASE"
#             if annual_change > 0
#             else "DECREASE"
#             if annual_change < 0
#             else "NO_CHANGE"
#         )

#         # -------------------------
#         # Explainable reasons
#         # -------------------------
#         reasons = [
#             {
#                 "factor": "Renewal rate level",
#                 "current": f"${stored_annual:,.2f}",
#                 "proposed": f"${renewal_baseline:,.2f}",
#                 "impact": _money(renewal_rate_amount),
#                 "reason": (
#                     "The new policy term uses an 8% renewal rate-level "
#                     "adjustment configured for this POC. Actual renewal "
#                     "rate changes are carrier- and state-specific."
#                 ),
#             }
#         ]

#         def add_factor_reason(
#             factor: str,
#             current_value: Any,
#             proposed_value: Any,
#             relative_factor: float,
#             reason: str,
#         ):
#             if current_value != proposed_value:
#                 reasons.append(
#                     {
#                         "factor": factor,
#                         "current": current_value,
#                         "proposed": proposed_value,
#                         "impact": relative_factor,
#                         "reason": reason,
#                     }
#                 )

#         add_factor_reason(
#             "Policy form",
#             current_form,
#             proposed_form,
#             form_relative,
#             (
#                 "HO-5 has a higher configured reference base than HO-3, "
#                 "reflecting broader policy coverage in this POC rating plan."
#             ),
#         )

#         add_factor_reason(
#             "Dwelling coverage",
#             f"${current_dwelling:,.0f}",
#             f"${proposed_dwelling:,.0f}",
#             dwelling_relative,
#             (
#                 "Higher dwelling coverage increases the insured property "
#                 "exposure; the POC uses a partial coverage elasticity rather "
#                 "than a dollar-for-dollar premium change."
#             ),
#         )

#         add_factor_reason(
#             "Personal property coverage",
#             f"${current_pp:,.0f}",
#             f"${proposed_pp:,.0f}",
#             personal_property_relative,
#             (
#                 "Higher personal-property coverage increases the amount "
#                 "of contents exposure being insured."
#             ),
#         )

#         add_factor_reason(
#             "Liability limit",
#             f"${current_liability:,.0f}",
#             f"${proposed_liability:,.0f}",
#             liability_relative,
#             (
#                 "A higher liability limit increases the potential liability "
#                 "exposure covered by the policy."
#             ),
#         )

#         add_factor_reason(
#             "Deductible",
#             f"${current_deductible:,.0f}",
#             f"${proposed_deductible:,.0f}",
#             deductible_relative,
#             (
#                 "A higher deductible generally transfers more of a covered "
#                 "loss to the policyholder, which can reduce the premium."
#             ),
#         )

#         add_factor_reason(
#             "Roof age",
#             current.get("roof_age"),
#             proposed.get("roof_age"),
#             roof_age_relative,
#             (
#                 "Roof age is a property-risk factor in the configured "
#                 "rating plan; older roofs receive a higher rating factor."
#             ),
#         )

#         add_factor_reason(
#             "Roof material",
#             current.get("roof_material"),
#             proposed.get("roof_material"),
#             roof_material_relative,
#             (
#                 "Roof material affects the configured property-risk factor "
#                 "because materials can have different loss characteristics."
#             ),
#         )

#         if current_addons != proposed_addons:
#             reasons.append(
#                 {
#                     "factor": "Add-ons",
#                     "current": current_addons or ["None"],
#                     "proposed": proposed_addons or ["None"],
#                     "impact": _money(addon_delta),
#                     "reason": (
#                         "Optional endorsements change the premium because "
#                         "they add additional insured protection. The POC "
#                         "uses configured annual charges of $500 for Water "
#                         "Backup and $700 for coverage line."
#                     ),
#                 }
#             )

#         today = date.today()
#         renewal_expiration = _one_year_later(today)

#         changed_fields = {}
#         for field in normalized_changes:
#             old_value = current.get(field)
#             new_value = proposed.get(field)
#             if isinstance(old_value, Decimal):
#                 old_value = float(old_value)
#             if isinstance(new_value, Decimal):
#                 new_value = float(new_value)
#             changed_fields[field] = {
#                 "current": old_value,
#                 "proposed": new_value,
#                 "changed": old_value != new_value,
#             }

#         return {
#             "status": "SUCCESS",
#             "policy_id": str(policy_id).strip(),
#             "renewal_eligibility": "ELIGIBLE",
#             "renewal_dates": {
#                 "effective_date": today.isoformat(),
#                 "expiration_date": renewal_expiration.isoformat(),
#             },
#             "current": {
#                 "policy_name": current_form,
#                 "dwelling_coverage": current_dwelling,
#                 "personal_property_coverage": current_pp,
#                 "liability_limit": current_liability,
#                 "deductible_amount": current_deductible,
#                 "add_ons": current_addons,
#                 "roof_age": current.get("roof_age"),
#                 "roof_material": current.get("roof_material"),
#                 "annual_premium": _money(stored_annual),
#                 "monthly_premium": _money(stored_annual / 12),
#             },
#             "proposed": {
#                 "policy_name": proposed_form,
#                 "dwelling_coverage": proposed_dwelling,
#                 "personal_property_coverage": proposed_pp,
#                 "liability_limit": proposed_liability,
#                 "deductible_amount": proposed_deductible,
#                 "add_ons": proposed_addons,
#                 "roof_age": proposed.get("roof_age"),
#                 "roof_material": proposed.get("roof_material"),
#                 "annual_premium": proposed_annual,
#                 "monthly_premium": proposed_monthly,
#             },
#             "renewal_rating": {
#                 "renewal_rate_level": RENEWAL_RATE_LEVEL,
#                 "renewal_rate_level_amount": _money(renewal_rate_amount),
#                 "renewal_baseline": _money(renewal_baseline),
#                 "rating_multiplier": _money(rating_multiplier),
#                 "form_factor": _money(form_relative),
#                 "deductible_factor": _money(deductible_relative),
#                 "liability_factor": _money(liability_relative),
#                 "roof_age_factor": _money(roof_age_relative),
#                 "roof_material_factor": _money(roof_material_relative),
#                 "dwelling_coverage_factor": _money(dwelling_relative),
#                 "personal_property_factor": _money(personal_property_relative),
#                 "add_on_delta": _money(addon_delta),
#                 "current_deductible_tier": current_ded_tier,
#                 "proposed_deductible_tier": proposed_ded_tier,
#                 "current_liability_tier": current_liab_tier,
#                 "proposed_liability_tier": proposed_liab_tier,
#                 "current_roof_age_tier": current_roof_age_tier,
#                 "proposed_roof_age_tier": proposed_roof_age_tier,
#                 "current_roof_material_tier": current_roof_material_tier,
#                 "proposed_roof_material_tier": proposed_roof_material_tier,
#             },
#             "premium_impact": {
#                 "annual_change": annual_change,
#                 "monthly_change": monthly_change,
#                 "percentage_change": percentage_change,
#                 "direction": direction,
#             },
#             "changed_fields": changed_fields,
#             "reasons": reasons,
#             "message": (
#                 f"Renewal premium changes from ${stored_annual:,.2f}/yr "
#                 f"to ${proposed_annual:,.2f}/yr "
#                 f"({direction.lower()}: ${abs(annual_change):,.2f}/yr)."
#             ),
#         }

#     except Exception as exc:
#         logger.exception("Renewal premium calculation failed")
#         return {
#             "status": "FAILED",
#             "policy_id": str(policy_id).strip() if policy_id else None,
#             "message": str(exc),
#         }


# __all__ = ["calculate_renewal_premium"]
