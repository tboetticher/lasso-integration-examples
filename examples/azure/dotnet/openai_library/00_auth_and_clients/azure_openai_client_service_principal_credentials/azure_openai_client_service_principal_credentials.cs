using Azure;
using Azure.AI.Inference;
using Azure.Core;
using Azure.Core.Pipeline;
using Azure.Identity;
using DotNetEnv;

// -----------------------------------------------------------------------------
// Lasso Azure AI Inference example using an Azure service principal.
//
// This example sends Azure SDK requests to the Lasso proxy. Lasso then forwards
// the request to the configured Azure OpenAI deployment.
//
// Auth flow:
//   1. DefaultAzureCredential gets an Azure bearer token from a service principal.
//   2. HttpClient adds the Lasso headers and Azure Authorization header.
//   3. Lasso uses lasso-azure-service to route the request to Azure.
//
// Required .env values:
//   AZURE_ENDPOINT
//   AZURE_DEPLOYMENT
//   LASSO_PROXY_ENDPOINT
//   LASSO_X_API_KEY
//   AZURE_TENANT_ID
//   AZURE_CLIENT_ID
//   AZURE_CLIENT_SECRET
//
// Optional .env value:
//   DISABLE_SSL_VERIFICATION=true
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
// 1. Load configuration
// -----------------------------------------------------------------------------
Env.Load(Path.Combine(AppContext.BaseDirectory, ".env"));

const string azureGovernmentCognitiveServicesScope =
    "https://cognitiveservices.azure.us/.default";

var azureEndpoint = RequireEnv("AZURE_ENDPOINT").TrimEnd('/');
var deploymentName = RequireEnv("AZURE_DEPLOYMENT");

var lassoProxyUrl = RequireEnv("LASSO_PROXY_ENDPOINT").TrimEnd('/');
var lassoApiKey = RequireEnv("LASSO_X_API_KEY");

// The Azure SDK sends requests to Lasso instead of Azure directly.
var lassoEndpoint = new Uri($"{lassoProxyUrl}/v1/azure");

// Lasso uses this header to route the request to the correct Azure deployment.
var azureService = $"{azureEndpoint}/openai/deployments/{deploymentName}";

// -----------------------------------------------------------------------------
// 2. Create an HTTP client with Lasso and Azure headers
// -----------------------------------------------------------------------------
var httpClient = CreateHttpClient();

httpClient.DefaultRequestHeaders.Add("lasso-x-api-key", lassoApiKey);
httpClient.DefaultRequestHeaders.Add("lasso-azure-service", azureService);

// -----------------------------------------------------------------------------
// 3. Configure the Azure SDK to send requests through Lasso
// -----------------------------------------------------------------------------
var options = new AzureAIInferenceClientOptions
{
    Transport = new HttpClientTransport(httpClient)
};

// -----------------------------------------------------------------------------
// 4. Get an Azure service principal token
// -----------------------------------------------------------------------------

// DefaultAzureCredential reads:
//   AZURE_TENANT_ID
//   AZURE_CLIENT_ID
//   AZURE_CLIENT_SECRET
//
// Azure Government requires AzureAuthorityHosts.AzureGovernment.
// For public Azure, remove the AuthorityHost setting and use:
//   https://cognitiveservices.azure.com/.default
var credential = new DefaultAzureCredential(
    new DefaultAzureCredentialOptions
    {
        AuthorityHost = AzureAuthorityHosts.AzureGovernment
    });

var token = credential.GetToken(
    new TokenRequestContext([azureGovernmentCognitiveServicesScope]),
    CancellationToken.None);

// -----------------------------------------------------------------------------
// 5. Create the Azure AI Inference chat client
// -----------------------------------------------------------------------------
// AzureKeyCredential is still required by the SDK constructor.
// The real Azure auth is the Authorization bearer token header above.
var client = new ChatCompletionsClient(
    lassoEndpoint,
    new AzureKeyCredential(token.Token),
    options);

// -----------------------------------------------------------------------------
// 6. Send a chat completion request
// -----------------------------------------------------------------------------
var requestOptions = new ChatCompletionsOptions
{
    Model = deploymentName,
    Messages =
    {
        new ChatRequestUserMessage(
            "In a single word, what is the answer to the great question of life, the universe and everything?")
    }
};

try
{
    Response<ChatCompletions> response = client.Complete(requestOptions);
    Console.WriteLine(response.Value.Content);
}
catch (RequestFailedException ex)
{
    Console.WriteLine("Azure SDK request failed.");
    Console.WriteLine($"Status: {ex.Status}");
    Console.WriteLine($"ErrorCode: {ex.ErrorCode}");
    Console.WriteLine(ex.Message);
}

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------
static HttpClient CreateHttpClient()
{
    var handler = new HttpClientHandler();

    // Local testing only.
    // Do not disable certificate validation in production.
    if (string.Equals(
            Environment.GetEnvironmentVariable("DISABLE_SSL_VERIFICATION"),
            "true",
            StringComparison.OrdinalIgnoreCase))
    {
        handler.ServerCertificateCustomValidationCallback =
            HttpClientHandler.DangerousAcceptAnyServerCertificateValidator;
    }

    return new HttpClient(
        new Treat201As200Handler
        {
            InnerHandler = handler
        });
}

static string RequireEnv(string name)
{
    var value = Environment.GetEnvironmentVariable(name);

    if (string.IsNullOrWhiteSpace(value))
    {
        throw new InvalidOperationException($"Missing required environment variable: {name}");
    }

    return value;
}

sealed class Treat201As200Handler : DelegatingHandler
{
    protected override HttpResponseMessage Send(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        var response = base.Send(request, cancellationToken);
        return Rewrite201As200(response);
    }

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        var response = await base.SendAsync(request, cancellationToken);
        return Rewrite201As200(response);
    }

    private static HttpResponseMessage Rewrite201As200(HttpResponseMessage response)
    {
        if (response.StatusCode == System.Net.HttpStatusCode.Created)
        {
            response.StatusCode = System.Net.HttpStatusCode.OK;
            response.ReasonPhrase = "OK";
        }

        return response;
    }
}