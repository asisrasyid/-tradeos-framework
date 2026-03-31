using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using TradeOS.Api.Common.Models;
using TradeOS.Api.Infrastructure.Python;

namespace TradeOS.Api.Modules.Analysis.Controllers;

[ApiController]
[Route("api/analysis")]
[Authorize]
public class AnalysisController(IPythonClient python) : ControllerBase
{
    [HttpPost("multi-tf")]
    public async Task<ActionResult<ApiResponse<object>>> MultiTf([FromBody] MultiTfRequest req)
    {
        var result = await python.PostAsync<object>("/python/analysis/multi-tf", new
        {
            instrument = req.Instrument,
            timeframes = req.Timeframes,
        });
        return Ok(ApiResponse<object>.Ok(result));
    }
}

public record MultiTfRequest(string Instrument, string[] Timeframes);
