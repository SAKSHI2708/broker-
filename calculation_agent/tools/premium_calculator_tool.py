"""Single deterministic premium-rating tool for the Broker Productivity Agent.

The agent decides WHAT the customer wants to change. This tool decides the
premium numbers: it reads the current Policy1 + Property + Risk + Claims
rating state, applies all proposed changes together, and returns current vs
proposed premium.

Updated with realistic US-based actuarial rating factors and comprehensive
state territory loads covering all properties in the BigQuery dataset.
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

RATING_FIELDS = {
    "policy_name", "policy_type", "dwelling_coverage",
    "personal_property_coverage", "liability_limit", "deductible_amount",
    "add_ons", "roof_age", "roof_material",
}

# Realistic US carrier base rates for HO-3 and HO-5
FORM_BASE = {"HO-3": 1250.0, "HO-5": 1550.0}
ADDON_PRICE = {"water backup": 350.0, "coverage line": 450.0}
DWELLING_BASE, DWELLING_STEP, DWELLING_RATE = 300_000, 50_000, 115.0
PP_STEP, PP_RATE = 10_000, 25.0

# Standard US deductible rate adjustments (relative to $1,000 baseline)
DEDUCTIBLE_RATE = {500: 175.0, 1000: 0.0, 1500: -90.0, 2500: -180.0, 5000: -320.0}

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

# Realistic US state catastrophe and hazard rating loads based on Property database states
STATE_TERRITORY_LOAD_PCT = {
    "FL": 0.35, "LA": 0.30, "TX": 0.18, "CA": 0.22, "OK": 0.20, 
    "CO": 0.12, "NC": 0.15, "SC": 0.15, "AZ": 0.08, "NV": 0.05, 
    "OR": 0.05, "WA": 0.08, "MA": 0.10, "VA": 0.08, "IN": 0.02, 
    "OH": 0.02, "WI": 0.02, "ID": 0.03, "UT": 0.05, "default": 0.05,
}

ANNUAL_TREND_RATE = 0.045  # 4.5% annual loss cost trend


def _num(v: Any, default: Optional[float] = None) -> Optional[float]:
    if v is None or v == "":
        return default
    try:
        return float(Decimal(str(v)))
    except Exception as exc:
        raise ValueError(f"Invalid numeric value: {v!r}") from exc


def _money(v: float) -> float:
    return round(float(v), 2)


def _form(name: Any, typ: Any) -> str:
    for v in (name, typ):
        if v:
            s = str(v).upper().replace(" ", "").replace("_", "")
            if "HO5" in s or "HO-5" in s:
                return "HO-5"
            if "HO3" in s or "HO-3" in s:
                return "HO-3"
    raise ValueError("Policy form must be HO-3 or HO-5.")


def _addons(v: Any) -> list[str]:
    if v is None or v == "" or str(v).strip().lower() == "none":
        return []
    raw = list(v) if isinstance(v, (list, tuple, set)) else str(v).split(",")
    out = []
    for item in raw:
        s = " ".join(str(item).lower().replace("_", " ").split())
        if s == "none":
            continue
        if s == "water backup":
            name = "Water Backup"
        elif s == "coverage line":
            name = "coverage line"
        else:
            raise ValueError(f"Unsupported add-on '{item}'. Supported: Water Backup, coverage line.")
        if name not in out:
            out.append(name)
    return out


def _deductible(v: float):
    selected = min(DEDUCTIBLE_RATE)
    for tier in sorted(DEDUCTIBLE_RATE):
        if v >= tier:
            selected = tier
        else:
            break
    return DEDUCTIBLE_RATE[selected], f"${selected:,.0f} deductible tier"


def _liability(v: float):
    if v >= 500_000:
        return 120.0, "$500K+ liability tier"
    if v >= 300_000:
        return 60.0, "$300K-$499,999 liability tier"
    return 0.0, "Up to $299,999 liability tier"


def _roof_age(v: Any):
    if v is None or v == "":
        return 0.0, "Roof age not provided"
    age = int(_num(v))
    if age < 0:
        raise ValueError("roof_age cannot be negative.")
    if age <= 3:
        return -180.0, f"Brand New Roof ({age} yrs)"
    if age <= 7:
        return -90.0, f"Preferred New Roof ({age} yrs)"
    if age <= 15:
        return 0.0, f"Standard Roof ({age} yrs)"
    if age <= 20:
        return 160.0, f"Aging Roof ({age} yrs)"
    return 320.0, f"Old Roof ({age} yrs)"


def _roof_material(v: Any):
    if not v:
        return 0.0, "Roof material not provided"
    s = str(v).lower().strip()
    if "metal" in s:
        return -140.0, "Metal Roof"
    if "tile" in s:
        return -110.0, "Tile Roof"
    if "slate" in s:
        return -90.0, "Slate Roof"
    if "wood" in s or "shake" in s:
        return 175.0, "Wood Shake/Shingle Roof"
    return 0.0, f"{v} (standard material)"


def _construction(v: Any) -> Tuple[float, str]:
    if not v:
        return 0.0, "Construction type not provided"
    s = str(v).lower()
    for key, adj in CONSTRUCTION_ADJ.items():
        if key in s:
            return adj, f"{v} Construction"
    return 0.0, f"{v} (standard construction)"


def _home_age(year_built: Any) -> Tuple[float, str]:
    if year_built is None or year_built == "":
        return 0.0, "Year built not provided"
    yr = int(_num(year_built))
    age = date.today().year - yr
    if age < 0:
        raise ValueError("year_built cannot be in the future.")
    if age <= 10:
        return -80.0, f"New Home ({age} yrs)"
    if age <= 30:
        return 0.0, f"Standard Age Home ({age} yrs)"
    if age <= 50:
        return 130.0, f"Older Home ({age} yrs)"
    return 290.0, f"Vintage Home ({age} yrs)"


def _floors(v: Any) -> Tuple[float, str]:
    if v is None or v == "":
        return 0.0, "Number of floors not provided"
    n = int(_num(v))
    if n <= 1:
        return 0.0, "Single-story"
    if n == 2:
        return 35.0, "Two-story"
    return 70.0, f"{n}-story (multi-level)"


def _coverage_adequacy(dwelling_coverage: float, estimated_value: Any) -> Tuple[float, str]:
    ev = _num(estimated_value)
    if not ev or ev <= 0:
        return 0.0, "Estimated property value not available - adequacy not evaluated"
    required = ev * COINSURANCE_MIN_PCT
    if dwelling_coverage >= required:
        return 0.0, "Dwelling coverage meets 80% replacement-cost adequacy guideline"
    shortfall_pct = (required - dwelling_coverage) / required
    penalty = _money(shortfall_pct * COINSURANCE_PENALTY_SCALE)
    return penalty, f"Underinsured - dwelling coverage is {shortfall_pct * 100:.0f}% below the 80% adequacy guideline"


def _risk_factor(risk_key: str, value: Any) -> Tuple[float, str]:
    label = risk_key.replace("_", " ").title()
    if not value:
        return 0.0, f"{label} not provided"
    tier = str(value).strip().lower()
    rate_table = RISK_RATE_TABLE[risk_key]
    adj = rate_table.get(tier)
    if adj is None:
        return 0.0, f"{label}: {value} (unrecognized tier, no adjustment applied)"
    return adj, f"{label}: {value}"


def _crime_factor(value: Any) -> Tuple[float, str]:
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


def _territory(state: Any) -> Tuple[float, str]:
    if not state:
        return 0.0, "State/territory not available - no territory load applied"
    s = str(state).strip().upper()
    pct = STATE_TERRITORY_LOAD_PCT.get(s, STATE_TERRITORY_LOAD_PCT["default"])
    if pct:
        return pct, f"{s} territory load (+{pct * 100:.0f}%)"
    return 0.0, f"{s} territory (no load)"


def _trend(effective_date: Any) -> Tuple[float, float, str]:
    if not effective_date:
        return 0.0, 1.0, "Effective date not available - no renewal trend applied"
    try:
        if isinstance(effective_date, str):
            ed = datetime.strptime(effective_date[:10], "%Y-%m-%d").date()
        elif isinstance(effective_date, datetime):
            ed = effective_date.date()
        else:
            ed = effective_date
        years = (date.today() - ed).days / 365.25
    except Exception:
        return 0.0, 1.0, "Could not parse effective date - no renewal trend applied"
    years = max(0.0, years)
    mult = round((1 + ANNUAL_TREND_RATE) ** years, 6)
    return round(years, 2), mult, f"{years:.1f} yr(s) since inception @ {ANNUAL_TREND_RATE * 100:.1f}%/yr trend"

def _calculate_remaining_term(effective_date: Any) -> Dict[str, Any]:
    """
    Calculate the remaining policy term based on today's date.

    Assumption:
    - Policy term is 12 months from effective_date.
    - Mid-term premium changes are prorated over the remaining days.
    """

    if not effective_date:
        return {
            "remaining_days": 365,
            "remaining_months": 12.0,
            "policy_expiration_date": None,
            "proration_factor": 1.0,
            "note": "Effective date not available - using full annual term."
        }

    try:
        if isinstance(effective_date, str):
            policy_start = datetime.strptime(
                effective_date[:10], "%Y-%m-%d"
            ).date()

        elif isinstance(effective_date, datetime):
            policy_start = effective_date.date()

        else:
            policy_start = effective_date

        # 12-month policy term
        policy_expiration = policy_start.replace(
            year=policy_start.year + 1
        )

        today = date.today()

        # Policy already expired
        if today >= policy_expiration:
            return {
                "remaining_days": 0,
                "remaining_months": 0.0,
                "policy_expiration_date": policy_expiration.isoformat(),
                "proration_factor": 0.0,
                "note": "Policy term has expired."
            }

        remaining_days = (policy_expiration - today).days

        # Convert remaining days to approximate months
        remaining_months = round(remaining_days / 30.4375, 2)

        # Exact day-based proration
        proration_factor = round(
            remaining_days / 365.25,
            6
        )

        return {
            "remaining_days": remaining_days,
            "remaining_months": remaining_months,
            "policy_expiration_date": policy_expiration.isoformat(),
            "proration_factor": proration_factor,
            "note": (
                f"{remaining_months:.2f} month(s) remaining "
                f"out of the 12-month policy term."
            )
        }

    except Exception as exc:
        logger.exception("Failed to calculate remaining policy term")

        return {
            "remaining_days": 365,
            "remaining_months": 12.0,
            "policy_expiration_date": None,
            "proration_factor": 1.0,
            "note": f"Could not calculate remaining term: {exc}"
        }

def _static_factors(row: Dict[str, Any], claims_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    construction_adj, construction_tier = _construction(row.get("construction_type"))
    age_adj, age_tier = _home_age(row.get("year_built"))
    floors_adj, floors_tier = _floors(row.get("number_of_floors"))

    flood_adj, flood_tier = _risk_factor("flood_risk", row.get("flood_risk"))
    wildfire_adj, wildfire_tier = _risk_factor("wildfire_risk", row.get("wildfire_risk"))
    wind_adj, wind_tier = _risk_factor("wind_risk", row.get("wind_risk"))
    hail_adj, hail_tier = _risk_factor("hail_risk", row.get("hail_risk"))
    eq_adj, eq_tier = _risk_factor("earthquake_risk", row.get("earthquake_risk"))
    crime_adj, crime_tier = _crime_factor(row.get("crime_score"))

    claims_adj, claims_tier, claims_detail = _claims_surcharge(claims_rows)
    territory_pct, territory_tier = _territory(row.get("property_state") or row.get("state"))

    dollar_total = _money(
        construction_adj + age_adj + floors_adj + flood_adj + wildfire_adj +
        wind_adj + hail_adj + eq_adj + crime_adj + claims_adj
    )

    breakdown = {
        "construction_type": row.get("construction_type"), "construction_adjustment": _money(construction_adj), "construction_tier": construction_tier,
        "year_built": row.get("year_built"), "home_age_adjustment": _money(age_adj), "home_age_tier": age_tier,
        "number_of_floors": row.get("number_of_floors"), "floors_adjustment": _money(floors_adj), "floors_tier": floors_tier,
        "flood_risk": row.get("flood_risk"), "flood_risk_adjustment": _money(flood_adj), "flood_risk_tier": flood_tier,
        "wildfire_risk": row.get("wildfire_risk"), "wildfire_risk_adjustment": _money(wildfire_adj), "wildfire_risk_tier": wildfire_tier,
        "wind_risk": row.get("wind_risk"), "wind_risk_adjustment": _money(wind_adj), "wind_risk_tier": wind_tier,
        "hail_risk": row.get("hail_risk"), "hail_risk_adjustment": _money(hail_adj), "hail_risk_tier": hail_tier,
        "earthquake_risk": row.get("earthquake_risk"), "earthquake_risk_adjustment": _money(eq_adj), "earthquake_risk_tier": eq_tier,
        "crime_score": row.get("crime_score"), "crime_score_adjustment": _money(crime_adj), "crime_score_tier": crime_tier,
        "claims_surcharge": _money(claims_adj), "claims_tier": claims_tier, "claims_detail": claims_detail,
        "territory_state": row.get("property_state") or row.get("state"), "territory_load_pct": territory_pct, "territory_tier": territory_tier,
        "static_dollar_total": dollar_total,
    }
    return {"dollar_total": dollar_total, "territory_pct": territory_pct, "estimated_value": row.get("estimated_value"), "breakdown": breakdown}


def _rate(s: Dict[str, Any], static: Dict[str, Any]) -> Dict[str, Any]:
    form = _form(s.get("policy_name"), s.get("policy_type"))
    base = FORM_BASE[form]
    dwelling = _num(s.get("dwelling_coverage"), DWELLING_BASE)
    pp = _num(s.get("personal_property_coverage"), dwelling * .50)
    liability = _num(s.get("liability_limit"), 100_000)
    deductible = _num(s.get("deductible_amount"), 1000)
    if dwelling <= 0 or pp < 0 or liability <= 0 or deductible <= 0:
        raise ValueError("Coverage, liability and deductible values must be valid positive amounts.")

    dwelling_adj = ((dwelling - DWELLING_BASE) / DWELLING_STEP) * DWELLING_RATE
    pp_adj = ((pp - dwelling * .50) / PP_STEP) * PP_RATE
    liability_adj, liability_tier = _liability(liability)
    deductible_adj, deductible_tier = _deductible(deductible)
    age_adj, age_tier = _roof_age(s.get("roof_age"))
    mat_adj, mat_tier = _roof_material(s.get("roof_material"))
    coverage_adj, coverage_tier = _coverage_adequacy(dwelling, static["estimated_value"])

    active = _addons(s.get("add_ons"))
    addon_breakdown = {a: ADDON_PRICE[a.lower()] for a in active}
    addons_total = sum(addon_breakdown.values())

    pre_load_subtotal = (
        base + dwelling_adj + pp_adj + liability_adj + deductible_adj +
        age_adj + mat_adj + coverage_adj + static["dollar_total"]
    )
    territory_load = _money(pre_load_subtotal * static["territory_pct"])
    annual = max(500.0, _money(pre_load_subtotal + territory_load + addons_total))

    return {
        "annual_premium": annual,
        "monthly_premium": _money(annual / 12),
        "breakdown": {
            "policy_form": form, "base_policy_premium": _money(base),
            "dwelling_coverage": int(dwelling), "dwelling_adjustment": _money(dwelling_adj),
            "personal_property_coverage": int(pp), "personal_property_adjustment": _money(pp_adj),
            "liability_limit": int(liability), "liability_adjustment": _money(liability_adj),
            "liability_rating_tier": liability_tier,
            "deductible_amount": int(deductible), "deductible_adjustment": _money(deductible_adj),
            "deductible_rating_tier": deductible_tier,
            "roof_age": int(_num(s.get("roof_age"))) if s.get("roof_age") not in (None, "") else None,
            "roof_age_adjustment": _money(age_adj), "roof_age_rating_tier": age_tier,
            "roof_material": s.get("roof_material"), "roof_material_adjustment": _money(mat_adj),
            "roof_material_rating_tier": mat_tier,
            "coverage_adequacy_adjustment": _money(coverage_adj), "coverage_adequacy_tier": coverage_tier,
            "territory_load": territory_load,
            "active_add_ons": active, "add_ons_cost": _money(addons_total),
            "add_on_breakdown": addon_breakdown,
            "property_and_risk_factors": static["breakdown"],
        },
    }


def _fetch(policy_id: str) -> Dict[str, Any]:
    q = f"""
    SELECT p.policy_id, p.policy_name, p.policy_type, p.dwelling_coverage,
           p.personal_property_coverage, p.liability_limit, p.deductible_amount,
           p.add_ons, p.annual_premium, p.monthly_premium, p.effective_date,
           pr.roof_age, pr.roof_material, pr.year_built, pr.square_footage,
           pr.construction_type, pr.estimated_value, pr.number_of_floors,
           pr.state AS property_state, pr.zip_code, pr.city,
           r.flood_risk, r.wildfire_risk, r.wind_risk, r.hail_risk,
           r.earthquake_risk, r.crime_score
    FROM `{PROJECT_ID}.{DATASET_ID}.Policy1` p
    LEFT JOIN `{PROJECT_ID}.{DATASET_ID}.Property` pr
      ON p.property_id = pr.property_id
    LEFT JOIN `{PROJECT_ID}.{DATASET_ID}.Risk` r
      ON p.property_id = r.property_id
    WHERE p.policy_id = @policy_id LIMIT 1
    """
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("policy_id", "STRING", policy_id.strip())
    ])
    rows = list(client.query(q, job_config=cfg).result())
    if not rows:
        raise ValueError(f"Policy '{policy_id}' was not found.")
    return dict(rows[0])


def _fetch_claims(policy_id: str) -> List[Dict[str, Any]]:
    q = f"""
    SELECT claim_amount, approved_amount, claim_status, incident_date
    FROM `{PROJECT_ID}.{DATASET_ID}.Claims`
    WHERE policy_id = @policy_id
    """
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("policy_id", "STRING", policy_id.strip())
    ])
    return [dict(r) for r in client.query(q, job_config=cfg).result()]


def _field(raw: str) -> str:
    aliases = {
        "policy form": "policy_name", "form": "policy_name", "policy": "policy_name",
        "policy type": "policy_type", "type": "policy_type", "policy_type": "policy_type",
        "deductible": "deductible_amount", "deductible amount": "deductible_amount", "deductible_amount": "deductible_amount",
        "dwelling": "dwelling_coverage", "dwelling coverage": "dwelling_coverage", "dwelling_coverage": "dwelling_coverage",
        "personal property": "personal_property_coverage", "personal property coverage": "personal_property_coverage", "personal_property_coverage": "personal_property_coverage",
        "liability": "liability_limit", "liability limit": "liability_limit", "liability_limit": "liability_limit",
        "addons": "add_ons", "add-ons": "add_ons", "add ons": "add_ons", "add_ons": "add_ons",
        "roof age": "roof_age", "roof-age": "roof_age", "roof_age": "roof_age",
        "roof material": "roof_material", "roof-material": "roof_material", "roof_material": "roof_material",
    }
    x = str(raw).strip().lower()
    return aliases.get(x, x)


def calculate_premium(policy_id: str, proposed_changes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        if not policy_id or not str(policy_id).strip():
            raise ValueError("policy_id is required.")
        row = _fetch(str(policy_id).strip())
        claims_rows = _fetch_claims(str(policy_id).strip())

        current = {k: row.get(k) for k in RATING_FIELDS}
        proposed = dict(current)
        normalized = {}

        for raw, value in (proposed_changes or {}).items():
            f = _field(raw)
            if f not in RATING_FIELDS:
                raise ValueError(f"'{raw}' is not a premium-rating field. Supported: {sorted(RATING_FIELDS)}")
            normalized[f] = value
            if f in {"dwelling_coverage", "personal_property_coverage", "liability_limit", "deductible_amount", "roof_age"}:
                proposed[f] = _num(value)
            elif f == "add_ons":
                proposed[f] = ", ".join(_addons(value)) or "None"
            else:
                proposed[f] = value

        static = _static_factors(row, claims_rows)
        old = _rate(current, static)
        new = _rate(proposed, static)

        trend_years, trend_mult, trend_note = _trend(
            row.get("effective_date")
        )

        stored_annual = _num(row.get("annual_premium"))
        recomputed_old_annual = old["annual_premium"]

        # ---------------------------------------------------------
        # 1. Calculate annualized premium difference
        # ---------------------------------------------------------

        coverage_change_delta = _money(
            new["annual_premium"] - recomputed_old_annual
        )

        if stored_annual is not None and stored_annual > 0:
            source_of_truth = "stored_premium_trended"

            current_annual = _money(
                stored_annual * trend_mult
            )

            drift = _money(
                recomputed_old_annual - stored_annual
            )

        else:
            source_of_truth = "recomputed_baseline"

            current_annual = _money(
                recomputed_old_annual * trend_mult
            )

            drift = None


        # ---------------------------------------------------------
        # 2. Calculate proposed annualized premium
        # ---------------------------------------------------------

        proposed_annual = _money(
            max(
                500.0,
                current_annual + coverage_change_delta
            )
        )


        # ---------------------------------------------------------
        # 3. Calculate remaining policy term
        # ---------------------------------------------------------

        remaining_term = _calculate_remaining_term(
            row.get("effective_date")
        )

        remaining_days = remaining_term["remaining_days"]
        remaining_months = remaining_term["remaining_months"]
        proration_factor = remaining_term["proration_factor"]


        # ---------------------------------------------------------
        # 4. Calculate full-year premium impact
        # ---------------------------------------------------------

        annual_delta = _money(
            proposed_annual - current_annual
        )


        # ---------------------------------------------------------
        # 5. Calculate ACTUAL mid-term adjustment
        #
        # Example:
        #
        # Annual increase = $300
        # Remaining term = 3 months
        #
        # Mid-term adjustment =
        # $300 × 3 / 12
        # = $75
        # ---------------------------------------------------------

        mid_term_adjustment = _money(
            annual_delta * proration_factor
        )


        # ---------------------------------------------------------
        # 6. Remaining premium amounts
        # ---------------------------------------------------------

        current_remaining_premium = _money(
            current_annual * proration_factor
        )

        proposed_remaining_premium = _money(
            proposed_annual * proration_factor
        )


        # ---------------------------------------------------------
        # 7. Monthly equivalent
        # ---------------------------------------------------------

        current_monthly = _money(
            current_annual / 12
        )

        proposed_monthly = _money(
            proposed_annual / 12
        )

        monthly_delta = _money(
            proposed_monthly - current_monthly
        )


        # ---------------------------------------------------------
        # 8. Percentage change
        #
        # Percentage remains based on annualized premium because
        # proration affects both current and proposed equally.
        # ---------------------------------------------------------

        pct = (
            _money(
                annual_delta / current_annual * 100
            )
            if current_annual
            else 0.0
        )

        direction = (
            "INCREASE"
            if annual_delta > 0
            else "DECREASE"
            if annual_delta < 0
            else "NO_CHANGE"
        )

        changed = {}
        for f in normalized:
            a, b = current.get(f), proposed.get(f)
            if isinstance(a, Decimal): a = float(a)
            if isinstance(b, Decimal): b = float(b)
            changed[f] = {"current": a, "proposed": b, "changed": a != b}

        return {
            "status": "SUCCESS", "policy_id": str(policy_id).strip(),
            "location_context": {
                "state": row.get("property_state"),
                "city": row.get("city"),
                "zip_code": row.get("zip_code"),
            },
            "current": {
                "annual_premium": current_annual, "monthly_premium": current_monthly,
                "stored_annual_premium": stored_annual,
                "stored_monthly_premium": _num(row.get("monthly_premium")),
                "recomputed_baseline_annual_premium": recomputed_old_annual,
                "breakdown": old["breakdown"],
            },
            "proposed": {
                "annual_premium": proposed_annual, "monthly_premium": proposed_monthly,
                "recomputed_baseline_annual_premium": new["annual_premium"],
                "breakdown": new["breakdown"],
            },
            "premium_impact": {
                # Full 12-month annualized impact
                "annual_change": annual_delta,
                # Monthly equivalent of annualized change
                "monthly_change": monthly_delta,
                # Actual amount applicable to the remaining policy term
                "mid_term_adjustment": mid_term_adjustment,
                "percentage_change": pct,
                "direction": direction,
                # Change caused specifically by requested coverage changes
                "coverage_change_delta": coverage_change_delta,
                # Remaining policy period
                "remaining_days": remaining_days,
                "remaining_months": remaining_months,
                # Remaining-term premium amounts
                "current_remaining_premium": current_remaining_premium,
                "proposed_remaining_premium": proposed_remaining_premium,
                # Exact proration factor
                "proration_factor": proration_factor,
            },
            "renewal_trend": {
                "years_since_inception": trend_years, "trend_multiplier": trend_mult, "note": trend_note,
            },
            "mid_term_proration": {
                "policy_effective_date": (
                    row.get("effective_date").isoformat()
                    if hasattr(row.get("effective_date"), "isoformat")
                    else row.get("effective_date")
                ),
                "policy_expiration_date": remaining_term["policy_expiration_date"],
                "calculation_date": date.today().isoformat(),
                "remaining_days": remaining_days,
                "remaining_months": remaining_months,
                "proration_factor": proration_factor,
                "current_remaining_premium": current_remaining_premium,
                "proposed_remaining_premium": proposed_remaining_premium,
                "mid_term_adjustment": mid_term_adjustment,
            },
            "rating_diagnostics": {
                "current_premium_source": source_of_truth,
                "stored_vs_recomputed_drift": drift,
            },
            "changed_fields": changed,
            "message": f"Premium changes from ${current_annual:,.2f}/yr to ${proposed_annual:,.2f}/yr ({direction.lower()}: ${abs(annual_delta):,.2f}/yr).",
        }
    except Exception as exc:
        logger.exception("Premium calculation failed")
        return {"status": "FAILED", "message": str(exc)}

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

__all__ = ["calculate_premium"]










# """Single deterministic premium-rating tool for the Broker Productivity Agent.

