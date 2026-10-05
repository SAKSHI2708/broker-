"""Cloud Storage tools for reserving policy IDs and uploading exterior photos."""

from __future__ import annotations

import logging
import os
from io import BytesIO
from typing import Any

from google.cloud import bigquery, storage
from google.adk.tools import ToolContext
from PIL import Image, ImageFilter, ImageStat

from .policy_insert import POLICY_ID_PREFIX, POLICY_ID_START, POLICY_ID_WIDTH

logger = logging.getLogger(__name__)

PHOTO_NAMES = ("front", "back", "left", "right", "top")
MIN_CLEAR_PHOTO_SCORE = 70


def _cfg() -> dict[str, str]:
    return {
        "project": os.getenv("BQ_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "gcp-app-builder")),
        "dataset": os.getenv("BQ_DATASET", "Broker_Productivity"),
        "table": os.getenv("BQ_POLICY_TABLE", "Policy"),
        "bucket": os.getenv("POLICY_PHOTOS_BUCKET", "").removeprefix("gs://").rstrip("/"),
    }


def _next_policy_number(client: bigquery.Client, fq_table: str) -> int:
    query = f"""
        SELECT MAX(CAST(SUBSTR(policy_id, {len(POLICY_ID_PREFIX) + 1}) AS INT64)) AS max_num
        FROM `{fq_table}`
        WHERE REGEXP_CONTAINS(policy_id, r'^{POLICY_ID_PREFIX}[0-9]+$')
    """
    rows = list(client.query(query).result())
    max_num = rows[0].max_num if rows and rows[0].max_num is not None else 0
    return max(int(max_num), POLICY_ID_START - 1) + 1


def _clarity_score(image_bytes: bytes) -> int:
    """Return a 0-100 sharpness estimate based on image edge detail."""
    with Image.open(BytesIO(image_bytes)) as image:
        grayscale = image.convert("L")
        edge_variance = ImageStat.Stat(grayscale.filter(ImageFilter.FIND_EDGES)).var[0]
    return min(100, round(edge_variance / 100))


async def _load_image_artifact(
    tool_context: ToolContext, artifact_name: str
) -> tuple[bytes, str] | None:
    artifact = await tool_context.load_artifact((artifact_name or "").strip())
    if artifact is None or artifact.inline_data is None:
        return None

    image_bytes = artifact.inline_data.data
    mime_type = artifact.inline_data.mime_type or "application/octet-stream"
    if not mime_type.startswith("image/"):
        return None
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
    except (OSError, ValueError):
        return None
    return image_bytes, mime_type


def reserve_policy_id() -> dict[str, Any]:
    """Reserve the next policy ID before exterior photographs are uploaded.

    Requires ``POLICY_PHOTOS_BUCKET``. A marker object prevents another request
    from receiving the same policy ID before the policy is issued.
    """
    cfg = _cfg()
    if not cfg["bucket"]:
        return {"status": "ERROR", "message": "POLICY_PHOTOS_BUCKET is not configured."}
    try:
        bq_client = bigquery.Client(project=cfg["project"])
        storage_client = storage.Client(project=cfg["project"])
        bucket = storage_client.bucket(cfg["bucket"])
        next_number = _next_policy_number(
            bq_client, f"{cfg['project']}.{cfg['dataset']}.{cfg['table']}"
        )

        for policy_number in range(next_number, next_number + 1000):
            policy_id = f"{POLICY_ID_PREFIX}{policy_number:0{POLICY_ID_WIDTH}d}"
            marker = bucket.blob(f"_reservations/{policy_id}")
            try:
                marker.upload_from_string("reserved", if_generation_match=0)
                return {
                    "status": "SUCCESS",
                    "message": "Policy ID reserved for exterior photo upload.",
                    "policy_id": policy_id,
                    "photo_folder": f"gs://{cfg['bucket']}/{policy_id}/",
                }
            except Exception as error:  # Existing marker means this ID is already reserved.
                if "PreconditionFailed" not in type(error).__name__:
                    raise

        return {"status": "ERROR", "message": "Unable to reserve a policy ID."}
    except Exception as error:  # noqa: BLE001
        logger.exception("Policy ID reservation failed")
        return {"status": "ERROR", "message": f"Failed to reserve policy ID: {error}"}


async def upload_property_photos(
    policy_id: str,
    front_photo_artifact: str,
    back_photo_artifact: str,
    left_photo_artifact: str,
    right_photo_artifact: str,
    top_photo_artifact: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Upload front, back, left, right, and top exterior photos to a policy folder.

    Each photo argument must be an uploaded ADK artifact name. Objects are stored
    as ``<policy_id>/<side>.<extension>`` in the policy's Cloud Storage folder.
    """
    cfg = _cfg()
    policy_id = (policy_id or "").strip().upper()
    if not cfg["bucket"]:
        return {"status": "ERROR", "message": "POLICY_PHOTOS_BUCKET is not configured."}
    if not policy_id.startswith(POLICY_ID_PREFIX) or not policy_id[len(POLICY_ID_PREFIX) :].isdigit():
        return {"status": "ERROR", "message": "policy_id must use the POL number format."}

    artifact_names = {
        "front": front_photo_artifact,
        "back": back_photo_artifact,
        "left": left_photo_artifact,
        "right": right_photo_artifact,
        "top": top_photo_artifact,
    }
    images = {
        side: await _load_image_artifact(tool_context, artifact_name)
        for side, artifact_name in artifact_names.items()
    }
    invalid = [side for side, image in images.items() if image is None]
    if invalid:
        return {
            "status": "ERROR",
            "message": f"Missing, unreadable, or non-image upload(s): {', '.join(invalid)}.",
        }

    try:
        bucket = storage.Client(project=cfg["project"]).bucket(cfg["bucket"])
        uploaded = []
        clarity_scores = {}
        for side in PHOTO_NAMES:
            image_bytes, mime_type = images[side]
            clarity_scores[side] = _clarity_score(image_bytes)
            extension = mime_type.removeprefix("image/").replace("jpeg", "jpg")
            object_name = f"{policy_id}/{side}.{extension}"
            blob = bucket.blob(object_name)
            blob.upload_from_string(image_bytes, content_type=mime_type)
            uploaded.append(f"gs://{cfg['bucket']}/{object_name}")
        unclear_sides = [
            side for side, score in clarity_scores.items() if score < MIN_CLEAR_PHOTO_SCORE
        ]
        return {
            "status": "SUCCESS",
            "message": (
                "All five exterior photos were uploaded."
                if not unclear_sides
                else "All five exterior photos were uploaded, but some may be blurry."
            ),
            "policy_id": policy_id,
            "photos": uploaded,
            "clarity_scores": clarity_scores,
            "clarity_threshold": MIN_CLEAR_PHOTO_SCORE,
            "low_clarity_photos": unclear_sides,
        }
    except Exception as error:  # noqa: BLE001
        logger.exception("Property photo upload failed for policy %s", policy_id)
        return {"status": "ERROR", "message": f"Failed to upload property photos: {error}"}