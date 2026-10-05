# # """Cloud Storage tools for staging exterior photos and promoting them after payment."""

# # from __future__ import annotations

# # import logging
# # import os
# # import secrets
# # from io import BytesIO
# # from typing import Any

# # from google.cloud import bigquery, storage
# # from PIL import Image, ImageFilter, ImageStat

# # from .policy_insert import (
# #     POLICY_ID_PREFIX,
# #     POLICY_ID_START,
# #     POLICY_ID_WIDTH,
# #     VALID_STATE_CODES,
# # )

# # logger = logging.getLogger(__name__)

# # # PHOTO_NAMES = ("front", "back", "left", "right", "top")
# # # REQUIRED_PHOTO_NAMES = ("front", "back", "left", "right")
# # # OPTIONAL_PHOTO_NAMES = ("top",)
# # # MIN_CLEAR_PHOTO_SCORE = 70
# # # STAGING_KEY_PREFIX = "STG-"

# # QUERY_PHOTOS_PREFIX = "query_id_images"
# # POLICY_PHOTOS_PREFIX = "policy_generated_images"

# # PHOTO_NAMES = ("front", "back", "left", "right", "top")
# # REQUIRED_PHOTO_NAMES = ("front", "back", "left", "right")
# # OPTIONAL_PHOTO_NAMES = ("top",)

# # MIN_CLEAR_PHOTO_SCORE = 70


# # def _cfg() -> dict[str, str]:
# #     return {
# #         "project": os.getenv("BQ_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "gcp-app-builder")),
# #         "dataset": os.getenv("BQ_DATASET", "Broker_Productivity"),
# #         "table": os.getenv("BQ_POLICY_TABLE", "Policy"),
# #         "bucket": os.getenv("POLICY_PHOTOS_BUCKET", "").removeprefix("gs://").rstrip("/"),
# #     }


# # def _next_policy_number(client: bigquery.Client, fq_table: str) -> int:
# #     query = f"""
# #         SELECT MAX(CAST(SUBSTR(policy_id, {len(POLICY_ID_PREFIX) + 1}) AS INT64)) AS max_num
# #         FROM `{fq_table}`
# #         WHERE REGEXP_CONTAINS(policy_id, r'^{POLICY_ID_PREFIX}[0-9]+$')
# #     """
# #     rows = list(client.query(query).result())
# #     max_num = rows[0].max_num if rows and rows[0].max_num is not None else 0
# #     return max(int(max_num), POLICY_ID_START - 1) + 1


# # def _clarity_score(image_bytes: bytes) -> int:
# #     """Return a 0-100 sharpness estimate based on image edge detail."""
# #     with Image.open(BytesIO(image_bytes)) as image:
# #         grayscale = image.convert("L")
# #         edge_variance = ImageStat.Stat(grayscale.filter(ImageFilter.FIND_EDGES)).var[0]
# #     return min(100, round(edge_variance / 100))


# # def reserve_policy_id() -> dict[str, Any]:
# #     """Reserve the next policy ID before exterior photographs are uploaded.

# #     Requires ``POLICY_PHOTOS_BUCKET``. A marker object prevents another request
# #     from receiving the same policy ID before the policy is issued.
# #     """
# #     cfg = _cfg()
# #     if not cfg["bucket"]:
# #         return {"status": "ERROR", "message": "POLICY_PHOTOS_BUCKET is not configured."}
# #     try:
# #         bq_client = bigquery.Client(project=cfg["project"])
# #         storage_client = storage.Client(project=cfg["project"])
# #         bucket = storage_client.bucket(cfg["bucket"])
# #         next_number = _next_policy_number(
# #             bq_client, f"{cfg['project']}.{cfg['dataset']}.{cfg['table']}"
# #         )

# #         for policy_number in range(next_number, next_number + 1000):
# #             policy_id = f"{POLICY_ID_PREFIX}{policy_number:0{POLICY_ID_WIDTH}d}"
# #             marker = bucket.blob(f"_reservations/{policy_id}")
# #             try:
# #                 marker.upload_from_string("reserved", if_generation_match=0)
# #                 return {
# #                     "status": "SUCCESS",
# #                     "message": "Policy ID reserved for exterior photo upload.",
# #                     "policy_id": policy_id,
# #                     "photo_folder": f"gs://{cfg['bucket']}/{policy_id}/",
# #                 }
# #             except Exception as error:  # Existing marker means this ID is already reserved.
# #                 if "PreconditionFailed" not in type(error).__name__:
# #                     raise

# #         return {"status": "ERROR", "message": "Unable to reserve a policy ID."}
# #     except Exception as error:  # noqa: BLE001
# #         logger.exception("Policy ID reservation failed")
# #         return {"status": "ERROR", "message": f"Failed to reserve policy ID: {error}"}