# The agent decides WHAT the customer wants to change. This tool decides the
# premium numbers: it reads the current Policy1 + Property rating state, applies
# all proposed changes together, and returns current vs proposed premium.
# POC assumptions only; not carrier-approved rating rules.
# """
# import logging
# from decimal import Decimal
# from typing import Any, Dict, Optional
# from google.cloud import bigquery

# PROJECT_ID = "gcp-app-builder"
# DATASET_ID = "Broker_Productivity"
# client = bigquery.Client(project=PROJECT_ID)
# logger = logging.getLogger(__name__)

# RATING_FIELDS = {
#     "policy_name", "policy_type", "dwelling_coverage",
#     "personal_property_coverage", "liability_limit", "deductible_amount",
#     "add_ons", "roof_age", "roof_material",
# }
# FORM_BASE = {"HO-3": 1000.0, "HO-5": 1500.0}
# ADDON_PRICE = {"water backup": 500.0, "coverage line": 700.0}
# DWELLING_BASE, DWELLING_STEP, DWELLING_RATE = 300_000, 50_000, 100.0
# PP_STEP, PP_RATE = 10_000, 25.0
# DEDUCTIBLE_RATE = {500: 150.0, 1000: 0.0, 1500: -100.0, 2500: -250.0, 5000: -400.0}


