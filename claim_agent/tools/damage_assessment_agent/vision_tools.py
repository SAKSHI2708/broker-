# from google.adk.tools import ToolContext

# #working one 
# # def record_damage_assessment(
# #     damage_type: str,
# #     severity: str,
# #     repair_or_replace: str,
# #     damaged_components: list[str],
# #     measurable: bool,
# #     affected_area_percent: int,
# #     visible_hazards: list[str],
# #     damage_summary: str,
# #     confidence: float,
# #     tool_context: ToolContext,
# # ) -> dict:
# #     """
# #     Persist the damage assessment you have already determined by
# #     visually comparing the reference photographs and the customer's
# #     damage photographs in this conversation.

# #     Call this exactly once, after you have finished your visual
# #     analysis, with your own conclusions as arguments. This tool does
# #     not analyze images itself — it only records and calculates the
# #     square footage for the values you provide. This step is required:
# #     the Claim Calculation Agent cannot see this conversation and reads
# #     only what this tool stores.

# #     Args:
# #         damage_type: One of "wind", "hail", "water", "fire",
# #             "earthquake", "unknown".
# #         severity: One of "Minor", "Moderate", "Major", "Severe".
# #         repair_or_replace: One of "repair", "replace", "uncertain".
# #         damaged_components: List of affected parts, e.g.
# #             ["roof", "asphalt shingles", "gutters"].
# #         measurable: True only if the damage can be mapped to the
# #             property's known roof area. False if geometry is
# #             unavailable and a percentage would be a guess.
# #         affected_area_percent: Whole number 0-100. Ignored if
# #             measurable is False.
# #         visible_hazards: List of visible safety hazards, if any.
# #         damage_summary: Short factual description of what is visible.
# #         confidence: 0 to 1, your confidence in this assessment.

# #     Returns:
# #         A dict with "status" and the stored "assessment".
# #     """

# def record_damage_assessment(
#     damage_type: str,
#     severity: str,
#     repair_or_replace: str,
#     damaged_components: list[str],
#     measurable: bool,
#     affected_area_percent: int,
#     visible_hazards: list[str],
#     damage_summary: str,
#     confidence: float,
#     tool_context: ToolContext,
# ) -> dict:
#     """
#     Persist the FINAL damage assessment after performing five
#     independent visual assessment passes on the customer-uploaded
#     damage photographs.

#     The customer damage photographs are already available to the
#     Damage Assessment Agent in the current ADK chat conversation.
#     Do not look for the customer photographs in GCS and do not ask
#     the customer for image filenames.

#     WORKFLOW:

#     1. Visually inspect the uploaded customer damage photographs
#        and the available reference/before photographs.

#     2. Perform five independent assessment passes of the same
#        photographs.

#        For each pass, independently determine:
#        - damage type
#        - severity
#        - repair or replace
#        - damaged components
#        - whether the affected area is measurable
#        - affected area percentage
#        - visible hazards
#        - damage summary
#        - confidence

#     3. Compare the five assessment results.

#     4. Aggregate the five results before recording the final result.

#        For categorical fields such as damage_type, severity, and
#        repair_or_replace, use the conclusion supported by the
#        majority of the five assessments.

#        For affected_area_percent, use the median of the five
#        valid measurable percentages.

#        Combine consistently identified damaged components and
#        visible hazards.

#        Use the combined evidence to determine the final confidence.

#     5. Call this recording tool only once, using the FINAL
#        aggregated assessment as the arguments.

#     IMPORTANT:
#     Do not call this tool five times to store five separate results.
#     The five visual assessments happen before this final recording
#     call. This tool stores only the final aggregated assessment.

#     This tool does not perform image analysis itself. It only
#     persists the final assessment that has already been determined
#     from the photographs and calculates the affected square footage.

#     This step is required because the Claim Calculation Agent
#     cannot see the damage-assessment conversation and reads the
#     stored assessment from ToolContext.

#     Args:
#         damage_type: One of "wind", "hail", "water", "fire",
#             "earthquake", "unknown".

#         severity: One of "Minor", "Moderate", "Major", "Severe".

#         repair_or_replace: One of "repair", "replace", "uncertain".

#         damaged_components: List of visibly affected parts, e.g.
#             ["roof", "asphalt shingles", "gutters"].

#         measurable: True only if the damage can be mapped to the
#             property's known roof area. False if geometry is
#             unavailable and a percentage would be a guess.

