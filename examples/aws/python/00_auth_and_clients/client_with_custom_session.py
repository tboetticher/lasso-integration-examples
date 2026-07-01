"""
Simple AWS Bedrock Converse example through the Lasso proxy using a custom boto3 session.

Required environment variables:
  LASSO_PROXY_ENDPOINT
  LASSO_X_API_KEY
  AWS_REGION
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  AWS_SESSION_TOKEN      # optional
  BEDROCK_MODEL_ID
"""

import json
import logging
import os
import boto3
import botocore.exceptions
from botocore.config import Config
from dotenv import load_dotenv
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


# 1. Load configuration
lasso_proxy_url = os.getenv("LASSO_PROXY_ENDPOINT")
lasso_api_key = os.getenv("LASSO_X_API_KEY")

region = os.getenv("AWS_REGION", "us-east-1")
access_key = os.getenv("AWS_ACCESS_KEY_ID")
secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
session_token = os.getenv("AWS_SESSION_TOKEN")

model_id = os.getenv("BEDROCK_TEXT_MODEL_ID")


# 2. Create a custom boto3 session
session = boto3.Session(
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    aws_session_token=session_token,
    region_name=region,
)


# 3. Create Bedrock client from the custom session and point it to Lasso
bedrock_client = session.client(
    "bedrock-runtime",
    endpoint_url=f"{lasso_proxy_url}/v1/bedrock",
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