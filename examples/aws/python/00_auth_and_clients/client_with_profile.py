"""
Simple AWS Bedrock Converse example through the Lasso proxy using an AWS profile.

Required environment variables:
  LASSO_PROXY_ENDPOINT
  LASSO_X_API_KEY
  AWS_PROFILE
  AWS_REGION            # optional, defaults to us-east-1
  BEDROCK_MODEL_ID
"""

import json
import logging
import os

import boto3
import botocore.exceptions
from botocore.config import Config
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


# 1. Load configuration
lasso_proxy_endpoint = os.getenv("LASSO_PROXY_ENDPOINT")
lasso_api_key = os.getenv("LASSO_X_API_KEY")

profile_name = os.getenv("AWS_PROFILE")
region = os.getenv("AWS_REGION", "us-east-1")

model_id = os.getenv("BEDROCK_TEXT_MODEL_ID")


# 2. Create a boto3 session using an AWS profile
session = boto3.Session(
    profile_name=profile_name,
    region_name=region,
)


# 3. Create Bedrock client from the profile session and point it to Lasso
bedrock_client = session.client(
    "bedrock-runtime",
    endpoint_url=lasso_proxy_endpoint,
    config=Config(
        retries={"max_attempts": 1, "mode": "standard"},
        connect_timeout=5,
        read_timeout=12,
        user_agent_extra="lasso-proxy-example/1.0",
    ),
    verify=False
)


# 4. Add the Lasso API key header to every Bedrock request
def add_lasso_header(request, **kwargs):
    request.headers.add_header("lasso-x-api-key", lasso_api_key)


bedrock_client.meta.events.register_first(
    "before-sign.bedrock-runtime.*",
    add_lasso_header,
)


# 5. Call Bedrock Converse through Lasso
try:
    response = bedrock_client.converse(
        modelId=model_id,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "text": "What is the ultimate answer to life, the universe, and everything?"
                    }
                ],
            }
        ],
        inferenceConfig={
            "maxTokens": 512,
        },
    )

    print(json.dumps(response, indent=2, default=str))

except botocore.exceptions.ClientError as error:
    logger.exception("Bedrock request failed: %s", error)