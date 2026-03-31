using System.ComponentModel.DataAnnotations.Schema;

namespace TradeOS.Api.Modules.Pattern.Models;

public class PatternEntity
{
    public Guid        Id                { get; set; } = Guid.NewGuid();
    public string      Code              { get; set; } = string.Empty;
    public string      Name              { get; set; } = string.Empty;
    public string?     Description       { get; set; }
    public string      PatternType       { get; set; } = string.Empty;
    public string?     Timeframe         { get; set; }
    public string?     StateSequence     { get; set; }   // JSONB
    public string?     StateSeqRepr      { get; set; }
    public string?     HmmModelVersion   { get; set; }
    public string      Source            { get; set; } = "manual";
    public int         Version           { get; set; } = 1;
    public bool        IsActive          { get; set; } = true;
    public DateTime    CreatedAt         { get; set; } = DateTime.UtcNow;
    public DateTime    UpdatedAt         { get; set; } = DateTime.UtcNow;
    public DateTime?   DeletedAt         { get; set; }
}

public record CreatePatternRequest(
    string Code,
    string Name,
    string? Description,
    string PatternType,
    string? Timeframe,
    string? StateSequence,
    string? StateSeqRepr
);

public record PatternDto(
    Guid     Id,
    string   Code,
    string   Name,
    string?  Description,
    string   PatternType,
    string?  Timeframe,
    string?  StateSeqRepr,
    string?  HmmModelVersion,
    string   Source,
    int      Version,
    bool     IsActive,
    DateTime CreatedAt
);
