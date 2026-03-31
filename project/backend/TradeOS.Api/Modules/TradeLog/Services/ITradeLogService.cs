using TradeOS.Api.Common.Models;
using TradeOS.Api.Modules.TradeLog.Models;

namespace TradeOS.Api.Modules.TradeLog.Services;

public interface ITradeLogService
{
    Task<PagedResult<TradeLogDto>> ListAsync(int page, int pageSize, string? instrument, string? outcome, Guid? theoryId = null);
    Task<TradeLogDto?>             GetAsync(Guid id);
    Task<TradeLogDto>              CreateAsync(TradeLogEntity entity);
    Task<TradeLogDto?>             RecordOutcomeAsync(Guid id, RecordOutcomeRequest req);
    Task<object>                   GetRecapAsync(string? instrument, Guid? theoryId);
    Task<IEnumerable<TradeLogDto>> GetByTheoryAsync(Guid theoryId, int limit);
}
