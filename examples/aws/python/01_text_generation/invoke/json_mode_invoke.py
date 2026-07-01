"""
examples/python/bedrock-lasso_proxy/aws-boto3/01_text_generation/invoke/json_mode_invoke.py

JSON-mode text generation example using Bedrock `invoke_model` via Lasso.

This script demonstrates:

- How to call `invoke_model` with a prompt that asks the model to return
  STRICT JSON (a fixed schema)
- How to parse the response body as JSON
- How to validate that required fields are present

IMPORTANT:
- The exact request/response schema for JSON mode is MODEL-SPECIFIC.
- Many providers (e.g., Anthropic Claude, Amazon models) support a way to
  bias responses toward valid JSON by including a "response_format" or similar
  field in the request.
- This example uses a generic pattern; you MUST adapt the request structure and
  any JSON-mode flags to match your chosen model’s Bedrock documentation.
"""

import os
import json
import logging
from typing import Any, Dict

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

    lasso_proxy_url = os.getenv("LASSO_PROXY_ENDPOINT")  # must include `/v1/bedrock`
    lasso_api_key = os.getenv("LASSO_X_API_KEY")
    region = os.getenv("AWS_REGION", "us-east-1")

    if not lasso_proxy_url:
        raise RuntimeError("LASSO_PROXY_ENDPOINT is not set.")
    if not lasso_api_key:
        raise RuntimeError("LASSO_X_API_KEY is not set.")

    client = boto3.client(
        "bedrock-runtime",
        region_name=region,
        endpoint_url=f"{lasso_proxy_url}/v1/bedrock",
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


# -------- JSON-mode invoke example --------

def build_json_mode_request_body() -> Dict[str, Any]:
    """
    Build a request body that asks the model to return a strict JSON object
    with a known schema.

    The schema we want back:

        {
          "title": string,
          "summary": string,
          "tags": [string, ...]
        }

    NOTE:
      - The exact fields you use (e.g., `prompt`, `messages`, `inputText`,
        `response_format`, etc.) and the JSON-mode switch are model-specific.
      - Update this function to match your model’s expected payload.
    """
    user_instruction = (
        "Return ONLY a JSON object with the following structure and no extra text:\n\n"
        "{\n"
        '  "title": string,\n'
        '  "summary": string,\n'
        '  "tags": string[]\n'
        "}\n\n"
        "Generate a short example describing a Python project that uses AWS Bedrock "
        "through a Lasso Proxy."
    )

    request_body: Dict[str, Any] = {
        "inputText": user_instruction,
        "generationConfig": {
            "maxTokens": 256,
            "temperature": 0.3,
        },
    }

    return request_body


def parse_and_validate_json_response(raw_body: bytes) -> Dict[str, Any]:
    """
    Parse the raw response body as JSON and validate that it matches the
    expected shape (title, summary, tags).

    Returns:
        The parsed JSON dict if valid; raises ValueError otherwise.
    """
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model response is not valid JSON: {e}") from e

    # At this point, `payload` is the top-level structure returned by the model.
    # Depending on the model, the actual JSON object we care about might be:
    #   - payload["outputText"]
    #   - payload["completion"]
    #   - payload["result"]["content"]
    #   - etc.
    #
    # For this example, we assume the model returns the desired JSON object
    # directly as the top-level payload, or under a commonly used field such as
    # "outputText". We’ll check both.

    candidate = None

    if isinstance(payload, dict):
        if all(k in payload for k in ("title", "summary", "tags")):
            candidate = payload
        elif isinstance(payload.get("outputText"), dict) and all(
            k in payload["outputText"] for k in ("title", "summary", "tags")
        ):
            candidate = payload["outputText"]
        elif isinstance(payload.get("completion"), dict) and all(
            k in payload["completion"] for k in ("title", "summary", "tags")
        ):
            candidate = payload["completion"]

    if candidate is None:
        raise ValueError(
            "Could not find expected JSON object with keys: "
            '"title", "summary", "tags" in model response.'
        )

    # Basic shape checks
    if not isinstance(candidate.get("title"), str):
        raise ValueError("Field 'title' must be a string.")
    if not isinstance(candidate.get("summary"), str):
        raise ValueError("Field 'summary' must be a string.")
    if not isinstance(candidate.get("tags"), list) or not all(
        isinstance(t, str) for t in candidate["tags"]
    ):
        raise ValueError("Field 'tags' must be a list of strings.")

    return candidate


def main():
    load_dotenv()

    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not model_id:
        raise RuntimeError("BEDROCK_MODEL_ID is not set.")

    client = create_bedrock_client_from_env()
    request_body = build_json_mode_request_body()

    logger.info("Calling invoke_model with JSON-mode style request")

    try:
        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body),
            contentType="application/json",
            accept="application/json",
        )

        # The response body is a streaming object; read and decode it
        raw_body = response["body"].read()

        print("Raw response body (decoded):")
        print(raw_body.decode("utf-8", errors="replace"))

        # Try to parse and validate JSON
        parsed = parse_and_validate_json_response(raw_body)

        print("\n--- Parsed and validated JSON object ---")
        print(json.dumps(parsed, indent=4))

    except ValueError as ve:
        logger.error("JSON validation error: %s", ve)
    except botocore.exceptions.ClientError as e:
        logger.exception("Bedrock invoke_model call failed: %s", e)


if __name__ == "__main__":
    main()
