"""
Use multiple tools with AWS Bedrock through the Lasso proxy using Converse.

Required environment variables:
  LASSO_PROXY_ENDPOINT
  LASSO_X_API_KEY
  AWS_REGION
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  AWS_SESSION_TOKEN          # optional
  BEDROCK_MODEL_ID           # must support tool use
"""

import json
import logging
import os

import boto3
import botocore.exceptions
import urllib3
from botocore.config import Config
from dotenv import load_dotenv


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


def get_order_status(order_id: str) -> dict:
    orders = {
        "A123": {
            "order_id": "A123",
            "status": "shipped",
            "estimated_delivery": "2026-05-21",
            "customer_id": "C100",
        },
        "B456": {
            "order_id": "B456",
            "status": "processing",
            "estimated_delivery": "2026-05-24",
            "customer_id": "C200",
        },
    }

    return orders.get(
        order_id,
        {
            "order_id": order_id,
            "status": "not_found",
        },
    )


def get_customer_profile(customer_id: str) -> dict:
    customers = {
        "C100": {
            "customer_id": "C100",
            "name": "Jane Doe",
            "membership": "gold",
            "preferred_contact": "email",
        },
        "C200": {
            "customer_id": "C200",
            "name": "John Smith",
            "membership": "standard",
            "preferred_contact": "sms",
        },
    }

    return customers.get(
        customer_id,
        {
            "customer_id": customer_id,
            "status": "not_found",
        },
    )


def handle_tool_use(tool_use: dict) -> dict:
    tool_name = tool_use["name"]
    tool_input = tool_use["input"]

    if tool_name == "get_order_status":
        return get_order_status(order_id=tool_input["order_id"])

    if tool_name == "get_customer_profile":
        return get_customer_profile(customer_id=tool_input["customer_id"])

    raise ValueError(f"Unknown tool requested: {tool_name}")


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


tool_config = {
    "tools": [
        {
            "toolSpec": {
                "name": "get_order_status",
                "description": "Get the current status, delivery date, and customer ID for an order.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "order_id": {
                                "type": "string",
                                "description": "The order ID to look up.",
                            }
                        },
                        "required": ["order_id"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "get_customer_profile",
                "description": "Get basic customer details for a customer ID.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "customer_id": {
                                "type": "string",
                                "description": "The customer ID to look up.",
                            }
                        },
                        "required": ["customer_id"],
                    }
                },
            }
        },
    ]
}


messages = [
    {
        "role": "user",
        "content": [
            {
                "text": (
                    "What is the status of order A123, and what is the "
                    "customer's membership level?"
                )
            }
        ],
    }
]


try:
    response = bedrock_client.converse(
        modelId=model_id,
        messages=messages,
        toolConfig=tool_config,
        inferenceConfig={
            "maxTokens": 512,
            "temperature": 0,
        },
    )

    assistant_message = response["output"]["message"]
    messages.append(assistant_message)

    while response.get("stopReason") == "tool_use":
        tool_results = []

        for content_item in assistant_message["content"]:
            if "toolUse" not in content_item:
                continue

            tool_use = content_item["toolUse"]
            tool_result = handle_tool_use(tool_use)

            tool_results.append(
                {
                    "toolResult": {
                        "toolUseId": tool_use["toolUseId"],
                        "content": [
                            {
                                "json": tool_result
                            }
                        ],
                    }
                }
            )

        messages.append(
            {
                "role": "user",
                "content": tool_results,
            }
        )

        response = bedrock_client.converse(
            modelId=model_id,
            messages=messages,
            toolConfig=tool_config,
            inferenceConfig={
                "maxTokens": 512,
                "temperature": 0,
            },
        )

        assistant_message = response["output"]["message"]
        messages.append(assistant_message)

    print(response["output"]["message"]["content"][0]["text"])

except ( botocore.exceptions.ClientError, Exception) as error:
    logger.exception("Bedrock request failed: %s", error)