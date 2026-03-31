using System.Text.Json;
using Microsoft.AspNetCore.SignalR;
using Microsoft.EntityFrameworkCore;
using TradeOS.Api.Common.Models;
using TradeOS.Api.Infrastructure.Database;
using TradeOS.Api.Infrastructure.Python;
using TradeOS.Api.Modules.Bayesian.Services;
using TradeOS.Api.Modules.Signal.Hubs;
using TradeOS.Api.Modules.Signal.Models;
using TradeOS.Api.Modules.MT5.Models;
using TradeOS.Api.Modules.TradeLog.Models;
using TradeOS.Api.Modules.TradeLog.Services;

namespace TradeOS.Api.Modules.Signal.Services;

public class SignalService(
    TradeOsDbContext db,
    IPythonClient python,
    ITradeLogService tradeLogs,
    IBayesianService bayesian,
    IHubContext<SignalHub> hub,
    ILogger<SignalService> logger
) : ISignalService
{
    // ── Live / History ────────────────────────────────────────────────────────

    public async Task<IEnumerable<LiveSignal>> GetLiveSignalsAsync()
    {
        var now = DateTime.UtcNow;

        // ── Expiry sweep: mark stale non-expired, non-closed signals as expired ──
        // Expiry windows by timeframe
        var expiryCandidates = await db.TradeLogs
            .Where(t => t.Outcome == null && !t.SignalExpired)
            .ToListAsync();

        var toExpire = expiryCandidates
            .Where(t =>
            {
                var window = t.Timeframe.ToUpperInvariant() switch
                {
                    "M1"  => TimeSpan.FromMinutes(5),
                    "M5"  => TimeSpan.FromMinutes(25),
                    "M15" => TimeSpan.FromHours(1),
                    "H1"  => TimeSpan.FromHours(5),
                    "H4"  => TimeSpan.FromHours(20),
                    "D1"  => TimeSpan.FromDays(5),
                    _     => TimeSpan.FromHours(24),
                };
                return now - t.SignalTime > window;
            })
            .Select(t => t.Id)
            .ToHashSet();

        if (toExpire.Count > 0)
        {
            await db.TradeLogs
                .Where(t => toExpire.Contains(t.Id))
                .ExecuteUpdateAsync(s => s.SetProperty(t => t.SignalExpired, true));
        }

        // ── Query: return non-expired, non-closed signals from last 48h ──
        var cutoff = now.AddHours(-48);
        return await db.TradeLogs
            .Where(t => t.Outcome == null && !t.SignalExpired && t.SignalTime >= cutoff)
            .Join(db.Theories, t => t.TheoryId, th => th.Id,
                (t, th) => new LiveSignal(
                    t.Id, t.TheoryId, th.Name,
                    t.Instrument, t.Timeframe, t.Direction,
                    t.EntryPrice, t.SlPrice, t.TpPrice,
                    t.CompositeScore, t.PWinAtSignal ?? 0.5m,
                    "unknown", t.StateSequence, "SIGNAL", t.SignalTime))
            .ToListAsync();
    }

    public async Task<PagedResult<LiveSignal>> GetHistoryAsync(int page, int pageSize)
    {
        var total = await db.TradeLogs.CountAsync();
        var items = await db.TradeLogs
            .OrderByDescending(t => t.SignalTime)
            .Join(db.Theories, t => t.TheoryId, th => th.Id,
                (t, th) => new LiveSignal(
                    t.Id, t.TheoryId, th.Name,
                    t.Instrument, t.Timeframe, t.Direction,
                    t.EntryPrice, t.SlPrice, t.TpPrice,
                    t.CompositeScore, t.PWinAtSignal ?? 0.5m,
                    "unknown", t.StateSequence, "SIGNAL", t.SignalTime))
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .ToListAsync();

        return new PagedResult<LiveSignal>(items, total, page, pageSize);
    }

    public async Task RecordOutcomeAsync(Guid tradeId, string outcome, decimal? pnlPips, decimal? rrActual)
        => await tradeLogs.RecordOutcomeAsync(tradeId, new RecordOutcomeRequest(outcome, pnlPips, rrActual, null));

    // ── Full Evaluation Pipeline ──────────────────────────────────────────────

    /// <summary>
    /// 9-step pipeline per guide_line.md:
    ///   a) Load theory + factors
    ///   b) Fetch recent OHLC from Python
    ///   c) Extract features → feature matrix
    ///   d) Classify HMM state + decode sequence
    ///   e) Compute C-codes (inject HMM states)
    ///   f) Pattern match score via /python/hmm/sequence
    ///   g) Call sp_evaluate_theory → composite_score + signal_decision
    ///   h) Bayesian lookup → P(WIN)
    ///   i) Insert trade_log + push SignalR if SIGNAL/WATCH
    /// </summary>
    public async Task<EvaluateResult> EvaluateTheoryAsync(
        Guid theoryId, string instrument, string timeframe)
    {
        // ── a) Load theory ────────────────────────────────────────────────
        var theory = await db.Theories
            .Include(t => t.Factors)
            .FirstOrDefaultAsync(t => t.Id == theoryId);

        if (theory is null)
            throw new KeyNotFoundException($"Theory {theoryId} not found");

        logger.LogInformation(
            "[SignalEval] Theory={Theory} {Instrument}/{Timeframe}",
            theory.Name, instrument, timeframe);

        // ── b) Fetch recent OHLC from Python ─────────────────────────────
        var ohlcResp = await python.PostAsync<OhlcFetchResult>(
            "/python/ohlc/fetch",
            new { instrument, timeframe, bars = 300 });

        if (ohlcResp?.Bars is null || ohlcResp.Bars.Count == 0)
        {
            logger.LogWarning("[SignalEval] No OHLC data for {Instrument}/{Timeframe}", instrument, timeframe);
            return new EvaluateResult("SKIP", 0, 0.5m, "", null);
        }

        var ohlcJson = JsonSerializer.Serialize(ohlcResp.Bars);

        // ── c) Extract features ───────────────────────────────────────────
        var featResp = await python.PostAsync<FeatureExtractResult>(
            "/python/features/extract",
            new { instrument, timeframe, ohlc_json = ohlcJson });

        // ── d) Classify HMM state + sequence ─────────────────────────────
        HmmClassifyResult?   classifyResult  = null;
        HmmSequenceResult?   sequenceResult  = null;
        int?                 hmmState        = null;
        string               seqRepr         = "S0";

        try
        {
            classifyResult = await python.PostAsync<HmmClassifyResult>(
                "/python/hmm/classify",
                new { instrument, timeframe, lookback = 100 });

            sequenceResult = await python.PostAsync<HmmSequenceResult>(
                "/python/hmm/sequence",
                new { instrument, timeframe, length = 5 });

            hmmState = classifyResult?.State;
            seqRepr  = sequenceResult?.Repr ?? "S0";
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "[SignalEval] HMM classify/sequence failed — proceeding without HMM state");
        }

        // H4 HMM state (best-effort — skip if not available)
        int? hmmH4State = null;
        try
        {
            var h4Classify = await python.PostAsync<HmmClassifyResult>(
                "/python/hmm/classify",
                new { instrument, timeframe = "H4", lookback = 100 });
            hmmH4State = h4Classify?.State;
        }
        catch { /* H4 HMM is optional */ }

        // ── e) Compute C-codes ────────────────────────────────────────────
        var ccodeResp = await python.PostAsync<CCodCalculateResult>(
            "/python/ccode/calculate",
            new
            {
                instrument,
                timeframe,
                ohlc_json    = ohlcJson,
                hmm_state    = hmmState,
                hmm_h4_state = hmmH4State,
            });

        var ccodes = ccodeResp?.Codes ?? new Dictionary<string, double>();

        // ── f) Pattern match score ────────────────────────────────────────
        double patternMatchScore = 0.0;
        try
        {
            var patternResp = await python.PostAsync<PatternMatchResult>(
                "/python/pattern/match",
                new
                {
                    instrument,
                    timeframe,
                    live_repr = seqRepr,
                    theory_id = theoryId,
                });
            patternMatchScore = patternResp?.MatchScore ?? 0.0;
        }
        catch (Exception ex)
        {
            logger.LogDebug(ex, "[SignalEval] Pattern match skipped");
        }

        // Inject pattern match into ccodes for sp_evaluate_theory
        ccodes["PATTERN_MATCH_SCORE"] = patternMatchScore;

        // ── g) sp_evaluate_theory ─────────────────────────────────────────
        var evalResp = await python.PostAsync<SpEvalResult>(
            "/python/ccode/evaluate",
            new
            {
                theory_id      = theoryId,
                instrument,
                timeframe,
                ccode_snapshot = ccodes,
                seq_repr       = seqRepr,
            });

        // Fallback: compute composite score locally if Python proc not available
        int    compositeScore = evalResp?.CompositeScore ?? _LocalScore(theory.Factors, ccodes);
        string decision       = evalResp?.SignalDecision ?? (compositeScore >= theory.Threshold ? "SIGNAL" : "SKIP");

        // ── h) Bayesian lookup ────────────────────────────────────────────
        var seqHash = BayesianService.ComputeHash(seqRepr);
        var probResult = await bayesian.GetProbabilityAsync(theoryId, instrument, timeframe, seqRepr);
        decimal pWin = probResult.PWin;

        logger.LogInformation(
            "[SignalEval] Score={Score} Decision={Decision} P(WIN)={PWin:.2%} SeqHash={Hash}",
            compositeScore, decision, pWin, seqHash);

        if (decision == "SKIP")
            return new EvaluateResult("SKIP", compositeScore, pWin, seqRepr, null);

        // ── i) Insert trade_log ───────────────────────────────────────────
        var snapshot = new
        {
            ccodes,
            hmm_state      = hmmState,
            hmm_h4_state   = hmmH4State,
            pattern_score  = patternMatchScore,
            theory_factors = theory.Factors.Select(f => new
            {
                f.FactorCode,
                f.DecisionPoint,
                met = ccodes.TryGetValue(f.FactorCode, out var v) && v >= (double)(f.ThresholdValue ?? 0.5m),
            }),
        };

        var tradeLog = new TradeLogEntity
        {
            TheoryId        = theoryId,
            Instrument      = instrument.ToUpperInvariant(),
            Timeframe       = timeframe.ToUpperInvariant(),
            SignalTime      = DateTime.UtcNow,
            Direction       = theory.Direction == "SHORT" ? "SELL" : "BUY",
            CompositeScore  = compositeScore,
            PWinAtSignal    = pWin,
            BayesianSampleN = probResult.Total,
            StateSequence   = JsonSerializer.Serialize(
                sequenceResult?.Sequence ?? new List<int>()),
            FactorSnapshot  = JsonSerializer.Serialize(snapshot),
            HmmModelVersion = classifyResult?.ModelVersion,
            SignalExpired   = false,
            Executed        = false,
        };

        db.TradeLogs.Add(tradeLog);
        await db.SaveChangesAsync();

        // ── Push to SignalR ───────────────────────────────────────────────
        var liveSignal = new LiveSignal(
            tradeLog.Id, theoryId, theory.Name,
            instrument, timeframe, tradeLog.Direction,
            null, null, null,
            compositeScore, pWin,
            probResult.ConfidenceTier,
            seqRepr,
            decision,
            tradeLog.SignalTime);

        await hub.Clients
            .Group($"instrument:{instrument.ToUpperInvariant()}")
            .SendAsync("NewSignal", new SignalHub_NewSignal(liveSignal));

        logger.LogInformation(
            "[SignalEval] TradeLog {Id} inserted — {Decision} pushed via SignalR",
            tradeLog.Id, decision);

        return new EvaluateResult(decision, compositeScore, pWin, seqRepr, tradeLog.Id);
    }

    // ── Ingest pre-computed signal from Python engine ─────────────────────────

    public async Task<Guid> IngestSignalAsync(IngestSignalRequest req)
    {
        if (!Guid.TryParse(req.TheoryId, out var theoryId))
            throw new ArgumentException($"Invalid theory_id: {req.TheoryId}");

        var theory = await db.Theories.FindAsync(theoryId);
        if (theory is null)
            throw new KeyNotFoundException($"Theory {theoryId} not found");

        // Similarity (0–1) mapped to composite score (0–100)
        var compositeScore = (int)Math.Round(req.Similarity * 100);

        var tradeLog = new TradeLogEntity
        {
            TheoryId        = theoryId,
            Instrument      = req.Instrument.ToUpperInvariant(),
            Timeframe       = req.Timeframe.ToUpperInvariant(),
            SignalTime      = DateTime.TryParse(req.SignalTime, out var st) ? st : DateTime.UtcNow,
            Direction       = req.Direction.ToUpperInvariant() == "LONG" ? "BUY" : "SELL",
            EntryPrice      = req.EntryPrice,
            SlPrice         = req.SlPrice,
            TpPrice         = req.TpPrice,
            CompositeScore  = compositeScore,
            PWinAtSignal    = (decimal)req.Similarity,
            StateSequence   = req.SeqRepr,
            FactorSnapshot  = System.Text.Json.JsonSerializer.Serialize(new
            {
                source      = "signal_engine",
                session_id  = req.SessionId,
                similarity  = req.Similarity,
                seq_repr    = req.SeqRepr,
            }),
            SignalExpired   = false,
            Executed        = false,
        };

        db.TradeLogs.Add(tradeLog);
        await db.SaveChangesAsync();

        // ── Auto-execute: place real MT5 order ────────────────────────────────
        if (req.AutoExecute)
        {
            try
            {
                var orderResult = await python.PostAsync<MT5OrderResult>("/python/mt5/order", new
                {
                    symbol    = req.Instrument,
                    action    = tradeLog.Direction,   // "BUY" | "SELL"
                    volume    = req.Volume,
                    sl_price  = (double)req.SlPrice,
                    tp_price  = (double)req.TpPrice,
                    comment   = $"TradeOS:{req.SessionId[..Math.Min(8, req.SessionId.Length)]}",
                });

                if (orderResult?.Success == true)
                {
                    tradeLog.Executed   = true;
                    tradeLog.Mt5Ticket  = orderResult.OrderId;
                    tradeLog.EntryPrice = (decimal)orderResult.Price;
                    await db.SaveChangesAsync();

                    logger.LogInformation(
                        "[SignalIngest] MT5 order placed: ticket={Ticket}  price={Price}  {Direction} {Symbol}",
                        orderResult.OrderId, orderResult.Price, tradeLog.Direction, req.Instrument);
                }
                else
                {
                    logger.LogWarning(
                        "[SignalIngest] MT5 order failed: retcode={Code} {Desc}",
                        orderResult?.Retcode, orderResult?.RetcodeDesc);
                }
            }
            catch (Exception ex)
            {
                logger.LogWarning(ex, "[SignalIngest] MT5 auto-execute error — signal recorded but not executed");
            }
        }

        // Push via SignalR
        var liveSignal = new LiveSignal(
            tradeLog.Id, theoryId, theory.Name,
            req.Instrument, req.Timeframe, tradeLog.Direction,
            tradeLog.EntryPrice, req.SlPrice, req.TpPrice,
            compositeScore, (decimal)req.Similarity,
            "engine", req.SeqRepr, "SIGNAL", tradeLog.SignalTime);

        await hub.Clients
            .Group($"instrument:{req.Instrument.ToUpperInvariant()}")
            .SendAsync("NewSignal", new SignalHub_NewSignal(liveSignal));

        logger.LogInformation(
            "[SignalIngest] TradeLog {Id} — {Direction} {Instrument}/{Timeframe}  entry={Entry}  sim={Sim:.2f}  executed={Exec}",
            tradeLog.Id, tradeLog.Direction, req.Instrument, req.Timeframe,
            tradeLog.EntryPrice, req.Similarity, tradeLog.Executed);

        return tradeLog.Id;
    }

    // ── Local fallback score when sp_evaluate_theory is unavailable ───────────

    private static int _LocalScore(
        IEnumerable<TradeOS.Api.Modules.Theory.Models.TheoryFactorEntity> factors,
        Dictionary<string, double> ccodes)
    {
        int score = 0;
        foreach (var f in factors)
        {
            if (!ccodes.TryGetValue(f.FactorCode, out var val)) continue;
            bool met = f.Operator switch
            {
                ">="  => val >= (double)(f.ThresholdValue ?? 0.5m),
                ">"   => val >  (double)(f.ThresholdValue ?? 0.5m),
                "=="  => Math.Abs(val - (double)(f.ThresholdValue ?? 1m)) < 0.01,
                _     => val >= 0.5,
            };
            if (met) score += f.DecisionPoint;
        }
        return score;
    }
}

// ─── Python response DTOs ─────────────────────────────────────────────────────

file record OhlcFetchResult(List<JsonElement> Bars);
file record FeatureExtractResult(List<JsonElement> Features);
file record HmmClassifyResult(int State, string StateLabel, string ModelVersion);
file record HmmSequenceResult(List<int> Sequence, string Repr, double LogProb, string ModelVersion);
file record CCodCalculateResult(Dictionary<string, double> Codes);
file record PatternMatchResult(double MatchScore, double LogProbRatio, bool IsMatch);
file record SpEvalResult(int CompositeScore, bool ThresholdMet, double PWin, string SignalDecision);
