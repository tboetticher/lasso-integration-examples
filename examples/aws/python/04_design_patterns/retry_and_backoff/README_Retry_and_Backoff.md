# Retry and Backoff Example

This example shows how to call AWS Bedrock through the Lasso proxy using the Boto3 `converse` method with simple error handling, retries, and exponential backoff.

The goal is to help application teams handle temporary failures without making the application hard to reason about.

## What this example demonstrates

This example shows how to:

- Route a Bedrock Runtime client through the Lasso proxy.
- Add the required `lasso-x-api-key` header to each request.
- Call Bedrock using the Boto3 `converse` method.
- Catch and inspect Boto3 and network errors.
- Retry only when the failure is likely temporary.
- Use exponential backoff to avoid retrying too fast.
- Add jitter so many clients do not retry at the same time.
- Keep retry behavior in one clear function.

## Why retries matter

LLM applications often depend on services that may fail for a short time.

Examples include:

- A temporary network issue.
- A request timeout.
- A throttling response.
- A model that is briefly unavailable.
- A service returning a temporary 5xx error.
- A proxy or upstream service that is under load.

A retry can help when the next request has a good chance of succeeding.

## Why backoff matters

Retrying too fast can make a problem worse.

Without backoff, an application may send repeated requests into a service that is already slow or overloaded. This can increase cost, create more failures, and make recovery harder.

Backoff spaces out retry attempts.

This gives the service time to recover and reduces pressure on the failing path.

## Why jitter matters

Jitter adds a small random delay to each retry.

This helps when many clients fail at the same time. Without jitter, every client may retry at the same schedule, which can create traffic spikes.

With jitter, retries spread out over time.

## When to use this pattern

Use retries and backoff when a request may fail due to a temporary condition.

Good use cases include:

- User-facing chat requests.
- Document summarization.
- Agent workflows.
- Batch enrichment jobs.
- Internal tools that call Bedrock.
- Applications that call Bedrock through the Lasso proxy.

This pattern is useful when the application can safely try the same request again.

## When not to retry

Do not retry errors that are unlikely to succeed on another attempt.

Examples include:

- Invalid request body.
- Missing required fields.
- Invalid model ID.
- Access denied.
- Bad AWS credentials.
- Unsupported inference parameters.
- Validation errors.
- Policy blocks that are expected Lasso behavior.

Retries should not hide application bugs or configuration errors.

## What this example retries

The example retries common temporary failures, including:

- Connection errors.
- Connection timeouts.
- Read timeouts.
- HTTP 429 throttling.
- HTTP 500 internal server errors.
- HTTP 502 bad gateway errors.
- HTTP 503 service unavailable errors.
- HTTP 504 gateway timeout errors.
- Selected Bedrock transient error codes.

The retryable error list is defined in the example:

```python
RETRYABLE_ERROR_CODES = {
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceUnavailableException",
    "InternalServerException",
    "RequestTimeout",
    "RequestTimeoutException",
    "ModelTimeoutException",
    "ModelNotReadyException",
}
```

Application teams should adjust this list based on their workload and error patterns.

## Recommended starting values

For most application teams, start with:

```python
converse_with_retry(
    client=bedrock_client,
    model_id=model_id,
    prompt=prompt,
    max_attempts=3,
)
```

And use conservative client settings:

```python
Config(
    retries={"max_attempts": 1, "mode": "standard"},
    connect_timeout=5,
    read_timeout=12,
)
```

This keeps retry behavior in the application code, not hidden inside the SDK.

## Why SDK retries are limited

Boto3 can retry some failures automatically.

This example sets SDK retries to one attempt:

```python
retries={"max_attempts": 1, "mode": "standard"}
```

That makes the example easier to understand because retries happen in one place:

```python
converse_with_retry(...)
```

In production, a team can choose to use Boto3 retries, application-level retries, or both. Avoid stacking too many retry layers. Too many retries can increase latency and cost.

