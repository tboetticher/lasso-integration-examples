import os
from openai import OpenAI
from dotenv import load_dotenv
import logging
import json

# 0. Modify client to vet SSL verification to False
import httpx
http_client = httpx.Client(verify=False)

# 1. Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Load configuration
load_dotenv()

API_VERSION = "2024-02-01"
AZURE_API_KEY = os.getenv("AZURE_API_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
AZURE_DEPLOYMENT = os.getenv("AZURE_DEPLOYMENT")
LASSO_PROXY_URL = os.getenv("LASSO_PROXY_ENDPOINT")
LASSO_API_KEY = os.getenv("LASSO_X_API_KEY")
azure_service = f"{AZURE_ENDPOINT}/openai/deployments/{AZURE_DEPLOYMENT}"

# 3. Create Azure client that points to the Lasso proxy
client = OpenAI(
    base_url=f"{LASSO_PROXY_URL}/v1/azure",
    api_key=AZURE_API_KEY,  # Lasso uses lasso-x-api-key, not this field
    default_headers={
        "lasso-x-api-key": LASSO_API_KEY,
        "lasso-azure-service": azure_service,
        "api-key": AZURE_API_KEY,
    },
    http_client=http_client,
    default_query={"api-version": API_VERSION},
)

# 4. Call Azure Chat Completion through Lasso
try:
    response = client.chat.completions.create(
        model=AZURE_DEPLOYMENT,
        messages=[{"role": "user", "content": "In a single word, what is the answer to the great question of life, the universe and everything?"}],
    )
    print (response.choices[0].message.content)

except Exception as e:
    logging.error(e)