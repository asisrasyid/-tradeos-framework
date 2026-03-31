using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using TradeOS.Api.Infrastructure.Database;
using TradeOS.Api.Infrastructure.Python;
using TradeOS.Api.Modules.HMM.Models;
using TradeOS.Api.Modules.HMM.Services;

namespace TradeOS.Api.Infrastructure.Jobs;

/// <summary>
/// Hangfire background job: fetch OHLC → train HMM → persist model → deactivate old models.
/// Implements IHmmTrainingJob so HmmService can enqueue it by interface.
/// </summary>
public class HmmTrainingJob(
    IPythonClient python,
    TradeOsDbContext db,
    ILogger<HmmTrainingJob> logger
) : IHmmTrainingJob
{
    public async Task TrainAsync(
        string instrument,
        string timeframe,
        DateTime from,
        DateTime to)
    {
        logger.LogInformation(
            "[HmmTrainingJob] START {Instrument}/{Timeframe} {From:yyyy-MM-dd}→{To:yyyy-MM-dd}",
            instrument, timeframe, from, to);

        // ── Step 1: Train via Python ────────────────────────────────────────
        var trainReq = new
        {
            instrument,
            timeframe,
            date_from = from.ToString("yyyy-MM-dd"),
            date_to   = to.ToString("yyyy-MM-dd"),
        };

        var trainResp = await python.PostAsync<HmmTrainResponse>(
            "/python/hmm/train", trainReq);

        if (trainResp is null)
            throw new InvalidOperationException(
                $"[HmmTrainingJob] Python /python/hmm/train returned null for {instrument}/{timeframe}");

        logger.LogInformation(
            "[HmmTrainingJob] Python training complete: K={K} BIC={Bic:.2f} N={N} version={Ver}",
            trainResp.NStates, trainResp.BicScore, trainResp.NSamples, trainResp.Version);

        // ── Step 2: Decode pickles from base64 ────────────────────────────
        byte[] modelBytes  = Convert.FromBase64String(trainResp.ModelPickleB64);
        byte[] scalerBytes = Convert.FromBase64String(trainResp.ScalerPickleB64);

        // ── Step 3: Deactivate old models (bypass soft-delete query filter) ─
        await db.HmmModels
            .IgnoreQueryFilters()
            .Where(m =>
                m.Instrument == instrument.ToUpperInvariant() &&
                m.Timeframe  == timeframe.ToUpperInvariant() &&
                m.IsActive)
            .ExecuteUpdateAsync(s => s.SetProperty(m => m.IsActive, false));

        logger.LogInformation(
            "[HmmTrainingJob] Deactivated old models for {Instrument}/{Timeframe}",
            instrument, timeframe);

        // ── Step 4: Persist new model ──────────────────────────────────────
        var entity = new HmmModelEntity
        {
            Instrument   = instrument.ToUpperInvariant(),
            Timeframe    = timeframe.ToUpperInvariant(),
            Version      = trainResp.Version,
            NStates      = trainResp.NStates,
            BicScore     = (double?)trainResp.BicScore,
            NSamples     = trainResp.NSamples,
            ModelPickle  = modelBytes,
            ScalerPickle = scalerBytes,
            StateLabels  = trainResp.StateLabels is not null
                ? JsonSerializer.Serialize(trainResp.StateLabels)
                : null,
            FeatureNames = JsonSerializer.Serialize(new[]
            {
                "ATR_pct", "momentum_z", "swing_prox",
                "body_dom", "htf_slope", "liq_prox",
            }),
            TrainingFrom = DateTime.SpecifyKind(from, DateTimeKind.Utc),
            TrainingTo   = DateTime.SpecifyKind(to,   DateTimeKind.Utc),
            IsActive     = true,
            CreatedAt    = DateTime.UtcNow,
        };

        db.HmmModels.Add(entity);
        await db.SaveChangesAsync();

        logger.LogInformation(
            "[HmmTrainingJob] DONE — model {Id} saved for {Instrument}/{Timeframe}",
            entity.Id, instrument, timeframe);
    }
}

// ─── Python response DTO ──────────────────────────────────────────────────────

/// <summary>Mirrors Python HmmTrainResponse schema from /python/hmm/train.</summary>
public record HmmTrainResponse(
    string                     Version,
    int                        NStates,
    decimal                     BicScore,
    int                        NSamples,
    string                     ModelPickleB64,
    string                     ScalerPickleB64,
    Dictionary<string, string>? StateLabels
);
