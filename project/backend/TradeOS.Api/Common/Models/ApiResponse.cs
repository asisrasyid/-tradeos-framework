namespace TradeOS.Api.Common.Models;

public record ApiResponse<T>(
    bool Success,
    T? Data,
    string? Error,
    DateTime Timestamp
)
{
    public static ApiResponse<T> Ok(T data) =>
        new(true, data, null, DateTime.UtcNow);

    public static ApiResponse<T> Fail(string error) =>
        new(false, default, error, DateTime.UtcNow);
}

public record PagedResult<T>(
    IEnumerable<T> Items,
    int Total,
    int Page,
    int PageSize
);
