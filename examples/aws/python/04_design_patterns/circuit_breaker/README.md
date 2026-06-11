# Circuit Breaker Example

This example shows how to call AWS Bedrock through the Lasso proxy using the Boto3 `converse` method with a simple circuit breaker.

The goal is to help application teams build safer LLM integrations. A circuit breaker prevents an application from repeatedly calling a service that is already failing. Instead of letting every request wait, timeout, or create more load, the application can fail fast and recover once the service is healthy again.

## What this example demonstrates

This example shows how to:

- Route a Bedrock Runtime client through the Lasso proxy.
- Add the required `lasso-x-api-key` header to each request.
- Call Bedrock using the Boto3 `converse` method.
- Wrap the LLM call with a simple circuit breaker.
- Stop repeated requests after a set number of failures.
- Allow a test request after a cool-down period.
- Return to normal once the test request succeeds.

## Why use a circuit breaker

LLM applications often depend on several services:

- The application itself.
- The network path.
- The Lasso proxy.
- AWS Bedrock.
- The selected model.
- Downstream logging, policy, or audit services.

Any of these can fail or slow down. Without a circuit breaker, the application may continue sending requests into a path that is already unhealthy.

That can cause:

- Long user waits.
- More timeouts.
- Higher retry volume.
- Increased load on unhealthy services.
- Poor user experience.
- Thread or worker exhaustion.
- Harder incident recovery.

A circuit breaker helps the application protect itself.

## How the pattern works

A circuit breaker has three basic states.

### Closed

The circuit starts closed.

Requests are allowed through. If the request succeeds, the circuit stays closed. If the request fails, the failure count increases.

### Open

After too many failures, the circuit opens.

When the circuit is open, new requests are blocked before calling Bedrock or the Lasso proxy. This is called failing fast.

The application can then return a clear error message, use a fallback response, or ask the user to try again later.

### Half-open

After a cool-down period, the circuit moves to half-open.

In this state, the application allows one request through to test if the service has recovered.

If the request succeeds, the circuit closes and normal traffic resumes.

If the request fails, the circuit opens again.

## When to use this pattern

Use a circuit breaker when the application calls a service that may fail, slow down, or become temporarily unavailable.

This is useful for:

- LLM chat applications.
- Agent workflows.
- Document summarization services.
- Batch enrichment jobs.
- User-facing applications with strict response time needs.
- Services that call Bedrock through the Lasso proxy.
- Workloads where repeated failures can increase cost or load.

A circuit breaker is especially useful when the application has retries. Retries can help with brief failures, but they can make an outage worse if every request keeps retrying. The circuit breaker limits that behavior.

## When not to use this pattern

A circuit breaker may be unnecessary for:

- One-time scripts.
- Local experiments.
- Low-volume internal tools.
- Jobs where slow failure is acceptable.
- Applications that already use a managed resilience library or service mesh policy.

For simple scripts, basic exception handling may be enough.

## Circuit breaker settings

The example uses two settings:

```python
CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=30,
)
```

### failure_threshold

This controls how many failures are allowed before the circuit opens.

A lower value opens the circuit faster. A higher value gives the service more chances before blocking requests.

Common starting values:

| Workload type | Suggested value |
| --- | ---: |
| User-facing chat | 3 |
| Internal app | 3 to 5 |
| Batch job | 5 to 10 |

### recovery_timeout

This controls how long the circuit stays open before allowing a test request.

A shorter timeout checks for recovery sooner. A longer timeout gives the failing service more time to recover.

Common starting values:

| Workload type | Suggested value |
| --- | ---: |
| User-facing chat | 15 to 30 seconds |
| Internal app | 30 to 60 seconds |
| Batch job | 60 to 300 seconds |

## What counts as a failure

In the example, any `botocore.exceptions.ClientError` or unexpected exception counts as a failure.

That is simple and easy to understand, but production applications may want more control.

For example, you may choose to count these as failures:

- Network timeouts.
- Connection errors.
- HTTP 429 throttling errors.
- HTTP 500 errors.
- HTTP 502 errors.
- HTTP 503 errors.
- HTTP 504 errors.
- Proxy unavailable errors.
- Bedrock service unavailable errors.

