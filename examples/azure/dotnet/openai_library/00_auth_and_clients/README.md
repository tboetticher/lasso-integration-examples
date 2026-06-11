# 00_auth_and_clients

This folder shows different ways to create .NET Azure OpenAI clients that talk to Azure OpenAI **through the Lasso Proxy**.

All examples:

- Load configuration from `.env`
- Point the SDK client at `LASSO_PROXY_ENDPOINT`
- Automatically send the `lasso-x-api-key` header on each request
- Send the `lasso-azure-service` header so Lasso can route to the correct Azure OpenAI deployment
- Include a simple chat completion smoke test

Use these examples to decide **which .NET client type you want to use** and **how you want to provide Azure credentials** in your own code.

---

## Prerequisites

1. .NET SDK

   These examples target `net10.0`. Install a compatible .NET SDK before running them.

2. NuGet dependencies

   Dependencies are declared in each example `.csproj` file and are restored automatically by `dotnet run`.

   The examples use packages such as:

   - `OpenAI`
   - `Azure.AI.Inference`
   - `Azure.Identity`
   - `DotNetEnv`

3. Environment variables

   The example projects copy the repo-level `.env` file into the build output folder. You can define these values in the repo root `.env`.

   Required for all examples:

   - `LASSO_PROXY_ENDPOINT` - Lasso proxy base URL
     Example: `https://your-lasso-host.example.com`
   - `LASSO_X_API_KEY` - Lasso API key value
   - `AZURE_ENDPOINT` - Azure OpenAI resource endpoint
     Example: `https://your-resource.openai.azure.com`
   - `AZURE_DEPLOYMENT` - Azure OpenAI deployment name used for the smoke test

   Required for API-key examples:

   - `AZURE_API_KEY` - Azure OpenAI API key

   Required for service-principal examples:

   - `AZURE_TENANT_ID` - Azure tenant ID
   - `AZURE_CLIENT_ID` - Azure application/client ID
   - `AZURE_CLIENT_SECRET` - Azure client secret

   Optional for local testing:

   - `DISABLE_SSL_VERIFICATION=true` - disables TLS certificate validation for local testing only

---

## Examples

### 1. `openai_client_default_credentials`

**What it shows**

- Uses the `OpenAI` .NET library `ChatClient`.
- Authenticates to Azure OpenAI with `AZURE_API_KEY`.
- Configures the OpenAI SDK endpoint as:

   ```text
   {LASSO_PROXY_ENDPOINT}/v1/azure?api-version=2024-02-01
   ```

- Adds Lasso routing headers through a custom `HttpClient`.
- Adds a custom pipeline policy so the OpenAI SDK treats Lasso's `201 Created` response as success.

**How to run**

```bash
dotnet run --project openai_client_default_credentials
```

You must provide `AZURE_API_KEY` along with the shared Lasso and Azure deployment settings.

---

### 2. `openai_client_service_principal_credentials`

**What it shows**

- Uses the `OpenAI` .NET library `ChatClient`.
- Uses `DefaultAzureCredential` to get an Azure bearer token from a service principal.
- Uses Azure Government authority and scope:

   ```text
   https://cognitiveservices.azure.us/.default
   ```

- Configures the OpenAI SDK to send chat completion requests through Lasso.
- Adds a custom pipeline policy so the OpenAI SDK treats Lasso's `201 Created` response as success.

**Key environment variables**

- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`

**How to run**

```bash
dotnet run --project openai_client_service_principal_credentials
```

If everything is configured properly, you'll see a short response from the model, confirming that:

- `DefaultAzureCredential` obtained a service-principal token.
- The client can invoke Azure OpenAI through Lasso using that token.

---

### 3. `azure_openai_client_default_credentials`

**What it shows**

- Uses the Azure SDK `Azure.AI.Inference` `ChatCompletionsClient`.
- Authenticates to Azure OpenAI with `AZURE_API_KEY`.
- Sends Azure SDK requests to:

   ```text
   {LASSO_PROXY_ENDPOINT}/v1/azure
   ```

- Adds `lasso-x-api-key` and `lasso-azure-service` headers through `HttpClientTransport`.
- Rewrites Lasso's `201 Created` response to `200 OK` before the Azure SDK processes it.

**How to run**

```bash
dotnet run --project azure_openai_client_default_credentials
```

You must provide `AZURE_API_KEY` along with the shared Lasso and Azure deployment settings.

---

### 4. `azure_openai_client_service_principal_credentials`

**What it shows**

- Uses the Azure SDK `Azure.AI.Inference` `ChatCompletionsClient`.
- Uses `DefaultAzureCredential` to get an Azure bearer token from a service principal.
- Uses Azure Government authority and scope:

   ```text
   https://cognitiveservices.azure.us/.default
   ```

- Sends Azure SDK requests through Lasso with `HttpClientTransport`.
- Rewrites Lasso's `201 Created` response to `200 OK` before the Azure SDK processes it.

**Key environment variables**

- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`

**How to run**

```bash
dotnet run --project azure_openai_client_service_principal_credentials
```

If everything is configured properly, you'll see a short response from the model, confirming that:

- `DefaultAzureCredential` obtained a service-principal token.
- The Azure SDK client can invoke Azure OpenAI through Lasso using that token.

---

## When to use which pattern

- **`openai_client_default_credentials`**
  Use when:
  - You want to use the `OpenAI` .NET library.
  - You authenticate to Azure OpenAI with an API key.
  - You want the simplest OpenAI SDK setup for local testing or key-based deployments.

- **`openai_client_service_principal_credentials`**
  Use when:
  - You want to use the `OpenAI` .NET library.
  - You authenticate with Microsoft Entra ID instead of an Azure OpenAI API key.
  - You want service-principal credentials supplied through environment variables.

- **`azure_openai_client_default_credentials`**
  Use when:
  - You prefer Azure SDK client patterns and types.
  - You authenticate to Azure OpenAI with an API key.
  - You want `Azure.AI.Inference` request and response models.

- **`azure_openai_client_service_principal_credentials`**
  Use when:
  - You prefer Azure SDK client patterns and types.
  - You authenticate with Microsoft Entra ID instead of an Azure OpenAI API key.
  - You are running in Azure Government or another environment where authority host and token scope matter.

