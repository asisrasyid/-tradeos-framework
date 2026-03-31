# API TEMPLATE — TradeOS v5.1
## Standard ApiResponse<T>
```csharp
public record ApiResponse<T> {
    public bool Success { get; init; }
    public T? Data { get; init; }
    public string? Error { get; init; }
    public DateTimeOffset Timestamp { get; init; } = DateTimeOffset.UtcNow;
    public static ApiResponse<T> Ok(T data) => new() { Success = true, Data = data };
    public static ApiResponse<object> Fail(string e) => new() { Success = false, Error = e };
}
```
## Python FastAPI endpoint
```python
@router.post("/compute")
async def compute(req: RequestModel):
    try:
        result = do_computation(req)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```
