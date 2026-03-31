using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using TradeOS.Api.Common.Models;
using TradeOS.Api.Modules.Bayesian.Models;
using TradeOS.Api.Modules.Bayesian.Services;

namespace TradeOS.Api.Modules.Bayesian.Controllers;

[ApiController]
[Route("api/bayes")]
[Authorize]
public class BayesianController(IBayesianService svc) : ControllerBase
{
    [HttpGet("probability")]
    public async Task<ActionResult<ApiResponse<ProbabilityResult>>> Probability(
        [FromQuery] Guid theoryId,
        [FromQuery] string instrument,
        [FromQuery] string timeframe,
        [FromQuery] string seqRepr)
        => Ok(ApiResponse<ProbabilityResult>.Ok(
            await svc.GetProbabilityAsync(theoryId, instrument, timeframe, seqRepr)));

    [HttpGet("counters/{theoryId:guid}")]
    public async Task<ActionResult<ApiResponse<IEnumerable<BayesianCounterDto>>>> Counters(Guid theoryId)
        => Ok(ApiResponse<IEnumerable<BayesianCounterDto>>.Ok(
            await svc.GetCountersAsync(theoryId)));

    [HttpGet("top-sequences")]
    public async Task<ActionResult<ApiResponse<IEnumerable<BayesianCounterDto>>>> TopSequences(
        [FromQuery] Guid theoryId,
        [FromQuery] string instrument,
        [FromQuery] int limit = 10)
        => Ok(ApiResponse<IEnumerable<BayesianCounterDto>>.Ok(
            await svc.GetTopSequencesAsync(theoryId, instrument, limit)));
}