# def _num(v: Any, default: Optional[float] = None) -> Optional[float]:
#     if v is None or v == "":
#         return default
#     try:
#         return float(Decimal(str(v)))
#     except Exception as exc:
#         raise ValueError(f"Invalid numeric value: {v!r}") from exc


# def _money(v: float) -> float:
#     return round(float(v), 2)


# def _form(name: Any, typ: Any) -> str:
#     # policy_name is preferred because the user's Policy data stores HO-3/HO-5 there.
#     for v in (name, typ):
#         if v:
#             s = str(v).upper().replace(" ", "").replace("_", "")
#             if "HO5" in s or "HO-5" in s:
#                 return "HO-5"
#             if "HO3" in s or "HO-3" in s:
#                 return "HO-3"
#     raise ValueError("Policy form must be HO-3 or HO-5.")


# def _addons(v: Any) -> list[str]:
#     if v is None or v == "" or str(v).strip().lower() == "none":
#         return []
#     raw = list(v) if isinstance(v, (list, tuple, set)) else str(v).split(",")
#     out = []
#     for item in raw:
#         s = " ".join(str(item).lower().replace("_", " ").split())
#         if s == "none":
#             continue
#         if s == "water backup":
#             name = "Water Backup"
#         elif s == "coverage line":
#             name = "coverage line"
#         else:
#             raise ValueError(f"Unsupported add-on '{item}'. Supported: Water Backup, coverage line.")
#         if name not in out:
#             out.append(name)
#     return out


