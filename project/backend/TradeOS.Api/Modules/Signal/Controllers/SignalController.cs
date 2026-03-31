using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using TradeOS.Api.Common.Models;
using TradeOS.Api.Modules.Signal.Models;
using TradeOS.Api.Modules.Signal.Services;
using System.Text.Json;

namespace TradeOS.Api.Modules.Signal.Controllers;

[ApiController]
[Route("api/signals")]
[Authorize]
public class SignalController(ISignalService svc) : ControllerBase
{
    [HttpGet("live")]
    public async Task<ActionResult<ApiResponse<IEnumerable<LiveSignal>>>> Live()
        => Ok(ApiResponse<IEnumerable<LiveSignal>>.Ok(await svc.GetLiveSignalsAsync()));

    [HttpGet("history")]
    public async Task<ActionResult<ApiResponse<PagedResult<LiveSignal>>>> History(
        [FromQuery] int page = 1, [FromQuery] int pageSize = 50)
        => Ok(ApiResponse<PagedResult<LiveSignal>>.Ok(
            await svc.GetHistoryAsync(page, pageSize)));

    [HttpPost("{id:guid}/outcome")]
    public async Task<ActionResult<ApiResponse<bool>>> RecordOutcome(
        Guid id,
        [FromQuery] string outcome,
        [FromQuery] decimal? pnlPips,
        [FromQuery] decimal? rrActual)
    {
        await svc.RecordOutcomeAsync(id, outcome, pnlPips, rrActual);
        return Ok(ApiResponse<bool>.Ok(true));
    }

    /// <summary>
    /// Trigger full 9-step evaluation pipeline for a theory.
    /// Returns SIGNAL | WATCH | SKIP + composite score + P(WIN).
    /// </summary>
    [HttpPost("evaluate")]
    public async Task<ActionResult<ApiResponse<EvaluateResult>>> Evaluate(
        [FromBody] EvaluateRequest req)
    {
        var result = await svc.EvaluateTheoryAsync(req.TheoryId, req.Instrument, req.Timeframe);
        return Ok(ApiResponse<EvaluateResult>.Ok(result));
    }

    /// <summary>
    /// Ingest a pre-computed signal from Python signal engine.
    /// Called by Python on every matched bar — NOT by frontend directly.
    /// [AllowAnonymous] because this is an internal loopback call from Python sidecar.
    /// </summary>
    [AllowAnonymous]
    [HttpPost("ingest")]
    public async Task<ActionResult<ApiResponse<object>>> Ingest([FromBody] IngestSignalRequest req)
    {
        var tradeLogId = await svc.IngestSignalAsync(req);
        return Ok(ApiResponse<object>.Ok(new { trade_log_id = tradeLogId }));
    }
}

public record EvaluateRequest(Guid TheoryId, string Instrument, string Timeframe);
