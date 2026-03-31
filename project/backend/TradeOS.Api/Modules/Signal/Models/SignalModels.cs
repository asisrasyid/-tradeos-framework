namespace TradeOS.Api.Modules.Signal.Models;

public record LiveSignal(
    Guid     TradeLogId,
    Guid     TheoryId,
    string   TheoryName,
    string   Instrument,
    string   Timeframe,
    string   Direction,
    decimal? EntryPrice,
    decimal? SlPrice,
    decimal? TpPrice,
    int      CompositeScore,
    decimal  PWin,
    string   ConfidenceTier,
    string   StateSeqRepr,
    string   Decision,      // SIGNAL | WATCH
    DateTime SignalTime
);

public record SignalHub_NewSignal(LiveSignal Signal);

/// <summary>
/// Payload posted by Python signal engine on each matched bar.
/// </summary>
public record IngestSignalRequest(
    string   SessionId,
    string   TheoryId,
    string   Instrument,
    string   Timeframe,
    string   Direction,
    decimal  EntryPrice,
    decimal  SlPrice,
    decimal  TpPrice,
    double   Similarity,      // 0.0 – 1.0
    string   SeqRepr,
    string   SignalTime,      // ISO-8601
    bool     AutoExecute = false,
    double   Volume      = 0.01
);
