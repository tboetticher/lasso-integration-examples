using System.ClientModel;
using System.ClientModel.Primitives;
using OpenAI;
using OpenAI.Chat;
using DotNetEnv;
using Azure.Core;
using Azure.Identity;
// -----------------------------------------------------------------------------
// 1. Load configuration
// -----------------------------------------------------------------------------
Env.Load(Path.Combine(AppContext.BaseDirectory, ".env"));

const string apiVersion = "2024-02-01";

var azureApiKey = RequireEnv("AZURE_API_KEY");
var azureEndpoint = RequireEnv("AZURE_ENDPOINT").TrimEnd('/');
var deploymentName = RequireEnv("AZURE_DEPLOYMENT");
var lassoProxyUrl = RequireEnv("LASSO_PROXY_ENDPOINT").TrimEnd('/');
var lassoApiKey = RequireEnv("LASSO_X_API_KEY");

var lassoEndpoint = $"{lassoProxyUrl.TrimEnd('/')}/v1/azure?api-version={apiVersion}";
var azureService = $"{azureEndpoint}/openai/deployments/{deploymentName}";


var credential = new DefaultAzureCredential(
    new DefaultAzureCredentialOptions
    {
        AuthorityHost = AzureAuthorityHosts.AzureGovernment
    });

var token = credential.GetToken(
    new TokenRequestContext(["https://cognitiveservices.azure.us/.default"]),
    CancellationToken.None);

// -----------------------------------------------------------------------------
// 2. Create HTTP client with Lasso and Azure headers
// -----------------------------------------------------------------------------
var httpClient = CreateHttpClient();

httpClient.DefaultRequestHeaders.Add("lasso-x-api-key", lassoApiKey);
httpClient.DefaultRequestHeaders.Add("lasso-azure-service", azureService);

// -----------------------------------------------------------------------------
// 3. Create OpenAI chat client that sends requests through Lasso
// -----------------------------------------------------------------------------
var options = new OpenAIClientOptions
{
    Endpoint = new Uri(lassoEndpoint),
    Transport = new HttpClientPipelineTransport(httpClient)
};

// Lasso currently returns 201 Created. The OpenAI SDK expects 200 OK.
options.AddPolicy(
    new Treat201AsSuccessPolicy(),
    PipelinePosition.BeforeTransport);

ChatClient chatClient = new(
    model: deploymentName,
    credential: new ApiKeyCredential(token.Token),
    options: options);

// -----------------------------------------------------------------------------
// 4. Send chat completion request
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
        throw new InvalidOperationException($"Missing {name}.");
    }

    return value;
}

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