# # def check_photo_clarity(query_id: str) -> dict[str, Any]:
# #     """Calculate clarity scores from images already uploaded to the staging bucket."""
# #     cfg = _cfg()
# #     staging_key = (staging_key or "").strip()
# #     if not cfg["bucket"]:
# #         return {"status": "ERROR", "message": "POLICY_PHOTOS_BUCKET is not configured."}
# #     if not staging_key or "/" in staging_key or staging_key.startswith(POLICY_ID_PREFIX):
# #         return {"status": "ERROR", "message": "A valid staging_key is required."}

# #     try:
# #         bucket = storage.Client(project=cfg["project"]).bucket(cfg["bucket"])
# #         scores = {}
# #         invalid = []
# #         for side in PHOTO_NAMES:
# #             blobs = list(bucket.list_blobs(prefix=f"{staging_key}/{side}."))
# #             if not blobs:
# #                 if side in REQUIRED_PHOTO_NAMES:
# #                     invalid.append(side)
# #                 continue
# #             if len(blobs) != 1:
# #                 invalid.append(side)
# #                 continue
# #             blob = blobs[0]
# #             if not (blob.content_type or "").startswith("image/"):
# #                 invalid.append(side)
# #                 continue
# #             image_bytes = blob.download_as_bytes()
# #             try:
# #                 with Image.open(BytesIO(image_bytes)) as image:
# #                     image.verify()
# #                 scores[side] = _clarity_score(image_bytes)
# #             except (OSError, ValueError):
# #                 invalid.append(side)

# #         if invalid:
# #             return {
# #                 "status": "ERROR",
# #                 "message": (
# #                     f"Missing, ambiguous, unreadable, or non-image staged photo(s): {', '.join(invalid)}. "
# #                     f"Upload each file directly to gs://{cfg['bucket']}/{staging_key}/<side>.<extension> "
# #                     "(required sides: front, back, left, right), then retry."
# #                 ),
# #             }

# #         low_clarity = [
# #             side for side, score in scores.items() if score < MIN_CLEAR_PHOTO_SCORE
# #         ]
# #         return {
# #             "status": "SUCCESS",
# #             "message": "Clarity checked from images in the staging bucket.",
# #             "staging_key": staging_key,
# #             "clarity_scores": scores,
# #             "clarity_threshold": MIN_CLEAR_PHOTO_SCORE,
# #             "low_clarity_photos": low_clarity,
# #             "top_view_included": "top" in scores,
# #         }
# #     except Exception as error:  # noqa: BLE001
# #         logger.exception("Staged photo clarity check failed for %s", staging_key)
# #         return {"status": "ERROR", "message": f"Failed to check staged photos: {error}"}


# # def reserve_staging_key(query_id: str = "") -> dict[str, Any]:
# #     """Return a temporary staging key for pre-payment photo uploads.

# #     A query-time user stages photos under their QUERY ID. Other users get
# #     a random STG key. The returned ``photo_folder`` is the object prefix
# #     that the frontend's secure upload component should write into.
# #     """
# #     cfg = _cfg()
# #     if not cfg["bucket"]:
# #         return {"status": "ERROR", "message": "POLICY_PHOTOS_BUCKET is not configured."}

# #     query_id = (query_id or "").strip().upper()
# #     if query_id and (
# #         not query_id.startswith("QUERY")
# #         or not query_id[len("QUERY"):].isdigit()
# #     ):
# #         return {"status": "ERROR", "message": "query_id must use the QUERY number format."}

# #     key = query_id or f"{STAGING_KEY_PREFIX}{secrets.token_hex(6).upper()}"
# #     return {
# #         "status": "SUCCESS",
# #         "message": "Bucket folder assigned for pre-payment photo upload.",
# #         "staging_key": key,
# #         "photo_folder": f"gs://{cfg['bucket']}/{key}/",
# #     }


# # def promote_staging_photos_to_policy(staging_key: str, policy_number: str) -> dict[str, Any]:
# #     """Copy staged photos to the final ``<policy_number>/`` folder after approval.

# #     Must be called only after payment is approved and ``create_policy`` has
# #     returned a customer-facing policy number. Staging objects are deleted
# #     after they are successfully copied.
# #     """
# #     cfg = _cfg()
# #     staging_key = (staging_key or "").strip()
# #     policy_number = (policy_number or "").strip().upper()

# #     if not cfg["bucket"]:
# #         return {"status": "ERROR", "message": "POLICY_PHOTOS_BUCKET is not configured."}
# #     if not staging_key:
# #         return {"status": "ERROR", "message": "staging_key is required."}
# #     if not policy_number.startswith("HO-") or len(policy_number.split("-")) != 3:
# #         return {"status": "ERROR", "message": "policy_number must use the HO-TX-00045 format."}
# #     state_code, sequence = policy_number.split("-")[1:]
# #     if state_code not in VALID_STATE_CODES or not sequence.isdigit():
# #         return {"status": "ERROR", "message": "policy_number must use the HO-TX-00045 format."}