# def _deductible(v: float):
#     selected = min(DEDUCTIBLE_RATE)
#     for tier in sorted(DEDUCTIBLE_RATE):
#         if v >= tier:
#             selected = tier
#         else:
#             break
#     return DEDUCTIBLE_RATE[selected], f"${selected:,.0f} deductible tier"


# def _liability(v: float):
#     if v >= 500_000:
#         return 100.0, "$500K+ liability tier"
#     if v >= 300_000:
#         return 50.0, "$300K-$499,999 liability tier"
#     return 0.0, "Up to $299,999 liability tier"


# def _roof_age(v: Any):
#     if v is None or v == "":
#         return 0.0, "Roof age not provided"
#     age = int(_num(v))
#     if age < 0:
#         raise ValueError("roof_age cannot be negative.")
#     if age <= 3:
#         return -200.0, f"Brand New Roof ({age} yrs)"
#     if age <= 7:
#         return -100.0, f"Preferred New Roof ({age} yrs)"
#     if age <= 15:
#         return 0.0, f"Standard Roof ({age} yrs)"
#     if age <= 20:
#         return 150.0, f"Aging Roof ({age} yrs)"
#     return 300.0, f"Old Roof ({age} yrs)"


# def _roof_material(v: Any):
#     if not v:
#         return 0.0, "Roof material not provided"
#     s = str(v).lower().strip()
#     if "metal" in s:
#         return -150.0, "Metal Roof"
#     if "tile" in s:
#         return -125.0, "Tile Roof"
#     if "slate" in s:
#         return -100.0, "Slate Roof"
#     if "wood" in s:
#         return 150.0, "Wood Shake/Shingle Roof"
#     return 0.0, f"{v} (standard material)"


