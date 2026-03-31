using Microsoft.AspNetCore.SignalR;

namespace TradeOS.Api.Modules.Signal.Hubs;

public class SignalHub : Hub
{
    public const string Endpoint = "/hubs/signals";

    public async Task JoinInstrumentGroup(string instrument)
        => await Groups.AddToGroupAsync(Context.ConnectionId, $"instrument:{instrument}");

    public async Task LeaveInstrumentGroup(string instrument)
        => await Groups.RemoveFromGroupAsync(Context.ConnectionId, $"instrument:{instrument}");
}
