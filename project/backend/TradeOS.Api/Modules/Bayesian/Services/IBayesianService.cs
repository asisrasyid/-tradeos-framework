using TradeOS.Api.Modules.Bayesian.Models;

namespace TradeOS.Api.Modules.Bayesian.Services;

public interface IBayesianService
{
    Task<ProbabilityResult>              GetProbabilityAsync(Guid theoryId, string instrument, string timeframe, string seqRepr);
    Task<IEnumerable<BayesianCounterDto>> GetCountersAsync(Guid theoryId);
    Task<IEnumerable<BayesianCounterDto>> GetTopSequencesAsync(Guid theoryId, string instrument, int limit);
    Task<ProbabilityResult>              UpdateCounterAsync(Guid theoryId, string seqHash, string seqRepr, string instrument, string timeframe, string outcome);
}