# def _rate(s: Dict[str, Any]) -> Dict[str, Any]:
#     form = _form(s.get("policy_name"), s.get("policy_type"))
#     base = FORM_BASE[form]
#     dwelling = _num(s.get("dwelling_coverage"), DWELLING_BASE)
#     pp = _num(s.get("personal_property_coverage"), dwelling * .50)
#     liability = _num(s.get("liability_limit"), 100_000)
#     deductible = _num(s.get("deductible_amount"), 1000)
#     if dwelling <= 0 or pp < 0 or liability <= 0 or deductible <= 0:
#         raise ValueError("Coverage, liability and deductible values must be valid positive amounts.")

#     dwelling_adj = ((dwelling - DWELLING_BASE) / DWELLING_STEP) * DWELLING_RATE
#     pp_adj = ((pp - dwelling * .50) / PP_STEP) * PP_RATE
#     liability_adj, liability_tier = _liability(liability)
#     deductible_adj, deductible_tier = _deductible(deductible)
#     age_adj, age_tier = _roof_age(s.get("roof_age"))
#     mat_adj, mat_tier = _roof_material(s.get("roof_material"))

#     active = _addons(s.get("add_ons"))
#     addon_breakdown = {a: ADDON_PRICE[a.lower()] for a in active}
#     addons_total = sum(addon_breakdown.values())
#     annual = max(500.0, _money(base + dwelling_adj + pp_adj + liability_adj + deductible_adj + age_adj + mat_adj + addons_total))

