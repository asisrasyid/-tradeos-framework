namespace TradeOS.Api.Modules.Pattern.Models;

public class PatternScoreEntity
{
    public Guid      Id                { get; set; } = Guid.NewGuid();
    public Guid      PatternId         { get; set; }
    public Guid      TheoryId          { get; set; }
    public string    Instrument        { get; set; } = string.Empty;
    public string?   Timeframe         { get; set; }
    public int       TotalAppearances  { get; set; }
    public int       ConfirmedWins     { get; set; }
    public int       ConfirmedLosses   { get; set; }
    public decimal?  WinRate           { get; set; }
    public decimal?  AvgLogProb        { get; set; }
    public DateTime  LastUpdated       { get; set; } = DateTime.UtcNow;
}