# #     try:
# #         client = storage.Client(project=cfg["project"])
# #         bucket = client.bucket(cfg["bucket"])
# #         prefix = f"{staging_key}/"
# #         copied = []
# #         for source in client.list_blobs(cfg["bucket"], prefix=prefix):
# #             if source.name == prefix:
# #                 continue
# #             relative = source.name[len(prefix):]
# #             dest_name = f"{policy_number}/{relative}"
# #             bucket.copy_blob(source, bucket, dest_name)
# #             source.delete()
# #             copied.append(f"gs://{cfg['bucket']}/{dest_name}")
# #         if not copied:
# #             return {
# #                 "status": "ERROR",
# #                 "message": f"No staged photos found under staging_key '{staging_key}'.",
# #             }
# #         return {
# #             "status": "SUCCESS",
# #             "message": f"Promoted {len(copied)} photo(s) to policy folder.",
# #             "policy_number": policy_number,
# #             "photos": copied,
# #         }
# #     except Exception as error:  # noqa: BLE001
# #         logger.exception("Failed to promote staged photos %s -> %s", staging_key, policy_number)
# #         return {"status": "ERROR", "message": f"Failed to promote staged photos: {error}"}





# """Cloud Storage tools for storing, checking, and promoting exterior photos."""

# from __future__ import annotations

# import logging
# import os
# import re
# from io import BytesIO
# from typing import Any

# from google.cloud import bigquery, storage
# from PIL import Image, ImageFilter, ImageStat

# from .policy_insert import (
#     POLICY_ID_PREFIX,
#     POLICY_ID_START,
#     POLICY_ID_WIDTH,
#     VALID_STATE_CODES,
# )

# logger = logging.getLogger(__name__)

# # ==========================================================
# # PHOTO CONFIGURATION
# # ==========================================================

# QUERY_PHOTOS_PREFIX = "query_id_images"
# POLICY_PHOTOS_PREFIX = "policy_generated_images"

# PHOTO_NAMES = ("front", "back", "left", "right", "top")
# REQUIRED_PHOTO_NAMES = ("front", "back", "left", "right")
# OPTIONAL_PHOTO_NAMES = ("top",)

# MIN_CLEAR_PHOTO_SCORE = 70

# QUERY_ID_PATTERN = re.compile(r"^QUERY[0-9]+$")


# # ==========================================================
# # CONFIGURATION
# # ==========================================================

# def _cfg() -> dict[str, str]:
#     """Read configuration from environment variables."""

#     return {
#         "project": os.getenv(
#             "BQ_PROJECT",
#             os.getenv("GOOGLE_CLOUD_PROJECT", "gcp-app-builder"),
#         ),
#         "dataset": os.getenv("BQ_DATASET", "Broker_Productivity"),
#         "table": os.getenv("BQ_POLICY_TABLE", "Policy"),
#         "bucket": os.getenv(
#             "POLICY_PHOTOS_BUCKET", ""
#         ).removeprefix("gs://").rstrip("/"),
#     }


# def _validate_query_id(query_id: str) -> str:
#     """Validate and normalize Query ID."""

#     query_id = (query_id or "").strip().upper()

#     if not QUERY_ID_PATTERN.fullmatch(query_id):
#         raise ValueError("Invalid Query ID. Expected format: QUERY0100.")

#     return query_id


# # ==========================================================
# # POLICY NUMBER GENERATION
# # ==========================================================

# def _next_policy_number(
#     client: bigquery.Client,
#     fq_table: str,
# ) -> int:

#     query = f"""
#         SELECT MAX(
#             CAST(
#                 SUBSTR(policy_id, {len(POLICY_ID_PREFIX) + 1})
#                 AS INT64
#             )
#         ) AS max_num
#         FROM `{fq_table}`
#         WHERE REGEXP_CONTAINS(
#             policy_id,
#             r'^{POLICY_ID_PREFIX}[0-9]+$'
#         )
#     """

#     rows = list(client.query(query).result())

#     max_num = (
#         rows[0].max_num
#         if rows and rows[0].max_num is not None
#         else 0
#     )

#     return max(int(max_num), POLICY_ID_START - 1) + 1


# def reserve_policy_id() -> dict[str, Any]:
#     """Reserve the next policy ID before exterior photo upload."""

#     cfg = _cfg()

#     if not cfg["bucket"]:
#         return {
#             "status": "ERROR",
#             "message": "POLICY_PHOTOS_BUCKET is not configured.",
#         }

#     try:
#         bq_client = bigquery.Client(project=cfg["project"])
#         storage_client = storage.Client(project=cfg["project"])

#         bucket = storage_client.bucket(cfg["bucket"])

#         next_number = _next_policy_number(
#             bq_client,
#             f"{cfg['project']}.{cfg['dataset']}.{cfg['table']}",
#         )