#         affected_area_percent: Whole number 0-100. Ignored when
#             measurable is False.

#         visible_hazards: List of visible safety hazards, if any.

#         damage_summary: Short factual description of the visible
#             damage supported by the photographs.

#         confidence: 0 to 1, representing confidence in the final
#             aggregated assessment.

#     Returns:
#         A dict with "status" and the stored final "assessment".
#     """
#     try:
#         claim_context = tool_context.state.get("claim_context") or {}
#         property_details = claim_context.get("property") or {}
#         roof_area_sqft = property_details.get("roof_area_sqft")

#         confidence = max(0.0, min(float(confidence), 1.0))

#         assessment = {
#             "damage_type": damage_type,
#             "severity": severity,
#             "repair_or_replace": repair_or_replace,
#             "damaged_components": damaged_components,
#             "damaged_component": damaged_components[0] if damaged_components else "",
#             "visible_hazards": visible_hazards,
#             "damage_summary": damage_summary,
#             "confidence": confidence,
#         }

#         if not measurable or affected_area_percent is None or not roof_area_sqft:
#             assessment["measurable"] = False
#             assessment["affected_area_percent"] = None
#             assessment["affected_area_sqft"] = None
#             assessment["human_review_required"] = True
#         else:
#             percent = max(0, min(int(affected_area_percent), 100))
#             affected_area_sqft = round(float(roof_area_sqft) * percent / 100, 2)

#             assessment["measurable"] = True
#             assessment["affected_area_percent"] = percent
#             assessment["affected_area_sqft"] = affected_area_sqft
#             assessment["calculation"] = {
#                 "known_roof_area_sqft": roof_area_sqft,
#                 "affected_area_percent": percent,
#                 "affected_area_sqft": affected_area_sqft,
#             }
#             # Single reasoning pass, no self-consistency sampling here —
#             # flag low-confidence calls for human review since there's
#             # no spread check to fall back on.
#             assessment["human_review_required"] = confidence < 0.7

#         tool_context.state["damage_assessment"] = assessment

#         return {"status": "SUCCESS", "assessment": assessment}

#     except Exception as e:
#         return {"status": "ERROR", "message": str(e)}


# import json
# import os
# import statistics

# from google import genai
# from google.adk.tools import ToolContext
# from google.genai import types


# MODEL = os.getenv(
#     "GEMINI_MODEL_PRO",
#     "gemini-3.6-flash",
# )

# PROJECT_ID = os.getenv(
#     "GOOGLE_CLOUD_PROJECT"
# )

# LOCATION = os.getenv(
#     "GOOGLE_CLOUD_LOCATION",
#     "us-central1",
# )


# _client = None


# def _get_client():
#     global _client

#     if _client is None:
#         _client = genai.Client(
#             vertexai=True,
#             project=PROJECT_ID,
#             location=LOCATION,
#         )

#     return _client


# def _get_uploaded_image_parts(
#     tool_context: ToolContext,
# ):
#     """
#     Get the image that the customer uploaded in ADK Web.

#     We are NOT looking for the image in GCS.
#     ADK already has the uploaded image in the invocation.
#     """

#     invocation_context = (
#         tool_context.get_invocation_context()
#     )

#     user_content = getattr(
#         invocation_context,
#         "user_content",
#         None,
#     )

#     if not user_content:
#         return []

#     image_parts = []

#     for part in (
#         user_content.parts or []
#     ):
#         if (
#             getattr(part, "inline_data", None)
#             or getattr(part, "file_data", None)
#         ):
#             image_parts.append(part)

#     return image_parts


# def _run_one_damage_assessment(
#     image_parts,
# ):
#     """
#     One independent Gemini vision assessment.
#     """

#     prompt = """
# Analyze the uploaded property damage photograph.

# This is an insurance damage assessment.

# Determine ONLY what is visibly supported by the photograph.

# Return ONLY valid JSON:

# {
#   "damage_type": "wind",
#   "severity": "Severe",
#   "repair_or_replace": "replace",
#   "damaged_components": ["roof", "asphalt shingles"],
#   "measurable": true,
#   "affected_area_percent": 25,
#   "visible_hazards": [],
#   "damage_summary": "Short factual description of visible damage.",
#   "confidence": 0.90
# }

# Rules:

# - Do not assume hidden damage.
# - Do not calculate claim payment.
# - Do not make a coverage decision.
# - For roof damage, estimate the visibly damaged roof surface
#   using a conceptual 10x10 grid.
# - affected_area_percent must be 0-100.
# - confidence must be between 0 and 1.
# """

