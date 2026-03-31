using TradeOS.Api.Modules.Pattern.Models;

namespace TradeOS.Api.Modules.Pattern.Services;

public interface IPatternService
{
    Task<IEnumerable<PatternDto>> ListAsync(int page, int pageSize);
    Task<PatternDto?>             GetAsync(Guid id);
    Task<PatternDto>              CreateAsync(CreatePatternRequest req);
    Task<PatternDto?>             UpdateAsync(Guid id, CreatePatternRequest req);
    Task                          SoftDeleteAsync(Guid id);
    Task<string>                  TriggerPatternMiningAsync(string instrument, string timeframe);
    Task<object>                  GetScoresAsync(Guid patternId);
}
