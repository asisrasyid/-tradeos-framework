using System.Security.Cryptography;
using System.Text;
using Dapper;
using Microsoft.EntityFrameworkCore;
using Npgsql;
using TradeOS.Api.Infrastructure.Database;
using TradeOS.Api.Modules.Bayesian.Models;

namespace TradeOS.Api.Modules.Bayesian.Services;

public class BayesianService(TradeOsDbContext db, IConfiguration config) : IBayesianService
{
    private NpgsqlConnection CreateConnection() =>
        new(config.GetConnectionString("Default"));

    public async Task<ProbabilityResult> GetProbabilityAsync(
        Guid theoryId, string instrument, string timeframe, string seqRepr)
    {
        var hash = ComputeHash(seqRepr);
        var counter = await db.BayesianCounters
            .FirstOrDefaultAsync(c =>
                c.TheoryId       == theoryId &&
                c.StateSeqHash   == hash &&
                c.Instrument     == instrument &&
                c.Timeframe      == timeframe);

        if (counter is null)
            return new ProbabilityResult(0.5m, 0, 0, "insufficient", seqRepr);

        decimal pWin = (counter.Wins + 1m) / (counter.Total + 2m);
        return new ProbabilityResult(pWin, counter.Total, counter.Wins, counter.ConfidenceTier, seqRepr);
    }

    public async Task<IEnumerable<BayesianCounterDto>> GetCountersAsync(Guid theoryId)
        => await db.BayesianCounters
            .Where(c => c.TheoryId == theoryId)
            .OrderByDescending(c => c.Total)
            .Select(c => ToDto(c))
            .ToListAsync();

    public async Task<IEnumerable<BayesianCounterDto>> GetTopSequencesAsync(
        Guid theoryId, string instrument, int limit)
        => await db.BayesianCounters
            .Where(c => c.TheoryId == theoryId && c.Instrument == instrument && c.Total >= 10)
            .OrderByDescending(c => c.PWinCurrent)
            .Take(limit)
            .Select(c => ToDto(c))
            .ToListAsync();

    public async Task<ProbabilityResult> UpdateCounterAsync(
        Guid theoryId, string seqHash, string seqRepr,
        string instrument, string timeframe, string outcome)
    {
        using var conn = CreateConnection();
        var row = await conn.QuerySingleAsync<dynamic>(
            "SELECT * FROM fn_update_bayesian_counter(@theory_id, @seq_hash, @seq_repr, @instrument, @timeframe, @outcome)",
            new { theory_id = theoryId, seq_hash = seqHash, seq_repr = seqRepr,
                  instrument, timeframe, outcome });

        return new ProbabilityResult(
            (decimal)row.p_win,
            (int)row.total_samples,
            (int)row.wins,
            (string)row.confidence_tier,
            seqRepr);
    }

    public static string ComputeHash(string seqRepr)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(seqRepr));
        return Convert.ToHexString(bytes)[..16].ToLower();
    }

    private static BayesianCounterDto ToDto(BayesianCounterEntity c) => new(
        c.Id, c.TheoryId, c.StateSeqRepr, c.Instrument, c.Timeframe,
        c.Wins, c.Losses, c.Breakeven, c.Total,
        c.PWinCurrent, c.ConfidenceTier, c.LastUpdated);
}
