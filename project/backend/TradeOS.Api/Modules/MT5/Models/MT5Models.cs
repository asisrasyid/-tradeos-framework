namespace TradeOS.Api.Modules.MT5.Models;

public record MT5ConnectRequest(int Login, string Password, string Server);
public record MT5AccountInfo(int Login, string Name, string Server, string Currency,
    decimal Balance, decimal Equity, decimal Margin, decimal FreeMargin, decimal Profit,
    int Leverage, bool TradeAllowed);
public record MT5OhlcRequest(string Symbol, string Timeframe, int Bars = 500);
public record MT5OhlcBar(string Time, double Open, double High, double Low, double Close, long TickVolume);
public record MT5OhlcResponse(string Symbol, string Timeframe, List<MT5OhlcBar> Bars);
public record MT5OrderRequest(string Symbol, string Action, double Volume = 0.01,
    double? SlPips = null, double? TpPips = null,
    double? SlPrice = null, double? TpPrice = null,    // absolute price (takes precedence over pips)
    string Comment = "TradeOS");
public record MT5OrderResult(bool Success, long OrderId, int Retcode, string RetcodeDesc,
    string Symbol, string Action, double Volume, double Price, double Sl, double Tp, string Comment);
public record MT5CloseRequest(long Ticket, double? Volume = null, string Comment = "TradeOS close");
public record MT5CloseResult(bool Success, long Ticket, int Retcode, string RetcodeDesc, double Profit);
public record MT5PositionInfo(long Ticket, string Symbol, string Type, double Volume,
    double OpenPrice, double Sl, double Tp, double Profit, double Swap, string Comment, string OpenTime);
public record MT5CloseAllResult(int Closed, int Failed, double TotalProfit);
public record MT5CloseAllRequest(string Filter = "all");  // "all" | "profit" | "loss"
