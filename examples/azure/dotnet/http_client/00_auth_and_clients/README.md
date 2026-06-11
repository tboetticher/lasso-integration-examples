# 00_auth_and_clients

This folder shows .NET authentication and client setup patterns for calling Azure OpenAI from C#.

The main HTTP client example:

- Uses `System.Net.Http.HttpClient` directly
- Sends requests to Azure OpenAI **through the Lasso Proxy**
- Points requests at `LASSO_PROXY_ENDPOINT`
- Adds the `lasso-x-api-key` header on each request
- Adds the `lasso-azure-service` header so Lasso can route to the correct Azure OpenAI deployment
- Includes a simple chat completions smoke test

Use these examples to decide **whether you want to call Lasso with raw HTTP** or **use Azure credential/client patterns** in your own code.

---

## Prerequisites

1. .NET SDK

   These examples target `net10.0`. Install a compatible .NET SDK before running them.

2. NuGet dependencies

   Dependencies are declared in each example `.csproj` file and are restored automatically by `dotnet run`.

   The examples use packages such as:

   - `DotNetEnv`
   - `Azure.Identity`

3. Environment variables

   Required for the HTTP client Lasso example:

   - `LASSO_PROXY_ENDPOINT` - Lasso proxy base URL
     Example: `https://your-lasso-host.example.com`
   - `LASSO_X_API_KEY` - Lasso API key value
   - `AZURE_ENDPOINT` - Azure OpenAI resource endpoint
     Example: `https://your-resource.openai.azure.com`
   - `AZURE_DEPLOYMENT` - Azure OpenAI deployment name used for the smoke test
   - `AZURE_OPENAI_API_KEY` or `AZURE_API_KEY` - Azure OpenAI API key

   Required for service-principal credential flows:

   - `AZURE_TENANT_ID` - Azure tenant ID
   - `AZURE_CLIENT_ID` - Azure application/client ID
   - `AZURE_CLIENT_SECRET` - Azure client secret

---

## Examples

### 1. `client_default_credentials`

**What it shows**

- Uses `HttpClient` directly instead of an Azure or OpenAI SDK client.
- Loads configuration from `.env` using `DotNetEnv`.
- Builds the Lasso request URL as:

   ```text
   {LASSO_PROXY_ENDPOINT}/v1/azure/chat/completions?api-version=2024-02-01
   ```

- Builds the Azure service route header as:

   ```text
   {AZURE_ENDPOINT}/openai/deployments/{AZURE_DEPLOYMENT}
   ```

- Sends these request headers:
  - `lasso-x-api-key`
  - `lasso-azure-service`
  - `api-key`
  - `Authorization: Bearer <Azure API key>`
- Validates that the request is being sent to Lasso, not directly to Azure.
- Prints response headers and a formatted JSON response body.

**How to run**

```bash
dotnet run --project client_default_credentials
```

You must provide the shared Lasso and Azure deployment settings, plus either `AZURE_OPENAI_API_KEY` or `AZURE_API_KEY`.

---

### 2. `client_service_principal_credentials`

**What it shows**

- Demonstrates the shape of a C# Azure OpenAI client setup for a deployment.
- Uses `AzureOpenAIClient` and `ChatClient` from the Azure/OpenAI client libraries.
- Sends a simple chat completion request to a configured deployment.
- The project includes `Azure.Identity`, which is commonly used for service-principal token flows.

**Current implementation note**

The current source file uses hard-coded placeholder values for:

- Azure OpenAI endpoint
- Deployment name
- API key

It does not currently send the request through Lasso or read service-principal environment variables. Treat this example as a starting point for adapting Azure client authentication, not as the raw `HttpClient` Lasso proxy pattern shown in `client_default_credentials`.

**How to run**

```bash
dotnet run --project client_service_principal_credentials
```

Before running, replace the placeholder endpoint, deployment name, and API key in the example source with values for your Azure OpenAI resource.

---

## When to use which pattern

- **`client_default_credentials`**
  Use when:
  - You want direct control over the HTTP request.
  - You do not need an SDK abstraction.
  - You want to see exactly which Lasso and Azure headers are sent.
  - You are testing the Lasso Azure proxy route with a minimal raw HTTP request.

- **`client_service_principal_credentials`**
  Use when:
  - You want to explore Azure/OpenAI client-library setup from C#.
  - You plan to adapt the example to use Microsoft Entra ID or service-principal token auth.
  - You prefer SDK request and response models over hand-built HTTP JSON.

