"""
Simple AWS Bedrock Converse example through the Lasso proxy using an STS assumed role.

Required environment variables:
  LASSO_PROXY_ENDPOINT
  LASSO_X_API_KEY
  AWS_REGION
  AWS_ROLE_ARN
  AWS_ROLE_SESSION_NAME  # optional, defaults to lasso-bedrock-example
  BEDROCK_MODEL_ID

AWS credentials must already be available through one of the standard boto3
credential sources, such as:
  - AWS profile
  - environment variables
  - EC2 instance role
  - ECS task role
  - EKS pod identity / IRSA
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
lasso_proxy_url = os.getenv("LASSO_PROXY_ENDPOINT")
lasso_api_key = os.getenv("LASSO_X_API_KEY")

region = os.getenv("AWS_REGION", "us-east-1")
role_arn = os.getenv("AWS_ROLE_ARN")
role_session_name = os.getenv("AWS_ROLE_SESSION_NAME", "lasso-bedrock-example")

model_id = os.getenv("BEDROCK_TEXT_MODEL_ID")


# 2. Assume the AWS role with STS
sts_client = boto3.client("sts", region_name=region)

assumed_role = sts_client.assume_role(
    RoleArn=role_arn,
    RoleSessionName=role_session_name,
)

credentials = assumed_role["Credentials"]


# 3. Create Bedrock client with the temporary role credentials and point it to Lasso
bedrock_client = boto3.client(
    "bedrock-runtime",
    region_name=region,
    endpoint_url=f"{lasso_proxy_url}/v1/bedrock",
    aws_access_key_id=credentials["AccessKeyId"],
    aws_secret_access_key=credentials["SecretAccessKey"],
    aws_session_token=credentials["SessionToken"],
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