#     contents = [
#         *image_parts,
#         types.Part.from_text(
#             text=prompt
#         ),
#     ]

#     response = (
#         _get_client()
#         .models
#         .generate_content(
#             model=MODEL,
#             contents=contents,
#             config=types.GenerateContentConfig(
#                 temperature=0.2,
#                 response_mime_type="application/json",
#             ),
#         )
#     )

#     return json.loads(
#         response.text
#     )


# def _aggregate_assessments(
#     assessments: list[dict],
# ) -> dict:
#     """
#     Aggregate the five independent assessments.
#     """

#     percentages = [
#         int(
#             a["affected_area_percent"]
#         )
#         for a in assessments
#         if a.get("measurable")
#         and a.get(
#             "affected_area_percent"
#         ) is not None
#     ]

#     damage_types = [
#         a["damage_type"]
#         for a in assessments
#         if a.get("damage_type")
#     ]

#     severities = [
#         a["severity"]
#         for a in assessments
#         if a.get("severity")
#     ]

#     repair_values = [
#         a["repair_or_replace"]
#         for a in assessments
#         if a.get("repair_or_replace")
#     ]

#     components = sorted({
#         component
#         for a in assessments
#         for component in (
#             a.get(
#                 "damaged_components"
#             )
#             or []
#         )
#     })

#     hazards = sorted({
#         hazard
#         for a in assessments
#         for hazard in (
#             a.get(
#                 "visible_hazards"
#             )
#             or []
#         )
#     })

#     confidences = [
#         float(
#             a.get(
#                 "confidence",
#                 0
#             )
#         )
#         for a in assessments
#     ]

#     def mode(values):
#         if not values:
#             return None

#         return max(
#             set(values),
#             key=values.count,
#         )

#     final_percent = (
#         int(
#             round(
#                 statistics.median(
#                     percentages
#                 )
#             )
#         )
#         if percentages
#         else None
#     )

#     spread = (
#         max(percentages)
#         - min(percentages)
#         if percentages
#         else None
#     )

#     return {
#         "damage_type": (
#             mode(damage_types)
#             or "unknown"
#         ),

#         "severity": (
#             mode(severities)
#             or "Minor"
#         ),

#         "repair_or_replace": (
#             mode(repair_values)
#             or "uncertain"
#         ),

#         "damaged_components": components,

#         "measurable": bool(
#             percentages
#         ),

#         "affected_area_percent": (
#             final_percent
#         ),

#         "visible_hazards": hazards,

#         "damage_summary": (
#             assessments[-1].get(
#                 "damage_summary",
#                 ""
#             )
#         ),

#         "confidence": round(
#             sum(confidences)
#             / len(confidences),
#             3,
#         ),

#         "sample_count": len(
#             assessments
#         ),

#         "sample_percents": percentages,

#         "percent_spread": spread,

#         "human_review_required": (
#             spread is not None
#             and spread > 15
#         ),
#     }


# def analyze_damage_images(
#     tool_context: ToolContext,
# ) -> dict:
#     """
#     Analyze the same ADK-uploaded damage photograph
#     five times and aggregate the results.
#     """

#     try:

#         # ---------------------------------------------
#         # Get image already uploaded in ADK Web.
#         # ---------------------------------------------

#         image_parts = (
#             _get_uploaded_image_parts(
#                 tool_context
#             )
#         )

#         if not image_parts:
#             return {
#                 "status": "ERROR",
#                 "message": (
#                     "No uploaded damage image "
#                     "was found in the current "
#                     "ADK invocation."
#                 ),
#             }

#         # ---------------------------------------------
#         # FIVE ACTUAL GEMINI CALLS
#         # ---------------------------------------------

#         assessments = []

#         for i in range(5):

#             assessment = (
#                 _run_one_damage_assessment(
#                     image_parts
#                 )
#             )

#             assessments.append(
#                 assessment
#             )

#             # This lets you SEE each result
#             # in the ADK/server logs.

#             print(
#                 "\n================================"
#             )

#             print(
#                 f"DAMAGE ASSESSMENT {i + 1}/5"
#             )

#             print(
#                 "================================"
#             )

#             print(
#                 json.dumps(
#                     assessment,
#                     indent=2,
#                 )
#             )

#         # ---------------------------------------------
#         # AGGREGATE FIVE RESULTS
#         # ---------------------------------------------

