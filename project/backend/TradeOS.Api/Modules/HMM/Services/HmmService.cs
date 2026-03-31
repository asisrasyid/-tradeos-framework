using Hangfire;
using Microsoft.EntityFrameworkCore;
using TradeOS.Api.Infrastructure.Database;
using TradeOS.Api.Infrastructure.Python;
using TradeOS.Api.Modules.HMM.Models;

namespace TradeOS.Api.Modules.HMM.Services;

public class HmmService(TradeOsDbContext db, IPythonClient python) : IHmmService
{
    public Task<string> QueueTrainingAsync(TrainHmmRequest req)
    {
        var jobId = BackgroundJob.Enqueue<IHmmTrainingJob>(
            j => j.TrainAsync(req.Instrument, req.Timeframe, req.DateFrom, req.DateTo));
        return Task.FromResult(jobId);
    }

    public async Task<IEnumerable<HmmModelDto>> ListModelsAsync()
        => await db.HmmModels
            .OrderByDescending(m => m.CreatedAt)
            .Select(m => new HmmModelDto(
                m.Id, m.Instrument, m.Timeframe, m.Version,
                m.NStates, m.BicScore, m.TrainingFrom, m.TrainingTo,
                m.NSamples, m.StateLabels, m.IsActive, m.CreatedAt))
            .ToListAsync();

    public async Task<object> GetStateDistributionAsync(Guid modelId)
    {
        var model = await db.HmmModels.FindAsync(modelId);
        return model is null
            ? new { Error = "Model not found" }
            : (object)new { model.StateLabels, model.NStates, model.BicScore };
    }

    public async Task<ClassifyStateResult> ClassifyCurrentStateAsync(
        string instrument, string timeframe, int lookback)
    {
        var result = await python.PostAsync<ClassifyStateResult>(
            "/python/hmm/classify",
            new { instrument, timeframe, lookback });
        return result ?? new ClassifyStateResult(0, "Unknown", "none");
    }

    public async Task<StateSequenceResult> GetStateSequenceAsync(
        string instrument, string timeframe, int length)
    {
        var result = await python.PostAsync<StateSequenceResult>(
            "/python/hmm/sequence",
            new { instrument, timeframe, length });
        return result ?? new StateSequenceResult([], "UNKNOWN", 0, "none");
    }

    public async Task<object> GetStateProfileAsync(string instrument, string timeframe, int recentBars)
    {
        var result = await python.GetAsync<object>(
            $"/python/hmm/state-profile?instrument={instrument}&timeframe={timeframe}&recent_bars={recentBars}");
        return result ?? new { error = "Failed to load state profile" };
    }
}

public interface IHmmTrainingJob
{
    Task TrainAsync(string instrument, string timeframe, DateTime from, DateTime to);
}
