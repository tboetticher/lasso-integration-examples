"""
Use single-tool calling with AWS Bedrock through the Lasso proxy using Converse,
with advanced error handling.

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
from typing import Any

import boto3
import botocore.exceptions
import urllib3
from botocore.config import Config
from dotenv import load_dotenv


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


class ToolError(Exception):
    """Raised when a tool cannot complete successfully."""


def get_order_status(order_id: str) -> dict[str, Any]:
    """
    Example application tool.

    In a real application, this could call a database, API, or internal service.
    """
    if not order_id:
        raise ToolError("order_id is required")

    orders = {
        "A123": {
            "order_id": "A123",
            "status": "shipped",
            "estimated_delivery": "2026-05-21",
        },
        "B456": {
            "order_id": "B456",
            "status": "processing",
            "estimated_delivery": "2026-05-24",
        },
    }

    if order_id not in orders:
        raise ToolError(f"Order {order_id} was not found")

    return orders[order_id]


def handle_tool_use(tool_use: dict[str, Any]) -> dict[str, Any]:
    """
    Validate and execute a model-requested tool call.
    """
    tool_name = tool_use.get("name")
    tool_input = tool_use.get("input") or {}

    if tool_name != "get_order_status":
        raise ToolError(f"Unsupported tool requested: {tool_name}")

    order_id = tool_input.get("order_id")

    if not isinstance(order_id, str):
        raise ToolError("order_id must be a string")

    return get_order_status(order_id=order_id)


def build_tool_result(tool_use: dict[str, Any]) -> dict[str, Any]:
    """
    Run the requested tool and return a Converse toolResult block.

    Tool errors are returned to the model with status='error'.
    This lets the model respond cleanly instead of ending the conversation
    with an application exception.
    """
    tool_use_id = tool_use["toolUseId"]

    try:
        result = handle_tool_use(tool_use)

        return {
            "toolResult": {
                "toolUseId": tool_use_id,
                "status": "success",
                "content": [
                    {
                        "json": result
                    }
                ],
            }
        }

    except ToolError as error:
        logger.warning("Tool failed: %s", error)

        return {
            "toolResult": {
                "toolUseId": tool_use_id,
                "status": "error",
                "content": [
                    {
                        "json": {
                            "error": str(error)
                        }
                    }
                ],
            }
        }

    except Exception as error:
        logger.exception("Unexpected tool failure")

        return {
            "toolResult": {
                "toolUseId": tool_use_id,
                "status": "error",
                "content": [
                    {
                        "json": {
                            "error": "The tool failed unexpectedly."
                        }
                    }
                ],
            }
        }


# Load configuration
lasso_proxy_endpoint = os.getenv("LASSO_PROXY_ENDPOINT")
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
                "description": "Get the current status and estimated delivery date for an order.",
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
        }
    ]
}


messages = [
    {
        "role": "user",
        "content": [
            {
                "text": "What is the status of order A999?"
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

    if response.get("stopReason") == "tool_use":
        tool_use = next(
            item["toolUse"]
            for item in assistant_message["content"]
            if "toolUse" in item
        )

        messages.append(
            {
                "role": "user",
                "content": [
                    build_tool_result(tool_use)
                ],
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

except StopIteration:
    logger.error("Model returned stopReason='tool_use' but no toolUse block was found")

except Exception as error:
    logger.exception("Unexpected application failure: %s", error)