#         final = _aggregate_assessments(
#             assessments
#         )

#         print(
#             "\n================================"
#         )

#         print(
#             "FINAL AGGREGATED ASSESSMENT"
#         )

#         print(
#             "================================"
#         )

#         print(
#             json.dumps(
#                 final,
#                 indent=2,
#             )
#         )

#         # ---------------------------------------------
#         # Store the five individual results
#         # so you can inspect them.
#         # ---------------------------------------------

#         tool_context.state[
#             "damage_assessment_runs"
#         ] = assessments

#         # ---------------------------------------------
#         # NOW call your existing recorder
#         # ONLY ONCE.
#         # ---------------------------------------------

#         record_result = (
#             record_damage_assessment(
#                 damage_type=final[
#                     "damage_type"
#                 ],

#                 severity=final[
#                     "severity"
#                 ],

#                 repair_or_replace=final[
#                     "repair_or_replace"
#                 ],

#                 damaged_components=final[
#                     "damaged_components"
#                 ],

#                 measurable=final[
#                     "measurable"
#                 ],

#                 affected_area_percent=final[
#                     "affected_area_percent"
#                 ],

#                 visible_hazards=final[
#                     "visible_hazards"
#                 ],

#                 damage_summary=final[
#                     "damage_summary"
#                 ],

#                 confidence=final[
#                     "confidence"
#                 ],

#                 tool_context=tool_context,
#             )
#         )

#         # Keep aggregation information alongside
#         # the final stored assessment.

#         if record_result.get(
#             "status"
#         ) == "SUCCESS":

#             tool_context.state[
#                 "damage_assessment"
#             ].update({
#                 "sample_count": 5,
#                 "sample_percents": final[
#                     "sample_percents"
#                 ],
#                 "percent_spread": final[
#                     "percent_spread"
#                 ],
#                 "human_review_required": final[
#                     "human_review_required"
#                 ],
#             })

#         return {
#             "status": "SUCCESS",

#             "individual_assessments":
#                 assessments,

#             "final_assessment":
#                 final,

#             "record_result":
#                 record_result,
#         }

#     except Exception as e:

#         return {
#             "status": "ERROR",
#             "message": str(e),
#         }


import json
import os
import statistics

from google import genai
from google.adk.tools import ToolContext
from google.genai import types


# ============================================================
# CONFIGURATION
# ============================================================

MODEL = os.getenv(
    "GEMINI_MODEL_PRO",
    "gemini-3.6-flash",
)

PROJECT_ID = os.getenv(
    "GOOGLE_CLOUD_PROJECT"
)

LOCATION = os.getenv(
    "GOOGLE_CLOUD_LOCATION",
    "us-central1",
)


_client = None


# ============================================================
# GEMINI CLIENT
# ============================================================

def _get_client():

    global _client

    if _client is None:

        _client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location=LOCATION,
        )

    return _client


# ============================================================
# 1. RECORD FINAL DAMAGE ASSESSMENT
# ============================================================

