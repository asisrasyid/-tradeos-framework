using TradeOS.Api.Modules.Theory.Models;

namespace TradeOS.Api.Modules.Theory.Services;

public interface ITheoryService
{
    Task<IEnumerable<TheoryDto>> ListAsync();
    Task<object?>                GetWithFactorsAsync(Guid id);
    Task<TheoryDto>              CreateAsync(CreateTheoryRequest req);
    Task<TheoryDto?>             UpdateAsync(Guid id, CreateTheoryRequest req);
    Task                         SoftDeleteAsync(Guid id);
    Task<IEnumerable<object>>    GetVersionsAsync(Guid theoryId);
    Task<TheoryDto?>             RollbackAsync(Guid theoryId, int version);
    Task<object>                 AddFactorAsync(Guid theoryId, TheoryFactorEntity factor);
    Task<object>                 UpdateFactorAsync(Guid theoryId, Guid factorId, TheoryFactorEntity factor);
    Task                         RemoveFactorAsync(Guid theoryId, Guid factorId);
}
