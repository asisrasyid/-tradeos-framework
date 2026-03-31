using Microsoft.EntityFrameworkCore;
using TradeOS.Api.Modules.Pattern.Models;
using TradeOS.Api.Modules.Theory.Models;
using TradeOS.Api.Modules.TradeLog.Models;
using TradeOS.Api.Modules.Backtest.Models;
using TradeOS.Api.Modules.HMM.Models;
using TradeOS.Api.Modules.Bayesian.Models;
using TradeOS.Api.Modules.SmartTradeLog.Models;

namespace TradeOS.Api.Infrastructure.Database;

public class TradeOsDbContext(DbContextOptions<TradeOsDbContext> options) : DbContext(options)
{
    public DbSet<PatternEntity>          Patterns           { get; set; }
    public DbSet<TheoryEntity>           Theories           { get; set; }
    public DbSet<TheoryFactorEntity>     TheoryFactors      { get; set; }
    public DbSet<TheoryVersionEntity>    TheoryVersions     { get; set; }
    public DbSet<TradeLogEntity>         TradeLogs          { get; set; }
    public DbSet<HmmModelEntity>         HmmModels          { get; set; }
    public DbSet<BayesianCounterEntity>  BayesianCounters   { get; set; }
    public DbSet<BacktestSessionEntity>  BacktestSessions   { get; set; }
    public DbSet<BacktestResultEntity>   BacktestResults    { get; set; }
    public DbSet<BacktestTradeEntity>    BacktestTrades     { get; set; }
    public DbSet<PatternScoreEntity>     PatternScores      { get; set; }
    public DbSet<SmartTradeLogEntity>    SmartTradeLogs     { get; set; }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        // patterns
        modelBuilder.Entity<PatternEntity>(e =>
        {
            e.ToTable("patterns");
            e.HasKey(x => x.Id);
            e.Property(x => x.StateSequence).HasColumnType("jsonb");
            e.HasQueryFilter(x => x.DeletedAt == null);
        });

        // theories
        modelBuilder.Entity<TheoryEntity>(e =>
        {
            e.ToTable("theories");
            e.HasKey(x => x.Id);
            e.HasQueryFilter(x => x.DeletedAt == null);
        });

        // theory_factors
        modelBuilder.Entity<TheoryFactorEntity>(e =>
        {
            e.ToTable("theory_factors");
            e.HasKey(x => x.Id);
            e.HasOne(x => x.Theory).WithMany(t => t.Factors).HasForeignKey(x => x.TheoryId);
        });

        // theory_versions
        modelBuilder.Entity<TheoryVersionEntity>(e =>
        {
            e.ToTable("theory_versions");
            e.HasKey(x => x.Id);
            e.Property(x => x.Snapshot).HasColumnType("jsonb");
        });

        // trade_log
        modelBuilder.Entity<TradeLogEntity>(e =>
        {
            e.ToTable("trade_log");
            e.HasKey(x => x.Id);
            e.Property(x => x.StateSequence).HasColumnType("jsonb");
            e.Property(x => x.FactorSnapshot).HasColumnType("jsonb");
        });

        // hmm_models
        modelBuilder.Entity<HmmModelEntity>(e =>
        {
            e.ToTable("hmm_models");
            e.HasKey(x => x.Id);
            e.Property(x => x.StateLabels).HasColumnType("jsonb");
            e.Property(x => x.FeatureNames).HasColumnType("jsonb");
            e.HasQueryFilter(x => x.IsActive);
        });

        // bayesian_counters
        modelBuilder.Entity<BayesianCounterEntity>(e =>
        {
            e.ToTable("bayesian_counters");
            e.HasKey(x => x.Id);
            e.HasIndex(x => new { x.TheoryId, x.StateSeqHash, x.Instrument, x.Timeframe }).IsUnique();
        });

        // backtest_sessions
        modelBuilder.Entity<BacktestSessionEntity>(e =>
        {
            e.ToTable("backtest_sessions");
            e.HasKey(x => x.Id);
            e.Property(x => x.Params).HasColumnType("jsonb");
        });

        // backtest_results
        modelBuilder.Entity<BacktestResultEntity>(e =>
        {
            e.ToTable("backtest_results");
            e.HasKey(x => x.Id);
            e.Property(x => x.EquityCurve).HasColumnType("jsonb");
            e.Property(x => x.StateDistribution).HasColumnType("jsonb");
        });

        // backtest_trades
        modelBuilder.Entity<BacktestTradeEntity>(e =>
        {
            e.ToTable("backtest_trades");
            e.HasKey(x => x.Id);
            e.HasIndex(x => x.SessionId);
        });

        // pattern_scores
        modelBuilder.Entity<PatternScoreEntity>(e =>
        {
            e.ToTable("pattern_scores");
            e.HasKey(x => x.Id);
            e.HasIndex(x => new { x.PatternId, x.TheoryId, x.Instrument, x.Timeframe }).IsUnique();
        });

        // smart_trade_log
        modelBuilder.Entity<SmartTradeLogEntity>(e =>
        {
            e.ToTable("smart_trade_log");
            e.HasKey(x => x.Id);
            e.Property(x => x.AiEnabled).HasColumnName("ai_enabled");
            e.Property(x => x.LlmModel).HasColumnName("llm_model");
            e.Property(x => x.LlmReasoning).HasColumnName("llm_reasoning");
            e.Property(x => x.LlmConfidence).HasColumnName("llm_confidence").HasColumnType("decimal(4,3)");
            e.Property(x => x.LlmPromptVer).HasColumnName("llm_prompt_ver");
            e.Property(x => x.LlmLatencyMs).HasColumnName("llm_latency_ms");
            e.Property(x => x.LlmSkipReason).HasColumnName("llm_skip_reason");
            e.Property(x => x.EntriesPerDecision).HasColumnName("entries_per_decision");
        });

        // Apply snake_case column names for all entities (PostgreSQL convention)
        foreach (var entity in modelBuilder.Model.GetEntityTypes())
        {
            foreach (var property in entity.GetProperties())
            {
                property.SetColumnName(ToSnakeCase(property.GetColumnName()));
            }
        }
    }

    private static string ToSnakeCase(string? name)
    {
        if (string.IsNullOrEmpty(name)) return name ?? string.Empty;
        var sb = new System.Text.StringBuilder();
        for (int i = 0; i < name.Length; i++)
        {
            char c = name[i];
            if (char.IsUpper(c) && i > 0)
                sb.Append('_');
            sb.Append(char.ToLower(c));
        }
        return sb.ToString();
    }
}
