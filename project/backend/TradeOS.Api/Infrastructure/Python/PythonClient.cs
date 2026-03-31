using System.Text;
using System.Text.Json;

namespace TradeOS.Api.Infrastructure.Python;

public class PythonClient(HttpClient http) : IPythonClient
{
    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy        = JsonNamingPolicy.SnakeCaseLower,
    };

    public async Task<T?> PostAsync<T>(string endpoint, object payload)
    {
        var content = new StringContent(
            JsonSerializer.Serialize(payload, JsonOpts),
            Encoding.UTF8,
            "application/json");

        var response = await http.PostAsync(endpoint, content);
        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<T>(json, JsonOpts);
    }

    public async Task<T?> GetAsync<T>(string endpoint, Dictionary<string, string>? queryParams = null)
    {
        var url = endpoint;
        if (queryParams?.Count > 0)
        {
            var query = string.Join("&", queryParams.Select(kv => $"{kv.Key}={Uri.EscapeDataString(kv.Value)}"));
            url = $"{endpoint}?{query}";
        }

        var response = await http.GetAsync(url);
        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<T>(json, JsonOpts);
    }
}
