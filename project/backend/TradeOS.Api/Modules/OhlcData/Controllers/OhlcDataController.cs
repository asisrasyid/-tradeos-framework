using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using TradeOS.Api.Common.Models;
using TradeOS.Api.Infrastructure.Python;

namespace TradeOS.Api.Modules.OhlcData.Controllers;

[ApiController]
[Route("api/ohlc-data")]
[Authorize]
public class OhlcDataController(IPythonClient python) : ControllerBase
{
    /// <summary>Return sync status for all instrument/timeframe pairs.</summary>
    [HttpGet("status")]
    public async Task<ActionResult<ApiResponse<object>>> Status()
    {
        var result = await python.GetAsync<object>("/python/ohlc-data/status");
        return Ok(ApiResponse<object>.Ok(result ?? new object()));
    }

    /// <summary>Trigger manual OHLC sync. Body optional — omit to sync all.</summary>
    [HttpPost("sync")]
    public async Task<ActionResult<ApiResponse<object>>> Sync([FromBody] ManualSyncRequest? req = null)
    {
        var payload = new
        {
            instrument = req?.Instrument,
            timeframe  = req?.Timeframe,
        };
        var result = await python.PostAsync<object>("/python/ohlc-data/sync", payload);
        return Ok(ApiResponse<object>.Ok(result ?? new object()));
    }
}

public record ManualSyncRequest(string? Instrument = null, string? Timeframe = null);