#         for policy_number in range(
#             next_number,
#             next_number + 1000,
#         ):
#             policy_id = (
#                 f"{POLICY_ID_PREFIX}"
#                 f"{policy_number:0{POLICY_ID_WIDTH}d}"
#             )

#             marker = bucket.blob(
#                 f"_reservations/{policy_id}"
#             )

#             try:
#                 marker.upload_from_string(
#                     "reserved",
#                     if_generation_match=0,
#                 )

#                 return {
#                     "status": "SUCCESS",
#                     "message": "Policy ID reserved successfully.",
#                     "policy_id": policy_id,
#                 }

#             except Exception as error:
#                 if "PreconditionFailed" not in type(error).__name__:
#                     raise

#         return {
#             "status": "ERROR",
#             "message": "Unable to reserve a policy ID.",
#         }

#     except Exception as error:
#         logger.exception("Policy ID reservation failed")

#         return {
#             "status": "ERROR",
#             "message": f"Failed to reserve policy ID: {error}",
#         }


# # ==========================================================
# # QUERY ID PHOTO FOLDER
# # ==========================================================

# def get_query_photo_folder(query_id: str) -> dict[str, Any]:
#     """
#     Return the direct photo upload destination for a Query ID.

#     Example:
#     gs://bucket/query_id_images/QUERY0102/
#     """

#     cfg = _cfg()

#     if not cfg["bucket"]:
#         return {
#             "status": "ERROR",
#             "message": "POLICY_PHOTOS_BUCKET is not configured.",
#         }

#     try:
#         query_id = _validate_query_id(query_id)

#         photo_folder = (
#             f"gs://{cfg['bucket']}/"
#             f"{QUERY_PHOTOS_PREFIX}/{query_id}/"
#         )

#         return {
#             "status": "SUCCESS",
#             "message": "Query ID photo folder assigned.",
#             "query_id": query_id,
#             "photo_folder": photo_folder,
#         }

#     except ValueError as error:
#         return {
#             "status": "ERROR",
#             "message": str(error),
#         }


# # ==========================================================
# # PHOTO CLARITY
# # ==========================================================

# def _clarity_score(image_bytes: bytes) -> int:
#     """Return a 0-100 sharpness estimate based on image edge detail."""

#     with Image.open(BytesIO(image_bytes)) as image:
#         grayscale = image.convert("L")

#         edge_variance = ImageStat.Stat(
#             grayscale.filter(ImageFilter.FIND_EDGES)
#         ).var[0]

#     return min(100, round(edge_variance / 100))


# def check_photo_clarity(query_id: str) -> dict[str, Any]:
#     """
#     Check exterior photo clarity directly from the Query ID folder.

#     Required:
#         front, back, left, right

#     Optional:
#         top

#     Photos remain stored in query_id_images after clarity checking.
#     """

#     cfg = _cfg()

#     if not cfg["bucket"]:
#         return {
#             "status": "ERROR",
#             "message": "POLICY_PHOTOS_BUCKET is not configured.",
#         }

#     try:
#         query_id = _validate_query_id(query_id)

#         client = storage.Client(project=cfg["project"])
#         bucket = client.bucket(cfg["bucket"])

#         photo_prefix = (
#             f"{QUERY_PHOTOS_PREFIX}/{query_id}/"
#         )

#         scores: dict[str, int] = {}
#         invalid: list[str] = []

#         for side in PHOTO_NAMES:

#             blobs = list(
#                 bucket.list_blobs(
#                     prefix=f"{photo_prefix}{side}."
#                 )
#             )

#             if not blobs:
#                 if side in REQUIRED_PHOTO_NAMES:
#                     invalid.append(side)

#                 continue

#             # Exactly one image per side is allowed.
#             if len(blobs) != 1:
#                 invalid.append(side)
#                 continue

#             blob = blobs[0]

#             if not (
#                 blob.content_type
#                 and blob.content_type.startswith("image/")
#             ):
#                 invalid.append(side)
#                 continue

#             image_bytes = blob.download_as_bytes()

#             try:
#                 # Verify that the uploaded file is a readable image.
#                 with Image.open(BytesIO(image_bytes)) as image:
#                     image.verify()

#                 scores[side] = _clarity_score(image_bytes)

#             except (OSError, ValueError):
#                 invalid.append(side)

#         if invalid:
#             return {
#                 "status": "ERROR",
#                 "message": (
#                     "Missing, ambiguous, unreadable, or non-image "
#                     f"photo(s): {', '.join(invalid)}. "
#                     f"Upload each photo directly to "
#                     f"gs://{cfg['bucket']}/{photo_prefix}"
#                     "<side>.<extension>. "
#                     "Required sides: front, back, left, right."
#                 ),
#                 "query_id": query_id,
#                 "photo_folder": (
#                     f"gs://{cfg['bucket']}/{photo_prefix}"
#                 ),
#             }

