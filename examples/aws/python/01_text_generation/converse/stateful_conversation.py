"""
Simple AWS Bedrock Converse stateful conversation example through the Lasso proxy.

This example keeps conversation state in memory by storing each user and
assistant message in a local messages list.

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
import urllib3

import boto3
import botocore.exceptions
from botocore.config import Config
from dotenv import load_dotenv


# Silence TLS warnings if using verify=False in a local/dev environment.
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
        read_timeout=12,
        user_agent_extra="lasso-proxy-example/1.0",
    ),
    verify=False,
)


# 3. Add the Lasso API key header to every Bedrock request
def add_lasso_header(request, **kwargs):
    request.headers.add_header("lasso-x-api-key", lasso_api_key)


bedrock_client.meta.events.register_first(
    "before-sign.bedrock-runtime.*",
    add_lasso_header,
)


# 4. Store conversation state in memory
messages = []


def send_message(user_text):
    """
    Add a user message to the conversation, send the full message history
    to Bedrock, then save the assistant response back to the conversation.
    """
    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "text": user_text,
                }
            ],
        }
    )

    response = bedrock_client.converse(
        modelId=model_id,
        messages=messages,
        inferenceConfig={
            "maxTokens": 512,
        },
    )

    assistant_message = response["output"]["message"]
    messages.append(assistant_message)

    return assistant_message


# 5. Run a simple stateful conversation
try:
    first_reply = send_message(
        "My name is Lasso and I am learning how to use AWS Bedrock through Lasso."
    )

    print("\nAssistant response 1:")
    print(json.dumps(first_reply, indent=2, default=str))

    second_reply = send_message(
        "What is my name and what am I learning?"
    )

    print("\nAssistant response 2:")
    print(json.dumps(second_reply, indent=2, default=str))

    third_reply = send_message(
        "Explain it back to me in one short sentence."
    )

    print("\nAssistant response 3:")
    print(json.dumps(third_reply, indent=2, default=str))

except botocore.exceptions.ClientError as error:
    logger.exception("Bedrock request failed: %s", error)