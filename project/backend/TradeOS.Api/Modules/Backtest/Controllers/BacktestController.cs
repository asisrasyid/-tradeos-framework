using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using TradeOS.Api.Common.Models;
using TradeOS.Api.Modules.Backtest.Models;
using TradeOS.Api.Modules.Backtest.Services;

namespace TradeOS.Api.Modules.Backtest.Controllers;

[ApiController]
[Route("api/backtest")]
[Authorize]
public class BacktestController(IBacktestService svc) : ControllerBase
{
    [HttpPost("run")]
    public async Task<ActionResult<ApiResponse<string>>> Run([FromBody] RunBacktestRequest req)
    {
        var jobId = await svc.QueueAsync(req);
        return Ok(ApiResponse<string>.Ok(jobId));
    }

    [HttpGet("sessions")]
    public async Task<ActionResult<ApiResponse<IEnumerable<BacktestSessionDto>>>> Sessions(
        [FromQuery] Guid? theoryId = null)
        => Ok(ApiResponse<IEnumerable<BacktestSessionDto>>.Ok(
            await svc.ListSessionsAsync(theoryId)));

    [HttpGet("sessions/{id:guid}/results")]
    public async Task<ActionResult<ApiResponse<object>>> Results(Guid id)
    {
        var result = await svc.GetResultsAsync(id);
        return result is null
            ? NotFound(ApiResponse<object>.Fail("Session not found"))
            : Ok(ApiResponse<object>.Ok(result));
    }

    [HttpGet("sessions/{id:guid}/trades")]
    public async Task<ActionResult<ApiResponse<IEnumerable<BacktestTradeDto>>>> Trades(Guid id)
        => Ok(ApiResponse<IEnumerable<BacktestTradeDto>>.Ok(await svc.GetTradesAsync(id)));

    [HttpGet("compare")]
    public async Task<ActionResult<ApiResponse<object>>> Compare(
        [FromQuery] Guid sessionA, [FromQuery] Guid sessionB)
        => Ok(ApiResponse<object>.Ok(await svc.CompareAsync(sessionA, sessionB)));

    [HttpDelete("sessions/{id:guid}")]
    public async Task<ActionResult<ApiResponse<bool>>> Delete(Guid id)
    {
        var ok = await svc.DeleteAsync(id);
        return ok
            ? Ok(ApiResponse<bool>.Ok(true))
            : NotFound(ApiResponse<bool>.Fail("Session not found"));
    }
}