def record_damage_assessment(
    damage_type: str,
    severity: str,
    repair_or_replace: str,
    damaged_components: list[str],
    measurable: bool,
    affected_area_percent: int,
    visible_hazards: list[str],
    damage_summary: str,
    confidence: float,
    tool_context: ToolContext,
) -> dict:
    """
    Store the final aggregated damage assessment.

    This function is called exactly once by
    analyze_damage_images() after five independent
    Gemini vision assessments have been completed
    and aggregated.

    It does NOT analyze images.
    """

    try:

        # ----------------------------------------------------
        # Get claim context
        # ----------------------------------------------------

        claim_context = (
            tool_context.state.get(
                "claim_context"
            )
            or {}
        )

        property_details = (
            claim_context.get(
                "property"
            )
            or {}
        )

        roof_area_sqft = (
            property_details.get(
                "roof_area_sqft"
            )
        )

        # ----------------------------------------------------
        # Normalize confidence
        # ----------------------------------------------------

        confidence = max(
            0.0,
            min(
                float(confidence),
                1.0
            )
        )

        # ----------------------------------------------------
        # Base assessment
        # ----------------------------------------------------

        assessment = {

            "damage_type":
                damage_type,

            "severity":
                severity,

            "repair_or_replace":
                repair_or_replace,

            "damaged_components":
                damaged_components,

            "damaged_component":
                (
                    damaged_components[0]
                    if damaged_components
                    else ""
                ),

            "visible_hazards":
                visible_hazards,

            "damage_summary":
                damage_summary,

            "confidence":
                confidence,
        }

        # ----------------------------------------------------
        # Calculate affected square footage
        # ----------------------------------------------------

        if (
            not measurable
            or affected_area_percent is None
            or not roof_area_sqft
        ):

            assessment[
                "measurable"
            ] = False

            assessment[
                "affected_area_percent"
            ] = None

            assessment[
                "affected_area_sqft"
            ] = None

            assessment[
                "human_review_required"
            ] = True

        else:

            percent = max(
                0,
                min(
                    int(
                        affected_area_percent
                    ),
                    100
                )
            )

            affected_area_sqft = round(
                float(
                    roof_area_sqft
                )
                * percent
                / 100,
                2,
            )

            assessment[
                "measurable"
            ] = True

            assessment[
                "affected_area_percent"
            ] = percent

            assessment[
                "affected_area_sqft"
            ] = affected_area_sqft

            assessment[
                "calculation"
            ] = {

                "known_roof_area_sqft":
                    roof_area_sqft,

                "affected_area_percent":
                    percent,

                "affected_area_sqft":
                    affected_area_sqft,
            }

            assessment[
                "human_review_required"
            ] = confidence < 0.7

        # ----------------------------------------------------
        # Store final assessment
        # ----------------------------------------------------

        tool_context.state[
            "damage_assessment"
        ] = assessment

        return {

            "status":
                "SUCCESS",

            "assessment":
                assessment,
        }

    except Exception as e:

        return {

            "status":
                "ERROR",

            "message":
                str(e),
        }


# ============================================================
# 2. GET CUSTOMER-UPLOADED IMAGE
# ============================================================

def _get_uploaded_image_parts(
    tool_context: ToolContext,
):
    """
    Get the customer-uploaded image parts from
    the current ADK invocation.

    IMPORTANT:
    These are the images uploaded directly through
    ADK Web. They are NOT fetched from GCS.
    """

    invocation_context = (
        tool_context.get_invocation_context()
    )

    user_content = getattr(
        invocation_context,
        "user_content",
        None,
    )

    if not user_content:
        return []

    image_parts = []

    for part in (
        user_content.parts or []
    ):

        if (
            getattr(
                part,
                "inline_data",
                None
            )
            or getattr(
                part,
                "file_data",
                None
            )
        ):

            image_parts.append(
                part
            )

    return image_parts


# ============================================================
# 3. ONE GEMINI DAMAGE ASSESSMENT
# ============================================================

def _run_one_damage_assessment(
    image_parts,
):
    """
    Perform ONE independent Gemini vision assessment.

    The same customer-uploaded image is sent to Gemini
    once per call.

    analyze_damage_images() calls this function five times.
    """

    prompt = """
Analyze the uploaded property damage photograph.

Return ONLY valid JSON.

Use exactly this structure:

{
  "damage_type": "wind",
  "severity": "Severe",
  "repair_or_replace": "replace",
  "damaged_components": [
    "roof",
    "asphalt shingles"
  ],
  "measurable": true,
  "affected_area_percent": 25,
  "visible_hazards": [],
  "damage_summary": "Short factual description.",
  "confidence": 0.90
}

Rules:

- Analyze only visible damage.
- Do not assume hidden or internal damage.
- Do not calculate claim payment.
- Do not make a coverage decision.
- Do not determine policy eligibility.
- For roof damage, estimate the visibly damaged
  roof surface using a conceptual 10x10 grid.
- affected_area_percent must be a whole number
  from 0 to 100.
- confidence must be a number from 0 to 1.
- damaged_components must always be a JSON list
  of strings.
- visible_hazards must always be a JSON list
  of strings.
- damage_summary must always be a string.
- Return one JSON object only.
"""

    contents = [
        *image_parts,
        types.Part.from_text(
            text=prompt
        ),
    ]

    response = (
        _get_client()
        .models
        .generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )
    )

    raw_text = response.text

    print(
        "\nRAW GEMINI RESPONSE:"
    )

    print(raw_text)

    result = json.loads(
        raw_text
    )

    return result


# ============================================================
# 4. NORMALIZE ONE GEMINI RESULT
# ============================================================

