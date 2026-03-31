using TradeOS.Api.Infrastructure.Python;
using TradeOS.Api.Modules.MT5.Models;

namespace TradeOS.Api.Modules.MT5.Services;

public class MT5Service(IPythonClient python, ILogger<MT5Service> logger) : IMT5Service
{
    public async Task<MT5AccountInfo> ConnectAsync(MT5ConnectRequest req)
    {
        logger.LogInformation("[MT5] Connecting login={Login} server={Server}", req.Login, req.Server);
        return (await python.PostAsync<MT5AccountInfo>("/python/mt5/connect", req))!;
    }

    public async Task<MT5AccountInfo> GetAccountAsync()
        => (await python.GetAsync<MT5AccountInfo>("/python/mt5/account"))!;

    public async Task<MT5OhlcResponse> GetOhlcAsync(string symbol, string timeframe, int bars = 500)
        => (await python.PostAsync<MT5OhlcResponse>("/python/mt5/ohlc", new { symbol, timeframe, bars }))!;

    public async Task<MT5OrderResult> SendOrderAsync(MT5OrderRequest req)
    {
        logger.LogInformation("[MT5] SendOrder {Action} {Symbol} vol={Volume}", req.Action, req.Symbol, req.Volume);
        return (await python.PostAsync<MT5OrderResult>("/python/mt5/order", req))!;
    }

    public async Task<MT5CloseResult> ClosePositionAsync(MT5CloseRequest req)
    {
        logger.LogInformation("[MT5] ClosePosition ticket={Ticket}", req.Ticket);
        return (await python.PostAsync<MT5CloseResult>("/python/mt5/close", req))!;
    }

    public async Task<List<MT5PositionInfo>> GetPositionsAsync()
        => (await python.GetAsync<List<MT5PositionInfo>>("/python/mt5/positions"))!;

    public async Task<MT5CloseAllResult> CloseAllAsync(string filter)
    {
        logger.LogInformation("[MT5] CloseAll filter={Filter}", filter);
        return (await python.PostAsync<MT5CloseAllResult>("/python/mt5/close-all", new { filter }))!;
    }

    public async Task DisconnectAsync()
    {
        logger.LogInformation("[MT5] Disconnecting");
        await python.PostAsync<object>("/python/mt5/disconnect", new { });
    }
}
