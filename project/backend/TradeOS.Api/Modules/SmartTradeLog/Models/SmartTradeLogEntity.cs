namespace TradeOS.Api.Modules.SmartTradeLog.Models;

public class SmartTradeLogEntity
{
    public Guid      Id              { get; set; } = Guid.NewGuid();
    public string    SessionId       { get; set; } = string.Empty;
    public string    Symbol          { get; set; } = string.Empty;

    // Decision
    public string    Direction       { get; set; } = string.Empty;
    public int       DirectionScore  { get; set; }

    // Market parameters
    public double?   AtrValue        { get; set; }
    public double?   Ema20Value      { get; set; }
    public int?      HmmState        { get; set; }
    public string?   HmmStateLabel   { get; set; }
    public double?   HmmConfidence   { get; set; }
    public double?   ClosePrice      { get; set; }
    public double?   SpreadPips      { get; set; }

    // Voting detail
    public int?      VoteHmm         { get; set; }
    public int?      VoteEma         { get; set; }
    public int?      VoteMomentum    { get; set; }

    // Entry & targets
    public double?   EntryPrice      { get; set; }
    public double?   TpPrice         { get; set; }
    public double?   SlPrice         { get; set; }
    public double?   TpAtrMult       { get; set; }
    public double?   SlAtrMult       { get; set; }
    public double?   Volume          { get; set; }
    public long?     Mt5Ticket       { get; set; }

    // Outcome
    public double?   ExitPrice       { get; set; }
    public double?   ProfitUsd       { get; set; }
    public string?   Outcome         { get; set; }
    public string?   CloseReason     { get; set; }
    public int?      DurationS       { get; set; }

    // Timestamps
    public DateTime  OpenedAt        { get; set; } = DateTime.UtcNow;
    public DateTime? ClosedAt        { get; set; }

    // AI Decision fields
    public bool     AiEnabled          { get; set; } = false;
    public string?  LlmModel           { get; set; }
    public string?  LlmReasoning       { get; set; }
    public double?  LlmConfidence      { get; set; }
    public string?  LlmPromptVer       { get; set; }
    public int?     LlmLatencyMs       { get; set; }
    public string?  LlmSkipReason      { get; set; }
    public int?     EntriesPerDecision { get; set; }
}

// DTO for API responses
public record SmartTradeLogDto(
    Guid     Id,
    string   SessionId,
    string   Symbol,
    string   Direction,
    int      DirectionScore,
    double?  AtrValue,
    int?     HmmState,
    string?  HmmStateLabel,
    double?  HmmConfidence,
    int?     VoteHmm,
    int?     VoteEma,
    int?     VoteMomentum,
    double?  EntryPrice,
    double?  TpPrice,
    double?  SlPrice,
    long?    Mt5Ticket,
    double?  ExitPrice,
    double?  ProfitUsd,
    string?  Outcome,
    string?  CloseReason,
    int?     DurationS,
    DateTime OpenedAt,
    DateTime? ClosedAt,
    bool    AiEnabled,
    string? LlmModel,
    string? LlmReasoning,
    double? LlmConfidence,
    int?    LlmLatencyMs,
    string? LlmSkipReason
);

// Payload sent from Python smart engine when opening a position
public record SmartTradeOpenRequest(
    string SessionId,
    string Symbol,
    string Direction,
    int    DirectionScore,
    double? AtrValue,
    double? Ema20Value,
    int?   HmmState,
    string? HmmStateLabel,
    double? HmmConfidence,
    double? ClosePrice,
    double? SpreadPips,
    int?   VoteHmm,
    int?   VoteEma,
    int?   VoteMomentum,
    double? EntryPrice,
    double? TpPrice,
    double? SlPrice,
    double  TpAtrMult,
    double  SlAtrMult,
    double  Volume,
    long?  Mt5Ticket,
    bool    AiEnabled         = false,
    string? LlmModel          = null,
    string? LlmReasoning      = null,
    double? LlmConfidence     = null,
    string? LlmPromptVer      = null,
    int?    LlmLatencyMs      = null,
    string? LlmSkipReason     = null,
    int?    EntriesPerDecision = null
);

// Payload sent from Python smart engine when closing a position
public record SmartTradeCloseRequest(
    long   Mt5Ticket,
    double ExitPrice,
    double ProfitUsd,
    string Outcome,
    string CloseReason
);

public record SmartTradeStatsDto(
    int    Total,
    int    Wins,
    int    Losses,
    int    BreakEven,
    int    Open,
    double WinRate,
    double TotalProfitUsd,
    double AvgProfitUsd,
    double AvgDurationS
);
