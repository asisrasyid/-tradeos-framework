using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using System.Text.Json;
using TradeOS.Api.Common.Models;
using TradeOS.Api.Infrastructure.Database;
using TradeOS.Api.Infrastructure.Python;

namespace TradeOS.Api.Modules.Engine.Controllers;

[ApiController]
[Route("api/engine")]
[Authorize]
public class EngineController(
    TradeOsDbContext   db,
    IPythonClient      python,
    ILogger<EngineController> logger
) : ControllerBase
{
    /// <summary>
    /// Start a live signal engine session for a theory.
    /// Looks up pattern_states from the theory's linked pattern in DB,
    /// then delegates the loop to Python sidecar.
    /// </summary>
    [HttpPost("start")]
    public async Task<ActionResult<ApiResponse<object>>> Start([FromBody] StartEngineRequest req)
    {
        var theory = await db.Theories
            .Include(t => t.Factors)
            .FirstOrDefaultAsync(t => t.Id == req.TheoryId && t.IsActive);

        if (theory is null)
            return NotFound(ApiResponse<object>.Fail($"Theory {req.TheoryId} not found"));

        // Resolve pattern_states from the theory's linked pattern
        var patternStates = new List<int>();
        var patternFactor = theory.Factors.FirstOrDefault(f => f.PatternId.HasValue);
        if (patternFactor?.PatternId != null)
        {
            var pattern = await db.Patterns.FindAsync(patternFactor.PatternId.Value);
            if (pattern?.StateSequence != null)
            {
                try { patternStates = JsonSerializer.Deserialize<List<int>>(pattern.StateSequence) ?? []; }
                catch { /* ignore malformed JSON */ }
            }
        }

        if (patternStates.Count == 0)
            return BadRequest(ApiResponse<object>.Fail("No pattern_states found for this theory — run strategy_init first"));

        var instrument = (req.Instrument ?? theory.Instrument).ToUpperInvariant();
        var timeframe  = (req.Timeframe ?? "H1").ToUpperInvariant();
        var threshold  = (double)(theory.MinConfidence / 100m);
        var sessionId  = Guid.NewGuid().ToString();

        // Build callback URL — Python will POST signals back here
        var callbackUrl = req.CallbackUrl
            ?? $"{Request.Scheme}://{Request.Host}/api/signals/ingest";

        var payload = new
        {
            session_id           = sessionId,
            theory_id            = req.TheoryId.ToString(),
            instrument,
            timeframe,
            pattern_states       = patternStates,
            similarity_threshold = threshold,
            direction            = theory.Direction,
            tp_mult              = 2.0,
            sl_mult              = 1.0,
            auto_execute         = req.AutoExecute,
            volume               = req.Volume,
            callback_url         = callbackUrl,
        };

        logger.LogInformation(
            "[Engine] Starting session {Session} for theory {Theory} {Instrument}/{Timeframe}  pattern={Pattern}",
            sessionId[..8], theory.Name, instrument, timeframe,
            string.Join(",", patternStates));

        var result = await python.PostAsync<object>("/python/signal-engine/start", payload);

        return Ok(ApiResponse<object>.Ok(new
        {
            session_id   = sessionId,
            theory_id    = req.TheoryId,
            theory_name  = theory.Name,
            instrument,
            timeframe,
            pattern_states = patternStates,
            threshold,
            callback_url = callbackUrl,
            python_response = result,
        }));
    }

    /// <summary>Stop a running engine session by session_id.</summary>
    [HttpPost("stop")]
    public async Task<ActionResult<ApiResponse<object>>> Stop([FromBody] StopEngineRequest req)
    {
        var result = await python.PostAsync<object>("/python/signal-engine/stop",
            new { session_id = req.SessionId });

        return Ok(ApiResponse<object>.Ok(result ?? new object()));
    }

    /// <summary>List all running/stopped engine sessions.</summary>
    [HttpGet("status")]
    public async Task<ActionResult<ApiResponse<object>>> Status()
    {
        var result = await python.GetAsync<object>("/python/signal-engine/status");
        return Ok(ApiResponse<object>.Ok(result ?? new object()));
    }

    /// <summary>Return the most recent fired HMM signal for a symbol.</summary>
    [HttpGet("last-signal")]
    public async Task<ActionResult<ApiResponse<object>>> LastSignal([FromQuery] string symbol)
    {
        if (string.IsNullOrWhiteSpace(symbol))
            return BadRequest(ApiResponse<object>.Fail("symbol is required"));

        var result = await python.GetAsync<object>($"/python/signal-engine/last-signal?symbol={Uri.EscapeDataString(symbol.ToUpperInvariant())}");
        return Ok(ApiResponse<object>.Ok(result ?? new { found = false, symbol }));
    }
}

public record StartEngineRequest(
    Guid    TheoryId,
    string? Instrument   = null,
    string? Timeframe    = null,
    string? CallbackUrl  = null,
    bool    AutoExecute  = false,
    double  Volume       = 0.01
);

public record StopEngineRequest(string SessionId);
