# 00_auth_and_clients

This folder shows different ways to create a Ruby AWS Bedrock Runtime client that talks to AWS Bedrock **through the Lasso Proxy**.

All examples:

- Use the AWS SDK for Ruby to create an `Aws::BedrockRuntime::Client`
- Point the client at `LASSO_PROXY_ENDPOINT`
- Add `/v1/bedrock` to the Lasso proxy base URL
- Automatically inject the `lasso-x-api-key` header on each request
- Include a simple `converse` smoke test

Use these examples to decide **how you want to provide AWS credentials** and **how you want to structure Bedrock client creation** in your own Ruby code.

---

## Prerequisites

1. Ruby dependencies

   From this folder:

   ```bash
   bundle install
   ```

   The `Gemfile` includes:

   - `aws-sdk-bedrockruntime`
   - `aws-sdk-sts`
   - `dotenv`

2. Environment variables

   Each example loads the shared examples `.env` file:

   ```text
   examples/.env
   ```

   Required for all examples:

   - `LASSO_PROXY_ENDPOINT` - Lasso proxy base URL, without `/v1/bedrock`
     Example: `https://your-lasso-host.example.com`
   - `LASSO_X_API_KEY` - Lasso API key value
   - `AWS_REGION` - AWS region, default: `us-east-1`
   - `BEDROCK_TEXT_MODEL_ID` - Bedrock text model ID for the `converse` smoke test
     Example: `anthropic.claude-3-5-sonnet-20241022-v2:0`

   Credentials are provided differently by each example: static environment credentials, AWS profile credentials, explicit Ruby credentials objects, or STS AssumeRole.

   Optional for local testing:

   - `DISABLE_SSL_VERIFICATION=true` - disables TLS certificate validation for local testing only

---

## How Lasso Header Injection Works

Each example defines a small AWS SDK plugin:

```ruby
class LassoHeaderPlugin < Seahorse::Client::Plugin
  option(:lasso_api_key)

  class Handler < Seahorse::Client::Handler
    def call(context)
      context.http_request.headers['lasso-x-api-key'] =
        context.config.lasso_api_key

      @handler.call(context)
    end
  end

  handler(Handler, step: :build)
end
```

The AWS SDK still signs the Bedrock request with AWS credentials. The plugin only adds the Lasso API key header before the request is sent through the proxy.

---

## Examples

### 1. `client_default_credentials.rb`

**What it shows**

- Creates an `Aws::BedrockRuntime::Client` directly.
- Uses AWS credentials from environment variables:
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - `AWS_SESSION_TOKEN` (optional)
- Configures the client endpoint as:

   ```text
   {LASSO_PROXY_ENDPOINT}/v1/bedrock
   ```

- Adds the Lasso API key header with an AWS SDK plugin.
- Sends a simple `converse` request and prints the HTTP status code and answer text.

**How to run**

```bash
ruby client_default_credentials.rb
```

You must provide AWS access key credentials in the environment or repo-level `.env`.

---

### 2. `client_with_profile.rb`

**What it shows**

- Uses an AWS named profile.
- Loads credentials from `~/.aws/credentials` and `~/.aws/config`.
- Keeps AWS keys out of the example code and `.env`.
- Builds the Bedrock Runtime client through Lasso using the selected profile.

**Key environment variables**

- `AWS_PROFILE` - profile name to load
- `AWS_REGION` - AWS region, default: `us-east-1`

**How to run**

```bash
ruby client_with_profile.rb
```

You must have a valid AWS profile configured locally with permission to invoke the selected Bedrock model.

---

### 3. `client_with_custom_session.rb`

**What it shows**

- Creates an explicit `Aws::Credentials` object.
- Passes that credentials object to a Bedrock Runtime client.
- Keeps credential construction separate from client construction.
- Good when credentials are resolved dynamically before creating the client.

**Key environment variables**

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN` (optional)

**How to run**

```bash
ruby client_with_custom_session.rb
```

If everything is configured properly, you'll see the HTTP status code and a short response from the model, confirming that the custom credentials can invoke Bedrock through Lasso.

---

### 4. `client_with_sts_role.rb`

**What it shows**

- Uses local/source AWS credentials to call STS `AssumeRole`.
- Creates temporary role credentials from the STS response.
- Uses those temporary credentials to create the Bedrock Runtime client.
- Supports `AWS_EXTERNAL_ID` when the target role trust policy requires it.
- Good when Bedrock access is centralized behind a dedicated IAM role.

**Key environment variables**

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN` (optional)
- `AWS_ROLE_ARN` - role to assume
- `AWS_ROLE_SESSION_NAME` (optional) - defaults to `lasso-ruby-bedrock-example`
- `AWS_EXTERNAL_ID` (optional) - external ID for role trust policies

**How to run**

```bash
ruby client_with_sts_role.rb
```

If everything is configured properly, you'll see a short response from the model, confirming that:

- STS assumed the role successfully.
- The Bedrock Runtime client can invoke Bedrock through Lasso using the role's temporary credentials.

---

## When to use which pattern

- **`client_default_credentials.rb`**
  Use when:
  - You want the simplest Ruby example using explicit environment credentials.
  - You are running a local smoke test.
  - You are comfortable providing `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` through the environment.

- **`client_with_profile.rb`**
  Use when:
  - You develop locally and switch between named AWS profiles.
  - Your team works across multiple AWS accounts.
  - You do not want to put AWS access keys in `.env`.

- **`client_with_custom_session.rb`**
  Use when:
  - Your application resolves credentials before constructing the Bedrock client.
  - You want explicit control over the `Aws::Credentials` object.
  - You need to pass temporary credentials into one specific client.

- **`client_with_sts_role.rb`**
  Use when:
  - You want to centralize Bedrock access behind a specific IAM role.
  - You need separation between the caller identity and the Bedrock-invoking identity.
  - You need support for cross-account role assumption or an external ID trust pattern.

---

## Production Notes

- Do not disable TLS verification in production.
- Prefer managed or short-lived AWS credentials over long-lived static access keys.
- Keep Bedrock traffic routed through Lasso when Lasso is required for policy enforcement, inspection, reporting, or audit.
- Avoid logging prompts or model outputs unless the application is approved to store that data.
