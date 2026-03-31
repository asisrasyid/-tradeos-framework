using TradeOS.Api.Modules.HMM.Models;

namespace TradeOS.Api.Modules.HMM.Services;

public interface IHmmService
{
    Task<string>                  QueueTrainingAsync(TrainHmmRequest req);
    Task<IEnumerable<HmmModelDto>> ListModelsAsync();
    Task<object>                  GetStateDistributionAsync(Guid modelId);
    Task<ClassifyStateResult>     ClassifyCurrentStateAsync(string instrument, string timeframe, int lookback);
    Task<StateSequenceResult>     GetStateSequenceAsync(string instrument, string timeframe, int length);
    Task<object>                  GetStateProfileAsync(string instrument, string timeframe, int recentBars);
}
