"""
Simple AWS Bedrock Converse example through the Lasso proxy.

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


bedrock_client.meta.events.register_first(
    "before-sign.bedrock-runtime.*",
    add_lasso_header,
)

native_request = {
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 512,
    "temperature": 0.5,
    "messages": [
        {
            "role": "user",
            "content": [{"type": "text", "text": "What is the ultimate answer to life, the universe, and everything?"}],
        }
    ],
}

request = json.dumps(native_request)

# 4. Call Bedrock Converse through Lasso
try:

    streaming_response = bedrock_client.invoke_model_with_response_stream(
        modelId=model_id,
        body=request
    )

    for event in streaming_response["body"]:
        chunk = json.loads(event["chunk"]["bytes"])
        if chunk["type"] == "content_block_delta":
            print(chunk["delta"].get("text", ""), end="")

except (botocore.exceptions.ClientError, Exception) as error:
    logger.exception("Bedrock request failed: %s", error)