"""
Send a text prompt to AWS Bedrock through the Lasso proxy using Converse,
with simple handling for throttling and service limit errors.

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
import random
import time

import boto3
import botocore.exceptions
import urllib3
from botocore.config import Config
from dotenv import load_dotenv


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


THROTTLE_ERROR_CODES = {
    "ThrottlingException",
    "TooManyRequestsException",
    "RequestLimitExceeded",
    "ServiceQuotaExceededException",
    "LimitExceededException",
    "ModelNotReadyException",
}


def is_throttle_or_limit_error(error: Exception) -> bool:
    if not isinstance(error, botocore.exceptions.ClientError):
        return False

    error_code = error.response.get("Error", {}).get("Code", "")
    status_code = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")

    return error_code in THROTTLE_ERROR_CODES or status_code == 429


def get_retry_after_seconds(error: botocore.exceptions.ClientError) -> float | None:
    headers = error.response.get("ResponseMetadata", {}).get("HTTPHeaders", {})
    retry_after = headers.get("retry-after")

    if retry_after is None:
        return None

    try:
        return float(retry_after)
    except ValueError:
        return None


def sleep_before_retry(error: Exception, attempt: int) -> None:
    if isinstance(error, botocore.exceptions.ClientError):
        retry_after = get_retry_after_seconds(error)

        if retry_after is not None:
            logger.info("Using retry-after header: %s seconds", retry_after)
            time.sleep(retry_after)
            return

    base_delay = 1
    max_delay = 20

    delay = min(base_delay * (2 ** attempt), max_delay)
    jitter = random.uniform(0, delay * 0.25)

    sleep_time = delay + jitter

    logger.info("Sleeping %.2f seconds before retry", sleep_time)
    time.sleep(sleep_time)


def converse_with_throttle_handling(
    client,
    *,
    model_id: str,
    prompt: str,
    max_attempts: int = 4,
) -> dict:
    for attempt in range(max_attempts):
        try:
            return client.converse(
                modelId=model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": prompt
                            }
                        ],
                    }
                ],
                inferenceConfig={
                    "maxTokens": 512,
                    "temperature": 0,
                },
            )

        except botocore.exceptions.ClientError as error:
            is_last_attempt = attempt == max_attempts - 1

            if not is_throttle_or_limit_error(error) or is_last_attempt:
                raise

            error_code = error.response.get("Error", {}).get("Code", "Unknown")
            status_code = error.response.get("ResponseMetadata", {}).get(
                "HTTPStatusCode",
                "Unknown",
            )

            logger.warning(
                "Request was throttled or limited. Status: %s, Code: %s, Attempt: %s of %s",
                status_code,
                error_code,
                attempt + 1,
                max_attempts,
            )

            sleep_before_retry(error, attempt)

    raise RuntimeError("Request failed after retry attempts")


# Load configuration
lasso_proxy_url = os.getenv("LASSO_PROXY_ENDPOINT")
lasso_api_key = os.getenv("LASSO_X_API_KEY")

region = os.getenv("AWS_REGION", "us-east-1")
access_key = os.getenv("AWS_ACCESS_KEY_ID")
secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
session_token = os.getenv("AWS_SESSION_TOKEN")

model_id = os.getenv("BEDROCK_MODEL_ID")


# Create a Bedrock client that routes requests through Lasso
bedrock_client = boto3.client(
    "bedrock-runtime",
    region_name=region,
    endpoint_url=f"{lasso_proxy_url}/v1/bedrock",
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    aws_session_token=session_token,
    config=Config(
        retries={"max_attempts": 1, "mode": "standard"},
        connect_timeout=5,
        read_timeout=12,
        user_agent_extra="lasso-proxy-example/1.0",
    ),
    verify=False,
)


# Add the Lasso API key to each request
def add_lasso_header(request, **kwargs):
    request.headers.add_header("lasso-x-api-key", lasso_api_key)


bedrock_client.meta.events.register_first(
    "before-sign.bedrock-runtime.*",
    add_lasso_header,
)


try:
    response = converse_with_throttle_handling(
        client=bedrock_client,
        model_id=model_id,
        prompt="What is the ultimate answer to life, the universe, and everything?",
        max_attempts=4,
    )

    print(response["output"]["message"]["content"][0]["text"])

except botocore.exceptions.ClientError as error:
    error_code = error.response.get("Error", {}).get("Code", "Unknown")
    error_message = error.response.get("Error", {}).get("Message", str(error))
    status_code = error.response.get("ResponseMetadata", {}).get(
        "HTTPStatusCode",
        "Unknown",
    )

    logger.error(
        "Bedrock request failed. Status: %s, Code: %s, Message: %s",
        status_code,
        error_code,
        error_message,
    )

except Exception as error:
    logger.exception("Unexpected request failure: %s", error)