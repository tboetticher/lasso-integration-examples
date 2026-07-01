"""
Send a text document to AWS Bedrock through the Lasso proxy.

Required environment variables:
  LASSO_PROXY_ENDPOINT
  LASSO_X_API_KEY
  AWS_REGION
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  AWS_SESSION_TOKEN          # optional
  BEDROCK_MODEL_ID           # must support document input
"""

import json
import logging
import os
from pathlib import Path

import boto3
import botocore.exceptions
import urllib3
from botocore.config import Config
from dotenv import load_dotenv


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


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


# Load the text document
document_path = Path("assets/lasso.txt")
document_text = document_path.read_text(encoding="utf-8")


# Build the native Anthropic request body for Bedrock InvokeModel
request_body = {
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 512,
    "temperature": 0.5,
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "text",
                        "media_type": "text/plain",
                        "data": document_text,
                    },
                    "title": document_path.name,
                },
                {
                    "type": "text",
                    "text": "Summarize this document in three bullets.",
                },
            ],
        }
    ],
}


# Send the request through Lasso
try:
    response = bedrock_client.invoke_model(
        modelId=model_id,
        body=json.dumps(request_body),
        contentType="application/json",
        accept="application/json",
    )

    response_body = json.loads(response["body"].read())
    print(response_body["content"][0]["text"])

except (botocore.exceptions.ClientError, Exception) as error:
    logger.exception("Bedrock request failed: %s", error)