#         low_clarity = [
#             side
#             for side, score in scores.items()
#             if score < MIN_CLEAR_PHOTO_SCORE
#         ]

#         return {
#             "status": "SUCCESS",
#             "message": "Photo clarity checked successfully.",
#             "query_id": query_id,
#             "photo_folder": (
#                 f"gs://{cfg['bucket']}/{photo_prefix}"
#             ),
#             "clarity_scores": scores,
#             "clarity_threshold": MIN_CLEAR_PHOTO_SCORE,
#             "low_clarity_photos": low_clarity,
#             "all_required_photos_clear": (
#                 len(low_clarity) == 0
#                 and all(
#                     side in scores
#                     for side in REQUIRED_PHOTO_NAMES
#                 )
#             ),
#             "top_view_included": "top" in scores,
#         }

#     except ValueError as error:
#         return {
#             "status": "ERROR",
#             "message": str(error),
#         }

#     except Exception as error:
#         logger.exception(
#             "Photo clarity check failed for Query ID %s",
#             query_id,
#         )

#         return {
#             "status": "ERROR",
#             "message": f"Failed to check photo clarity: {error}",
#         }


# # ==========================================================
# # PROMOTE QUERY PHOTOS TO POLICY FOLDER
# # ==========================================================

# def promote_query_photos_to_policy(
#     query_id: str,
#     policy_number: str,
# ) -> dict[str, Any]:
#     """
#     Copy Query ID photos to the final policy folder after payment
#     approval and successful policy creation.

#     Source:
#         query_id_images/<query_id>/

#     Destination:
#         policy_generated_images/<policy_number>/

#     Source photos are deleted only after all copies are verified.
#     """

#     cfg = _cfg()

#     if not cfg["bucket"]:
#         return {
#             "status": "ERROR",
#             "message": "POLICY_PHOTOS_BUCKET is not configured.",
#         }

#     try:
#         query_id = _validate_query_id(query_id)

#         policy_number = (
#             policy_number or ""
#         ).strip().upper()

#         # Validate policy number.
#         parts = policy_number.split("-")

#         if len(parts) != 3 or parts[0] != "HO":
#             return {
#                 "status": "ERROR",
#                 "message": (
#                     "Invalid policy number. "
#                     "Expected format: HO-TX-00045."
#                 ),
#             }

#         state_code, sequence = parts[1], parts[2]

#         if (
#             state_code not in VALID_STATE_CODES
#             or not sequence.isdigit()
#         ):
#             return {
#                 "status": "ERROR",
#                 "message": (
#                     "Invalid policy number. "
#                     "Expected format: HO-TX-00045."
#                 ),
#             }

#         client = storage.Client(project=cfg["project"])
#         bucket = client.bucket(cfg["bucket"])

#         source_prefix = (
#             f"{QUERY_PHOTOS_PREFIX}/{query_id}/"
#         )

#         destination_prefix = (
#             f"{POLICY_PHOTOS_PREFIX}/{policy_number}/"
#         )

#         sources = list(
#             client.list_blobs(
#                 cfg["bucket"],
#                 prefix=source_prefix,
#             )
#         )

#         if not sources:
#             return {
#                 "status": "ERROR",
#                 "message": (
#                     f"No photos found for Query ID {query_id}."
#                 ),
#             }

#         copied: list[str] = []
#         pending_deletions = []

#         # --------------------------------------------------
#         # STEP 1: Copy all source objects.
#         # Do not delete any source yet.
#         # --------------------------------------------------

#         for source in sources:

#             if source.name.endswith("/"):
#                 continue

#             relative_path = source.name[len(source_prefix):]

#             destination_name = (
#                 f"{destination_prefix}{relative_path}"
#             )

#             destination = bucket.copy_blob(
#                 source,
#                 bucket,
#                 destination_name,
#             )

#             copied.append(destination_name)

#             pending_deletions.append(source)

#         if not copied:
#             return {
#                 "status": "ERROR",
#                 "message": "No valid photo objects found.",
#             }

#         # --------------------------------------------------
#         # STEP 2: Verify all destination objects.
#         # --------------------------------------------------

#         for destination_name in copied:

#             destination = bucket.blob(destination_name)

#             destination.reload()

#             if not destination.exists():
#                 raise RuntimeError(
#                     "Photo copy verification failed: "
#                     f"{destination_name}"
#                 )

#         # --------------------------------------------------
#         # STEP 3: Delete source only after successful copy.
#         # --------------------------------------------------

#         deleted = []

#         for source in pending_deletions:
#             source.delete()
#             deleted.append(source.name)

#         promoted_photos = [
#             f"gs://{cfg['bucket']}/{name}"
#             for name in copied
#         ]

