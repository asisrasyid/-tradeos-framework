using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using TradeOS.Api.Common.Models;
using TradeOS.Api.Infrastructure.Python;

namespace TradeOS.Api.Modules.Aggressive.Controllers;

/// <summary>
/// Aggressive Layer Trading Engine — no HMM/pattern validation.
/// Opens N concurrent positions; closes any that reach profit target; immediately re-opens.
/// </summary>
[ApiController]
[Route("api/aggressive")]
[Authorize]
public class AggressiveController(
    IPythonClient             python,
    ILogger<AggressiveController> logger
) : ControllerBase
{
    /// <summary>Start an aggressive layer session.</summary>
    [HttpPost("start")]
    public async Task<ActionResult<ApiResponse<object>>> Start([FromBody] StartAggressiveRequest req)
    {
        logger.LogInformation(
            "[Aggressive] Start {Symbol} {Direction} x{Layers} vol={Volume} target={Target}",
            req.Symbol, req.Direction, req.Layers, req.Volume, req.ProfitTarget);

        var result = await python.PostAsync<object>("/python/aggressive/start", new
        {
            symbol                = req.Symbol,
            direction             = req.Direction,
            layers                = req.Layers,
            volume                = req.Volume,
            profit_target         = req.ProfitTarget,
            sl_pips               = req.SlPips,
            tp_pips               = req.TpPips,
            flip_mode             = req.FlipMode,
            flip_percentile       = req.FlipPercentile,
            flip_after            = req.FlipAfter,
            lookback_bars         = req.LookbackBars,
            trend_guided          = req.TrendGuided,
            mc_guard              = req.McGuard,
            mc_level_pct          = req.McLevelPct,
            safety_multiplier     = req.SafetyMultiplier,
            emergency_multiplier  = req.EmergencyMultiplier,
            sl_loss_multiplier      = req.SlLossMultiplier,
            sl_cooldown_sec         = req.SlCooldownSec,
            max_session_loss_usd    = req.MaxSessionLossUsd,
            max_drawdown_from_peak  = req.MaxDrawdownFromPeak,
            hmm_gate_enabled        = req.HmmGateEnabled,
            hmm_cooldown_sec        = req.HmmCooldownSec,
            auto_direction_hmm      = req.AutoDirectionHmm,
            limit_atr_mult          = req.LimitAtrMult,
            pending_expiry_sec      = req.PendingExpirySec,
        });

        return Ok(ApiResponse<object>.Ok(result ?? new object()));
    }

    /// <summary>Stop an aggressive session by session_id.</summary>
    [HttpPost("stop")]
    public async Task<ActionResult<ApiResponse<object>>> Stop([FromBody] StopAggressiveRequest req)
    {
        var result = await python.PostAsync<object>("/python/aggressive/stop",
            new { session_id = req.SessionId });

        return Ok(ApiResponse<object>.Ok(result ?? new object()));
    }

    /// <summary>List all aggressive sessions and their stats.</summary>
    [HttpGet("status")]
    public async Task<ActionResult<ApiResponse<object>>> Status()
    {
        var result = await python.GetAsync<object>("/python/aggressive/status");
        return Ok(ApiResponse<object>.Ok(result ?? new object()));
    }
}

public record StartAggressiveRequest(
    string Symbol                = "XAUUSDm",
    string Direction             = "BUY",    // BUY | SELL | BOTH
    int    Layers                = 10,
    double Volume                = 0.01,
    double ProfitTarget          = 0.5,      // USD profit per position to trigger close
    double SlPips                = 0.0,      // 0 = no broker SL (engine monitors profit)
    double TpPips                = 0.0,      // 0 = use profit_target monitoring only
    // Anti-trap flip settings
    string FlipMode              = "none",   // none | percentile | counter | hybrid
    double FlipPercentile        = 0.80,
    int    FlipAfter             = 3,
    int    LookbackBars          = 20,
    // Cascade merge: trend-guided re-open (EMA M1+M5+M15 — default on)
    bool   TrendGuided           = true,
    // MCGuard — equity protection
    bool   McGuard               = false,
    double McLevelPct            = 0.10,
    double SafetyMultiplier      = 3.0,
    double EmergencyMultiplier   = 1.5,
    // Per-position SL
    double SlLossMultiplier      = 1.0,   // 1.0 = break-even at 50% winrate (recommended); 0 = disabled
    double SlCooldownSec         = 0.0,   // 0 = disabled; N = wait N seconds after SL before reopen
    // Profit Guard
    double MaxSessionLossUsd     = 0.0,   // 0 = disabled; stop if net loss exceeds this
    double MaxDrawdownFromPeak   = 0.0,   // 0 = disabled; stop if profit drops this from peak
    // HMM Gate — danger detection + cooldown (default OFF)
    bool   HmmGateEnabled        = false,
    double HmmCooldownSec        = 60.0,
    bool   AutoDirectionHmm      = false,
    // Limit Order — pending BUY_LIMIT/SELL_LIMIT instead of market (default OFF)
    double LimitAtrMult          = 0.0,   // 0 = disabled; e.g. 0.1 = 10% ATR offset
    double PendingExpirySec      = 15.0   // cancel pending if not filled within N seconds
);

public record StopAggressiveRequest(string SessionId);
