namespace TradeOS.Api.Modules.Bayesian.Models;

public class BayesianCounterEntity
{
    public Guid     Id              { get; set; } = Guid.NewGuid();
    public Guid     TheoryId        { get; set; }
    public string   StateSeqHash    { get; set; } = string.Empty;
    public string   StateSeqRepr    { get; set; } = string.Empty;
    public string   Instrument      { get; set; } = string.Empty;
    public string   Timeframe       { get; set; } = string.Empty;
    public int      Wins            { get; set; }
    public int      Losses          { get; set; }
    public int      Breakeven       { get; set; }
    public int      Total           { get; set; }
    public decimal  PWinCurrent     { get; set; } = 0.5m;
    public string   ConfidenceTier  { get; set; } = "insufficient";
    public DateTime LastUpdated     { get; set; } = DateTime.UtcNow;
}

public record ProbabilityRequest(
    Guid   TheoryId,
    string Instrument,
    string Timeframe,
    string SeqRepr    // "S0S0S3S2S4"
);

public record ProbabilityResult(
    decimal PWin,
    int     Total,
    int     Wins,
    string  ConfidenceTier,
    string  SeqRepr
);

public record BayesianCounterDto(
    Guid     Id,
    Guid     TheoryId,
    string   StateSeqRepr,
    string   Instrument,
    string   Timeframe,
    int      Wins,
    int      Losses,
    int      Breakeven,
    int      Total,
    decimal  PWinCurrent,
    string   ConfidenceTier,
    DateTime LastUpdated
);
