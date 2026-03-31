using Hangfire;
using Microsoft.EntityFrameworkCore;
using TradeOS.Api.Infrastructure.Database;
using TradeOS.Api.Modules.Pattern.Models;

namespace TradeOS.Api.Modules.Pattern.Services;

public class PatternService(TradeOsDbContext db) : IPatternService
{
    public async Task<IEnumerable<PatternDto>> ListAsync(int page, int pageSize)
    {
        return await db.Patterns
            .Where(p => p.DeletedAt == null)
            .OrderByDescending(p => p.CreatedAt)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .Select(p => ToDto(p))
            .ToListAsync();
    }

    public async Task<PatternDto?> GetAsync(Guid id)
    {
        var e = await db.Patterns.FindAsync(id);
        return e is null ? null : ToDto(e);
    }

    public async Task<PatternDto> CreateAsync(CreatePatternRequest req)
    {
        // Upsert by code — update existing instead of throwing duplicate key
        var existing = await db.Patterns
            .FirstOrDefaultAsync(p => p.Code == req.Code);

        if (existing is not null)
        {
            existing.Name          = req.Name;
            existing.Description   = req.Description;
            existing.PatternType   = req.PatternType;
            existing.Timeframe     = req.Timeframe;
            existing.StateSequence = req.StateSequence;
            existing.StateSeqRepr  = req.StateSeqRepr;
            existing.UpdatedAt     = DateTime.UtcNow;
            existing.IsActive      = true;
            await db.SaveChangesAsync();
            return ToDto(existing);
        }

        var entity = new PatternEntity
        {
            Code            = req.Code,
            Name            = req.Name,
            Description     = req.Description,
            PatternType     = req.PatternType,
            Timeframe       = req.Timeframe,
            StateSequence   = req.StateSequence,
            StateSeqRepr    = req.StateSeqRepr
        };
        db.Patterns.Add(entity);
        await db.SaveChangesAsync();
        return ToDto(entity);
    }

    public async Task<PatternDto?> UpdateAsync(Guid id, CreatePatternRequest req)
    {
        var entity = await db.Patterns.FindAsync(id);
        if (entity is null) return null;

        entity.Name          = req.Name;
        entity.Description   = req.Description;
        entity.PatternType   = req.PatternType;
        entity.Timeframe     = req.Timeframe;
        entity.StateSequence = req.StateSequence;
        entity.StateSeqRepr  = req.StateSeqRepr;
        entity.UpdatedAt     = DateTime.UtcNow;

        await db.SaveChangesAsync();
        return ToDto(entity);
    }

    public async Task SoftDeleteAsync(Guid id)
    {
        var entity = await db.Patterns.FindAsync(id);
        if (entity is null) return;
        entity.DeletedAt = DateTime.UtcNow;
        entity.IsActive  = false;
        await db.SaveChangesAsync();
    }

    public Task<string> TriggerPatternMiningAsync(string instrument, string timeframe)
    {
        var jobId = BackgroundJob.Enqueue<IPatternMiningJob>(
            j => j.MineFromWinsAsync(instrument, timeframe));
        return Task.FromResult(jobId);
    }

    public async Task<object> GetScoresAsync(Guid patternId)
    {
        var scores = await db.PatternScores
            .Where(s => s.PatternId == patternId)
            .Select(s => new
            {
                s.Instrument,
                s.Timeframe,
                s.TotalAppearances,
                s.ConfirmedWins,
                s.ConfirmedLosses,
                s.WinRate,
                s.AvgLogProb,
                s.LastUpdated
            })
            .ToListAsync();
        return scores;
    }

    private static PatternDto ToDto(PatternEntity e) => new(
        e.Id, e.Code, e.Name, e.Description, e.PatternType,
        e.Timeframe, e.StateSeqRepr, e.HmmModelVersion,
        e.Source, e.Version, e.IsActive, e.CreatedAt);
}

// Hangfire job interface for pattern mining
public interface IPatternMiningJob
{
    Task MineFromWinsAsync(string instrument, string timeframe);
}
