# AWS Python Examples

This section provides Python examples for integrating AWS Bedrock with the **Lasso Proxy** using `boto3` and `botocore`.

The examples are organized as an enterprise adoption path: start with client construction and credential strategy, move into core Bedrock workloads, then layer in reliability, observability, and troubleshooting patterns that application teams need before production rollout.

At a high level, these examples show how to:

- Route Bedrock Runtime traffic through `LASSO_PROXY_ENDPOINT`
- Authenticate to Lasso with the `lasso-x-api-key` request header
- Continue using standard AWS credential mechanisms for Bedrock authorization
- Exercise Bedrock APIs such as `converse`, `converse_stream`, `invoke_model`, and streaming invoke calls
- Build text generation, embeddings, and multimodal workflows
- Add production resilience patterns such as retries, backoff, jitter, circuit breakers, and reusable client factories
- Capture and explain Lasso proxy errors, including policy enforcement responses

---

## Prerequisites

Install dependencies from this directory:

```bash
cd examples/aws/python
pip install -r requirements.txt
```

The examples use:

- `boto3`
- `botocore`
- `python-dotenv`
- `urllib3`

Most examples read configuration from environment variables or a local `.env` file.

Common variables:

- `LASSO_PROXY_ENDPOINT` - Lasso proxy URL, typically including `/v1/bedrock`
- `LASSO_X_API_KEY` - Lasso API key
- `AWS_REGION` - AWS region, defaulting to `us-east-1` in many examples
- `AWS_ACCESS_KEY_ID` - AWS access key, when using environment credentials
- `AWS_SECRET_ACCESS_KEY` - AWS secret key, when using environment credentials
- `AWS_SESSION_TOKEN` - optional AWS session token
- `AWS_PROFILE` - AWS profile name, when using profile-based credentials
- `AWS_ROLE_ARN` - role ARN, when using STS assume-role examples
- `BEDROCK_TEXT_MODEL_ID` - text-capable Bedrock model ID
- `BEDROCK_EMBEDDING_MODEL_ID` - embedding model ID
- `BEDROCK_MODEL_ID` - general Bedrock model ID used by some examples

For production deployments, prefer managed credentials such as IAM roles for compute, ECS task roles, EKS pod identity or IRSA, or a controlled STS assume-role flow. Static keys are useful for local smoke tests, but should not become the enterprise default.

---

## Architecture Pattern

The common integration pattern is:

1. Build a `bedrock-runtime` client with `boto3`.
2. Set `endpoint_url` to `LASSO_PROXY_ENDPOINT`.
3. Register a botocore event hook that injects `lasso-x-api-key` before signing each Bedrock Runtime request.
4. Let AWS credentials continue to come from the chosen AWS credential source.
5. Send normal Bedrock Runtime calls through the client.

This keeps application code close to standard Bedrock usage while ensuring traffic flows through Lasso for policy enforcement, inspection, reporting, and audit.

Most examples use conservative `botocore.config.Config` values:

```python
Config(
    retries={"max_attempts": 1, "mode": "standard"},
    connect_timeout=5,
    read_timeout=12,
    user_agent_extra="lasso-proxy-example/1.0",
)
```

The design-pattern examples then show how to make retry behavior explicit at the application layer so teams can tune it by workload.

---

## Directory Guide

### `00_auth_and_clients`

Use this section first. It explains the supported ways to construct Bedrock clients that route through Lasso.

It includes examples for:

- Default AWS credential chain
- Explicit `boto3.Session`
- Named AWS profiles
- STS assume-role credentials

This section is the foundation for enterprise teams because credential strategy usually differs by environment:

- Local development may use named profiles.
- CI may use short-lived credentials.
- Cloud runtime workloads should use IAM roles or pod/task identity.
- Cross-account Bedrock access may require STS assume role.

### `01_text_generation`

This section covers text generation workflows through Lasso.

It includes examples for:

- Quickstart `converse`
- Quickstart `invoke_model`
- Simple and multi-turn conversations
- Stateful conversation history
- Streaming responses with `converse_stream`
- Native model invocation
- JSON-oriented generation patterns
- Tool-use examples, including multi-tool routing and tool error handling
- Prompt caching examples

Some job-oriented files are currently marked `Not Currently Supported`. Treat those as placeholders for future batch invocation coverage.

### `02_embeddings`

This section covers embedding workflows through Bedrock and Lasso.

It includes examples for:

- Single-text embedding requests
- Embedding requests with metadata
- Batch embedding patterns
- Embedding cache concepts
- Embedding quality troubleshooting concepts

Embedding request and response schemas are model-specific. The examples intentionally show reusable integration patterns, but production teams should align request bodies and vector extraction logic with the selected Bedrock embedding model documentation.

Some embedding job examples are currently marked `Not Currently Supported`.

### `03_multimodal`

This section covers text-plus-media interactions through Lasso.

It includes examples for:

- Simple multimodal `converse`
- Image chat
- Document chat
- Text-plus-image `invoke_model`
- Text-plus-document `invoke_model`
- Multimodal prompt caching concepts

