using TradeOS.Api.Modules.MT5.Models;

namespace TradeOS.Api.Modules.MT5.Services;

public interface IMT5Service
{
    Task<MT5AccountInfo> ConnectAsync(MT5ConnectRequest req);
    Task<MT5AccountInfo> GetAccountAsync();
    Task<MT5OhlcResponse> GetOhlcAsync(string symbol, string timeframe, int bars = 500);
    Task<MT5OrderResult> SendOrderAsync(MT5OrderRequest req);
    Task<MT5CloseResult> ClosePositionAsync(MT5CloseRequest req);
    Task<List<MT5PositionInfo>> GetPositionsAsync();
    Task<MT5CloseAllResult> CloseAllAsync(string filter);
    Task DisconnectAsync();
}