#         return {
#             "status": "SUCCESS",
#             "message": (
#                 f"Successfully promoted {len(copied)} photo(s) "
#                 "to the policy folder."
#             ),
#             "query_id": query_id,
#             "policy_number": policy_number,
#             "policy_photo_folder": (
#                 f"gs://{cfg['bucket']}/{destination_prefix}"
#             ),
#             "photos": promoted_photos,
#             "source_photos_deleted": len(deleted),
#         }

#     except ValueError as error:
#         return {
#             "status": "ERROR",
#             "message": str(error),
#         }

#     except Exception as error:
#         logger.exception(
#             "Photo promotion failed: Query ID %s, Policy %s",
#             query_id,
#             policy_number,
#         )

#         return {
#             "status": "ERROR",
#             "message": (
#                 f"Failed to promote photos: {error}. "
#                 "Original Query ID photos have not been "
#                 "intentionally deleted after a failed copy."
#             ),
#         }


import os
import re
from io import BytesIO
from typing import Any

from google.adk.tools import ToolContext
from google.cloud import storage
from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError


# ==========================================================
# CONFIGURATION
# ==========================================================

ALLOWED_SIDES = {"front", "back", "left", "right", "top"}
REQUIRED_SIDES = {"front", "back", "left", "right"}

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
CLARITY_THRESHOLD = 70
SHARPNESS_THRESHOLD = 65


def _cfg() -> tuple[str, str, str]:
    bucket_name = os.getenv("POLICY_PHOTOS_BUCKET", "").strip()
    query_prefix = (os.getenv("QUERY_PHOTOS_PREFIX") or "query_id_images").strip()
    policy_prefix = (os.getenv("POLICY_PHOTOS_PREFIX") or "policy_generated_images").strip()

    bucket_name = bucket_name.removeprefix("gs://").strip("/")

    if not bucket_name:
        raise ValueError("POLICY_PHOTOS_BUCKET is not configured.")

    return (
        bucket_name,
        query_prefix.strip("/"),
        policy_prefix.strip("/"),
    )


# ==========================================================
# VALIDATION
# ==========================================================

def _validate_query_id(query_id: str) -> str:
    if not query_id or not isinstance(query_id, str):
        raise ValueError("Query ID is required.")

    query_id = query_id.strip().upper()

    if not re.fullmatch(r"QUERY\d+|QRY\d+|Q\d+", query_id):
        raise ValueError(f"Invalid Query ID: {query_id}")

    return query_id


def _validate_policy_number(policy_number: str) -> str:
    if not policy_number or not isinstance(policy_number, str):
        raise ValueError("Policy number is required.")

    policy_number = policy_number.strip().upper()

    if not re.fullmatch(r"[A-Z0-9_-]+", policy_number):
        raise ValueError("Invalid policy number.")

    return policy_number


def _validate_side(side: str) -> str:
    side = (side or "").strip().lower()

    if side not in ALLOWED_SIDES:
        raise ValueError(
            f"Invalid side. Allowed sides: {', '.join(sorted(ALLOWED_SIDES))}"
        )

    return side


def _validate_image(image_bytes: bytes, filename: str) -> str:
    if not image_bytes:
        raise ValueError("Image file is empty.")

    if len(image_bytes) > MAX_FILE_SIZE:
        raise ValueError("Image size must not exceed 10 MB.")

    extension = os.path.splitext(filename or "")[1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported image format. Use JPG, JPEG, PNG or WEBP.")

    try:
        image = Image.open(BytesIO(image_bytes))
        image.verify()
    except (UnidentifiedImageError, OSError):
        raise ValueError("Uploaded file is not a valid image.")

    return extension


# ==========================================================
# GCS HELPERS
# ==========================================================

def _get_bucket():
    bucket_name, _, _ = _cfg()
    client = storage.Client()
    return client.bucket(bucket_name)


def _get_query_prefix() -> str:
    _, query_prefix, _ = _cfg()
    return query_prefix


def _get_policy_prefix() -> str:
    _, _, policy_prefix = _cfg()
    return policy_prefix


def _get_side_blob(bucket, folder_prefix: str, side: str):
    """
    Finds a photo by side, regardless of supported extension.
    Example: front.jpg, front.png, front.webp
    """

    for extension in ALLOWED_EXTENSIONS:
        blob_name = f"{folder_prefix.rstrip('/')}/{side}{extension}"
        blob = bucket.blob(blob_name)

        if blob.exists():
            return blob

    return None


# ==========================================================
# QUERY PHOTO FOLDER
# ==========================================================

def get_query_photo_folder(query_id: str) -> str:
    """
    Returns the GCS folder URI for staged Query ID photos.
    """

    query_id = _validate_query_id(query_id)

    bucket_name, query_prefix, _ = _cfg()

    return f"gs://{bucket_name}/{query_prefix}/{query_id}/"


# ==========================================================
# UPLOAD PROPERTY PHOTO
# ==========================================================

def upload_property_photo(
    query_id: str,
    side: str,
    image_bytes: bytes,
    filename: str,
) -> dict[str, Any]:
    """
    Uploads a property photo to:

    <QUERY_PHOTOS_PREFIX>/<QUERY_ID>/<side>.<extension>
    """

    query_id = _validate_query_id(query_id)
    side = _validate_side(side)
    extension = _validate_image(image_bytes, filename)

    bucket = _get_bucket()
    query_prefix = _get_query_prefix()

    folder_prefix = f"{query_prefix}/{query_id}"

    # Remove any previous image for the same side.
    for existing_extension in ALLOWED_EXTENSIONS:
        existing_blob_name = (
            f"{folder_prefix}/{side}{existing_extension}"
        )
        existing_blob = bucket.blob(existing_blob_name)

        if existing_blob.exists():
            existing_blob.delete()

    object_name = f"{folder_prefix}/{side}{extension}"
    blob = bucket.blob(object_name)

    content_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }[extension]

    blob.upload_from_string(
        image_bytes,
        content_type=content_type,
    )

    return {
        "success": True,
        "query_id": query_id,
        "side": side,
        "gcs_path": f"gs://{bucket.name}/{object_name}",
        "message": f"{side.capitalize()} photo uploaded successfully.",
    }