You may choose not to count these as circuit breaker failures:

- Validation errors caused by a bad request.
- Access denied errors caused by missing permissions.
- Model ID errors caused by configuration mistakes.
- Policy blocks that are expected Lasso behavior.

The key design choice is this:

> Count failures that suggest the service path is unhealthy. Do not count failures that are caused by a user request or a known application configuration issue.

## Circuit breaker and retries

Retries and circuit breakers solve different problems.

Retries help with short, temporary failures.

Circuit breakers help when failures continue.

A good application often uses both:

1. Use a small number of retries for brief network or throttling issues.
2. Use a circuit breaker to stop repeated calls when the service path is not healthy.

Avoid aggressive retries. They can increase cost, delay users, and add pressure to the same service that is already failing.

For LLM applications, start with conservative retries:

```python
Config(
    retries={"max_attempts": 1, "mode": "standard"},
    connect_timeout=5,
    read_timeout=12,
)
```

Then tune based on application needs.

## Fallback options

When the circuit is open, the application should respond in a controlled way.

Common fallback options include:

- Return a friendly message to the user.
- Ask the user to try again later.
- Return a cached response when safe.
- Queue the request for later processing.
- Route to a different model or region.
- Reduce the request size and try again.
- Disable non-critical LLM features while keeping the main app running.

For security-sensitive workloads, avoid fallback behavior that bypasses required Lasso policy controls.

## Logging and monitoring

Application teams should log circuit breaker state changes.

Useful events include:

- Circuit opened.
- Circuit moved to half-open.
- Circuit closed after a successful test request.
- Request blocked because the circuit was open.
- Failure count increased.

Useful metrics include:

- Total LLM requests.
- Successful LLM requests.
- Failed LLM requests.
- Circuit open count.
- Circuit open duration.
- Blocked request count.
- Error count by type.
- Latency before and after circuit breaker adoption.

These metrics help teams understand whether the circuit breaker is protecting the application or hiding a larger issue that needs to be fixed.

## Thread safety

The example keeps the circuit breaker in memory.

That is fine for a simple example, but production systems need to consider how the app runs.

If the app runs with multiple threads, the circuit breaker should use a lock around state changes.

If the app runs across multiple processes, containers, or pods, each instance will have its own local circuit state.

That may be acceptable for many applications. If the team needs shared circuit state across instances, use a shared store such as Redis or a managed resilience layer.

## Design choices for production

Before using this pattern in production, application teams should decide:

- Which errors should open the circuit?
- Which errors should not count?
- How many failures should be allowed?
- How long should the cool-down period last?
- What should users see when the circuit is open?
- Should there be a fallback path?
- Should circuit state be local or shared?
- What metrics should be emitted?
- Who gets alerted when the circuit opens?
- How does this interact with retries and timeouts?

## Recommended starting point

For most user-facing LLM applications, start with:

- `failure_threshold=3`
- `recovery_timeout=30`
- Low retry count
- Clear logging
- A user-friendly fallback message
- Metrics for blocked requests and circuit state changes

Then tune based on real traffic, latency, error rates, and user impact.

## Example behavior

With this configuration:

```python
CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=30,
)
```

The behavior is:

1. The application sends requests normally.
2. If three requests fail, the circuit opens.
3. New requests fail fast for 30 seconds.
4. After 30 seconds, one test request is allowed.
5. If the test request succeeds, the circuit closes.
6. If the test request fails, the circuit opens again.

## Security notes

This pattern does not replace Lasso policy enforcement.

The application should continue routing LLM traffic through the Lasso proxy when Lasso is required for inspection, policy enforcement, audit, or reporting.

Do not add fallback logic that sends requests directly to Bedrock unless that is approved for the application and security model.

## Summary

A circuit breaker helps application teams build more reliable LLM applications.

It prevents repeated calls to an unhealthy service path, reduces user wait time, protects application resources, and gives the system time to recover.

Use this pattern when the application depends on Bedrock, the Lasso proxy, or other network services that can fail or slow down.