def _normalize_assessment(
    assessment,
):
    """
    Make sure every Gemini assessment has the
    expected dictionary structure.

    This prevents:
        'list' object has no attribute 'get'
    """

    # --------------------------------------------------------
    # Gemini normally returns a dictionary.
    # --------------------------------------------------------

    if isinstance(
        assessment,
        dict
    ):

        result = assessment

    # --------------------------------------------------------
    # Sometimes JSON may contain a single object
    # inside a list.
    # --------------------------------------------------------

    elif isinstance(
        assessment,
        list
    ):

        if (
            len(assessment) == 1
            and isinstance(
                assessment[0],
                dict
            )
        ):

            result = assessment[0]

        else:

            raise ValueError(
                "Gemini returned a list instead of "
                "a single damage assessment object."
            )

    else:

        raise ValueError(
            "Gemini returned an unsupported "
            f"assessment type: "
            f"{type(assessment).__name__}"
        )

    # --------------------------------------------------------
    # Normalize damaged_components
    # --------------------------------------------------------

    damaged_components = (
        result.get(
            "damaged_components"
        )
        or []
    )

    if isinstance(
        damaged_components,
        str
    ):

        damaged_components = [
            damaged_components
        ]

    elif not isinstance(
        damaged_components,
        list
    ):

        damaged_components = []

    result[
        "damaged_components"
    ] = [
        str(component)
        for component
        in damaged_components
        if component is not None
    ]

    # --------------------------------------------------------
    # Normalize visible_hazards
    # --------------------------------------------------------

    visible_hazards = (
        result.get(
            "visible_hazards"
        )
        or []
    )

    if isinstance(
        visible_hazards,
        str
    ):

        visible_hazards = [
            visible_hazards
        ]

    elif not isinstance(
        visible_hazards,
        list
    ):

        visible_hazards = []

    result[
        "visible_hazards"
    ] = [
        str(hazard)
        for hazard
        in visible_hazards
        if hazard is not None
    ]

    # --------------------------------------------------------
    # Normalize measurable
    # --------------------------------------------------------

    result[
        "measurable"
    ] = bool(
        result.get(
            "measurable",
            False
        )
    )

    # --------------------------------------------------------
    # Normalize affected percentage
    # --------------------------------------------------------

    affected_percent = result.get(
        "affected_area_percent"
    )

    if (
        affected_percent is not None
        and result["measurable"]
    ):

        try:

            affected_percent = max(
                0,
                min(
                    int(
                        affected_percent
                    ),
                    100
                )
            )

        except (
            TypeError,
            ValueError
        ):

            affected_percent = None

    else:

        affected_percent = None

    result[
        "affected_area_percent"
    ] = affected_percent

    # --------------------------------------------------------
    # Normalize confidence
    # --------------------------------------------------------

    try:

        confidence = float(
            result.get(
                "confidence",
                0
            )
        )

    except (
        TypeError,
        ValueError
    ):

        confidence = 0.0

    result[
        "confidence"
    ] = max(
        0.0,
        min(
            confidence,
            1.0
        )
    )

    # --------------------------------------------------------
    # Normalize strings
    # --------------------------------------------------------

    result[
        "damage_type"
    ] = str(
        result.get(
            "damage_type",
            "unknown"
        )
    )

    result[
        "severity"
    ] = str(
        result.get(
            "severity",
            "Minor"
        )
    )

    result[
        "repair_or_replace"
    ] = str(
        result.get(
            "repair_or_replace",
            "uncertain"
        )
    )

    result[
        "damage_summary"
    ] = str(
        result.get(
            "damage_summary",
            ""
        )
    )

    return result


# ============================================================
# 5. AGGREGATE FIVE ASSESSMENTS
# ============================================================

