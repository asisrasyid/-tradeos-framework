using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using TradeOS.Api.Common.Models;
using TradeOS.Api.Modules.HMM.Models;
using TradeOS.Api.Modules.HMM.Services;

namespace TradeOS.Api.Modules.HMM.Controllers;

[ApiController]
[Route("api/hmm")]
[Authorize]
public class HmmController(IHmmService svc) : ControllerBase
{
    [HttpPost("train")]
    public async Task<ActionResult<ApiResponse<string>>> Train([FromBody] TrainHmmRequest req)
    {
        var jobId = await svc.QueueTrainingAsync(req);
        return Ok(ApiResponse<string>.Ok(jobId));
    }

    [HttpGet("models")]
    public async Task<ActionResult<ApiResponse<IEnumerable<HmmModelDto>>>> ListModels()
        => Ok(ApiResponse<IEnumerable<HmmModelDto>>.Ok(await svc.ListModelsAsync()));

    [HttpGet("models/{id:guid}/states")]
    public async Task<ActionResult<ApiResponse<object>>> States(Guid id)
        => Ok(ApiResponse<object>.Ok(await svc.GetStateDistributionAsync(id)));

    [HttpGet("classify")]
    public async Task<ActionResult<ApiResponse<ClassifyStateResult>>> Classify(
        [FromQuery] string instrument, [FromQuery] string timeframe,
        [FromQuery] int lookback = 20)
        => Ok(ApiResponse<ClassifyStateResult>.Ok(
            await svc.ClassifyCurrentStateAsync(instrument, timeframe, lookback)));

    [HttpGet("sequence")]
    public async Task<ActionResult<ApiResponse<StateSequenceResult>>> Sequence(
        [FromQuery] string instrument, [FromQuery] string timeframe,
        [FromQuery] int length = 5)
        => Ok(ApiResponse<StateSequenceResult>.Ok(
            await svc.GetStateSequenceAsync(instrument, timeframe, length)));

    [HttpGet("state-profile")]
    public async Task<ActionResult<ApiResponse<object>>> StateProfile(
        [FromQuery] string instrument, [FromQuery] string timeframe,
        [FromQuery] int recentBars = 60)
        => Ok(ApiResponse<object>.Ok(
            await svc.GetStateProfileAsync(instrument, timeframe, recentBars)));
}