## Backoff behavior

The example uses exponential backoff:

```python
delay = min(base_delay * (2 ** attempt), max_delay)
```

With the default values, delays grow like this:

| Attempt | Base delay |
| --- | ---: |
| Retry 1 | 1 second |
| Retry 2 | 2 seconds |
| Retry 3 | 4 seconds |

The delay is capped by `max_delay`.

The example also adds jitter:

```python
jitter = random.uniform(0, delay * 0.25)
```

This adds up to 25% extra delay at random.

## Tuning guidance

Use shorter timeouts for user-facing apps.

Use longer timeouts for batch jobs.

Suggested starting points:

| Workload type | Max attempts | Connect timeout | Read timeout |
| --- | ---: | ---: | ---: |
| User-facing chat | 2 to 3 | 3 to 5 seconds | 10 to 30 seconds |
| Internal tool | 3 | 5 seconds | 30 to 60 seconds |
| Batch job | 3 to 5 | 5 to 10 seconds | 60 seconds or more |

Tune these values based on user impact, model latency, token size, and service-level goals.

## Error handling design

The example separates error handling into three parts.

### Detect retryable errors

```python
is_retryable_error(error)
```

This function decides whether the error is temporary.

### Sleep before retrying

```python
sleep_with_backoff(attempt)
```

This function controls the retry delay.

### Wrap the Bedrock call

```python
converse_with_retry(...)
```

This function owns the request, retry loop, and final error behavior.

This keeps the code easy to test and change.

## Logging

The example logs each retry attempt.

Useful log fields include:

- Attempt number.
- Max attempts.
- Error code.
- HTTP status code.
- Model ID.
- Request type.
- Whether the request was retried.
- Whether the request failed permanently.

Avoid logging prompt text or model output unless your application has approval to store that data.

## Security notes

This pattern does not replace Lasso policy enforcement.

When Lasso is required for inspection, policy enforcement, reporting, or audit, retries should continue to route through the Lasso proxy.

Do not add fallback logic that bypasses Lasso unless that path is approved for the application and security model.

## Retry safety

Most simple LLM requests are safe to retry because they do not change server-side state.

Be more careful with workflows that trigger actions.

For example, do not blindly retry if the model response causes the application to:

- Send an email.
- Create a ticket.
- Submit a form.
- Update a database.
- Call an external tool.
- Start a payment or transaction.

For action-taking workflows, use idempotency keys, request IDs, or application-level guards.

## Retries and circuit breakers

Retries and circuit breakers work well together.

Retries handle brief failures.

Circuit breakers stop repeated calls when failures continue.

A common design is:

1. Retry a request a small number of times.
2. If repeated requests continue to fail, let a circuit breaker open.
3. Fail fast while the service path recovers.
4. Allow a test request after a cool-down period.

This keeps the application responsive during outages.

## Production checklist

Before using this pattern in production, decide:

- Which errors should be retried?
- Which errors should fail immediately?
- How many attempts are allowed?
- What backoff timing should be used?
- What timeout values are right for the workload?
- Should Boto3 retries be enabled, disabled, or reduced?
- What should users see after retries fail?
- What metrics should be emitted?
- Should retries be paired with a circuit breaker?
- How will the team avoid retrying action-taking workflows in unsafe ways?

## Recommended metrics

Track these metrics:

- Total requests.
- Successful requests.
- Failed requests.
- Retried requests.
- Retry count by error code.
- Final failure count by error code.
- Latency per attempt.
- Total request latency including retries.
- Throttling count.
- Timeout count.

These metrics help teams tune retry behavior and identify service issues.

## Summary

Retries help an application recover from short-lived failures.

Backoff prevents the application from retrying too fast.

Jitter spreads retries across time and reduces traffic spikes.

Use this pattern for temporary failures, but avoid retrying bad requests, access problems, policy blocks, or unsafe action-taking workflows.