def _aggregate_assessments(
    assessments: list[dict],
) -> dict:
    """
    Aggregate the five independent Gemini assessments.

    Affected area:
        median of the five measurable percentages.

    Categorical fields:
        mode.

    Confidence:
        average.

    Human review:
        required if percentage spread > 15 points.
    """

    normalized = []

    # --------------------------------------------------------
    # Normalize all five results
    # --------------------------------------------------------

    for index, item in enumerate(
        assessments,
        start=1
    ):

        try:

            normalized_item = (
                _normalize_assessment(
                    item
                )
            )

            normalized.append(
                normalized_item
            )

        except Exception as e:

            print(
                "\nWARNING:"
                f" Assessment {index}/5 "
                "could not be normalized."
            )

            print(
                str(e)
            )

    # --------------------------------------------------------
    # Require at least one valid result
    # --------------------------------------------------------

    if not normalized:

        raise ValueError(
            "No valid damage assessments "
            "were returned by Gemini."
        )

    # --------------------------------------------------------
    # Affected percentages
    # --------------------------------------------------------

    percentages = [
        int(
            a[
                "affected_area_percent"
            ]
        )
        for a in normalized
        if (
            a.get(
                "measurable"
            ) is True
            and a.get(
                "affected_area_percent"
            ) is not None
        )
    ]

    # --------------------------------------------------------
    # Damage types
    # --------------------------------------------------------

    damage_types = [
        a[
            "damage_type"
        ]
        for a in normalized
        if a.get(
            "damage_type"
        )
    ]

    # --------------------------------------------------------
    # Severities
    # --------------------------------------------------------

    severities = [
        a[
            "severity"
        ]
        for a in normalized
        if a.get(
            "severity"
        )
    ]

    # --------------------------------------------------------
    # Repair / replace
    # --------------------------------------------------------

    repair_values = [
        a[
            "repair_or_replace"
        ]
        for a in normalized
        if a.get(
            "repair_or_replace"
        )
    ]

    # --------------------------------------------------------
    # Damaged components
    # --------------------------------------------------------

    components = sorted({
        component

        for a in normalized

        for component in (
            a.get(
                "damaged_components"
            )
            or []
        )

        if isinstance(
            component,
            str
        )
    })

    # --------------------------------------------------------
    # Visible hazards
    # --------------------------------------------------------

    hazards = sorted({
        hazard

        for a in normalized

        for hazard in (
            a.get(
                "visible_hazards"
            )
            or []
        )

        if isinstance(
            hazard,
            str
        )
    })

    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    confidences = [
        float(
            a.get(
                "confidence",
                0
            )
        )
        for a in normalized
    ]

    # --------------------------------------------------------
    # Mode helper
    # --------------------------------------------------------

    def mode(values):

        if not values:
            return None

        return max(
            set(values),
            key=values.count
        )

    # --------------------------------------------------------
    # Final affected percentage
    # --------------------------------------------------------

    final_percent = (

        int(
            round(
                statistics.median(
                    percentages
                )
            )
        )

        if percentages

        else None
    )

    # --------------------------------------------------------
    # Percentage spread
    # --------------------------------------------------------

    spread = (

        max(percentages)
        - min(percentages)

        if percentages

        else None
    )

    # --------------------------------------------------------
    # Final damage summary
    #
    # Use the assessment with the highest confidence.
    # --------------------------------------------------------

    best_summary_assessment = max(
        normalized,
        key=lambda a: float(
            a.get(
                "confidence",
                0
            )
        )
    )

    # --------------------------------------------------------
    # Final confidence
    # --------------------------------------------------------

    final_confidence = (

        round(
            sum(confidences)
            / len(confidences),
            3,
        )

        if confidences

        else 0.0
    )

    # --------------------------------------------------------
    # Final aggregated result
    # --------------------------------------------------------

    final = {

        "damage_type":
            mode(
                damage_types
            )
            or "unknown",

        "severity":
            mode(
                severities
            )
            or "Minor",

        "repair_or_replace":
            mode(
                repair_values
            )
            or "uncertain",

        "damaged_components":
            components,

        "measurable":
            bool(
                percentages
            ),

        "affected_area_percent":
            final_percent,

        "visible_hazards":
            hazards,

        "damage_summary":
            best_summary_assessment.get(
                "damage_summary",
                ""
            ),

        "confidence":
            final_confidence,

        "sample_count":
            len(
                normalized
            ),

        "sample_percents":
            percentages,

        "percent_spread":
            spread,

        "human_review_required":
            (
                spread is not None
                and spread > 15
            ),
    }

    return final


# ============================================================
# 6. MAIN DAMAGE ANALYSIS TOOL
# ============================================================

