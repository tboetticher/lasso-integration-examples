"""
examples/python/bedrock-lasso_proxy/aws-boto3/02_embeddings/invoke/single_text_embedding.py

Single-text embedding example using Bedrock `invoke_model` via Lasso.

This script demonstrates:

- How to build a `bedrock-runtime` client that routes through LASSO_PROXY_ENDPOINT
- How to send a single text string to an embedding model using `invoke_model`
- How to decode and inspect the returned embedding vector

Compared to the _quickstart/simple_embedding_invoke.py example, this script:

- Focuses on a single input string
- Wraps the embedding extraction in small helper functions you can reuse
"""

import os
import json
import logging
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


# -------- Embedding helpers --------

def build_single_embedding_request_body(text: str) -> Dict[str, Any]:
    """
    Build the request body for a single-text embedding call.

    NOTE:
      - This uses a generic "inputText" pattern as an example.
      - Many Bedrock embedding models (e.g., Amazon Titan) use a specific
        field and structure – consult your model docs and update accordingly.
    """
    return {
        "inputText": text
    }


def extract_single_embedding_from_payload(payload: Dict[str, Any]) -> List[float]:
    """
    Extract a single embedding vector from the model response payload.

    Because response schemas differ by embedding model, this function tries a
    few generic patterns:

      - payload["embedding"] -> single vector
      - payload["embeddings"][0] -> first vector in a list

    Return:
        The embedding vector as a list of floats. Raises ValueError if no
        embedding is found.
    """
    # Pattern 1: single embedding vector at "embedding"
    vec = payload.get("embedding")
    if isinstance(vec, list) and all(isinstance(x, (int, float)) for x in vec):
        return [float(x) for x in vec]

    # Pattern 2: first embedding in "embeddings" list
    many = payload.get("embeddings")
    if isinstance(many, list) and many:
        first = many[0]
        if isinstance(first, list) and all(isinstance(x, (int, float)) for x in first):
            return [float(x) for x in first]

    raise ValueError(
        "Could not find a single embedding vector in the payload. "
        "Inspect the raw JSON and update extract_single_embedding_from_payload "
        "to match your model's schema."
    )


def main():
    load_dotenv()

    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not model_id:
        raise RuntimeError("BEDROCK_MODEL_ID is not set. Set it to an embedding-capable model.")

    client = create_bedrock_client_from_env()

    text = (
        "This is a single sentence whose embedding will be generated using "
        "an AWS Bedrock embedding model via a Lasso Proxy."
    )

    request_body = build_single_embedding_request_body(text)

    try:
        logger.info("Calling invoke_model for a single-text embedding")

        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body),
            contentType="application/json",
            accept="application/json",
        )

        # The response body is a streaming object; read and decode it
        raw_body = response["body"].read()
        decoded_body = raw_body.decode("utf-8", errors="replace")

        print("Raw response body (decoded):")
        print(decoded_body)

        try:
            payload = json.loads(decoded_body)
        except json.JSONDecodeError:
            logger.error("Response body is not valid JSON; cannot parse embedding.")
            return

        embedding = extract_single_embedding_from_payload(payload)

        print("\nExtracted single embedding vector.")
        print(f"Text: {text}")
        print(f"Vector length: {len(embedding)}")
        print(f"First 8 dimensions: {embedding[:8]}")

    except ValueError as ve:
        logger.error("Embedding extraction error: %s", ve)
    except botocore.exceptions.ClientError as e:
        logger.exception("Bedrock invoke_model call for single-text embedding failed: %s", e)


if __name__ == "__main__":
    main()
