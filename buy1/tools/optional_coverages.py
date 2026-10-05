"""Deterministic pricing for optional homeowners coverages."""

from __future__ import annotations

from datetime import date
from typing import Any


WATER_BACKUP_BASE_PRICES = {5000: 50, 10000: 85, 25000: 150}
SERVICE_LINE_BASE_PRICE = 45


def _normalise_answers(
    year_built: int,
    basement_type: str,
    has_sump_pump: str,
    large_trees_near_utility_lines: str,
) -> tuple[int, str, str, str]:
    try:
        built = int(year_built)
    except (TypeError, ValueError) as error:
        raise ValueError("year_built must be an integer.") from error

    if built < 1800 or built > date.today().year:
        raise ValueError("year_built must be between 1800 and the current year.")

    basement_values = {
        "finished": "finished",
        "yes - finished": "finished",
        "yes finished": "finished",
        "unfinished": "unfinished",
        "yes - unfinished": "unfinished",
        "yes unfinished": "unfinished",
        "no": "no",
        "no basement": "no",
    }
    basement = basement_values.get((basement_type or "").strip().lower())
    sump_pump = (has_sump_pump or "").strip().lower()
    trees = (large_trees_near_utility_lines or "").strip().lower()

    if basement is None:
        raise ValueError("basement_type must be Finished, Unfinished, or No.")
    if sump_pump not in {"yes", "no"}:
        raise ValueError("has_sump_pump must be Yes or No.")
    if trees not in {"yes", "no", "not sure"}:
        raise ValueError("large_trees_near_utility_lines must be Yes, No, or Not sure.")

    return built, basement, sump_pump, trees


def _prices(
    built: int, basement: str, sump_pump: str, trees: str
) -> tuple[list[dict[str, int]], dict[str, Any]]:
    basement_surcharge = {"finished": 25, "unfinished": 10, "no": 0}[basement]
    sump_discount = 10 if sump_pump == "yes" else 0
    water_backup = [
        {
            "limit": limit,
            "annual_price": base_price + basement_surcharge - sump_discount,
        }
        for limit, base_price in WATER_BACKUP_BASE_PRICES.items()
    ]

    if trees == "not sure":
        service_line = {
            "status": "NEEDS_REVIEW",
            "message": "Price unavailable until nearby utility-line trees are verified.",
        }
    else:
        property_age = date.today().year - built
        service_line = {
            "status": "AVAILABLE",
            "annual_price": SERVICE_LINE_BASE_PRICE
            + (15 if trees == "yes" else 0)
            + (10 if property_age >= 20 else 0),
        }

    return water_backup, service_line


def calculate_optional_coverage_options(
    year_built: int,
    basement_type: str,
    has_sump_pump: str,
    large_trees_near_utility_lines: str,
) -> dict[str, Any]:
    """Return add-on prices using the provided underwriting rules."""
    try:
        built, basement, sump_pump, trees = _normalise_answers(
            year_built,
            basement_type,
            has_sump_pump,
            large_trees_near_utility_lines,
        )
    except ValueError as error:
        return {"status": "ERROR", "message": str(error)}

    water_backup, service_line = _prices(built, basement, sump_pump, trees)
    return {
        "status": "SUCCESS",
        "water_backup_options": water_backup,
        "service_line_option": service_line,
    }


def calculate_final_premium(
    policy_type: str,
    base_annual_premium: int,
    year_built: int,
    basement_type: str,
    has_sump_pump: str,
    large_trees_near_utility_lines: str,
    selected_water_backup_limit: int = 0,
    add_service_line: bool = False,
) -> dict[str, Any]:
    """Recalculate selected add-ons and return the final annual premium."""
    policy = (policy_type or "").strip().upper()
    if policy not in {"HO-3", "HO-5"}:
        return {"status": "ERROR", "message": "policy_type must be HO-3 or HO-5."}

    try:
        base_premium = int(base_annual_premium)
        built, basement, sump_pump, trees = _normalise_answers(
            year_built,
            basement_type,
            has_sump_pump,
            large_trees_near_utility_lines,
        )
    except (TypeError, ValueError) as error:
        return {"status": "ERROR", "message": str(error)}

    if base_premium <= 0:
        return {"status": "ERROR", "message": "base_annual_premium must be positive."}
    if selected_water_backup_limit not in {0, *WATER_BACKUP_BASE_PRICES}:
        return {
            "status": "ERROR",
            "message": "selected_water_backup_limit must be 0, 5000, 10000, or 25000.",
        }
    if add_service_line and trees == "not sure":
        return {
            "status": "NEEDS_REVIEW",
            "message": "Service Line Protection cannot be priced until nearby utility-line trees are verified.",
        }

    water_backup, service_line = _prices(built, basement, sump_pump, trees)
    selected_add_ons = []
    if selected_water_backup_limit:
        water_option = next(
            option
            for option in water_backup
            if option["limit"] == selected_water_backup_limit
        )
        selected_add_ons.append(
            {
                "name": f"Water Backup Coverage ({selected_water_backup_limit:,} limit)",
                "annual_price": water_option["annual_price"],
            }
        )
    if add_service_line:
        selected_add_ons.append(
            {
                "name": "Service Line Protection",
                "annual_price": service_line["annual_price"],
            }
        )

    add_on_total = sum(item["annual_price"] for item in selected_add_ons)
    return {
        "status": "SUCCESS",
        "selected_policy": policy,
        "base_annual_premium": base_premium,
        "selected_add_ons": selected_add_ons,
        "add_on_total": add_on_total,
        "final_annual_premium": base_premium + add_on_total,
    }