Multimodal payloads are highly model-specific. Teams should verify supported media types, size limits, content block shapes, and encoding requirements for the selected Bedrock model before promoting an example into production code.

### `04_design_patterns`

This section contains production-readiness patterns for enterprise applications.

It includes:

- `retry_and_backoff` - explicit retry handling, exponential backoff, jitter, retryable error classification, and tuning guidance
- `circuit_breaker` - closed/open/half-open circuit breaker behavior for unhealthy Bedrock or Lasso paths
- `client_factory_pattern` - a reusable `BedrockClientFactory` supporting default credentials, profiles, static credentials, STS assume role, Lasso API key injection, and optional Basic Auth
- `lasso_monkey_patch` - an advanced pattern that patches `boto3.client` and `Session.client` so Lasso-specific arguments and error handling can be centralized

For enterprise application code, prefer an explicit factory or platform SDK wrapper over copy-pasting client construction into every service. That gives teams one place to enforce endpoint routing, headers, timeouts, user-agent metadata, error normalization, and credential policy.

### `05_troubleshooting`

This section contains diagnostic examples for common operational problems.

It includes examples for:

- Throttling and service limit handling
- Lasso policy `422` response explanation
- Extracting Lasso trace headers and policy block reasons from botocore errors

Some troubleshooting files are currently empty placeholders. The implemented examples focus on the most important production debugging flows: distinguishing retryable throttling from permanent failures and surfacing Lasso policy decisions clearly to operators.

---

## Recommended Adoption Path

1. Start with `00_auth_and_clients`.

   Pick the credential pattern that matches your runtime environment. Validate that a basic `converse` call reaches Bedrock through Lasso.

2. Choose the workload folder.

   Use `01_text_generation`, `02_embeddings`, or `03_multimodal` depending on the application capability being built.

3. Standardize client construction.

   Move from one-off scripts to the `client_factory_pattern` or an internal wrapper so teams do not reimplement Lasso endpoint routing and header injection differently in each service.

4. Add reliability controls.

   Use retry and backoff for temporary failures. Add a circuit breaker for user-facing or high-volume systems where repeated failures can increase latency, cost, or pressure on downstream services.

5. Add troubleshooting and observability.

   Capture request IDs, error codes, Lasso trace headers, policy block reasons, retry counts, latency, and circuit breaker state changes.

6. Harden for production.

   Replace local testing shortcuts with production settings, especially around TLS verification, credential sourcing, logging, prompt/output handling, and fallback behavior.

---

## Enterprise Production Considerations

### Security and Governance

- Keep Bedrock traffic routed through Lasso when Lasso is required for inspection, policy enforcement, reporting, or audit.
- Do not add fallback paths that bypass Lasso unless they are explicitly approved for the application and data classification.
- Avoid logging prompts, documents, images, embeddings, or model responses unless the application has approval to store that data.
- Treat Lasso policy blocks as expected governance outcomes, not generic application failures.
- Prefer short-lived AWS credentials and managed identity patterns over long-lived static keys.

### Reliability

- Keep SDK retries conservative when application-level retries are implemented.
- Retry only temporary failures such as throttling, timeouts, and selected 5xx responses.
- Do not retry validation errors, access denied errors, invalid model IDs, or expected Lasso policy blocks.
- Add jitter to avoid synchronized retry spikes.
- Pair retries with a circuit breaker for high-volume or user-facing services.

### Observability

Recommended metrics include:

- Total Bedrock requests through Lasso
- Success and failure counts
- Error counts by HTTP status and AWS error code
- Lasso policy block counts
- Retry attempts and final retry failures
- Throttling and timeout counts
- End-to-end latency and per-attempt latency
- Circuit breaker open count, duration, and blocked request count

Recommended log fields include:

- Model ID
- Operation type, such as `converse` or `invoke_model`
- AWS region
- Request ID or trace ID
- Lasso response metadata, where available
- Retry attempt number
- Final error class

### Model-Specific Adaptation

Bedrock request and response bodies vary by model family and provider. The examples are integration patterns, not a universal schema layer.

Before production use, validate:

- Text generation request format
- Streaming response parsing
- Embedding vector field names and dimensions
- Multimodal content block format
- Maximum input size and supported file types
- Tool-use schema and tool error conventions
- Provider-specific inference parameters

---

## Current Catalog Notes

Several subdirectory README files are currently empty, and a few Python examples are placeholders marked `Not Currently Supported`. The implemented examples still cover the main enterprise integration surface:

- Client authentication and Lasso routing
- Text generation
- Embeddings
- Multimodal requests
- Retry/backoff
- Circuit breaking
- Client factory abstraction
- Lasso error enrichment and policy block diagnostics

Use the placeholder files as signposts for future expansion rather than as runnable examples.

---

## Quick Smoke Test

From `examples/aws/python`, configure `.env` and run:

```bash
python 00_auth_and_clients/client_default_credentials.py
```

If the environment is configured correctly, the request should be sent to AWS Bedrock through the Lasso Proxy and print a Bedrock response.

