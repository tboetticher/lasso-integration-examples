"""
Send a text prompt to AWS Bedrock through the Lasso proxy using Converse,
with a simple circuit breaker.

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
import time
from enum import Enum

import boto3
import botocore.exceptions
import urllib3
from botocore.config import Config
from dotenv import load_dotenv


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    def before_request(self):
        if self.state == CircuitState.OPEN:
            elapsed = time.time() - self.last_failure_time

            if elapsed >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker moved to half-open")
            else:
                raise RuntimeError("Circuit breaker is open. Request blocked.")

    def record_success(self):
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning("Circuit breaker opened after repeated failures")


# Load configuration
lasso_proxy_url = os.getenv("LASSO_PROXY_ENDPOINT")
lasso_api_key = os.getenv("LASSO_X_API_KEY")
region = os.getenv("AWS_REGION", "us-east-1")
access_key = os.getenv("AWS_ACCESS_KEY_ID")
secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
session_token = os.getenv("AWS_SESSION_TOKEN")

model_id = os.getenv("BEDROCK_TEXT_MODEL_ID")


# Create a Bedrock client that routes requests through Lasso
# 2. Create Bedrock client that points to the Lasso proxy
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
        read_timeout=15,
        user_agent_extra="lasso-proxy-example/1.0",
    ),
    verify=False
)


# 3. Add the Lasso API key header to every Bedrock request
def add_lasso_header(request, **kwargs):
    request.headers.add_header("lasso-x-api-key", lasso_api_key)


bedrock_client.meta.events.register_first(
    "before-sign.bedrock-runtime.*",
    add_lasso_header,
)



# Create the circuit breaker
circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=30,
)


def converse_with_circuit_breaker(prompt: str) -> str:
    circuit_breaker.before_request()

    try:
        response = bedrock_client.converse(
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
            },
        )

        circuit_breaker.record_success()
        return response["output"]["message"]["content"][0]["text"]

    except botocore.exceptions.ClientError as error:
        circuit_breaker.record_failure()
        logger.exception("Bedrock request failed: %s", error)
        raise

    except Exception as error:
        circuit_breaker.record_failure()
        logger.exception("Unexpected request failure: %s", error)
        raise


try:
    answer = converse_with_circuit_breaker(
        "What is the ultimate answer to life, the universe, and everything?"
    )

    print(answer)

except (RuntimeError, Exception) as error:
    logger.error("Request skipped: %s", error)