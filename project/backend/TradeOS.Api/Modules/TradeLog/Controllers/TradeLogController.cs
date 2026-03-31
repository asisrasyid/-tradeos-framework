using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using TradeOS.Api.Common.Models;
using TradeOS.Api.Modules.TradeLog.Models;
using TradeOS.Api.Modules.TradeLog.Services;

namespace TradeOS.Api.Modules.TradeLog.Controllers;

[ApiController]
[Route("api/trades")]
[Authorize]
public class TradeLogController(ITradeLogService svc) : ControllerBase
{
    [HttpGet]
    public async Task<ActionResult<ApiResponse<PagedResult<TradeLogDto>>>> List(
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 50,
        [FromQuery] string? instrument = null,
        [FromQuery] string? outcome = null)
        => Ok(ApiResponse<PagedResult<TradeLogDto>>.Ok(
            await svc.ListAsync(page, pageSize, instrument, outcome)));

    [HttpGet("{id:guid}")]
    public async Task<ActionResult<ApiResponse<TradeLogDto>>> Get(Guid id)
    {
        var t = await svc.GetAsync(id);
        return t is null
            ? NotFound(ApiResponse<TradeLogDto>.Fail("Trade not found"))
            : Ok(ApiResponse<TradeLogDto>.Ok(t));
    }

    [HttpPost("{id:guid}/outcome")]
    public async Task<ActionResult<ApiResponse<TradeLogDto>>> RecordOutcome(
        Guid id, [FromBody] RecordOutcomeRequest req)
    {
        var updated = await svc.RecordOutcomeAsync(id, req);
        return updated is null
            ? NotFound(ApiResponse<TradeLogDto>.Fail("Trade not found"))
            : Ok(ApiResponse<TradeLogDto>.Ok(updated));
    }

    [HttpGet("recap")]
    public async Task<ActionResult<ApiResponse<object>>> Recap(
        [FromQuery] string? instrument = null,
        [FromQuery] Guid? theoryId = null)
        => Ok(ApiResponse<object>.Ok(await svc.GetRecapAsync(instrument, theoryId)));

    [HttpGet("by-theory/{theoryId:guid}")]
    public async Task<ActionResult<ApiResponse<IEnumerable<TradeLogDto>>>> ByTheory(
        Guid theoryId, [FromQuery] int limit = 100)
        => Ok(ApiResponse<IEnumerable<TradeLogDto>>.Ok(
            await svc.GetByTheoryAsync(theoryId, limit)));
}
