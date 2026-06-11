# 00_auth_and_clients

This folder shows different ways to create a Bedrock Runtime client that talks to AWS Bedrock **through the Lasso Proxy**.

All examples:

- Use `boto3` to create a `bedrock-runtime` client
- Point the client at `LASSO_PROXY_ENDPOINT`
- Automatically inject the `lasso-x-api-key` header on each request
- Include a simple `converse` smoke test

Use these examples to decide **how you want to provide AWS credentials** and **how to structure client creation** in your own code.

---

## Prerequisites

1. Python dependencies (from repo root or examples root):

   ```bash
   pip install -r requirements.txt
   ```

   or at minimum:
   ```bash
   pip install boto3 botocore python-dotenv urllib3
   ```

2. Environment variables (or `.env` in this folder):

   Required for all examples:

   - `LASSO_PROXY_ENDPOINT` – Lasso proxy URL, including `/v1/bedrock`  
     Example: `https://your-lasso-host.example.com/v1/bedrock`
   - `LASSO_X_API_KEY` – Lasso API key value
   - `AWS_REGION` – AWS region (default: `us-east-1`)
   - `BEDROCK_MODEL_ID` – Bedrock model ID for testing `converse`  
     Example: `anthropic.claude-3-5-sonnet-20241022-v2:0`

   Credentials will be provided differently by each example (default chain, profile, STS).

---

## Examples

### 1. `client_default_credentials.py`

**What it shows**

- Uses the **default AWS credential chain**:
  - Environment variables
  - `~/.aws/credentials` and `~/.aws/config`
  - IAM role on EC2 / containers, etc.
- No explicit keys in code.
- Configures the Lasso Proxy endpoint and header once, then sends a simple `converse` request.

**How to run**

```bash
python client_default_credentials.py
```
You must have valid AWS credentials resolvable by the default Boto3 chain.

---
### 2. `client_with_custom_session.py`

**What it shows**

- Creates an explicit `boto3.Session` with optional:
  - `AWS_PROFILE` (e.g., `dev`, `prod`)
  - `AWS_REGION`
- Builds the Bedrock client from that Session.
- Good when you want to reuse a Session across multiple clients or customize Session creation.

**Key environment variables**

- `AWS_PROFILE` (optional) – Which profile to use from `~/.aws/credentials`
- `AWS_REGION` – Region for the Session

**How to run**

```bash
python client_with_custom_session.py
```

If everything is configured properly, you’ll see a short response from the model, confirming that:

- STS assumed the role successfully.
- The client can invoke Bedrock through Lasso using that role’s credentials.

---

## When to use which pattern

- **`client_default_credentials.py`**  
  Use when:
  - You’re running in an environment with well-configured IAM roles or env-based credentials.
  - You want minimal configuration in code.

- **`client_with_profile.py`**  
  Use when:
  - You develop locally and want to explicitly switch between named profiles.
  - Your team uses multiple AWS accounts and you need to pick one each time.

- **`client_with_custom_session.py`**  
  Use when:
  - You want fine-grained control over the Session (e.g., pass it to multiple modules).
  - You need to support dynamic profile/region selection at runtime.

- **`client_with_sts_role.py`**  
  Use when:
  - You want to centralize Bedrock access behind a specific IAM role.
  - You need a clear separation between the caller identity and the Bedrock-invoking identity.