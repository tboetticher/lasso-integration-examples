"""
examples/python/bedrock-lasso_proxy/aws-boto3/01_text_generation/advanced_features/prompt_caching/simple_prompt_cache.py

Simple prompt-caching example (conceptual) using the Bedrock `converse` API
through a Lasso Proxy.

This script shows the *minimal* pattern:

- Build a Bedrock Runtime client via Lasso
- Send a request where part of the prompt is intended to be cacheable
- Call the same request twice so you can compare behavior (e.g., latency, usage)

IMPORTANT:
- Prompt caching is model- and provider-specific.
- The exact request fields that enable caching (and how to observe cache hits)
  depend on your chosen model.
- This example uses placeholder/illustrative fields. You must adapt it to the
  schema documented for your target model family.
"""

import os
import json
import logging
import time
from typing import Any, Dict

import urllib3
from dotenv import load_dotenv
import boto3
import botocore.exceptions

# Silence TLS warnings if you're using self-signed certs in dev
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------- Client construction via Lasso ----------

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


# ---------- Simple prompt-caching call ----------

def build_messages() -> list[dict[str, Any]]:
    """
    Build a simple message list consisting of:

    - A system message that we *intend* to cache and reuse
    - A user message with the actual question

    NOTE:
      Where and how you mark content as cacheable depends on the model.
      This example shows the *shape* only. Replace or extend with the real
      cache-related fields for your provider.
    """
    system_msg = {
        "role": "system",
        "content": [
            {
                "text": (
                    "You are a concise, helpful assistant. Respond in 1–2 sentences. "
                    "This system prompt is likely to be reused across many requests."
                ),
                # Placeholder example of where cache-related config might live.
                # Consult your model docs and replace/remove this as appropriate.
                #
                # "cacheConfig": {
                #     "type": "ephemeral"
                # }
            }
        ],
    }

    user_msg = {
        "role": "user",
        "content": [
            {
                "text": "Briefly explain what prompt caching is and why it can be useful."
            }
        ],
    }

    return [system_msg, user_msg]


def call_with_simple_cache_pattern(
    client: boto3.client,
    model_id: str,
    label: str,
    extra_inference_config: Dict[str, Any] | None = None,
) -> dict:
    """
    Call `converse` with messages intended to demonstrate a repeatable prompt,
    optionally passing additional cache-related config at the inference level.

    Args:
        client:  Configured Bedrock Runtime client.
        model_id: Bedrock model ID.
        label:   Label to prefix logs (e.g., "FIRST_CALL" / "SECOND_CALL").
        extra_inference_config: Optional dict with any model-specific fields
                                that enable/tune prompt caching.

    Returns:
        The raw response dict from `converse`.
    """
    messages = build_messages()

    inference_config: Dict[str, Any] = {
        "maxTokens": 128,
        "temperature": 0.2,
    }
    if extra_inference_config:
        inference_config.update(extra_inference_config)

    logger.info("Calling converse for label=%s", label)
    response = client.converse(
        modelId=model_id,
        messages=messages,
        inferenceConfig=inference_config,
    )

    # Print a minimal summary
    print(f"\n=== {label}: top-level keys ===")
    print(list(response.keys()))

    # Try to extract the first text segment
    output_msg = response.get("output", {}).get("message", {})
    content = output_msg.get("content", []) or []
    text_parts = [p.get("text") for p in content if isinstance(p.get("text"), str)]

    if text_parts:
        print(f"\n--- {label}: extracted text ---")
        print(text_parts[0])

    # If the provider exposes usage/metrics, print them to compare calls
    usage = response.get("usage") or response.get("metrics")
    if usage:
        print(f"\n{label}: usage/metrics block:")
        print(json.dumps(usage, indent=4))

    return response


def main():
    load_dotenv()

    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not model_id:
        raise RuntimeError("BEDROCK_MODEL_ID is not set.")

    client = create_bedrock_client_from_env()

    # OPTIONAL: If your model supports prompt-cache options at the inference level,
    # put them here and merge into inferenceConfig. These keys are EXAMPLES ONLY.
    #
    # Example structure (replace with real fields from your model docs):
    #
    # extra_cache_config = {
    #     "promptCacheConfig": {
    #         "mode": "READ_WRITE",
    #         "ttlSeconds": 600
    #     }
    # }
    #
    extra_cache_config: Dict[str, Any] | None = None

    # First call – likely a cache miss
    resp1 = call_with_simple_cache_pattern(
        client=client,
        model_id=model_id,
        label="FIRST_CALL",
        extra_inference_config=extra_cache_config,
    )

    # Short pause so logs are easier to read
    time.sleep(1)

    # Second call – identical request. If prompt caching is enabled and configured
    # correctly for your model, you may see differences in usage/metrics or latency.
    resp2 = call_with_simple_cache_pattern(
        client=client,
        model_id=model_id,
        label="SECOND_CALL",
        extra_inference_config=extra_cache_config,
    )

    # For debugging, you can uncomment these to inspect full responses:
    # print(json.dumps(resp1, indent=4))
    # print(json.dumps(resp2, indent=4))


if __name__ == "__main__":
    try:
        main()
    except botocore.exceptions.ClientError as e:
        logger.exception("Bedrock call failed: %s", e)