async def upload_property_photo_artifact(
    query_id: str,
    side: str,
    artifact_name: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Load a chat attachment artifact and upload it directly to its GCS object."""
    artifact_name = (artifact_name or "").strip()
    if not artifact_name:
        return {"success": False, "message": "An uploaded image artifact is required."}

    try:
        artifact = await tool_context.load_artifact(artifact_name)
    except Exception as error:  # noqa: BLE001
        return {"success": False, "message": f"Could not load uploaded image: {error}"}

    if artifact is None or artifact.inline_data is None:
        return {
            "success": False,
            "message": f"Uploaded image artifact '{artifact_name}' has no image data.",
        }

    mime_type = (artifact.inline_data.mime_type or "").lower()
    extension = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(mime_type)
    if extension is None:
        return {"success": False, "message": "Use a JPG, PNG, or WEBP image."}

    try:
        return upload_property_photo(
            query_id=query_id,
            side=side,
            image_bytes=artifact.inline_data.data,
            filename=f"{side}{extension}",
        )
    except (ValueError, OSError) as error:
        return {"success": False, "message": str(error)}


# ==========================================================
# CHECK PHOTO CLARITY
# ==========================================================

def _check_image_quality(image_bytes: bytes) -> dict[str, Any]:
    """
    Basic heuristic image check using resolution, contrast, and sharpness.
    This is not an AI-based image-quality assessment.
    """

    image = Image.open(BytesIO(image_bytes)).convert("L")

    width, height = image.size

    resolution_score = min(
        100,
        int((width * height) / 10000),
    )

    extrema = image.getextrema()
    contrast = extrema[1] - extrema[0]
    contrast_score = min(100, int(contrast / 2.55))

    laplacian = image.filter(
        ImageFilter.Kernel(
            size=(3, 3),
            kernel=(0, 1, 0, 1, -4, 1, 0, 1, 0),
        )
    )
    laplacian_variance = ImageStat.Stat(laplacian).var[0]
    sharpness_score = min(100, int(laplacian_variance / 2))

    score = int(
        (resolution_score * 0.2)
        + (contrast_score * 0.2)
        + (sharpness_score * 0.6)
    )
    is_sharp = sharpness_score >= SHARPNESS_THRESHOLD

    return {
        "width": width,
        "height": height,
        "clarity_score": score,
        "sharpness_score": sharpness_score,
        "is_blurry": not is_sharp,
        "status": (
            "Clear"
            if score >= CLARITY_THRESHOLD and is_sharp
            else "Needs Review"
        ),
    }


def check_photo_clarity(query_id: str) -> dict[str, Any]:
    """
    Checks required property photos in:

    <QUERY_PHOTOS_PREFIX>/<QUERY_ID>/

    Required photos:
        front, back, left, right
    """

    query_id = _validate_query_id(query_id)

    bucket = _get_bucket()
    query_prefix = _get_query_prefix()

    folder_prefix = f"{query_prefix}/{query_id}/"

    blobs = list(bucket.list_blobs(prefix=folder_prefix))

    photo_map = {}

    for blob in blobs:
        filename = os.path.basename(blob.name)
        side, extension = os.path.splitext(filename)

        if (
            side.lower() in ALLOWED_SIDES
            and extension.lower() in ALLOWED_EXTENSIONS
        ):
            photo_map[side.lower()] = blob

    missing_sides = sorted(REQUIRED_SIDES - set(photo_map.keys()))

    results = {}
    scores = []

    for side, blob in photo_map.items():
        try:
            image_bytes = blob.download_as_bytes()
            quality = _check_image_quality(image_bytes)

            scores.append(quality["clarity_score"])

            results[side] = {
                "gcs_path": f"gs://{bucket.name}/{blob.name}",
                **quality,
            }

        except Exception as exc:
            results[side] = {
                "gcs_path": f"gs://{bucket.name}/{blob.name}",
                "clarity_score": 0,
                "status": "Error",
                "error": str(exc),
            }

    average_score = (
        int(sum(scores) / len(scores))
        if scores
        else 0
    )

    all_required_present = not missing_sides

    all_clear = (
        all_required_present
        and all(
            results.get(side, {}).get("clarity_score", 0)
            >= CLARITY_THRESHOLD
            for side in REQUIRED_SIDES
        )
    )

    if not all_required_present:
        status = "Missing Photos"
        message = (
            "The system could not find all required photos. "
            f"Missing views: {', '.join(missing_sides)}."
        )

    elif not all_clear:
        status = "Needs Review"
        message = "Some photos did not pass the basic clarity check."

    else:
        status = "Clear"
        message = (
            "All required photos are available and passed "
            "the basic clarity check."
        )

    return {
        "query_id": query_id,
        "photo_folder": get_query_photo_folder(query_id),
        "required_sides": sorted(REQUIRED_SIDES),
        "uploaded_sides": sorted(photo_map.keys()),
        "missing_sides": missing_sides,
        "average_clarity_score": average_score,
        "threshold": CLARITY_THRESHOLD,
        "photos": results,
        "status": status,
        "message": message,
    }


# ==========================================================
# PROMOTE QUERY PHOTOS TO POLICY FOLDER
# ==========================================================

def promote_query_photos_to_policy(
    query_id: str,
    policy_number: str,
) -> dict[str, Any]:
    """
    Copies Query ID photos to:

    <POLICY_PHOTOS_PREFIX>/<POLICY_NUMBER>/

    Original Query ID photos are retained.
    """

    query_id = _validate_query_id(query_id)
    policy_number = _validate_policy_number(policy_number)

    bucket = _get_bucket()

    query_prefix = _get_query_prefix()
    policy_prefix = _get_policy_prefix()

    source_prefix = f"{query_prefix}/{query_id}/"
    destination_prefix = f"{policy_prefix}/{policy_number}/"

    source_blobs = list(bucket.list_blobs(prefix=source_prefix))

    if not source_blobs:
        raise ValueError(
            f"No photos found for Query ID {query_id} "
            f"in {source_prefix}"
        )

    copied_files = []
    copied_sides = set()

    for source_blob in source_blobs:
        filename = os.path.basename(source_blob.name)

        if not filename:
            continue

        side, extension = os.path.splitext(filename)

        if (
            side.lower() not in ALLOWED_SIDES
            or extension.lower() not in ALLOWED_EXTENSIONS
        ):
            continue

        destination_name = f"{destination_prefix}{filename}"

        bucket.copy_blob(
            source_blob,
            bucket,
            destination_name,
        )

        copied_sides.add(side.lower())

        copied_files.append({
            "side": side.lower(),
            "source": f"gs://{bucket.name}/{source_blob.name}",
            "destination": f"gs://{bucket.name}/{destination_name}",
        })

    missing_sides = sorted(REQUIRED_SIDES - copied_sides)

    if missing_sides:
        return {
            "success": False,
            "status": "INCOMPLETE",
            "query_id": query_id,
            "policy_number": policy_number,
            "copied_files": copied_files,
            "missing_sides": missing_sides,
            "message": (
                "Some required photos are missing. "
                "Please complete the Query ID photo upload first."
            ),
        }

    return {
        "success": True,
        "status": "COMPLETED",
        "query_id": query_id,
        "policy_number": policy_number,
        "source_folder": f"gs://{bucket.name}/{source_prefix}",
        "policy_photo_folder": f"gs://{bucket.name}/{destination_prefix}",
        "copied_files": copied_files,
        "copied_count": len(copied_files),
        "original_query_photos_retained": True,
        "message": "Property photos copied to the policy folder successfully.",
    }


# ==========================================================
# LIST QUERY PHOTOS - DEBUGGING
# ==========================================================

def list_query_photos(query_id: str) -> dict[str, Any]:
    """
    Lists all files present under the Query ID folder.
    Useful for debugging missing-photo issues.
    """

    query_id = _validate_query_id(query_id)

    bucket = _get_bucket()
    query_prefix = _get_query_prefix()

    folder_prefix = f"{query_prefix}/{query_id}/"

    blobs = list(bucket.list_blobs(prefix=folder_prefix))

    found_files = [
        {
            "name": blob.name,
            "size": blob.size,
            "gcs_path": f"gs://{bucket.name}/{blob.name}",
        }
        for blob in blobs
    ]

    return {
        "query_id": query_id,
        "expected_folder": f"gs://{bucket.name}/{folder_prefix}",
        "found_files": found_files,
        "count": len(found_files),
    }