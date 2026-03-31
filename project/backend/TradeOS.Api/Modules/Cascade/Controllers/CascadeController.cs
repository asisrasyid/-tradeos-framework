using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using TradeOS.Api.Common.Models;
using TradeOS.Api.Infrastructure.Python;

namespace TradeOS.Api.Modules.Cascade.Controllers;

[ApiController]
[Route("api/cascade")]
[Authorize]
public class CascadeController(
    IPythonClient python,
    ILogger<CascadeController> logger
) : ControllerBase
{
    [HttpPost("start")]
    public async Task<ActionResult<ApiResponse<object>>> Start([FromBody] StartCascadeRequest req)
    {
        logger.LogInformation(
            "[Cascade] Start {Symbol} init={Init} topup={Topup} eval={Eval}s mc={Mc}%",
            req.Symbol, req.InitialBatch, req.TopupBatch, req.EvalInterval,
            req.McLevelPct * 100);

        var result = await python.PostAsync<object>("/python/cascade/start", new
        {
            symbol               = req.Symbol,
            initial_batch        = req.InitialBatch,
            topup_batch          = req.TopupBatch,
            volume               = req.Volume,
            profit_target        = req.ProfitTarget,
            hard_sl_pips         = req.HardSlPips,
            sl_loss_multiplier      = req.SlLossMultiplier,
            max_session_loss_usd    = req.MaxSessionLossUsd,
            max_drawdown_from_peak  = req.MaxDrawdownFromPeak,
            max_positions           = req.MaxPositions,
            eval_interval        = req.EvalInterval,
            mc_level_pct         = req.McLevelPct,
            safety_multiplier    = req.SafetyMultiplier,
            emergency_multiplier = req.EmergencyMultiplier,
        });

        return Ok(ApiResponse<object>.Ok(result ?? new object()));
    }

    [HttpPost("stop")]
    public async Task<ActionResult<ApiResponse<object>>> Stop([FromBody] StopCascadeRequest req)
    {
        var result = await python.PostAsync<object>("/python/cascade/stop",
            new { session_id = req.SessionId });
        return Ok(ApiResponse<object>.Ok(result ?? new object()));
    }

    [HttpGet("status")]
    public async Task<ActionResult<ApiResponse<object>>> Status()
    {
        var result = await python.GetAsync<object>("/python/cascade/status");
        return Ok(ApiResponse<object>.Ok(result ?? new object()));
    }
}

public record StartCascadeRequest(
    string Symbol               = "XAUUSDm",
    int    InitialBatch         = 10,
    int    TopupBatch           = 5,
    double Volume               = 0.01,
    double ProfitTarget         = 2.0,
    double HardSlPips           = 0.0,
    double SlLossMultiplier     = 1.0,   // 1.0 = break-even at 50% winrate; 0 = disabled
    double MaxSessionLossUsd    = 0.0,
    double MaxDrawdownFromPeak  = 0.0,
    int    MaxPositions         = 30,
    int    EvalInterval         = 300,
    double McLevelPct           = 0.10,
    double SafetyMultiplier     = 3.0,
    double EmergencyMultiplier  = 1.5
);

public record StopCascadeRequest(string SessionId);
