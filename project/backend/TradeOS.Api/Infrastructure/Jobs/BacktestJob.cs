using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using TradeOS.Api.Infrastructure.Database;
using TradeOS.Api.Infrastructure.Python;
using TradeOS.Api.Modules.Backtest.Models;
using TradeOS.Api.Modules.Backtest.Services;

namespace TradeOS.Api.Infrastructure.Jobs;

public class BacktestJob(
    TradeOsDbContext db,
    IPythonClient python,
    ILogger<BacktestJob> logger
) : IBacktestJob
{
    public async Task RunAsync(Guid sessionId)
    {
        // 1. Load session
        var session = await db.BacktestSessions.FindAsync(sessionId);
        if (session is null)
        {
            logger.LogWarning("[BacktestJob] Session {SessionId} not found", sessionId);
            return;
        }

        // 2. Mark running
        session.Status = "running";
        session.RanAt  = DateTime.UtcNow;
        await db.SaveChangesAsync();

        try
        {
            // 3. Load Theory + Factors
            var theory = await db.Theories
                .Include(t => t.Factors)
                .FirstOrDefaultAsync(t => t.Id == session.TheoryId);

            if (theory is null)
            {
                session.Status       = "failed";
                session.ErrorMessage = $"Theory {session.TheoryId} not found";
                await db.SaveChangesAsync();
                return;
            }

            var factorsJson = JsonSerializer.Serialize(theory.Factors.Select(f => new
            {
                f.FactorCode,
                f.FactorType,
                f.DecisionPoint,
                f.IsRequired,
                f.Operator,
                f.ThresholdValue,
                f.Timeframe,
                f.SortOrder
            }));

            // 4. Resolve pattern_states dari factor yang punya PatternId
            //    (sama seperti EngineController — pattern_states wajib ada untuk backtest runner)
            var patternStates = new List<int>();
            var patternFactor = theory.Factors.FirstOrDefault(f => f.PatternId.HasValue);
            if (patternFactor?.PatternId != null)
            {
                var pattern = await db.Patterns.FindAsync(patternFactor.PatternId.Value);
                if (pattern?.StateSequence != null)
                {
                    try { patternStates = JsonSerializer.Deserialize<List<int>>(pattern.StateSequence) ?? []; }
                    catch { /* ignore malformed JSON */ }
                }
            }

            if (patternStates.Count == 0)
            {
                logger.LogWarning(
                    "[BacktestJob] Theory {TheoryId} tidak punya pattern_states — " +
                    "pastikan ada factor HMM_STATE_SEQ_MATCH dengan pattern yang linked",
                    theory.Id);
            }

            // Resolve similarity_threshold dari MinConfidence theory
            var similarityThreshold = (double)(theory.MinConfidence / 100m);

            // 5. Build theory snapshot JSON string for Python
            var theorySnapshot = JsonSerializer.Serialize(new
            {
                theory_id            = theory.Id.ToString(),
                theory_name          = theory.Name,
                instrument           = theory.Instrument,
                direction            = theory.Direction,
                threshold            = theory.Threshold,
                pattern_states       = patternStates,       // ← resolved state sequence
                similarity_threshold = similarityThreshold, // ← dari MinConfidence
                factors              = theory.Factors.Select(f => new
                {
                    factor_code     = f.FactorCode,
                    factor_type     = f.FactorType,
                    decision_point  = f.DecisionPoint,
                    is_required     = f.IsRequired,
                    @operator       = f.Operator,
                    threshold_value = f.ThresholdValue,
                    timeframe       = f.Timeframe,
                    sort_order      = f.SortOrder,
                    pattern_id      = f.PatternId?.ToString(),
                })
            });

            var extraParams = session.Params != "{}" && !string.IsNullOrEmpty(session.Params)
                ? JsonSerializer.Deserialize<Dictionary<string, object>>(session.Params)
                : new Dictionary<string, object>();

            // Merge SL/TP config into params so Python runner can read them
            var mergedParams = extraParams ?? new Dictionary<string, object>();
            mergedParams["sl_type"]       = session.SlType;
            mergedParams["sl_value"]      = (double)session.SlValue;
            mergedParams["tp_type"]       = session.TpType;
            mergedParams["tp_value"]      = (double)session.TpValue;
            mergedParams["max_hold_bars"] = session.MaxHoldBars;

            var payload = new
            {
                session_id      = sessionId.ToString(),
                theory_snapshot = theorySnapshot,
                instrument      = session.Instrument,
                timeframe       = session.Timeframe,
                date_from       = session.DateFrom.ToString("yyyy-MM-dd"),
                date_to         = session.DateTo.ToString("yyyy-MM-dd"),
                @params         = mergedParams,
            };

            var result = await python.PostAsync<BacktestRunResult>("/python/backtest/run", payload);

            // 5. Handle null response
            if (result is null)
            {
                session.Status       = "failed";
                session.ErrorMessage = "Python returned null";
                await db.SaveChangesAsync();
                return;
            }

            // 6. Create and insert BacktestResultEntity
            var entity = new BacktestResultEntity
            {
                SessionId         = sessionId,
                TotalSignals      = result.TotalSignals,
                Wins              = result.Wins,
                Losses            = result.Losses,
                Breakeven         = result.Breakeven,
                WinRate           = (decimal)result.WinRate,
                ProfitFactor      = (decimal)result.ProfitFactor,
                SharpeRatio       = (decimal)result.SharpeRatio,
                SortinoRatio      = (decimal)result.SortinoRatio,
                MaxDrawdown       = (decimal)result.MaxDrawdown,
                AvgRr             = (decimal)result.AvgRr,
                TotalPips         = (decimal)result.TotalPips,
                EquityCurve       = JsonSerializer.Serialize(result.EquityCurve),
                StateDistribution = JsonSerializer.Serialize(result.StateDistribution),
                BestSeqRepr       = result.BestSeqRepr,
                WorstSeqRepr      = result.WorstSeqRepr,
            };

            db.BacktestResults.Add(entity);

            // 6b. Save individual trade records
            if (result.Trades is { Count: > 0 })
            {
                var tradeEntities = result.Trades.Select(t => new BacktestTradeEntity
                {
                    SessionId  = sessionId,
                    BarIndex   = t.BarIndex,
                    Time       = t.Time,
                    Direction  = t.Direction,
                    Entry      = (decimal)t.Entry,
                    Sl         = (decimal)t.Sl,
                    Tp         = (decimal)t.Tp,
                    SlType     = t.SlType,
                    TpType     = t.TpType,
                    Atr        = (decimal)t.Atr,
                    Outcome    = t.Outcome,
                    ExitBar    = t.ExitBar,
                    ExitPrice  = (decimal)t.ExitPrice,
                    PnlPips    = (decimal)t.PnlPips,
                    RrAchieved = (decimal)t.RrAchieved,
                    SeqRepr    = t.SeqRepr,
                    Similarity = (decimal)t.Similarity,
                });
                db.BacktestTrades.AddRange(tradeEntities);
            }

            // 7. Mark completed
            session.Status      = "completed";
            session.CompletedAt = DateTime.UtcNow;
            await db.SaveChangesAsync();

            logger.LogInformation(
                "[BacktestJob] Session {SessionId} completed — {Wins}W/{Losses}L WinRate={WinRate:.2%}",
                sessionId, result.Wins, result.Losses, result.WinRate);
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "[BacktestJob] Session {SessionId} failed", sessionId);
            session.Status       = "failed";
            session.ErrorMessage = ex.Message;
            await db.SaveChangesAsync();
        }
    }
}

// ─── Python response DTO ──────────────────────────────────────────────────────

file record BacktestRunResult(
    int    TotalSignals,
    int    Wins,
    int    Losses,
    int    Breakeven,
    double WinRate,
    double ProfitFactor,
    double SharpeRatio,
    double SortinoRatio,
    double MaxDrawdown,
    double AvgRr,
    double TotalPips,
    List<double>               EquityCurve,
    Dictionary<string, double> StateDistribution,
    string? BestSeqRepr,
    string? WorstSeqRepr,
    List<BacktestTradeResult>? Trades       = null,
    string SlType      = "atr",
    double SlValue     = 1.0,
    string TpType      = "atr",
    double TpValue     = 2.0,
    int    MaxHoldBars = 20
);

file record BacktestTradeResult(
    int    BarIndex,
    string Time,
    string Direction,
    double Entry,
    double Sl,
    double Tp,
    string SlType,
    string TpType,
    double Atr,
    string Outcome,
    int    ExitBar,
    double ExitPrice,
    double PnlPips,
    double RrAchieved,
    string SeqRepr,
    double Similarity
);
