"""
examples/python/bedrock-lasso_proxy/aws-boto3/02_embeddings/invoke/embeddings_with_metadata.py

Embedding example using Bedrock `invoke_model` via Lasso, including metadata.

This script demonstrates:

- How to include per-item metadata alongside texts you embed
- How to call an embedding model via `invoke_model`
- How to map each returned embedding back to its metadata and input text

Typical use cases:

- Storing embeddings in a vector database with document IDs, source types, etc.
- Keeping track of which embedding corresponds to which record in your system

IMPORTANT:
- Embedding request/response schemas are MODEL-SPECIFIC.
- This example uses generic patterns like "inputTextList" / "embeddings".
  You MUST adapt the request and extraction logic to match your chosen
  embedding model’s Bedrock documentation (e.g., Amazon Titan Embeddings).
"""

import os
import json
import logging
from typing import Any, Dict, List, TypedDict

import urllib3
from dotenv import load_dotenv
import boto3
import botocore.exceptions

# Silence TLS warnings if you're using self-signed certs in dev
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# -------- Types --------

class TextWithMetadata(TypedDict):
    text: str
    id: str
    source: str
    extra: Dict[str, Any]


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

def get_sample_items() -> List[TextWithMetadata]:
    """
    Build a sample list of items with text and metadata.

    In a real application, these might be documents, knowledge base entries,
    tickets, etc.
    """
    return [
        {
            "id": "doc-001",
            "text": "How to configure a Bedrock client through a Lasso Proxy.",
            "source": "docs",
            "extra": {"category": "bedrock", "priority": "high"},
        },
        {
            "id": "doc-002",
            "text": "Troubleshooting TLS and proxy configuration when calling Bedrock.",
            "source": "docs",
            "extra": {"category": "troubleshooting", "priority": "medium"},
        },
        {
            "id": "faq-101",
            "text": "What is an embedding vector and how is it used in semantic search?",
            "source": "faq",
            "extra": {"category": "embeddings", "priority": "low"},
        },
    ]


def build_embedding_request_body(items: List[TextWithMetadata]) -> Dict[str, Any]:
    """
    Build the request body for an embedding model from a list of items.

    NOTE:
      - This uses a generic "inputTextList" pattern as an example.
      - Many Bedrock embedding models (e.g., Amazon Titan) use a specific
        field and structure – consult your model docs and update accordingly.
    """
    if not items:
        raise ValueError("At least one item is required to embed.")

    texts = [item["text"] for item in items]

    # Example multi-input shape; adjust field name to your model schema.
    return {
        "inputTextList": texts
    }


def extract_batch_embeddings_from_payload(payload: Dict[str, Any]) -> List[List[float]]:
    """
    Extract batch embedding vectors from the model response payload.

    Because response schemas differ by embedding model, this function tries a
    generic pattern:

      - payload["embeddings"] -> list of vectors

    Return:
        List of embedding vectors (each is a list of floats). May be empty if
        no known pattern is found.
    """
    embeddings: List[List[float]] = []

    many = payload.get("embeddings")
    if isinstance(many, list):
        for item in many:
            if isinstance(item, list) and all(isinstance(x, (int, float)) for x in item):
                embeddings.append([float(x) for x in item])

    return embeddings


def main():
    load_dotenv()

    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not model_id:
        raise RuntimeError("BEDROCK_MODEL_ID is not set. Set it to an embedding-capable model.")

    client = create_bedrock_client_from_env()

    items = get_sample_items()
    request_body = build_embedding_request_body(items)

    try:
        logger.info("Calling invoke_model for embeddings with metadata (n=%d)", len(items))

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
            logger.error("Response body is not valid JSON; cannot parse embeddings.")
            return

        embeddings = extract_batch_embeddings_from_payload(payload)

        if not embeddings:
            print(
                "\nCould not find embeddings in the response using the generic "
                "'embeddings' pattern. Inspect the raw JSON structure above and "
                "update extract_batch_embeddings_from_payload to match your model's schema."
            )
            return

        if len(embeddings) != len(items):
            logger.warning(
                "Number of embeddings (%d) does not match number of items (%d). "
                "Check your model's response schema.",
                len(embeddings),
                len(items),
            )

        print(f"\nMapped {len(embeddings)} embeddings back to items with metadata:")

        for item, vec in zip(items, embeddings):
            print("\nItem metadata:")
            print(f"  id:     {item['id']}")
            print(f"  source: {item['source']}")
            print(f"  extra:  {item['extra']}")
            print(f"  text:   {item['text']}")
            print(f"  embedding length: {len(vec)}")
            print(f"  first 8 dims: {vec[:8]}")

        # In a real application, this is where you would upsert into a vector
        # store along with the metadata (id, source, extra, etc.).

    except botocore.exceptions.ClientError as e:
        logger.exception("Bedrock invoke_model call for embeddings with metadata failed: %s", e)


if __name__ == "__main__":
    main()
