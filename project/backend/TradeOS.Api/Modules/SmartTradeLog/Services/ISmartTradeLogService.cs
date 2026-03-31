using TradeOS.Api.Modules.SmartTradeLog.Models;

namespace TradeOS.Api.Modules.SmartTradeLog.Services;

public interface ISmartTradeLogService
{
    Task<Guid>              OpenAsync(SmartTradeOpenRequest req);
    Task<bool>              CloseAsync(SmartTradeCloseRequest req);
    Task<IEnumerable<SmartTradeLogDto>> ListAsync(string? sessionId = null, string? symbol = null, int limit = 200);
    Task<SmartTradeStatsDto>            StatsAsync(string? sessionId = null);
}
