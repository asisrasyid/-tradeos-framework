namespace TradeOS.Api.Modules.HMM.Models;

public class HmmModelEntity
{
    public Guid     Id            { get; set; } = Guid.NewGuid();
    public string   Instrument    { get; set; } = string.Empty;
    public string   Timeframe     { get; set; } = string.Empty;
    public string   Version       { get; set; } = string.Empty;
    public int      NStates       { get; set; }
    public double?  BicScore      { get; set; }   // double precision in DB
    public DateTime TrainingFrom  { get; set; }
    public DateTime TrainingTo    { get; set; }
    public int      NSamples      { get; set; }
    public byte[]   ModelPickle   { get; set; } = [];
    public byte[]   ScalerPickle  { get; set; } = [];
    public string?  StateLabels   { get; set; }   // JSONB
    public string?  FeatureNames  { get; set; }   // JSONB
    public bool     IsActive      { get; set; } = true;
    public DateTime CreatedAt     { get; set; } = DateTime.UtcNow;
}

public record TrainHmmRequest(
    string   Instrument,
    string   Timeframe,
    DateTime DateFrom,
    DateTime DateTo
);

public record HmmModelDto(
    Guid     Id,
    string   Instrument,
    string   Timeframe,
    string   Version,
    int      NStates,
    double?  BicScore,
    DateTime TrainingFrom,
    DateTime TrainingTo,
    int      NSamples,
    string?  StateLabels,
    bool     IsActive,
    DateTime CreatedAt
);

public record ClassifyStateRequest(
    string   Instrument,
    string   Timeframe,
    string   OhlcJson    // serialized recent OHLC bars
);

public record ClassifyStateResult(
    int      State,
    string   StateLabel,
    string   ModelVersion
);

public record StateSequenceResult(
    List<int> Sequence,
    string    Repr,        // "S0S0S3S2S4"
    double    LogProb,
    string    ModelVersion
);
