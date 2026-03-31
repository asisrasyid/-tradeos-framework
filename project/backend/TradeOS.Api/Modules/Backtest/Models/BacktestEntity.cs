namespace TradeOS.Api.Modules.Backtest.Models;

public class BacktestSessionEntity
{
    public Guid      Id              { get; set; } = Guid.NewGuid();
    public Guid      TheoryId        { get; set; }
    public int       TheoryVersion   { get; set; }
    public Guid?     HmmModelId      { get; set; }
    public string    Instrument      { get; set; } = string.Empty;
    public string    Timeframe       { get; set; } = string.Empty;
    public DateTime  DateFrom        { get; set; }
    public DateTime  DateTo          { get; set; }
    public string    Params          { get; set; } = "{}";   // JSONB
    public string    Status          { get; set; } = "pending";
    public string    TriggeredBy     { get; set; } = "manual";
    // SL/TP config — stored as dedicated columns for display & query
    public string    SlType          { get; set; } = "atr";   // "atr" | "fixed"
    public decimal   SlValue         { get; set; } = 1.0m;
    public string    TpType          { get; set; } = "atr";
    public decimal   TpValue         { get; set; } = 2.0m;
    public int       MaxHoldBars     { get; set; } = 20;
    public DateTime? RanAt           { get; set; }
    public DateTime? CompletedAt     { get; set; }
    public string?   ErrorMessage    { get; set; }
    public DateTime  CreatedAt       { get; set; } = DateTime.UtcNow;
}

public class BacktestResultEntity
{
    public Guid      Id                 { get; set; } = Guid.NewGuid();
    public Guid      SessionId          { get; set; }
    public int       TotalSignals       { get; set; }
    public int       Wins               { get; set; }
    public int       Losses             { get; set; }
    public int       Breakeven          { get; set; }
    public decimal?  WinRate            { get; set; }
    public decimal?  ProfitFactor       { get; set; }
    public decimal?  SharpeRatio        { get; set; }
    public decimal?  SortinoRatio       { get; set; }
    public decimal?  MaxDrawdown        { get; set; }
    public decimal?  AvgRr              { get; set; }
    public decimal?  TotalPips          { get; set; }
    public string?   EquityCurve        { get; set; }   // JSONB
    public string?   StateDistribution  { get; set; }   // JSONB
    public string?   BestSeqRepr        { get; set; }
    public string?   WorstSeqRepr       { get; set; }
    public DateTime  CreatedAt          { get; set; } = DateTime.UtcNow;
}

/// <summary>Per-trade record from backtest simulation.</summary>
public class BacktestTradeEntity
{
    public Guid     Id          { get; set; } = Guid.NewGuid();
    public Guid     SessionId   { get; set; }
    public int      BarIndex    { get; set; }
    public string?  Time        { get; set; }
    public string   Direction   { get; set; } = string.Empty;
    public decimal  Entry       { get; set; }
    public decimal  Sl          { get; set; }
    public decimal  Tp          { get; set; }
    public string   SlType      { get; set; } = "atr";
    public string   TpType      { get; set; } = "atr";
    public decimal  Atr         { get; set; }
    public string   Outcome     { get; set; } = "breakeven";  // win | loss | breakeven
    public int      ExitBar     { get; set; }
    public decimal  ExitPrice   { get; set; }
    public decimal  PnlPips     { get; set; }
    public decimal  RrAchieved  { get; set; }
    public string?  SeqRepr     { get; set; }
    public decimal  Similarity  { get; set; }
}

public record RunBacktestRequest(
    Guid     TheoryId,
    string   Instrument,
    string   Timeframe,
    DateTime DateFrom,
    DateTime DateTo,
    string?  ParamsJson   = null,
    string   DataSource   = "db",   // "db" | "mt5"
    string   SlType       = "atr",
    decimal  SlValue      = 1.0m,
    string   TpType       = "atr",
    decimal  TpValue      = 2.0m,
    int      MaxHoldBars  = 20
);

public record BacktestSessionDto(
    Guid     Id,
    Guid     TheoryId,
    string   Instrument,
    string   Timeframe,
    DateTime DateFrom,
    DateTime DateTo,
    string   Status,
    DateTime? CompletedAt,
    DateTime CreatedAt,
    string   SlType,
    decimal  SlValue,
    string   TpType,
    decimal  TpValue,
    int      MaxHoldBars
);

public record BacktestTradeDto(
    Guid    Id,
    Guid    SessionId,
    int     BarIndex,
    string? Time,
    string  Direction,
    decimal Entry,
    decimal Sl,
    decimal Tp,
    string  SlType,
    string  TpType,
    decimal Atr,
    string  Outcome,
    int     ExitBar,
    decimal ExitPrice,
    decimal PnlPips,
    decimal RrAchieved,
    string? SeqRepr,
    decimal Similarity
);
