using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using DotNetEnv;

Env.TraversePath().Load();

const string apiVersion = "2024-02-01";

var azureApiKey = RequireEnv("AZURE_OPENAI_API_KEY", "AZURE_API_KEY");
var azureEndpoint = RequireEnv("AZURE_ENDPOINT").TrimEnd('/');
var azureDeployment = RequireEnv("AZURE_DEPLOYMENT");
var lassoProxyUrl = RequireEnv("LASSO_PROXY_ENDPOINT").TrimEnd('/');
var lassoApiKey = RequireEnv("LASSO_X_API_KEY");

var azureService = $"{azureEndpoint}/openai/deployments/{azureDeployment}";
var lassoRequestUrl = $"{lassoProxyUrl}/v1/azure/chat/completions?api-version={apiVersion}";

EnsureRequestGoesToLasso(lassoRequestUrl, azureEndpoint);

// The request is sent to Lasso. Azure routing details are passed as headers for Lasso.
Console.WriteLine($"Sending request to Lasso: {lassoRequestUrl}");
Console.WriteLine($"Azure service for Lasso: {azureService}");

using var httpClient = CreateHttpClient(azureApiKey, lassoApiKey, azureService);
using var request = CreateChatCompletionRequest(lassoRequestUrl, azureDeployment);

try
{
    using var response = await httpClient.SendAsync(request);
    var responseBody = await response.Content.ReadAsStringAsync();

    PrintHeaders("Response headers", response.Headers);
    PrintHeaders("Response content headers", response.Content.Headers);

    if (!response.IsSuccessStatusCode)
    {
        Console.Error.WriteLine($"Request failed: {(int)response.StatusCode} {response.ReasonPhrase}");
        Console.Error.WriteLine(responseBody);
        return;
    }

    PrintJson(responseBody);
}
catch (Exception ex)
{
    Console.Error.WriteLine(ex.Message);
}

static HttpClient CreateHttpClient(string azureApiKey, string lassoApiKey, string azureService)
{
    // Use certificate validation in production. This is only for local test certificates.
    var handler = new HttpClientHandler
    {
        ServerCertificateCustomValidationCallback =
            HttpClientHandler.DangerousAcceptAnyServerCertificateValidator
    };

    var httpClient = new HttpClient(handler);

    httpClient.DefaultRequestHeaders.Add("lasso-x-api-key", lassoApiKey);
    httpClient.DefaultRequestHeaders.Add("lasso-azure-service", azureService);
    httpClient.DefaultRequestHeaders.Add("api-key", azureApiKey);
    httpClient.DefaultRequestHeaders.Authorization =
        new AuthenticationHeaderValue("Bearer", azureApiKey);

    return httpClient;
}

static HttpRequestMessage CreateChatCompletionRequest(string requestUrl, string deployment)
{
    var body = new
    {
        model = deployment,
        messages = new[]
        {
            new
            {
                role = "user",
                content = "Tell me a joke"
            }
        }
    };

    var json = JsonSerializer.Serialize(body, CreateJsonOptions());

    return new HttpRequestMessage(HttpMethod.Post, requestUrl)
    {
        Content = new StringContent(json, Encoding.UTF8, "application/json")
    };
}

static void EnsureRequestGoesToLasso(string lassoRequestUrl, string azureEndpoint)
{
    var lassoUri = new Uri(lassoRequestUrl);
    var azureUri = new Uri(azureEndpoint);

    var requestTargetsAzure = Uri.Compare(
        lassoUri,
        azureUri,
        UriComponents.SchemeAndServer,
        UriFormat.Unescaped,
        StringComparison.OrdinalIgnoreCase) == 0;

    if (requestTargetsAzure)
    {
        throw new InvalidOperationException(
            "LASSO_PROXY_ENDPOINT resolves to Azure. Set it to the Lasso proxy URL.");
    }
}

static string RequireEnv(params string[] names)
{
    foreach (var name in names)
    {
        var value = Environment.GetEnvironmentVariable(name);

        if (!string.IsNullOrWhiteSpace(value))
        {
            return value;
        }
    }

    throw new InvalidOperationException(
        $"Missing required environment variable: {string.Join(" or ", names)}");
}

static void PrintHeaders(string title, IEnumerable<KeyValuePair<string, IEnumerable<string>>> headers)
{
    Console.WriteLine(title);

    foreach (var header in headers.OrderBy(header => header.Key))
    {
        Console.WriteLine($"  {header.Key}: {string.Join(", ", header.Value)}");
    }
}

static void PrintJson(string json)
{
    using var document = JsonDocument.Parse(json);
    Console.WriteLine(JsonSerializer.Serialize(document, CreateJsonOptions()));
}

static JsonSerializerOptions CreateJsonOptions() => new()
{
    PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    WriteIndented = true
};
