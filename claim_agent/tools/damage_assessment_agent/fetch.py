import os

from dotenv import load_dotenv, find_dotenv
from google.cloud import storage
from google.adk.tools import ToolContext

load_dotenv(find_dotenv())

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
BUCKET_NAME = os.getenv("CLAIM_IMAGES_BUCKET")


def fetch_reference_images(
    policy_number: str,
    tool_context: ToolContext,
) -> dict:
    """
    Fetch all reference images for a policy from GCS.

    GCS path:
        gs://broker_productivity/<policy_number>/reference/

    Args:
        policy_number: Policy number whose reference images
                       should be fetched.
        tool_context: ADK tool context.

    Returns:
        List of reference image paths.
    """

    # -----------------------------
    # Validate policy number
    # -----------------------------

    if not policy_number:
        return {
            "status": "ERROR",
            "message": "Policy number is required."
        }

    # -----------------------------
    # Validate bucket
    # -----------------------------

    if not BUCKET_NAME:
        return {
            "status": "ERROR",
            "message": (
                "CLAIM_IMAGES_BUCKET is not configured "
                "in .env"
            )
        }

    try:

        # -----------------------------
        # Connect to GCS
        # -----------------------------

        storage_client = storage.Client(
            project=PROJECT_ID
        )

        bucket = storage_client.bucket(
            BUCKET_NAME
        )

        # -----------------------------
        # Reference folder
        # -----------------------------

        prefix = (
            f"{policy_number}/"
            f"reference/"
        )

        # -----------------------------
        # Fetch images
        # -----------------------------

        blobs = bucket.list_blobs(
            prefix=prefix
        )

        image_extensions = (
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".heic",
        )

        reference_images = []

        for blob in blobs:

            if blob.name.endswith("/"):
                continue

            if not blob.name.lower().endswith(
                image_extensions
            ):
                continue

            reference_images.append({
                "file_name": os.path.basename(
                    blob.name
                ),
                "gcs_path": (
                    f"gs://{BUCKET_NAME}/"
                    f"{blob.name}"
                ),
                "content_type": (
                    blob.content_type
                    or "image/jpeg"
                ),
            })

        # -----------------------------
        # No images found
        # -----------------------------

        if not reference_images:
            return {
                "status": "ERROR",
                "message": (
                    f"No reference images found "
                    f"for policy {policy_number} "
                    f"under {prefix}"
                ),
            }

        # -----------------------------
        # Save paths in state
        # -----------------------------

        tool_context.state[
            "reference_image_paths"
        ] = [
            image["gcs_path"]
            for image in reference_images
        ]

        # -----------------------------
        # Return result
        # -----------------------------

        return {
            "status": "SUCCESS",
            "policy_number": policy_number,
            "reference_folder": (
                f"gs://{BUCKET_NAME}/{prefix}"
            ),
            "reference_images": reference_images,
            "image_count": len(
                reference_images
            ),
        }

    except Exception as e:

        return {
            "status": "ERROR",
            "message": (
                f"Failed to fetch reference "
                f"images: {str(e)}"
            ),
        }