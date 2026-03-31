using Microsoft.EntityFrameworkCore;
using System.Text.Json;
using TradeOS.Api.Infrastructure.Database;
using TradeOS.Api.Modules.Theory.Models;

namespace TradeOS.Api.Modules.Theory.Services;

public class TheoryService(TradeOsDbContext db) : ITheoryService
{
    public async Task<IEnumerable<TheoryDto>> ListAsync()
        => await db.Theories
            .OrderByDescending(t => t.CreatedAt)
            .Select(t => ToDto(t))
            .ToListAsync();

    public async Task<object?> GetWithFactorsAsync(Guid id)
    {
        var t = await db.Theories
            .Include(x => x.Factors)
            .FirstOrDefaultAsync(x => x.Id == id);
        if (t is null) return null;
        return new
        {
            Theory  = ToDto(t),
            Factors = t.Factors.Select(f => new
            {
                f.Id, f.PatternId, f.FactorCode, f.FactorType,
                f.DecisionPoint, f.IsRequired, f.ConditionLogic,
                f.Operator, f.ThresholdValue, f.Timeframe, f.SortOrder, f.CreatedAt
            })
        };
    }

    public async Task<TheoryDto> CreateAsync(CreateTheoryRequest req)
    {
        var entity = new TheoryEntity
        {
            Name          = req.Name,
            Description   = req.Description,
            Instrument    = req.Instrument,
            Direction     = req.Direction,
            Threshold     = req.Threshold,
            MinConfidence = req.MinConfidence
        };
        db.Theories.Add(entity);
        await db.SaveChangesAsync();
        return ToDto(entity);
    }

    public async Task<TheoryDto?> UpdateAsync(Guid id, CreateTheoryRequest req)
    {
        var entity = await db.Theories.Include(t => t.Factors).FirstOrDefaultAsync(t => t.Id == id);
        if (entity is null) return null;

        // Save version snapshot before update
        var snapshot = JsonSerializer.Serialize(new
        {
            entity.Name, entity.Description, entity.Instrument,
            entity.Direction, entity.Threshold, entity.MinConfidence,
            Factors = entity.Factors.Select(f => new {
                f.Id, f.FactorCode, f.FactorType, f.DecisionPoint,
                f.IsRequired, f.Operator, f.ThresholdValue, f.SortOrder
            })
        });

        db.TheoryVersions.Add(new TheoryVersionEntity
        {
            TheoryId      = entity.Id,
            VersionNumber = entity.Version,
            Snapshot      = snapshot,
            ChangeNotes   = "Auto-saved before update"
        });

        entity.Name          = req.Name;
        entity.Description   = req.Description;
        entity.Instrument    = req.Instrument;
        entity.Direction     = req.Direction;
        entity.Threshold     = req.Threshold;
        entity.MinConfidence = req.MinConfidence;
        entity.Version      += 1;
        entity.UpdatedAt     = DateTime.UtcNow;

        await db.SaveChangesAsync();
        return ToDto(entity);
    }

    public async Task SoftDeleteAsync(Guid id)
    {
        var entity = await db.Theories.FindAsync(id);
        if (entity is null) return;
        entity.DeletedAt = DateTime.UtcNow;
        entity.IsActive  = false;
        await db.SaveChangesAsync();
    }

    public async Task<IEnumerable<object>> GetVersionsAsync(Guid theoryId)
        => await db.TheoryVersions
            .Where(v => v.TheoryId == theoryId)
            .OrderByDescending(v => v.VersionNumber)
            .Select(v => (object)new { v.Id, v.VersionNumber, v.ChangeNotes, v.WinRateAtSave, v.SavedAt })
            .ToListAsync();

    public async Task<TheoryDto?> RollbackAsync(Guid theoryId, int version)
    {
        // 1. Load entity with Factors
        var entity = await db.Theories
            .Include(t => t.Factors)
            .FirstOrDefaultAsync(t => t.Id == theoryId);
        if (entity is null) return null;

        // 2. Save CURRENT state as a new version before overwriting
        var currentSnapshot = JsonSerializer.Serialize(new
        {
            entity.Name, entity.Description, entity.Instrument,
            entity.Direction, entity.Threshold, entity.MinConfidence,
            Factors = entity.Factors.Select(f => new {
                f.Id, f.FactorCode, f.FactorType, f.DecisionPoint,
                f.IsRequired, f.Operator, f.ThresholdValue, f.SortOrder
            })
        });

        db.TheoryVersions.Add(new TheoryVersionEntity
        {
            TheoryId      = entity.Id,
            VersionNumber = entity.Version,
            Snapshot      = currentSnapshot,
            ChangeNotes   = $"Auto-saved before rollback to v{version}"
        });

        // 3. Load the target version snapshot
        var ver = await db.TheoryVersions
            .FirstOrDefaultAsync(v => v.TheoryId == theoryId && v.VersionNumber == version);
        if (ver is null) return null;

        // 4. Restore fields from snapshot
        var snap = JsonSerializer.Deserialize<JsonElement>(ver.Snapshot);
        entity.Name          = snap.GetProperty("Name").GetString() ?? entity.Name;
        entity.Description   = snap.GetProperty("Description").GetString();
        entity.Threshold     = snap.GetProperty("Threshold").GetInt32();
        entity.MinConfidence = snap.GetProperty("MinConfidence").GetDecimal();

        // 5. Increment version
        entity.Version  += 1;
        entity.UpdatedAt = DateTime.UtcNow;

        await db.SaveChangesAsync();
        return ToDto(entity);
    }

    public async Task<object> AddFactorAsync(Guid theoryId, TheoryFactorEntity factor)
    {
        factor.TheoryId  = theoryId;
        factor.CreatedAt = DateTime.UtcNow;
        db.TheoryFactors.Add(factor);
        await db.SaveChangesAsync();
        return factor;
    }

    public async Task<object> UpdateFactorAsync(Guid theoryId, Guid factorId, TheoryFactorEntity factor)
    {
        var existing = await db.TheoryFactors
            .FirstOrDefaultAsync(f => f.Id == factorId && f.TheoryId == theoryId);
        if (existing is null) return new { Error = "Factor not found" };

        existing.FactorCode     = factor.FactorCode;
        existing.FactorType     = factor.FactorType;
        existing.DecisionPoint  = factor.DecisionPoint;
        existing.IsRequired     = factor.IsRequired;
        existing.ConditionLogic = factor.ConditionLogic;
        existing.Operator       = factor.Operator;
        existing.ThresholdValue = factor.ThresholdValue;
        existing.Timeframe      = factor.Timeframe;
        existing.SortOrder      = factor.SortOrder;

        await db.SaveChangesAsync();
        return existing;
    }

    public async Task RemoveFactorAsync(Guid theoryId, Guid factorId)
    {
        var factor = await db.TheoryFactors
            .FirstOrDefaultAsync(f => f.Id == factorId && f.TheoryId == theoryId);
        if (factor is null) return;
        db.TheoryFactors.Remove(factor);
        await db.SaveChangesAsync();
    }

    private static TheoryDto ToDto(TheoryEntity e) => new(
        e.Id, e.Name, e.Description, e.Instrument,
        e.Direction, e.Threshold, e.MinConfidence,
        e.Version, e.IsActive, e.CreatedAt);
}
