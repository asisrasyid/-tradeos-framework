using TradeOS.Api.Modules.Backtest.Models;

namespace TradeOS.Api.Modules.Backtest.Services;

public interface IBacktestService
{
    Task<string>                            QueueAsync(RunBacktestRequest req);
    Task<IEnumerable<BacktestSessionDto>>   ListSessionsAsync(Guid? theoryId);
    Task<object?>                           GetResultsAsync(Guid sessionId);
    Task<IEnumerable<BacktestTradeDto>>     GetTradesAsync(Guid sessionId);
    Task<object>                            CompareAsync(Guid sessionA, Guid sessionB);
    Task<bool>                              DeleteAsync(Guid sessionId);
}
