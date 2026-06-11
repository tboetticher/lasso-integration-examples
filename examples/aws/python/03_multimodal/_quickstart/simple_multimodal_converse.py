"""
examples/python/bedrock-lasso_proxy/aws-boto3/03_multimodal/_quickstart/simple_multimodal_converse.py

Quickstart: simple multimodal example using Bedrock `converse` via Lasso.

This script demonstrates the *pattern* for sending text + image input
to a multimodal Bedrock model through the Lasso Proxy:

- Build a `bedrock-runtime` client pointed at LASSO_PROXY_ENDPOINT
- Construct a `converse` request with:
  - A system message (text only)
  - A user message that may contain both text and an image
- Call `converse` and print the assistant’s reply

IMPORTANT:
- Multimodal request/response schemas are MODEL-SPECIFIC.
- You MUST adapt:
  - How images are encoded (e.g., base64)
  - The `content` structure for image blocks
  - Any additional multimodal config
  to match your chosen model’s Bedrock documentation.
"""

import os
import json
import logging
import base64
from typing import Any, Dict, List

import urllib3
from dotenv import load_dotenv
import boto3
import botocore.exceptions

# Silence TLS warnings if you're using self-signed certs in dev
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# -------- Client construction via Lasso --------

def create_bedrock_client_from_env() -> boto3.client:
    """
    Create a Bedrock Runtime client using:
      - LASSO_PROXY_ENDPOINT as the endpoint_url
      - LASSO_X_API_KEY injected as a custom header
      - Default AWS credential chain for credentials

    Required env vars:
      - LASSO_PROXY_ENDPOINT (must include `/v1/bedrock`)
      - LASSO_X_API_KEY
      - AWS_REGION (optional, defaults to us-east-1)
    """
    load_dotenv()

    lasso_proxy_endpoint = os.getenv("LASSO_PROXY_ENDPOINT")  # must include `/v1/bedrock`
    lasso_api_key = os.getenv("LASSO_X_API_KEY")
    region = os.getenv("AWS_REGION", "us-east-1")

    if not lasso_proxy_endpoint:
        raise RuntimeError("LASSO_PROXY_ENDPOINT is not set.")
    if not lasso_api_key:
        raise RuntimeError("LASSO_X_API_KEY is not set.")

    client = boto3.client(
        "bedrock-runtime",
        region_name=region,
        endpoint_url=lasso_proxy_endpoint,
        # Set verify=False only for dev/self-signed certs. Prefer True in production.
        verify=False,
    )

    # Inject the Lasso header on every Bedrock Runtime call
    def add_custom_header(request, **kwargs):
        request.headers.add_header("lasso-x-api-key", lasso_api_key)

    client.meta.events.register_first(
        "before-sign.bedrock-runtime.*",
        add_custom_header,
    )

    return client


# -------- Multimodal helpers (pattern, model-specific) --------

def load_image_as_base64(image_path: str) -> str:
    """
    Read an image file from disk and return a base64-encoded string.

    NOTE:
      - Some models expect:
          - 'base64' payload + a MIME type (e.g., 'image/png')
          - Or a bytes-like object in a specific structure.
      - This helper simply produces base64; adapt for your model.
    """
    with open(image_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode("ascii")


def build_multimodal_messages(
    user_text: str,
    image_base64: str | None = None,
    image_mime_type: str = "image/png",
) -> List[Dict[str, Any]]:
    """
    Build a messages list for a simple multimodal request:

    - A system message that configures behavior
    - A user message that includes:
        - Text content
        - An image part (if provided)

    The exact shape of an image content block is MODEL-SPECIFIC. This example
    uses a generic pattern like:

        {
          "image": {
            "format": "png",
            "data": "<base64 string>"
          }
        }

    You MUST update this to match your model’s expected multimodal payload.
    """
    system_msg = {
        "role": "system",
        "content": [
            {
                "text": (
                    "You are a helpful assistant that can see both images and text. "
                    "Describe what you see and answer questions about the image "
                    "and the text together."
                )
            }
        ],
    }

    # Start with the text part of the user message
    user_content: List[Dict[str, Any]] = [
        {
            "text": user_text
        }
    ]

    # If an image is provided, add it as another content block
    if image_base64 is not None:
        # Generic placeholder image representation; update for your model
        user_content.append(
            {
                "image": {
                    "format": image_mime_type.split("/")[-1],  # e.g., "png"
                    "data": image_base64,
                }
            }
        )

    user_msg = {
        "role": "user",
        "content": user_content,
    }

    return [system_msg, user_msg]


def extract_first_text(response: Dict[str, Any]) -> str:
    """
    Extract the first text segment from a `converse` response.

    Returns:
        The first text string found in the output message's content, or
        an empty string if none is present.
    """
    output_msg = response.get("output", {}).get("message", {})
    content = output_msg.get("content", []) or []

    for part in content:
        text = part.get("text")
        if isinstance(text, str):
            return text

    return ""


def main():
    load_dotenv()

    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not model_id:
        raise RuntimeError("BEDROCK_MODEL_ID is not set. Set it to a multimodal-capable model.")

    client = create_bedrock_client_from_env()

    # Optional: a local image file to include. If not provided or not found,
    # the request will be text-only but still use the multimodal pattern.
    image_path = os.getenv("MULTIMODAL_IMAGE_PATH")  # e.g., "./examples/assets/sample.png"

    image_base64: str | None = None
    if image_path:
        if os.path.exists(image_path):
            logger.info("Loading image from %s", image_path)
            image_base64 = load_image_as_base64(image_path)
        else:
            logger.warning("MULTIMODAL_IMAGE_PATH is set but file does not exist: %s", image_path)

    user_prompt = (
        "Given this image (if provided) and my text, describe what you see and "
        "summarize how it relates to building applications with AWS Bedrock via Lasso."
    )

    messages = build_multimodal_messages(
        user_text=user_prompt,
        image_base64=image_base64,
        image_mime_type="image/png",
    )

    try:
        response = client.converse(
            modelId=model_id,
            messages=messages,
            inferenceConfig={
                "maxTokens": 256,
                "temperature": 0.4,
            },
        )

        # Show top-level keys so users can inspect the full response structure
        print("Top-level response keys:", list(response.keys()))

        # Extract and print the assistant's reply text
        reply_text = extract_first_text(response)
        if reply_text:
            print("\n--- Assistant reply ---")
            print(reply_text)
        else:
            print("\nNo text content found in the response; inspect the raw JSON below:")
            print(json.dumps(response, indent=4))

    except botocore.exceptions.ClientError as e:
        logger.exception("Bedrock converse call for multimodal example failed: %s", e)


if __name__ == "__main__":
    main()
