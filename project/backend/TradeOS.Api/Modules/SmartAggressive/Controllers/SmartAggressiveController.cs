using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using TradeOS.Api.Common.Models;
using TradeOS.Api.Infrastructure.Python;
using TradeOS.Api.Modules.SmartTradeLog.Models;
using TradeOS.Api.Modules.SmartTradeLog.Services;

namespace TradeOS.Api.Modules.SmartAggressive.Controllers;

[ApiController]
[Route("api/smart-aggressive")]
[Authorize]
public class SmartAggressiveController(
    IPythonClient               python,
    ISmartTradeLogService       logSvc,
    ILogger<SmartAggressiveController> logger
) : ControllerBase
{
    [HttpPost("start")]
    public async Task<ActionResult<ApiResponse<object>>> Start([FromBody] StartSmartRequest req)
    {
        logger.LogInformation(
            "[Smart] Start {Symbol} layers={Layers} open_per_interval={Opi} eval={Eval}s",
            req.Symbol, req.MaxLayers, req.OpenPerInterval, req.EvalIntervalS);

        var result = await python.PostAsync<object>("/python/smart-aggressive/start", new
        {
            symbol            = req.Symbol,
            max_layers        = req.MaxLayers,
            open_per_interval = req.OpenPerInterval,
            eval_interval_s   = req.EvalIntervalS,
            volume            = req.Volume,
            tp_atr_mult       = req.TpAtrMult,
            sl_atr_mult       = req.SlAtrMult,
            min_atr           = req.MinAtr,
            max_atr           = req.MaxAtr,
            min_confidence    = req.MinConfidence,
            timeframe         = req.Timeframe,
            callback_url      = $"{Request.Scheme}://{Request.Host}/api/smart-aggressive/log",
        });

        return Ok(ApiResponse<object>.Ok(result ?? new object()));
    }

    [HttpPost("stop")]
    public async Task<ActionResult<ApiResponse<object>>> Stop([FromBody] StopSmartRequest req)
    {
        var result = await python.PostAsync<object>("/python/smart-aggressive/stop",
            new { session_id = req.SessionId });
        return Ok(ApiResponse<object>.Ok(result ?? new object()));
    }

    [HttpGet("status")]
    public async Task<ActionResult<ApiResponse<object>>> Status()
    {
        var result = await python.GetAsync<object>("/python/smart-aggressive/status");
        return Ok(ApiResponse<object>.Ok(result ?? new object()));
    }

    // Called by Python engine to log each trade open
    [HttpPost("log/open")]
    [AllowAnonymous]
    public async Task<ActionResult<ApiResponse<object>>> LogOpen([FromBody] SmartTradeOpenRequest req)
    {
        var id = await logSvc.OpenAsync(req);
        return Ok(ApiResponse<object>.Ok(new { log_id = id }));
    }

    // Called by Python engine to log each trade close
    [HttpPost("log/close")]
    [AllowAnonymous]
    public async Task<ActionResult<ApiResponse<object>>> LogClose([FromBody] SmartTradeCloseRequest req)
    {
        var ok = await logSvc.CloseAsync(req);
        return Ok(ApiResponse<object>.Ok(new { updated = ok }));
    }

    // Query trade logs
    [HttpGet("logs")]
    public async Task<ActionResult<ApiResponse<IEnumerable<SmartTradeLogDto>>>> Logs(
        [FromQuery] string? sessionId = null,
        [FromQuery] string? symbol    = null,
        [FromQuery] int     limit     = 200)
    {
        var logs = await logSvc.ListAsync(sessionId, symbol, limit);
        return Ok(ApiResponse<IEnumerable<SmartTradeLogDto>>.Ok(logs));
    }

    // Stats summary
    [HttpGet("stats")]
    public async Task<ActionResult<ApiResponse<SmartTradeStatsDto>>> Stats(
        [FromQuery] string? sessionId = null)
    {
        var stats = await logSvc.StatsAsync(sessionId);
        return Ok(ApiResponse<SmartTradeStatsDto>.Ok(stats));
    }
}

public record StartSmartRequest(
    string Symbol          = "XAUUSDm",
    string Timeframe       = "M15",
    int    MaxLayers       = 10,
    int    OpenPerInterval = 1,
    int    EvalIntervalS   = 30,
    double Volume          = 0.01,
    double TpAtrMult       = 1.0,
    double SlAtrMult       = 0.5,
    double MinAtr          = 0.5,
    double MaxAtr          = 15.0,
    double MinConfidence   = 0.5
);

public record StopSmartRequest(string SessionId);
