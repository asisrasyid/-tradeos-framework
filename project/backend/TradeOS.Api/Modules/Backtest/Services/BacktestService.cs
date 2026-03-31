using Hangfire;
using Microsoft.EntityFrameworkCore;
using System.Text.Json;
using TradeOS.Api.Infrastructure.Database;
using TradeOS.Api.Modules.Backtest.Models;

namespace TradeOS.Api.Modules.Backtest.Services;

public class BacktestService(TradeOsDbContext db) : IBacktestService
{
    public async Task<string> QueueAsync(RunBacktestRequest req)
    {
        var paramsDict = new Dictionary<string, object> { ["data_source"] = req.DataSource };
        if (!string.IsNullOrWhiteSpace(req.ParamsJson) && req.ParamsJson != "{}")
        {
            try
            {
                var extra = JsonSerializer.Deserialize<Dictionary<string, object>>(req.ParamsJson);
                if (extra is not null)
                    foreach (var kv in extra) paramsDict[kv.Key] = kv.Value;
            }
            catch { /* ignore malformed params */ }
        }

        var session = new BacktestSessionEntity
        {
            TheoryId      = req.TheoryId,
            TheoryVersion = 1,
            Instrument    = req.Instrument,
            Timeframe     = req.Timeframe,
            DateFrom      = req.DateFrom,
            DateTo        = req.DateTo,
            Params        = JsonSerializer.Serialize(paramsDict),
            Status        = "pending",
            SlType        = req.SlType,
            SlValue       = req.SlValue,
            TpType        = req.TpType,
            TpValue       = req.TpValue,
            MaxHoldBars   = req.MaxHoldBars,
        };
        db.BacktestSessions.Add(session);
        await db.SaveChangesAsync();

        var jobId = BackgroundJob.Enqueue<IBacktestJob>(j => j.RunAsync(session.Id));
        return jobId;
    }

    public async Task<IEnumerable<BacktestSessionDto>> ListSessionsAsync(Guid? theoryId)
    {
        var query = db.BacktestSessions.AsQueryable();
        if (theoryId.HasValue) query = query.Where(s => s.TheoryId == theoryId.Value);

        return await query
            .OrderByDescending(s => s.CreatedAt)
            .Select(s => new BacktestSessionDto(
                s.Id, s.TheoryId, s.Instrument, s.Timeframe,
                s.DateFrom, s.DateTo, s.Status, s.CompletedAt, s.CreatedAt,
                s.SlType, s.SlValue, s.TpType, s.TpValue, s.MaxHoldBars))
            .ToListAsync();
    }

    public async Task<object?> GetResultsAsync(Guid sessionId)
    {
        var session = await db.BacktestSessions.FindAsync(sessionId);
        if (session is null) return null;

        var result = await db.BacktestResults
            .FirstOrDefaultAsync(r => r.SessionId == sessionId);

        return new { Session = session, Result = result };
    }

    public async Task<IEnumerable<BacktestTradeDto>> GetTradesAsync(Guid sessionId)
    {
        return await db.BacktestTrades
            .Where(t => t.SessionId == sessionId)
            .OrderBy(t => t.BarIndex)
            .Select(t => new BacktestTradeDto(
                t.Id, t.SessionId, t.BarIndex, t.Time, t.Direction,
                t.Entry, t.Sl, t.Tp, t.SlType, t.TpType, t.Atr,
                t.Outcome, t.ExitBar, t.ExitPrice, t.PnlPips, t.RrAchieved,
                t.SeqRepr, t.Similarity))
            .ToListAsync();
    }

    public async Task<object> CompareAsync(Guid sessionA, Guid sessionB)
    {
        var a = await db.BacktestResults.FirstOrDefaultAsync(r => r.SessionId == sessionA);
        var b = await db.BacktestResults.FirstOrDefaultAsync(r => r.SessionId == sessionB);
        return new { SessionA = a, SessionB = b };
    }

    public async Task<bool> DeleteAsync(Guid sessionId)
    {
        var session = await db.BacktestSessions.FindAsync(sessionId);
        if (session is null) return false;

        var trades = db.BacktestTrades.Where(t => t.SessionId == sessionId);
        db.BacktestTrades.RemoveRange(trades);

        var result = await db.BacktestResults.FirstOrDefaultAsync(r => r.SessionId == sessionId);
        if (result is not null) db.BacktestResults.Remove(result);

        db.BacktestSessions.Remove(session);
        await db.SaveChangesAsync();
        return true;
    }
}

public interface IBacktestJob
{
    Task RunAsync(Guid sessionId);
}
