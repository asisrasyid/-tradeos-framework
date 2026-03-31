using Hangfire;
using Hangfire.PostgreSql;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;
using Serilog;
using StackExchange.Redis;
using System.Text;
using TradeOS.Api.Infrastructure.Database;
using TradeOS.Api.Infrastructure.Python;
using TradeOS.Api.Infrastructure.Jobs;
using TradeOS.Api.Modules.Backtest.Services;
using TradeOS.Api.Modules.Bayesian.Services;
using TradeOS.Api.Modules.HMM.Services;
using TradeOS.Api.Modules.MT5.Services;
using TradeOS.Api.Modules.Pattern.Services;
using TradeOS.Api.Modules.Signal.Hubs;
using TradeOS.Api.Modules.Signal.Services;
using TradeOS.Api.Modules.Theory.Services;
using TradeOS.Api.Modules.TradeLog.Services;
using TradeOS.Api.Modules.SmartTradeLog.Services;

// ─── Serilog ───────────────────────────────────────────────────────────────
Log.Logger = new LoggerConfiguration()
    .WriteTo.Console()
    .CreateBootstrapLogger();

var builder = WebApplication.CreateBuilder(args);

builder.Host.UseSerilog((ctx, cfg) =>
    cfg.ReadFrom.Configuration(ctx.Configuration));

// ─── Database ──────────────────────────────────────────────────────────────
var connStr = builder.Configuration.GetConnectionString("Default")
    ?? throw new InvalidOperationException("Connection string 'Default' is required.");

builder.Services.AddDbContext<TradeOsDbContext>(opt =>
    opt.UseNpgsql(connStr));

//// ─── Redis ─────────────────────────────────────────────────────────────────
//var redisConn = builder.Configuration.GetConnectionString("Redis") ?? "localhost:6379";
//builder.Services.AddSingleton<IConnectionMultiplexer>(
//    ConnectionMultiplexer.Connect(redisConn));

// ─── Hangfire ──────────────────────────────────────────────────────────────
builder.Services.AddHangfire(cfg =>
    cfg.UsePostgreSqlStorage(c => c.UseNpgsqlConnection(connStr)));
builder.Services.AddHangfireServer();

// ─── SignalR ───────────────────────────────────────────────────────────────
builder.Services.AddSignalR();

// ─── JWT Auth ──────────────────────────────────────────────────────────────
var jwtKey = builder.Configuration["Jwt:Key"]
    ?? "TRADEOS_DEFAULT_DEV_SECRET_CHANGE_IN_PROD_32CHARS!";
var jwtIssuer = builder.Configuration["Jwt:Issuer"] ?? "TradeOS";

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(opt =>
    {
        opt.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer           = true,
            ValidateAudience         = false,
            ValidateLifetime         = true,
            ValidateIssuerSigningKey = true,
            ValidIssuer              = jwtIssuer,
            IssuerSigningKey         = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtKey))
        };

        // Support JWT from SignalR query string
        opt.Events = new JwtBearerEvents
        {
            OnMessageReceived = ctx =>
            {
                var token = ctx.Request.Query["access_token"];
                if (!string.IsNullOrEmpty(token) &&
                    ctx.HttpContext.Request.Path.StartsWithSegments("/hubs"))
                    ctx.Token = token;
                return Task.CompletedTask;
            }
        };
    });

builder.Services.AddAuthorization();

// ─── Python Sidecar Client ─────────────────────────────────────────────────
var pythonUrl = builder.Configuration["Python:BaseUrl"] ?? "http://localhost:8000";
builder.Services.AddHttpClient<IPythonClient, PythonClient>(c =>
{
    c.BaseAddress = new Uri(pythonUrl);
    c.Timeout     = TimeSpan.FromMinutes(10);
});

// ─── Module Services ───────────────────────────────────────────────────────
builder.Services.AddScoped<IPatternService,   PatternService>();
builder.Services.AddScoped<ITheoryService,    TheoryService>();
builder.Services.AddScoped<ITradeLogService,  TradeLogService>();
builder.Services.AddScoped<ISignalService,    SignalService>();
builder.Services.AddScoped<IHmmService,       HmmService>();
builder.Services.AddScoped<IBayesianService,  BayesianService>();
builder.Services.AddScoped<IBacktestService,  BacktestService>();
builder.Services.AddScoped<IMT5Service,       MT5Service>();
builder.Services.AddScoped<ISmartTradeLogService, SmartTradeLogService>();

// ─── Hangfire Jobs ─────────────────────────────────────────────────────────
builder.Services.AddScoped<IHmmTrainingJob,   HmmTrainingJob>();
builder.Services.AddScoped<IBacktestJob,      BacktestJob>();
builder.Services.AddScoped<OutcomePollerJob>();

// ─── Controllers + Swagger ─────────────────────────────────────────────────
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(c =>
{
    c.SwaggerDoc("v1", new() { Title = "TradeOS API", Version = "v1" });
    c.AddSecurityDefinition("Bearer", new()
    {
        Name   = "Authorization",
        Type   = Microsoft.OpenApi.Models.SecuritySchemeType.Http,
        Scheme = "bearer"
    });
    c.AddSecurityRequirement(new()
    {
        {
            new() { Reference = new() { Type = Microsoft.OpenApi.Models.ReferenceType.SecurityScheme, Id = "Bearer" } },
            []
        }
    });
});

// ─── CORS ──────────────────────────────────────────────────────────────────
builder.Services.AddCors(opt =>
    opt.AddDefaultPolicy(p =>
        p.WithOrigins(
            builder.Configuration["Cors:Origin"] ?? "http://localhost:3000")
         .AllowAnyHeader()
         .AllowAnyMethod()
         .AllowCredentials()));

// ─────────────────────────────── BUILD ────────────────────────────────────
var app = builder.Build();

app.UseSerilogRequestLogging();
app.UseCors();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseAuthentication();
app.UseAuthorization();

app.UseHangfireDashboard("/hangfire");

// Outcome poller: check closed MT5 positions every 60 seconds
RecurringJob.AddOrUpdate<OutcomePollerJob>(
    "outcome-poller",
    job => job.PollAsync(),
    "*/1 * * * *");   // every minute

app.MapControllers();
app.MapHub<SignalHub>(SignalHub.Endpoint);

app.Run();
