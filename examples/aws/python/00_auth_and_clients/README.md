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

2. Environment variables

   Local examples use the shared `examples/.env` file. Create it from the
   repository root and keep it out of source control:

   ```bash
   touch examples/.env
   ```

   The Python examples call `load_dotenv()` and discover this file while
   searching parent directories.

   Required for all examples:

   - `LASSO_PROXY_ENDPOINT` – Lasso proxy URL, including `/v1/bedrock`

     Example: `https://your-lasso-host.example.com/v1/bedrock`
   - `LASSO_X_API_KEY` – Lasso API key value
   - `AWS_REGION` – AWS region (default: `us-east-1`)
   - `BEDROCK_TEXT_MODEL_ID` – Bedrock model ID for testing `converse`

     Example: `anthropic.claude-3-5-sonnet-20241022-v2:0`

   Credentials will be provided differently by each example (default chain, profile, STS).

   Do not commit Lasso API keys, AWS credentials, or session tokens.

---

## Examples

### 1. `client_default_credentials.py`

**What it shows**

- Reads `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and optional
  `AWS_SESSION_TOKEN` from the environment.
- Passes those values directly to the Bedrock Runtime client.
- Configures the Lasso Proxy endpoint and header once, then sends a simple `converse` request.

**How to run**

```bash
python client_default_credentials.py
```
You must define valid AWS environment credentials in `examples/.env` or the
process environment.

---
### 2. `client_with_custom_session.py`

**What it shows**

- Creates an explicit `boto3.Session` from `AWS_ACCESS_KEY_ID`,
  `AWS_SECRET_ACCESS_KEY`, optional `AWS_SESSION_TOKEN`, and `AWS_REGION`.
- Builds the Bedrock client from that Session.
- Good when you want to reuse an explicitly configured Session across multiple clients.

**Key environment variables**

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN` (optional)
- `AWS_REGION`

**How to run**

```bash
python client_with_custom_session.py
```

If everything is configured properly, you will see a short response from the
model, confirming that the custom Session can invoke Bedrock through Lasso.

---

### 3. `client_with_profile.py`

**What it shows**

- Creates a `boto3.Session` using `AWS_PROFILE`.
- Loads credentials from the standard AWS shared configuration files.
- Uses `AWS_REGION`, defaulting to `us-east-1`.

**How to run**

```bash
python client_with_profile.py
```

---

### 4. `client_with_sts_role.py`

**What it shows**

- Uses credentials available to the standard Boto3 credential chain to call
  AWS STS.
- Assumes `AWS_ROLE_ARN`.
- Creates a Bedrock Runtime client with temporary role credentials.

**Key environment variables**

- `AWS_ROLE_ARN`
- `AWS_ROLE_SESSION_NAME` (optional)
- `AWS_REGION`

**How to run**

```bash
python client_with_sts_role.py
```

---

## When to use which pattern

- **`client_default_credentials.py`**

  Use when:
  - You are testing with AWS credentials supplied through environment variables.
  - You want the most direct client-construction example.

- **`client_with_profile.py`**

  Use when:
  - You develop locally and want to explicitly switch between named profiles.
  - Your team uses multiple AWS accounts and you need to pick one each time.

- **`client_with_custom_session.py`**

  Use when:
  - You want to construct and reuse a Session from explicit environment credentials.
  - You need to pass the configured Session to multiple modules.

- **`client_with_sts_role.py`**

  Use when:
  - You want to centralize Bedrock access behind a specific IAM role.
  - You need a clear separation between the caller identity and the Bedrock-invoking identity.

---

## TLS verification

The current examples set `verify=False` and are intended for controlled local
testing. Production clients must validate TLS certificates using the
organization-approved trust store.
