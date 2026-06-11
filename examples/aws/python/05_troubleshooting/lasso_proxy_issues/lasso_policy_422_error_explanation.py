"""
Send a text prompt to AWS Bedrock and retrieve 422 error to understand why a policy was enforced for the request.

Required environment variables:
  LASSO_PROXY_ENDPOINT
  LASSO_X_API_KEY
  AWS_REGION
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  AWS_SESSION_TOKEN          # optional
  BEDROCK_MODEL_ID
"""

import json
import logging
import os
import urllib3
from typing import Any, Dict
import boto3
import botocore.exceptions
from botocore.config import Config
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


# 1. Load configuration
lasso_proxy_endpoint = os.getenv("LASSO_PROXY_ENDPOINT")
lasso_api_key = os.getenv("LASSO_X_API_KEY")
region = os.getenv("AWS_REGION", "us-east-1")
access_key = os.getenv("AWS_ACCESS_KEY_ID")
secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
session_token = os.getenv("AWS_SESSION_TOKEN")

model_id = os.getenv("BEDROCK_TEXT_MODEL_ID")


# 2. Create Bedrock client that points to the Lasso proxy
bedrock_client = boto3.client(
    "bedrock-runtime",
    region_name=region,
    endpoint_url=lasso_proxy_endpoint,
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    aws_session_token=session_token,
    config=Config(
        retries={"max_attempts": 1, "mode": "standard"},
        connect_timeout=5,
        read_timeout=12,
        user_agent_extra="lasso-proxy-example/1.0",
    ),
    verify=False
)


# 3. Add the Lasso API key header to every Bedrock request
def add_lasso_header(request, **kwargs):
    request.headers.add_header("lasso-x-api-key", lasso_api_key)

_TRACE_HEADERS = (
    "x-request-id",
    "x-tenant-id",
    "x-amzn-requestid",
    "x-amz-request-id",
)
def attach_block_reason(http_response, parsed: Dict[str, Any], **_: Any) -> None:
    """
    Attach error details to the parsed response for ClientError handling.

    - 422: parsed["BlockReason"] from {"error":{"message": "..."}}
    - Trace: parsed["LassoTrace"] from known trace headers if present
    """

    try:
        ctype = (http_response.headers.get("Content-Type") or "").lower()
        if "application/json" not in ctype:
            return
        data = json.loads(http_response.text or "{}")
    except Exception as exc:
        logger.debug("attach_block_reason: failed to parse JSON: %s", exc)
        data = {}

    status = getattr(http_response, "status_code", None)

    if status == 422:
        # Lasso policy block format
        reason = (data.get("error") or {}).get("message")
        if isinstance(reason, str) and reason.strip():
            parsed["BlockReason"] = reason.strip()


    # Optional append trace headers to message
    trace = {k: http_response.headers[k] for k in _TRACE_HEADERS if k in http_response.headers}
    if trace:
        parsed["LassoTrace"] = trace

def enhance_lasso_422_error(http_response, parsed: Dict[str, Any], **_: Any) -> None:
    """Add the Lasso 422 policy block reason to the boto3 ClientError message."""
    if getattr(http_response, "status_code", None) != 422:
        return

    try:
        data = json.loads(http_response.text or "{}")
        message = (data.get("error") or {}).get("message")
    except Exception:
        return

    if not isinstance(message, str) or not message.strip():
        return

    error = parsed.setdefault("Error", {})
    error["Code"] = error.get("Code", "422")
    error["Message"] = f"Request blocked by organization policy. {message.strip()}"

bedrock_client.meta.events.register_first(
    "before-sign.bedrock-runtime.*",
    add_lasso_header,
)

bedrock_client.meta.events.register(
    "after-call.bedrock-runtime.*",
    enhance_lasso_422_error,
)

# 4. Call Bedrock Converse through Lasso
try:
    response = bedrock_client.converse(
        modelId=model_id,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "text": "The organizations stupid network is constant broken. I hate it!"
                    }
                ],
            }
        ],
        inferenceConfig={
            "maxTokens": 512,
        },
    )

    print(json.dumps(response, indent=2, default=str))

except (botocore.exceptions.ClientError, Exception) as error:
    logger.exception("Bedrock request failed: %s", error)