using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using TradeOS.Api.Common.Models;
using TradeOS.Api.Modules.Theory.Models;
using TradeOS.Api.Modules.Theory.Services;

namespace TradeOS.Api.Modules.Theory.Controllers;

[ApiController]
[Route("api/theories")]
[Authorize]
public class TheoryController(ITheoryService svc) : ControllerBase
{
    [HttpGet]
    public async Task<ActionResult<ApiResponse<IEnumerable<TheoryDto>>>> List()
        => Ok(ApiResponse<IEnumerable<TheoryDto>>.Ok(await svc.ListAsync()));

    [HttpGet("{id:guid}")]
    public async Task<ActionResult<ApiResponse<object>>> Get(Guid id)
    {
        var t = await svc.GetWithFactorsAsync(id);
        return t is null
            ? NotFound(ApiResponse<object>.Fail("Theory not found"))
            : Ok(ApiResponse<object>.Ok(t));
    }

    [HttpPost]
    public async Task<ActionResult<ApiResponse<TheoryDto>>> Create([FromBody] CreateTheoryRequest req)
    {
        var created = await svc.CreateAsync(req);
        return CreatedAtAction(nameof(Get), new { id = created.Id },
            ApiResponse<TheoryDto>.Ok(created));
    }

    [HttpPut("{id:guid}")]
    public async Task<ActionResult<ApiResponse<TheoryDto>>> Update(
        Guid id, [FromBody] CreateTheoryRequest req)
    {
        var updated = await svc.UpdateAsync(id, req);
        return updated is null
            ? NotFound(ApiResponse<TheoryDto>.Fail("Theory not found"))
            : Ok(ApiResponse<TheoryDto>.Ok(updated));
    }

    [HttpDelete("{id:guid}")]
    public async Task<ActionResult<ApiResponse<bool>>> Delete(Guid id)
    {
        await svc.SoftDeleteAsync(id);
        return Ok(ApiResponse<bool>.Ok(true));
    }

    [HttpGet("{id:guid}/versions")]
    public async Task<ActionResult<ApiResponse<IEnumerable<object>>>> Versions(Guid id)
        => Ok(ApiResponse<IEnumerable<object>>.Ok(await svc.GetVersionsAsync(id)));

    [HttpPost("{id:guid}/rollback/{version:int}")]
    public async Task<ActionResult<ApiResponse<TheoryDto>>> Rollback(Guid id, int version)
    {
        var rolled = await svc.RollbackAsync(id, version);
        return rolled is null
            ? NotFound(ApiResponse<TheoryDto>.Fail("Version not found"))
            : Ok(ApiResponse<TheoryDto>.Ok(rolled));
    }

    [HttpPost("{id:guid}/factors")]
    public async Task<ActionResult<ApiResponse<object>>> AddFactor(
        Guid id, [FromBody] TheoryFactorEntity factor)
    {
        var result = await svc.AddFactorAsync(id, factor);
        return Ok(ApiResponse<object>.Ok(result));
    }

    [HttpPut("{id:guid}/factors/{factorId:guid}")]
    public async Task<ActionResult<ApiResponse<object>>> UpdateFactor(
        Guid id, Guid factorId, [FromBody] TheoryFactorEntity factor)
    {
        var result = await svc.UpdateFactorAsync(id, factorId, factor);
        return Ok(ApiResponse<object>.Ok(result));
    }

    [HttpDelete("{id:guid}/factors/{factorId:guid}")]
    public async Task<ActionResult<ApiResponse<bool>>> RemoveFactor(Guid id, Guid factorId)
    {
        await svc.RemoveFactorAsync(id, factorId);
        return Ok(ApiResponse<bool>.Ok(true));
    }
}
