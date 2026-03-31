using TradeOS.Api.Common.Models;
using TradeOS.Api.Modules.Signal.Models;

namespace TradeOS.Api.Modules.Signal.Services;

public interface ISignalService
{
    Task<IEnumerable<LiveSignal>>    GetLiveSignalsAsync();
    Task<PagedResult<LiveSignal>>    GetHistoryAsync(int page, int pageSize);
    Task                             RecordOutcomeAsync(Guid tradeId, string outcome, decimal? pnlPips, decimal? rrActual);

    /// <summary>
    /// Full 9-step evaluation pipeline: OHLC → features → HMM → C-codes → pattern match
    /// → sp_evaluate_theory → Bayesian lookup → insert trade_log → SignalR push.
    /// </summary>
    Task<EvaluateResult> EvaluateTheoryAsync(Guid theoryId, string instrument, string timeframe);

    /// <summary>
    /// Ingest a pre-computed signal from the Python signal engine.
    /// Saves trade_log with entry/SL/TP prices and pushes via SignalR.
    /// </summary>
    Task<Guid> IngestSignalAsync(IngestSignalRequest req);
}

public record EvaluateResult(
    string   Decision,          // SIGNAL | WATCH | SKIP
    int      CompositeScore,
    decimal  PWin,
    string   StateSeqRepr,
    Guid?    TradeLogId          // null when SKIP
);
