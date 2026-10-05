# from typing import Dict, Any


# # ---------------------------------------------------------
# # LOCATION RISK MODIFIERS
# # ---------------------------------------------------------
# #
# # IMPORTANT:
# # These modifiers are NOT claim-cost multipliers.
# #
# # They are used as supporting factors when evaluating
# # event evidence.
# #
# # HIGH   = 1.0
# # MEDIUM = 0.5
# # LOW    = 0.1
# #
# # This is a POC rule and should not be presented as an
# # actuarial or insurance-industry standard.
# # ---------------------------------------------------------

# RISK_MODIFIERS = {
#     "HIGH": 1.0,
#     "MEDIUM": 0.5,
#     "LOW": 0.1,
#     "UNKNOWN": 0.0,
# }


# def normalize_risk(value: str) -> str:
#     """
#     Normalize risk values into HIGH / MEDIUM / LOW / UNKNOWN.
#     """

#     if not value:
#         return "UNKNOWN"

#     value = str(value).strip().upper()

#     if value in {"HIGH", "MEDIUM", "LOW"}:
#         return value

#     return "UNKNOWN"


# def get_risk_modifier(risk_level: str) -> float:
#     """
#     Return the configured POC modifier for a risk level.
#     """

#     risk_level = normalize_risk(risk_level)

#     return RISK_MODIFIERS.get(
#         risk_level,
#         RISK_MODIFIERS["UNKNOWN"],
#     )


# def calculate_event_evidence_score(
#     risk_level: str,
#     event_found: bool,
#     date_match: float = 0,
#     location_match: float = 0,
#     peril_match: float = 0,
# ) -> Dict[str, Any]:
#     """
#     Calculate a supporting event-evidence score.

#     This is NOT a fraud score and NOT a claim payment
#     calculation.

#     Inputs:
#         risk_level:
#             HIGH / MEDIUM / LOW

#         event_found:
#             Whether external search found a relevant event.

#         date_match:
#             0-100 confidence that the event date matches.

#         location_match:
#             0-100 confidence that the event location matches.

#         peril_match:
#             0-100 confidence that the event type matches
#             the reported peril.
#     """

#     risk_level = normalize_risk(risk_level)

#     risk_modifier = get_risk_modifier(risk_level)

#     # No external event = no positive event evidence.
#     if not event_found:
#         return {
#             "risk_level": risk_level,
#             "risk_modifier": risk_modifier,
#             "event_found": False,
#             "date_match": date_match,
#             "location_match": location_match,
#             "peril_match": peril_match,
#             "event_evidence_score": 0,
#             "evidence_level": "NONE",
#         }

#     # -----------------------------------------------------
#     # Base evidence score
#     # -----------------------------------------------------
#     #
#     # Date       = 40%
#     # Location   = 40%
#     # Peril      = 20%
#     #
#     # These are POC weights.
#     # -----------------------------------------------------

#     base_score = (
#         (float(date_match) * 0.40)
#         + (float(location_match) * 0.40)
#         + (float(peril_match) * 0.20)
#     )

#     # -----------------------------------------------------
#     # Apply location-risk modifier only as a confidence
#     # supporting factor.
#     #
#     # We DO NOT multiply the repair cost.
#     # -----------------------------------------------------

#     adjusted_score = base_score * risk_modifier

#     # Keep score within 0-100.
#     adjusted_score = max(
#         0,
#         min(round(adjusted_score), 100)
#     )

#     if adjusted_score >= 75:
#         evidence_level = "STRONG"
#     elif adjusted_score >= 50:
#         evidence_level = "MEDIUM"
#     elif adjusted_score > 0:
#         evidence_level = "WEAK"
#     else:
#         evidence_level = "NONE"

#     return {
#         "risk_level": risk_level,
#         "risk_modifier": risk_modifier,
#         "event_found": True,
#         "date_match": date_match,
#         "location_match": location_match,
#         "peril_match": peril_match,
#         "base_event_score": round(base_score),
#         "event_evidence_score": adjusted_score,
#         "evidence_level": evidence_level,
#     }