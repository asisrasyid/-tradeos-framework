using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using Microsoft.AspNetCore.Mvc;
using Microsoft.IdentityModel.Tokens;
using TradeOS.Api.Common.Models;

namespace TradeOS.Api.Modules.Auth.Controllers;

/// <summary>
/// Single-user JWT auth for TradeOS MVP.
/// Credentials are stored as SHA256 hash in appsettings under Auth:PasswordHash.
/// Default dev password: "tradeos" (SHA256: see appsettings.json).
/// </summary>
[ApiController]
[Route("api/auth")]
public class AuthController(IConfiguration config) : ControllerBase
{
    [HttpPost("login")]
    public IActionResult Login([FromBody] LoginRequest req)
    {
        if (string.IsNullOrWhiteSpace(req.Username) || string.IsNullOrWhiteSpace(req.Password))
            return BadRequest(ApiResponse<string>.Fail("Username and password are required"));

        // Validate username
        var expectedUser = config["Auth:Username"] ?? "admin";
        if (!string.Equals(req.Username, expectedUser, StringComparison.OrdinalIgnoreCase))
            return Unauthorized(ApiResponse<string>.Fail("Invalid credentials"));
        ///"8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92"
        // Validate password via SHA256 hash comparison
        //var expectedHash = config["Auth:PasswordHash"]
        //    ?? "8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92"; // "123456" default dev
        var expectedHash = "8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92"; // "123456" default dev
        var actualHash = ComputeSha256(req.Password);

        if (!string.Equals(actualHash, expectedHash, StringComparison.OrdinalIgnoreCase))
            return Unauthorized(ApiResponse<string>.Fail("Invalid credentials"));

        // Build JWT
        var jwtKey    = config["Jwt:Key"] ?? "TRADEOS_DEFAULT_DEV_SECRET_CHANGE_IN_PROD_32CHARS!";
        var jwtIssuer = config["Jwt:Issuer"] ?? "TradeOS";
        var expHours  = int.TryParse(config["Jwt:ExpiryHours"], out var h) ? h : 24;

        var claims = new[]
        {
            new Claim(ClaimTypes.Name,           req.Username),
            new Claim(ClaimTypes.Role,           "trader"),
            new Claim(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString()),
        };

        var key   = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtKey));
        var creds = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);
        var token = new JwtSecurityToken(
            issuer:             jwtIssuer,
            audience:           null,
            claims:             claims,
            notBefore:          DateTime.UtcNow,
            expires:            DateTime.UtcNow.AddHours(expHours),
            signingCredentials: creds
        );

        var tokenStr = new JwtSecurityTokenHandler().WriteToken(token);

        return Ok(ApiResponse<LoginResponse>.Ok(
            new LoginResponse(tokenStr, req.Username, DateTime.UtcNow.AddHours(expHours))));
    }

    private static string ComputeSha256(string input)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(input));
        return Convert.ToHexString(bytes).ToLower();
    }
}

public record LoginRequest(string Username, string Password);
public record LoginResponse(string Token, string Username, DateTime ExpiresAt);