#     return {
#         "annual_premium": annual,
#         "monthly_premium": _money(annual / 12),
#         "breakdown": {
#             "policy_form": form, "base_policy_premium": _money(base),
#             "dwelling_coverage": int(dwelling), "dwelling_adjustment": _money(dwelling_adj),
#             "personal_property_coverage": int(pp), "personal_property_adjustment": _money(pp_adj),
#             "liability_limit": int(liability), "liability_adjustment": _money(liability_adj),
#             "liability_rating_tier": liability_tier,
#             "deductible_amount": int(deductible), "deductible_adjustment": _money(deductible_adj),
#             "deductible_rating_tier": deductible_tier,
#             "roof_age": int(_num(s.get("roof_age"))) if s.get("roof_age") not in (None, "") else None,
#             "roof_age_adjustment": _money(age_adj), "roof_age_rating_tier": age_tier,
#             "roof_material": s.get("roof_material"), "roof_material_adjustment": _money(mat_adj),
#             "roof_material_rating_tier": mat_tier,
#             "active_add_ons": active, "add_ons_cost": _money(addons_total),
#             "add_on_breakdown": addon_breakdown,
#         },
#     }


# def _fetch(policy_id: str) -> Dict[str, Any]:
#     # One targeted query; no scan of unrelated Customer/Risk/Claims tables.
#     q = f"""
#     SELECT p.policy_id, p.policy_name, p.policy_type, p.dwelling_coverage,
#            p.personal_property_coverage, p.liability_limit, p.deductible_amount,
#            p.add_ons, p.annual_premium, p.monthly_premium,
#            pr.roof_age, pr.roof_material
#     FROM `{PROJECT_ID}.{DATASET_ID}.Policy1` p
#     LEFT JOIN `{PROJECT_ID}.{DATASET_ID}.Property` pr
#       ON p.property_id = pr.property_id
#     WHERE p.policy_id = @policy_id LIMIT 1
#     """
#     cfg = bigquery.QueryJobConfig(query_parameters=[
#         bigquery.ScalarQueryParameter("policy_id", "STRING", policy_id.strip())
#     ])
#     rows = list(client.query(q, job_config=cfg).result())
#     if not rows:
#         raise ValueError(f"Policy '{policy_id}' was not found.")
#     return dict(rows[0])


