namespace TradeOS.Api.Modules.TradeLog.Models;

public class TradeLogEntity
{
    public Guid      Id                { get; set; } = Guid.NewGuid();
    public Guid      TheoryId          { get; set; }
    public string    Instrument        { get; set; } = string.Empty;
    public string    Timeframe         { get; set; } = string.Empty;
    public DateTime  SignalTime        { get; set; }
    public string    Direction         { get; set; } = string.Empty;
    public decimal?  EntryPrice        { get; set; }
    public decimal?  SlPrice           { get; set; }
    public decimal?  TpPrice           { get; set; }
    public int       CompositeScore    { get; set; }
    public decimal?  ConfidencePct     { get; set; }
    public decimal?  PWinAtSignal      { get; set; }
    public int?      BayesianSampleN   { get; set; }
    public string    StateSequence     { get; set; } = string.Empty;  // JSONB
    public string    FactorSnapshot    { get; set; } = string.Empty;  // JSONB
    public string?   HmmModelVersion   { get; set; }
    public string?   Outcome           { get; set; }   // WIN | LOSS | BREAK_EVEN
    public decimal?  PnlPips           { get; set; }
    public decimal?  RrActual          { get; set; }
    public bool      SignalExpired      { get; set; }
    public bool      Executed           { get; set; }
    public long?     Mt5Ticket         { get; set; }   // MT5 position ticket when auto-executed
    public DateTime? ClosedAt          { get; set; }
    public string?   Notes             { get; set; }
    public DateTime  CreatedAt         { get; set; } = DateTime.UtcNow;
}

public record RecordOutcomeRequest(
    string  Outcome,       // WIN | LOSS | BREAK_EVEN
    decimal? PnlPips,
    decimal? RrActual,
    string?  Notes
);

public record TradeLogDto(
    Guid      Id,
    Guid      TheoryId,
    string    Instrument,
    string    Timeframe,
    DateTime  SignalTime,
    string    Direction,
    decimal?  EntryPrice,
    decimal?  SlPrice,
    decimal?  TpPrice,
    int       CompositeScore,
    decimal?  ConfidencePct,
    decimal?  PWinAtSignal,
    int?      BayesianSampleN,
    string    StateSequence,
    string    FactorSnapshot,
    string?   Outcome,
    decimal?  PnlPips,
    decimal?  RrActual,
    bool      Executed,
    DateTime  CreatedAt
);
