using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using TradeOS.Api.Common.Models;
using TradeOS.Api.Modules.MT5.Models;
using TradeOS.Api.Modules.MT5.Services;

namespace TradeOS.Api.Modules.MT5.Controllers;

[ApiController]
[Route("api/mt5")]
[Authorize]
public class MT5Controller(IMT5Service svc) : ControllerBase
{
    [HttpPost("connect")]
    [AllowAnonymous]
    public async Task<ActionResult<ApiResponse<MT5AccountInfo>>> Connect([FromBody] MT5ConnectRequest req)
        => Ok(ApiResponse<MT5AccountInfo>.Ok(await svc.ConnectAsync(req)));

    [HttpGet("account")]
    public async Task<ActionResult<ApiResponse<MT5AccountInfo>>> Account()
        => Ok(ApiResponse<MT5AccountInfo>.Ok(await svc.GetAccountAsync()));

    [HttpPost("ohlc")]
    public async Task<ActionResult<ApiResponse<MT5OhlcResponse>>> Ohlc([FromBody] MT5OhlcRequest req)
        => Ok(ApiResponse<MT5OhlcResponse>.Ok(await svc.GetOhlcAsync(req.Symbol, req.Timeframe, req.Bars)));

    [HttpPost("order")]
    public async Task<ActionResult<ApiResponse<MT5OrderResult>>> Order([FromBody] MT5OrderRequest req)
        => Ok(ApiResponse<MT5OrderResult>.Ok(await svc.SendOrderAsync(req)));

    [HttpPost("close")]
    public async Task<ActionResult<ApiResponse<MT5CloseResult>>> Close([FromBody] MT5CloseRequest req)
        => Ok(ApiResponse<MT5CloseResult>.Ok(await svc.ClosePositionAsync(req)));

    [HttpGet("positions")]
    public async Task<ActionResult<ApiResponse<List<MT5PositionInfo>>>> Positions()
        => Ok(ApiResponse<List<MT5PositionInfo>>.Ok(await svc.GetPositionsAsync()));

    [HttpPost("close-all")]
    public async Task<ActionResult<ApiResponse<MT5CloseAllResult>>> CloseAll([FromBody] MT5CloseAllRequest req)
        => Ok(ApiResponse<MT5CloseAllResult>.Ok(await svc.CloseAllAsync(req.Filter)));

    [HttpDelete("disconnect")]
    public async Task<ActionResult<ApiResponse<bool>>> Disconnect()
    {
        await svc.DisconnectAsync();
        return Ok(ApiResponse<bool>.Ok(true));
    }
}
