using Microsoft.EntityFrameworkCore;
using TradeOS.Api.Common.Models;
using TradeOS.Api.Infrastructure.Database;
using TradeOS.Api.Modules.Bayesian.Services;
using TradeOS.Api.Modules.Pattern.Models;
using TradeOS.Api.Modules.TradeLog.Models;
using System.Text.Json;

namespace TradeOS.Api.Modules.TradeLog.Services;

public class TradeLogService(TradeOsDbContext db, IBayesianService bayes) : ITradeLogService
{
    public async Task<PagedResult<TradeLogDto>> ListAsync(
        int page, int pageSize, string? instrument, string? outcome, Guid? theoryId = null)
    {
        var query = db.TradeLogs.AsQueryable();
        if (instrument is not null) query = query.Where(t => t.Instrument == instrument);
        if (outcome    is not null) query = query.Where(t => t.Outcome    == outcome);
        if (theoryId   is not null) query = query.Where(t => t.TheoryId   == theoryId.Value);

        var total = await query.CountAsync();
        var items = await query
            .OrderByDescending(t => t.SignalTime)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .Select(t => ToDto(t))
            .ToListAsync();

        return new PagedResult<TradeLogDto>(items, total, page, pageSize);
    }

    public async Task<TradeLogDto?> GetAsync(Guid id)
    {
        var t = await db.TradeLogs.FindAsync(id);
        return t is null ? null : ToDto(t);
    }

    public async Task<TradeLogDto> CreateAsync(TradeLogEntity entity)
    {
        db.TradeLogs.Add(entity);
        await db.SaveChangesAsync();
        return ToDto(entity);
    }

    public async Task<TradeLogDto?> RecordOutcomeAsync(Guid id, RecordOutcomeRequest req)
    {
        await using var tx = await db.Database.BeginTransactionAsync();
        try
        {
            var trade = await db.TradeLogs.FindAsync(id);
            if (trade is null) return null;

            // Update trade fields
            trade.Outcome  = req.Outcome;
            trade.PnlPips  = req.PnlPips;
            trade.RrActual = req.RrActual;
            trade.Notes    = req.Notes;
            trade.ClosedAt = DateTime.UtcNow;

            // Build seqRepr from StateSequence JSON array [0,0,3,2,4] → "S0S0S3S2S4"
            string seqRepr = "";
            try
            {
                var ints = JsonSerializer.Deserialize<List<int>>(trade.StateSequence);
                if (ints is not null)
                    seqRepr = string.Concat(ints.Select(i => $"S{i}"));
            }
            catch { /* parse failed — leave seqRepr as empty string */ }

            var seqHash = BayesianService.ComputeHash(seqRepr);

            // Update Bayesian counter
            await bayes.UpdateCounterAsync(
                trade.TheoryId, seqHash, seqRepr,
                trade.Instrument, trade.Timeframe, req.Outcome);

            // Update pattern_scores for matching Instrument + Timeframe
            var scores = await db.PatternScores
                .Where(s => s.Instrument == trade.Instrument && s.Timeframe == trade.Timeframe)
                .ToListAsync();

            foreach (var score in scores)
            {
                score.TotalAppearances++;

                if (req.Outcome == "WIN")
                    score.ConfirmedWins++;
                else if (req.Outcome == "LOSS")
                    score.ConfirmedLosses++;

                var denominator = score.ConfirmedWins + score.ConfirmedLosses;
                score.WinRate     = denominator > 0
                    ? (decimal)score.ConfirmedWins / denominator
                    : score.WinRate;
                score.LastUpdated = DateTime.UtcNow;
            }

            await db.SaveChangesAsync();
            await tx.CommitAsync();

            return ToDto(trade);
        }
        catch
        {
            await tx.RollbackAsync();
            throw;
        }
    }

    public async Task<object> GetRecapAsync(string? instrument, Guid? theoryId)
    {
        var query = db.TradeLogs.Where(t => t.Outcome != null);
        if (instrument is not null) query = query.Where(t => t.Instrument == instrument);
        if (theoryId   is not null) query = query.Where(t => t.TheoryId   == theoryId);

        var trades = await query.ToListAsync();
        int total  = trades.Count;
        int wins   = trades.Count(t => t.Outcome == "WIN");
        int losses = trades.Count(t => t.Outcome == "LOSS");
        int be     = trades.Count(t => t.Outcome == "BREAK_EVEN");
        decimal totalPips = trades.Sum(t => t.PnlPips ?? 0);

        return new
        {
            Total     = total,
            Wins      = wins,
            Losses    = losses,
            BreakEven = be,
            WinRate   = total > 0 ? Math.Round((decimal)wins / total * 100, 2) : 0,
            TotalPips = totalPips
        };
    }

    public async Task<IEnumerable<TradeLogDto>> GetByTheoryAsync(Guid theoryId, int limit)
        => await db.TradeLogs
            .Where(t => t.TheoryId == theoryId)
            .OrderByDescending(t => t.SignalTime)
            .Take(limit)
            .Select(t => ToDto(t))
            .ToListAsync();

    private static TradeLogDto ToDto(TradeLogEntity t) => new(
        t.Id, t.TheoryId, t.Instrument, t.Timeframe, t.SignalTime,
        t.Direction, t.EntryPrice, t.SlPrice, t.TpPrice,
        t.CompositeScore, t.ConfidencePct, t.PWinAtSignal, t.BayesianSampleN,
        t.StateSequence, t.FactorSnapshot, t.Outcome,
        t.PnlPips, t.RrActual, t.Executed, t.CreatedAt);
}
