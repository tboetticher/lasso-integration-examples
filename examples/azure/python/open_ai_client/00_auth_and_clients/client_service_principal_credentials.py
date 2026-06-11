import os
from openai.lib.azure import AzureOpenAI, AsyncAzureOpenAI, AzureADTokenProvider, AsyncAzureADTokenProvider
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
import logging

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
LASSO_API_KEY = os.getenv("LASSO_X_API_KEY")+"/v1/azure/chat/completions?api-version={apiVersion}"
azure_service = os.getenv("AZURE_ENDPOINT")
TOKEN_PROVIDER = os.getenv("TOKEN_PROVIDER")

token_provider: AzureADTokenProvider = get_bearer_token_provider(DefaultAzureCredential(), TOKEN_PROVIDER)

# 3. Create Azure client that points to the Lasso proxy

client = AzureOpenAI(
    api_version=API_VERSION,
    azure_endpoint=AZURE_ENDPOINT,
    azure_ad_token_provider=token_provider,
    default_headers={
            "lasso-x-api-key": LASSO_API_KEY,
            "lasso-azure-service": azure_service,
            "azure_ad_token_provider": token_provider,
        },
)

# 4. Call Azure Chat Completion through Lasso
try:
    response = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": "What is the answer to the great question of life, the universe and everything?",
            }
        ],
        temperature=1.0,
        model=AZURE_DEPLOYMENT
    )

    print (response.choices[0].message.content)

except Exception as e:
    logging.error(e)