# def _field(raw: str) -> str:
#     aliases = {
#         "policy form": "policy_name", "form": "policy_name", "policy": "policy_name",
#         "deductible": "deductible_amount", "deductible amount": "deductible_amount",
#         "dwelling": "dwelling_coverage", "dwelling coverage": "dwelling_coverage",
#         "personal property": "personal_property_coverage", "personal property coverage": "personal_property_coverage",
#         "liability": "liability_limit", "liability limit": "liability_limit",
#         "addons": "add_ons", "add-ons": "add_ons", "add ons": "add_ons",
#         "roof age": "roof_age", "roof material": "roof_material",
#     }
#     x = str(raw).strip().lower()
#     return aliases.get(x, x)


# def calculate_premium(policy_id: str, proposed_changes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
#     """Rate a policy's COMPLETE current state vs COMPLETE proposed state.

#     Example:
#       calculate_premium("POL1006", {"deductible_amount": 500})
#       calculate_premium("POL1006", {
#           "policy_name": "HO-5", "dwelling_coverage": 400000,
#           "deductible_amount": 1000, "add_ons": "Water Backup, coverage line"
#       })
#     """
#     try:
#         if not policy_id or not str(policy_id).strip():
#             raise ValueError("policy_id is required.")
#         row = _fetch(str(policy_id).strip())
#         current = {k: row.get(k) for k in RATING_FIELDS}
#         proposed = dict(current)
#         normalized = {}

