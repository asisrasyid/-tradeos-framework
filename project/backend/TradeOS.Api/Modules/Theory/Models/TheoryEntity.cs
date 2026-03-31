namespace TradeOS.Api.Modules.Theory.Models;

public class TheoryEntity
{
    public Guid        Id             { get; set; } = Guid.NewGuid();
    public string      Name           { get; set; } = string.Empty;
    public string?     Description    { get; set; }
    public string      Instrument     { get; set; } = string.Empty;
    public string      Direction      { get; set; } = string.Empty;   // LONG | SHORT | BOTH
    public int         Threshold      { get; set; } = 10;
    public decimal     MinConfidence  { get; set; } = 60.0m;
    public int         Version        { get; set; } = 1;
    public bool        IsActive       { get; set; } = true;
    public DateTime    CreatedAt      { get; set; } = DateTime.UtcNow;
    public DateTime    UpdatedAt      { get; set; } = DateTime.UtcNow;
    public DateTime?   DeletedAt      { get; set; }

    public ICollection<TheoryFactorEntity> Factors { get; set; } = [];
}

public class TheoryFactorEntity
{
    public Guid     Id             { get; set; } = Guid.NewGuid();
    public Guid     TheoryId       { get; set; }
    public Guid?    PatternId      { get; set; }
    public string   FactorCode     { get; set; } = string.Empty;
    public string   FactorType     { get; set; } = string.Empty;
    public int      DecisionPoint  { get; set; }
    public bool     IsRequired     { get; set; }
    public string?  ConditionLogic { get; set; }
    public string?  Operator       { get; set; }
    public decimal? ThresholdValue { get; set; }
    public string?  Timeframe      { get; set; }
    public int      SortOrder      { get; set; }
    public DateTime CreatedAt      { get; set; } = DateTime.UtcNow;

    public TheoryEntity? Theory { get; set; }
}

public class TheoryVersionEntity
{
    public Guid     Id                 { get; set; } = Guid.NewGuid();
    public Guid     TheoryId           { get; set; }
    public int      VersionNumber      { get; set; }
    public string   Snapshot           { get; set; } = string.Empty;  // JSONB
    public string?  ChangeNotes        { get; set; }
    public decimal? WinRateAtSave      { get; set; }
    public Guid?    BacktestSessionId  { get; set; }
    public DateTime SavedAt            { get; set; } = DateTime.UtcNow;
}

public record CreateTheoryRequest(
    string  Name,
    string? Description,
    string  Instrument,
    string  Direction,
    int     Threshold,
    decimal MinConfidence
);

public record TheoryDto(
    Guid     Id,
    string   Name,
    string?  Description,
    string   Instrument,
    string   Direction,
    int      Threshold,
    decimal  MinConfidence,
    int      Version,
    bool     IsActive,
    DateTime CreatedAt
);
