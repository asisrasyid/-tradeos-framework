using Microsoft.EntityFrameworkCore;
using TradeOS.Api.Infrastructure.Database;
using TradeOS.Api.Modules.SmartTradeLog.Models;

namespace TradeOS.Api.Modules.SmartTradeLog.Services;

public class SmartTradeLogService(TradeOsDbContext db) : ISmartTradeLogService
{
    public async Task<Guid> OpenAsync(SmartTradeOpenRequest req)
    {
        var entity = new SmartTradeLogEntity
        {
            SessionId      = req.SessionId,
            Symbol         = req.Symbol,
            Direction      = req.Direction,
            DirectionScore = req.DirectionScore,
            AtrValue       = req.AtrValue,
            Ema20Value     = req.Ema20Value,
            HmmState       = req.HmmState,
            HmmStateLabel  = req.HmmStateLabel,
            HmmConfidence  = req.HmmConfidence,
            ClosePrice     = req.ClosePrice,
            SpreadPips     = req.SpreadPips,
            VoteHmm        = req.VoteHmm,
            VoteEma        = req.VoteEma,
            VoteMomentum   = req.VoteMomentum,
            EntryPrice     = req.EntryPrice,
            TpPrice        = req.TpPrice,
            SlPrice        = req.SlPrice,
            TpAtrMult      = req.TpAtrMult,
            SlAtrMult      = req.SlAtrMult,
            Volume         = req.Volume,
            Mt5Ticket      = req.Mt5Ticket,
            AiEnabled          = req.AiEnabled,
            LlmModel           = req.LlmModel,
            LlmReasoning       = req.LlmReasoning,
            LlmConfidence      = req.LlmConfidence,
            LlmPromptVer       = req.LlmPromptVer,
            LlmLatencyMs       = req.LlmLatencyMs,
            LlmSkipReason      = req.LlmSkipReason,
            EntriesPerDecision = req.EntriesPerDecision,
            OpenedAt       = DateTime.UtcNow,
        };
        db.SmartTradeLogs.Add(entity);
        await db.SaveChangesAsync();
        return entity.Id;
    }

    public async Task<bool> CloseAsync(SmartTradeCloseRequest req)
    {
        var entity = await db.SmartTradeLogs
            .Where(t => t.Mt5Ticket == req.Mt5Ticket && t.ClosedAt == null)
            .FirstOrDefaultAsync();

        if (entity is null) return false;

        entity.ExitPrice   = req.ExitPrice;
        entity.ProfitUsd   = req.ProfitUsd;
        entity.Outcome     = req.Outcome;
        entity.CloseReason = req.CloseReason;
        entity.ClosedAt    = DateTime.UtcNow;
        entity.DurationS   = (int)(DateTime.UtcNow - entity.OpenedAt).TotalSeconds;

        await db.SaveChangesAsync();
        return true;
    }

    public async Task<IEnumerable<SmartTradeLogDto>> ListAsync(
        string? sessionId = null, string? symbol = null, int limit = 200)
    {
        var q = db.SmartTradeLogs.AsQueryable();
        if (sessionId is not null) q = q.Where(t => t.SessionId == sessionId);
        if (symbol    is not null) q = q.Where(t => t.Symbol == symbol);

        return await q
            .OrderByDescending(t => t.OpenedAt)
            .Take(limit)
            .Select(t => new SmartTradeLogDto(
                t.Id, t.SessionId, t.Symbol, t.Direction, t.DirectionScore,
                t.AtrValue, t.HmmState, t.HmmStateLabel, t.HmmConfidence,
                t.VoteHmm, t.VoteEma, t.VoteMomentum,
                t.EntryPrice, t.TpPrice, t.SlPrice,
                t.Mt5Ticket, t.ExitPrice, t.ProfitUsd,
                t.Outcome, t.CloseReason, t.DurationS,
                t.OpenedAt, t.ClosedAt,
                t.AiEnabled, t.LlmModel, t.LlmReasoning, t.LlmConfidence, t.LlmLatencyMs, t.LlmSkipReason))
            .ToListAsync();
    }

    public async Task<SmartTradeStatsDto> StatsAsync(string? sessionId = null)
    {
        var q = db.SmartTradeLogs.AsQueryable();
        if (sessionId is not null) q = q.Where(t => t.SessionId == sessionId);

        var all    = await q.ToListAsync();
        var closed = all.Where(t => t.Outcome != null).ToList();
        var wins   = closed.Count(t => t.Outcome == "WIN");
        var losses = closed.Count(t => t.Outcome == "LOSS");
        var be     = closed.Count(t => t.Outcome == "BE");
        var open   = all.Count(t => t.ClosedAt == null);

        return new SmartTradeStatsDto(
            Total:        all.Count,
            Wins:         wins,
            Losses:       losses,
            BreakEven:    be,
            Open:         open,
            WinRate:      closed.Count > 0 ? Math.Round((double)wins / closed.Count * 100, 1) : 0,
            TotalProfitUsd: Math.Round(closed.Sum(t => t.ProfitUsd ?? 0), 2),
            AvgProfitUsd: closed.Count > 0 ? Math.Round(closed.Average(t => t.ProfitUsd ?? 0), 2) : 0,
            AvgDurationS: closed.Count > 0 ? Math.Round(closed.Average(t => t.DurationS ?? 0), 0) : 0
        );
    }
}
