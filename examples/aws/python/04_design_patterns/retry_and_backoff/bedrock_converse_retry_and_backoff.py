"""
Send a text prompt to AWS Bedrock through the Lasso proxy using Converse,
with simple error handling, retries, and exponential backoff.

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


RETRYABLE_ERROR_CODES = {
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceUnavailableException",
    "InternalServerException",
    "RequestTimeout",
    "RequestTimeoutException",
    "ModelTimeoutException",
    "ModelNotReadyException",
}


def is_retryable_error(error: Exception) -> bool:
    if isinstance(error, botocore.exceptions.EndpointConnectionError):
        return True

    if isinstance(error, botocore.exceptions.ConnectTimeoutError):
        return True

    if isinstance(error, botocore.exceptions.ReadTimeoutError):
        return True

    if isinstance(error, botocore.exceptions.ClientError):
        error_code = error.response.get("Error", {}).get("Code", "")
        status_code = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)

        return error_code in RETRYABLE_ERROR_CODES or status_code in {429, 500, 502, 503, 504}

    return False


def sleep_with_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 10.0) -> None:
    delay = min(base_delay * (2 ** attempt), max_delay)
    jitter = random.uniform(0, delay * 0.25)
    time.sleep(delay + jitter)


def converse_with_retry(client, *, model_id: str, prompt: str, max_attempts: int = 3) -> str:
    last_error = None

    for attempt in range(max_attempts):
        try:
            response = client.converse(
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
                    "temperature": 0.5,
                },
            )

            return response["output"]["message"]["content"][0]["text"]

        except Exception as error:
            last_error = error
            is_last_attempt = attempt == max_attempts - 1

            if not is_retryable_error(error) or is_last_attempt:
                logger.exception("Bedrock request failed")
                raise

            logger.warning(
                "Bedrock request failed. Retrying attempt %s of %s. Error: %s",
                attempt + 2,
                max_attempts,
                error,
            )

            sleep_with_backoff(attempt)

    raise RuntimeError("Bedrock request failed") from last_error


# Load configuration
lasso_proxy_url = os.getenv("LASSO_PROXY_ENDPOINT")
lasso_api_key = os.getenv("LASSO_X_API_KEY")

region = os.getenv("AWS_REGION", "us-east-1")
access_key = os.getenv("AWS_ACCESS_KEY_ID")
secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
session_token = os.getenv("AWS_SESSION_TOKEN")

model_id = os.getenv("BEDROCK_TEXT_MODEL_ID")


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
    answer = converse_with_retry(
        client=bedrock_client,
        model_id=model_id,
        prompt="What is the ultimate answer to life, the universe, and everything?",
        max_attempts=3,
    )

    print(answer)

except botocore.exceptions.ClientError as error:
    error_code = error.response.get("Error", {}).get("Code", "Unknown")
    error_message = error.response.get("Error", {}).get("Message", str(error))
    status_code = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode", "Unknown")

    logger.error(
        "Bedrock request failed. Status: %s, Code: %s, Message: %s",
        status_code,
        error_code,
        error_message,
    )

except Exception as error:
    logger.error("Request failed: %s", error)