def analyze_damage_images(
    tool_context: ToolContext,
) -> dict:
    """
    Perform five independent Gemini vision assessments
    on the same customer-uploaded damage photograph(s).

    Then:

    1. Store all five assessments.
    2. Aggregate them.
    3. Call record_damage_assessment() exactly once.
    4. Store the final assessment.
    """

    try:

        # ====================================================
        # GET CUSTOMER-UPLOADED IMAGES
        # ====================================================

        image_parts = (
            _get_uploaded_image_parts(
                tool_context
            )
        )

        if not image_parts:

            return {

                "status":
                    "ERROR",

                "message":
                    (
                        "No uploaded damage image "
                        "was found in the current "
                        "ADK invocation."
                    ),
            }

        print(
            "\n================================"
        )

        print(
            "CUSTOMER DAMAGE IMAGES FOUND"
        )

        print(
            f"Image parts: {len(image_parts)}"
        )

        print(
            "================================"
        )

        # ====================================================
        # FIVE GEMINI ASSESSMENTS
        # ====================================================

        assessments = []

        for i in range(5):

            print(
                "\n================================"
            )

            print(
                f"STARTING GEMINI ASSESSMENT "
                f"{i + 1}/5"
            )

            print(
                "================================"
            )

            # ------------------------------------------------
            # One actual Gemini call
            # ------------------------------------------------

            raw_assessment = (
                _run_one_damage_assessment(
                    image_parts
                )
            )

            # ------------------------------------------------
            # Print returned Python type
            # ------------------------------------------------

            print(
                "GEMINI RESULT TYPE:",
                type(
                    raw_assessment
                ).__name__
            )

            # ------------------------------------------------
            # Normalize result
            # ------------------------------------------------

            assessment = (
                _normalize_assessment(
                    raw_assessment
                )
            )

            # ------------------------------------------------
            # Store result
            # ------------------------------------------------

            assessments.append(
                assessment
            )

            # ------------------------------------------------
            # Print result
            # ------------------------------------------------

            print(
                "\nDAMAGE ASSESSMENT "
                f"{i + 1}/5"
            )

            print(
                json.dumps(
                    assessment,
                    indent=2
                )
            )

        # ====================================================
        # STORE ALL FIVE ASSESSMENTS
        # ====================================================

        tool_context.state[
            "damage_assessment_runs"
        ] = assessments

        # ====================================================
        # AGGREGATE
        # ====================================================

        final = (
            _aggregate_assessments(
                assessments
            )
        )

        print(
            "\n================================"
        )

        print(
            "FINAL AGGREGATED ASSESSMENT"
        )

        print(
            "================================"
        )

        print(
            json.dumps(
                final,
                indent=2
            )
        )

        # ====================================================
        # RECORD FINAL RESULT ONCE
        # ====================================================

        print(
            "\n================================"
        )

        print(
            "CALLING "
            "record_damage_assessment()"
        )

        print(
            "================================"
        )

        record_result = (
            record_damage_assessment(

                damage_type=
                    final[
                        "damage_type"
                    ],

                severity=
                    final[
                        "severity"
                    ],

                repair_or_replace=
                    final[
                        "repair_or_replace"
                    ],

                damaged_components=
                    final[
                        "damaged_components"
                    ],

                measurable=
                    final[
                        "measurable"
                    ],

                affected_area_percent=
                    final[
                        "affected_area_percent"
                    ],

                visible_hazards=
                    final[
                        "visible_hazards"
                    ],

                damage_summary=
                    final[
                        "damage_summary"
                    ],

                confidence=
                    final[
                        "confidence"
                    ],

                tool_context=
                    tool_context,
            )
        )

        # ====================================================
        # CHECK RECORD RESULT
        # ====================================================

        if (
            record_result.get(
                "status"
            )
            == "SUCCESS"
        ):

            # -----------------------------------------------
            # Add five-run information to final state
            # -----------------------------------------------

            tool_context.state[
                "damage_assessment"
            ].update({

                "sample_count":
                    final[
                        "sample_count"
                    ],

                "sample_percents":
                    final[
                        "sample_percents"
                    ],

                "percent_spread":
                    final[
                        "percent_spread"
                    ],

                "human_review_required":
                    final[
                        "human_review_required"
                    ],
            })

        else:

            return {

                "status":
                    "ERROR",

                "message":
                    (
                        "Five Gemini assessments "
                        "completed, but "
                        "record_damage_assessment() "
                        "failed."
                    ),

                "individual_assessments":
                    assessments,

                "final_assessment":
                    final,

                "record_result":
                    record_result,
            }

        # ====================================================
        # SUCCESS
        # ====================================================

        return {

            "status":
                "SUCCESS",

            "individual_assessments":
                assessments,

            "final_assessment":
                final,

            "record_result":
                record_result,
        }

    except Exception as e:

        print(
            "\n================================"
        )

        print(
            "DAMAGE ANALYSIS ERROR"
        )

        print(
            "================================"
        )

        print(
            str(e)
        )

        return {

            "status":
                "ERROR",

            "message":
                str(e),
        }