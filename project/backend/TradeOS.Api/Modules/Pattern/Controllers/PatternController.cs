using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using TradeOS.Api.Common.Models;
using TradeOS.Api.Modules.Pattern.Models;
using TradeOS.Api.Modules.Pattern.Services;

namespace TradeOS.Api.Modules.Pattern.Controllers;

[ApiController]
[Route("api/patterns")]
[Authorize]
public class PatternController(IPatternService svc) : ControllerBase
{
    [HttpGet]
    public async Task<ActionResult<ApiResponse<IEnumerable<PatternDto>>>> List(
        [FromQuery] int page = 1, [FromQuery] int pageSize = 50)
        => Ok(ApiResponse<IEnumerable<PatternDto>>.Ok(await svc.ListAsync(page, pageSize)));

    [HttpGet("{id:guid}")]
    public async Task<ActionResult<ApiResponse<PatternDto>>> Get(Guid id)
    {
        var pattern = await svc.GetAsync(id);
        return pattern is null
            ? NotFound(ApiResponse<PatternDto>.Fail("Pattern not found"))
            : Ok(ApiResponse<PatternDto>.Ok(pattern));
    }

    [HttpPost]
    public async Task<ActionResult<ApiResponse<PatternDto>>> Create([FromBody] CreatePatternRequest req)
    {
        var created = await svc.CreateAsync(req);
        return CreatedAtAction(nameof(Get), new { id = created.Id },
            ApiResponse<PatternDto>.Ok(created));
    }

    [HttpPut("{id:guid}")]
    public async Task<ActionResult<ApiResponse<PatternDto>>> Update(
        Guid id, [FromBody] CreatePatternRequest req)
    {
        var updated = await svc.UpdateAsync(id, req);
        return updated is null
            ? NotFound(ApiResponse<PatternDto>.Fail("Pattern not found"))
            : Ok(ApiResponse<PatternDto>.Ok(updated));
    }

    [HttpDelete("{id:guid}")]
    public async Task<ActionResult<ApiResponse<bool>>> Delete(Guid id)
    {
        await svc.SoftDeleteAsync(id);
        return Ok(ApiResponse<bool>.Ok(true));
    }

    [HttpPost("mine-from-wins")]
    public async Task<ActionResult<ApiResponse<string>>> MineFromWins(
        [FromQuery] string instrument, [FromQuery] string timeframe)
    {
        var jobId = await svc.TriggerPatternMiningAsync(instrument, timeframe);
        return Ok(ApiResponse<string>.Ok(jobId));
    }

    [HttpGet("{id:guid}/scores")]
    public async Task<ActionResult<ApiResponse<object>>> Scores(Guid id)
        => Ok(ApiResponse<object>.Ok(await svc.GetScoresAsync(id)));
}
