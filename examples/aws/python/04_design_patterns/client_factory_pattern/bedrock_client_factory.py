"""
Create an AWS Bedrock Runtime client that can route through the Lasso proxy.

Supported authentication options:
  1. Default AWS credential chain
  2. AWS profile
  3. Static AWS credentials
  4. STS assume role
  5. Optional Lasso API key
  6. Optional Basic Auth header

Environment variables:
  AWS_REGION
  AWS_PROFILE
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  AWS_SESSION_TOKEN          # optional

  ROLE_ARN                   # optional
  LASSO_PROXY_ENDPOINT       # optional
  LASSO_X_API_KEY            # optional

  LASSO_BASIC_AUTH_USERNAME  # optional
  LASSO_BASIC_AUTH_PASSWORD  # optional

  BEDROCK_MODEL_ID
"""

import base64
import json
import logging
import os
from typing import Optional

import boto3
import botocore.exceptions
import urllib3
from botocore.config import Config
from dotenv import load_dotenv


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


class BedrockClientFactory:
    @staticmethod
    def create(
        *,
        region: Optional[str] = None,
        aws_profile: Optional[str] = None,
        role_arn: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        lasso_api_key: Optional[str] = None,
        basic_auth_username: Optional[str] = None,
        basic_auth_password: Optional[str] = None,
        verify_ssl: bool = False,
        config: Optional[Config] = None,
    ):
        region = region or os.getenv("AWS_REGION", "us-east-1")
        aws_profile = aws_profile or os.getenv("AWS_PROFILE")
        role_arn = role_arn or os.getenv("ROLE_ARN")

        endpoint_url = endpoint_url or os.getenv("LASSO_PROXY_ENDPOINT")
        lasso_api_key = lasso_api_key or os.getenv("LASSO_X_API_KEY")

        basic_auth_username = basic_auth_username or os.getenv("LASSO_BASIC_AUTH_USERNAME")
        basic_auth_password = basic_auth_password or os.getenv("LASSO_BASIC_AUTH_PASSWORD")

        session = boto3.Session(
            profile_name=aws_profile,
            region_name=region,
        )

        credentials = None

        if role_arn:
            credentials = BedrockClientFactory._assume_role(
                session=session,
                role_arn=role_arn,
            )

        client_kwargs = {
            "service_name": "bedrock-runtime",
            "region_name": region,
            "endpoint_url": endpoint_url,
            "verify": verify_ssl,
            "config": config or Config(
                signature_version="v4",
                retries={"max_attempts": 1, "mode": "standard"},
                connect_timeout=5,
                read_timeout=12,
                user_agent_extra="lasso-proxy-example/1.0",
            ),
        }

        if credentials:
            client_kwargs.update(credentials)

        client = session.client(**client_kwargs)

        BedrockClientFactory._add_headers(
            client=client,
            lasso_api_key=lasso_api_key,
            basic_auth_username=basic_auth_username,
            basic_auth_password=basic_auth_password,
        )

        return client

    @staticmethod
    def _assume_role(*, session: boto3.Session, role_arn: str) -> dict:
        try:
            response = session.client("sts").assume_role(
                RoleArn=role_arn,
                RoleSessionName="bedrock-client-session",
            )

            credentials = response["Credentials"]

            return {
                "aws_access_key_id": credentials["AccessKeyId"],
                "aws_secret_access_key": credentials["SecretAccessKey"],
                "aws_session_token": credentials["SessionToken"],
            }

        except botocore.exceptions.ClientError as error:
            error_code = error.response.get("Error", {}).get("Code", "Unknown")
            error_message = error.response.get("Error", {}).get("Message", str(error))

            raise RuntimeError(
                f"Failed to assume role {role_arn}: {error_code} - {error_message}"
            ) from error

    @staticmethod
    def _add_headers(
        *,
        client,
        lasso_api_key: Optional[str],
        basic_auth_username: Optional[str],
        basic_auth_password: Optional[str],
    ) -> None:
        basic_auth_value = None

        if basic_auth_username and basic_auth_password:
            token = f"{basic_auth_username}:{basic_auth_password}".encode("utf-8")
            basic_auth_value = "Basic " + base64.b64encode(token).decode("utf-8")

        def add_headers(request, **kwargs):
            if lasso_api_key:
                request.headers.add_header("lasso-x-api-key", lasso_api_key)

            if basic_auth_value:
                request.headers.add_header("Authorization", basic_auth_value)

        client.meta.events.register_first(
            "before-sign.bedrock-runtime.*",
            add_headers,
        )

client = BedrockClientFactory.create()

response = client.converse(
    modelId=os.getenv("BEDROCK_TEXT_MODEL_ID"),
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "text": "Respond with Yes."
                }
            ],
        }
    ],
    inferenceConfig={
        "maxTokens": 10,
    },
)

print(json.dumps(response, indent=2, default=str))