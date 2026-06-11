using System.ClientModel;
using System.ClientModel.Primitives;
using DotNetEnv;
using OpenAI;
using OpenAI.Chat;

// -----------------------------------------------------------------------------
// Lasso Azure OpenAI example using an Azure OpenAI API key.
//
// This example sends OpenAI SDK requests to the Lasso proxy. Lasso then forwards
// the request to the configured Azure OpenAI deployment.
//
// Auth flow:
//   1. The app sends the Lasso API key to authenticate to Lasso.
//   2. The app sends the Azure OpenAI API key so Lasso can call Azure.
//   3. Lasso uses lasso-azure-service to route the request to the right deployment.
//
// Required .env values:
//   AZURE_API_KEY
//   AZURE_ENDPOINT
//   AZURE_DEPLOYMENT
//   LASSO_PROXY_ENDPOINT
//   LASSO_X_API_KEY
//
// Optional .env value:
//   DISABLE_SSL_VERIFICATION=true
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
// 1. Load configuration
// -----------------------------------------------------------------------------

// The .csproj copies examples/.env into the build output folder.
// AppContext.BaseDirectory points to that output folder at runtime.
Env.Load(Path.Combine(AppContext.BaseDirectory, ".env"));

const string apiVersion = "2024-02-01";

var azureApiKey = RequireEnv("AZURE_API_KEY");
var azureEndpoint = RequireEnv("AZURE_ENDPOINT").TrimEnd('/');
var deploymentName = RequireEnv("AZURE_DEPLOYMENT");
var lassoProxyUrl = RequireEnv("LASSO_PROXY_ENDPOINT").TrimEnd('/');
var lassoApiKey = RequireEnv("LASSO_X_API_KEY");

// The OpenAI SDK sends requests to Lasso instead of Azure directly.
var lassoEndpoint = $"{lassoProxyUrl}/v1/azure?api-version={apiVersion}";

// Lasso uses this header to know which Azure OpenAI deployment to call.
var azureService = $"{azureEndpoint}/openai/deployments/{deploymentName}";

// -----------------------------------------------------------------------------
// 2. Create an HTTP client with Lasso and Azure headers
// -----------------------------------------------------------------------------

var httpClient = CreateHttpClient();

// Lasso uses this key to authenticate the caller to the proxy.
httpClient.DefaultRequestHeaders.Add("lasso-x-api-key", lassoApiKey);

// Lasso uses this value to route the request to the right Azure deployment.
httpClient.DefaultRequestHeaders.Add("lasso-azure-service", azureService);

// Azure OpenAI API key. Lasso forwards this when it calls Azure.
httpClient.DefaultRequestHeaders.Add("api-key", azureApiKey);

// -----------------------------------------------------------------------------
// 3. Configure the OpenAI SDK to send requests through Lasso
// -----------------------------------------------------------------------------

var options = new OpenAIClientOptions
{
    Endpoint = new Uri(lassoEndpoint),
    Transport = new HttpClientPipelineTransport(httpClient)
};

// Lasso currently returns 201 Created for successful chat completions.
// The OpenAI SDK expects 200 OK, so this policy tells the SDK to treat both
// 200 and 201 as success.
options.AddPolicy(
    new Treat201AsSuccessPolicy(),
    PipelinePosition.BeforeTransport);

// The SDK requires an ApiKeyCredential. We pass the Azure API key here because
// the SDK uses it to create its normal Authorization header. Lasso also receives
// the Azure key through the api-key header above.
ChatClient chatClient = new(
    model: deploymentName,
    credential: new ApiKeyCredential(azureApiKey),
    options: options);

// -----------------------------------------------------------------------------
// 4. Send a chat completion request
// -----------------------------------------------------------------------------

var response = chatClient.CompleteChat(
    "In a single word, what is the answer to the great question of life, the universe and everything?");

Console.WriteLine(response.Value.Content[0].Text);

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

    return new HttpClient(handler);
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

// The SDK classifies responses before it returns the typed result.
// Since Lasso currently returns 201 Created, we mark 201 as successful.
sealed class Treat201AsSuccessPolicy : PipelinePolicy
{
    private static readonly PipelineMessageClassifier Success200Or201 =
        PipelineMessageClassifier.Create(new ushort[] { 200, 201 });

    public override void Process(
        PipelineMessage message,
        IReadOnlyList<PipelinePolicy> pipeline,
        int currentIndex)
    {
        message.ResponseClassifier = Success200Or201;
        ProcessNext(message, pipeline, currentIndex);
    }

    public override ValueTask ProcessAsync(
        PipelineMessage message,
        IReadOnlyList<PipelinePolicy> pipeline,
        int currentIndex)
    {
        message.ResponseClassifier = Success200Or201;
        return ProcessNextAsync(message, pipeline, currentIndex);
    }
}