#         for raw, value in (proposed_changes or {}).items():
#             f = _field(raw)
#             if f not in RATING_FIELDS:
#                 raise ValueError(f"'{raw}' is not a premium-rating field. Supported: {sorted(RATING_FIELDS)}")
#             normalized[f] = value
#             if f in {"dwelling_coverage", "personal_property_coverage", "liability_limit", "deductible_amount", "roof_age"}:
#                 proposed[f] = _num(value)
#             elif f == "add_ons":
#                 proposed[f] = ", ".join(_addons(value)) or "None"
#             else:
#                 proposed[f] = value

#         old = _rate(current)
#         new = _rate(proposed)
#         annual_delta = _money(new["annual_premium"] - old["annual_premium"])
#         monthly_delta = _money(new["monthly_premium"] - old["monthly_premium"])
#         pct = _money(annual_delta / old["annual_premium"] * 100) if old["annual_premium"] else 0.0
#         direction = "INCREASE" if annual_delta > 0 else "DECREASE" if annual_delta < 0 else "NO_CHANGE"

#         changed = {}
#         for f in normalized:
#             a, b = current.get(f), proposed.get(f)
#             if isinstance(a, Decimal): a = float(a)
#             if isinstance(b, Decimal): b = float(b)
#             changed[f] = {"current": a, "proposed": b, "changed": a != b}

#         return {
#             "status": "SUCCESS", "policy_id": str(policy_id).strip(),
#             "current": {
#                 "annual_premium": old["annual_premium"], "monthly_premium": old["monthly_premium"],
#                 "stored_annual_premium": _num(row.get("annual_premium")),
#                 "stored_monthly_premium": _num(row.get("monthly_premium")),
#                 "breakdown": old["breakdown"],
#             },
#             "proposed": {"annual_premium": new["annual_premium"], "monthly_premium": new["monthly_premium"], "breakdown": new["breakdown"]},
#             "premium_impact": {
#                 "annual_change": annual_delta, "monthly_change": monthly_delta,
#                 "percentage_change": pct, "direction": direction,
#             },
#             "changed_fields": changed,
#             "message": f"Premium changes from ${old['annual_premium']:,.2f}/yr to ${new['annual_premium']:,.2f}/yr ({direction.lower()}: ${abs(annual_delta):,.2f}/yr).",
#         }
#     except Exception as exc:
#         logger.exception("Premium calculation failed")
#         return {"status": "FAILED", "message": str(exc)}


# __all__ = ["calculate_premium"]
