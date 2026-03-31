using Microsoft.EntityFrameworkCore;
using TradeOS.Api.Infrastructure.Database;
using TradeOS.Api.Infrastructure.Python;
using TradeOS.Api.Modules.MT5.Models;

namespace TradeOS.Api.Infrastructure.Jobs;

/// <summary>
/// Reconciles executed trade_log entries against MT5 deal history.
/// For each executed trade with no outcome:
///   1. Check if position is still open via MT5 positions list
///   2. If closed: fetch the exit deal via /python/mt5/deal-history
///   3. Record WIN/LOSS/BREAK_EVEN based on actual P&amp;L from MT5
///
/// Runs every 60 seconds via Hangfire recurring job.
/// </summary>
public class OutcomePollerJob(
    TradeOsDbContext          db,
    IPythonClient             python,
    ILogger<OutcomePollerJob> logger
)
{
    // Pips per unit profit movement (XAU=10, FX pairs=10000; approximate)
    private const double PipsPerUnit = 10.0;

    public async Task PollAsync()
    {
        // 1. Find executed trades awaiting outcome
        var pending = await db.TradeLogs
            .Where(t => t.Executed && t.Mt5Ticket != null && t.Outcome == null && !t.SignalExpired)
            .ToListAsync();

        if (pending.Count == 0)
            return;

        logger.LogDebug("[OutcomePoller] Checking {N} pending trades", pending.Count);

        // 2. Fetch open positions once
        List<MT5PositionInfo> openPositions;
        try
        {
            openPositions = await python.GetAsync<List<MT5PositionInfo>>("/python/mt5/positions")
                            ?? [];
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "[OutcomePoller] Cannot fetch MT5 positions");
            return;
        }

        var openTickets = openPositions.Select(p => p.Ticket).ToHashSet();
        bool changed = false;

        // 3. Check each pending trade
        foreach (var trade in pending)
        {
            var ticket = trade.Mt5Ticket!.Value;

            if (openTickets.Contains(ticket))
                continue;   // position still open

            // Position is closed — fetch exit deal for actual P&L
            ClosedDealResult? deal = null;
            try
            {
                deal = await python.GetAsync<ClosedDealResult>(
                    "/python/mt5/deal-history",
                    new Dictionary<string, string> { ["ticket"] = ticket.ToString() });
            }
            catch (Exception ex)
            {
                logger.LogWarning(ex, "[OutcomePoller] deal-history failed for ticket {T}", ticket);
            }

            string  outcome;
            decimal? pnlPips = null;

            if (deal != null)
            {
                var profit = deal.Profit + deal.Swap + deal.Commission;
                pnlPips = (decimal)(profit * PipsPerUnit);

                outcome = profit > 0.01
                    ? "WIN"
                    : profit < -0.01
                        ? "LOSS"
                        : "BREAK_EVEN";
            }
            else
            {
                // No history found yet — position may have closed very recently,
                // mark expired and let the next poll find the history
                trade.SignalExpired = true;
                changed = true;
                logger.LogDebug("[OutcomePoller] Ticket {T}: no history yet — marking expired", ticket);
                continue;
            }

            trade.Outcome  = outcome;
            trade.PnlPips  = pnlPips;
            trade.ClosedAt = DateTime.UtcNow;
            changed = true;

            logger.LogInformation(
                "[OutcomePoller] Trade {Id} ticket={Ticket} → {Outcome}  pnl={Pnl:F1} pips",
                trade.Id, ticket, outcome, pnlPips);
        }

        if (changed)
            await db.SaveChangesAsync();
    }
}

// DTO matching Python /python/mt5/deal-history response
file record ClosedDealResult(
    int    Ticket,
    int    PositionId,
    string Symbol,
    string Type,
    double Volume,
    double Price,
    double Profit,
    double Swap,
    double Commission,
    string Time
);
