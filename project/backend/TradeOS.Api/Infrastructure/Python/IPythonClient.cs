namespace TradeOS.Api.Infrastructure.Python;

public interface IPythonClient
{
    Task<T?> PostAsync<T>(string endpoint, object payload);
    Task<T?> GetAsync<T>(string endpoint, Dictionary<string, string>? queryParams = null);
}
