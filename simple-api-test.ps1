$results = @()

Write-Host "BOOKSTORE API TEST SUITE" -ForegroundColor Cyan
Write-Host "=========================" -ForegroundColor Cyan
Write-Host ""

# Test endpoints without token
Write-Host "TESTING APIs WITHOUT TOKEN:" -ForegroundColor Yellow
Write-Host ""

$urls = @(
    "http://localhost:8001/api/customers/",
    "http://localhost:8002/api/books/",
    "http://localhost:8003/api/carts/1/",
    "http://localhost:8004/api/orders/",
    "http://localhost:8005/api/payments/",
    "http://localhost:8006/api/shipments/",
    "http://localhost:8007/api/staff/",
    "http://localhost:8008/api/comments/",
    "http://localhost:8010/api/manager/"
)

$passCount = 0
$failCount = 0

foreach ($url in $urls) {
    try {
        $response = Invoke-RestMethod -Uri $url -Method GET -TimeoutSec 10
        Write-Host "PASS: $url" -ForegroundColor Green
        $passCount++
    }
    catch {
        Write-Host "FAIL: $url" -ForegroundColor Red
        Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
        $failCount++
    }
}

# Try to register a user and get token
Write-Host ""
Write-Host "REGISTERING TEST USER:" -ForegroundColor Yellow
Write-Host ""

$randomId = Get-Random -Minimum 1000 -Maximum 9999
$userData = @{
    username = "apitest_$randomId"
    email = "apitest$randomId@bookstore.local"
    password = "TestPass@12345"
} | ConvertTo-Json

try {
    $userResponse = Invoke-RestMethod -Uri "http://localhost:8012/api/auth/register/" -Method POST -Body $userData -ContentType "application/json" -TimeoutSec 10
    Write-Host "SUCCESS: User registered" -ForegroundColor Green
    Write-Host "  Username: $($userResponse.user.username)" -ForegroundColor Cyan
    $username = $userResponse.user.username
    $token = $userResponse.access_token
    $hasToken = $true
}
catch {
    Write-Host "FAIL: Could not register user" -ForegroundColor Red
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
    $username = ""
    $hasToken = $false
}

# Try to get JWT token
Write-Host ""
Write-Host "GETTING JWT TOKEN FROM AUTH SERVICE:" -ForegroundColor Yellow
Write-Host ""

if ($hasToken -and $token) {
    Write-Host "SUCCESS: JWT Token obtained" -ForegroundColor Green
    Write-Host "  Token: $($token.Substring(0, 40))..." -ForegroundColor Cyan
}
elseif ($username) {
    $loginData = @{
        username = $username
        password = "TestPass@12345"
    } | ConvertTo-Json
    
    try {
        $loginResponse = Invoke-RestMethod -Uri "http://localhost:8012/api/auth/login/" -Method POST -Body $loginData -ContentType "application/json" -TimeoutSec 10
        $token = $loginResponse.access_token
        Write-Host "SUCCESS: JWT Token obtained" -ForegroundColor Green
        Write-Host "  Token: $($token.Substring(0, 40))..." -ForegroundColor Cyan
        $hasToken = $true
    }
    catch {
        Write-Host "FAIL: Could not get JWT token" -ForegroundColor Yellow
        Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Yellow
        $hasToken = $false
    }
}
else {
    Write-Host "SKIP: No user available for authentication" -ForegroundColor Yellow
    $hasToken = $false
}

# Test with token if available
if ($hasToken) {
    Write-Host ""
    Write-Host "TESTING APIs WITH TOKEN:" -ForegroundColor Yellow
    Write-Host ""
    
    $headers = @{
        "Authorization" = "Bearer $token"
        "Content-Type" = "application/json"
    }
    
    foreach ($url in $urls) {
        try {
            $response = Invoke-RestMethod -Uri $url -Method GET -Headers $headers -TimeoutSec 10
            Write-Host "PASS (with token): $url" -ForegroundColor Green
            $passCount++
        }
        catch {
            Write-Host "FAIL (with token): $url" -ForegroundColor Red
            Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
            $failCount++
        }
    }
}

# Summary
Write-Host ""
Write-Host "=========================" -ForegroundColor Cyan
Write-Host "TEST SUMMARY:" -ForegroundColor Cyan
Write-Host "Total Passed: $passCount" -ForegroundColor Green
Write-Host "Total Failed: $failCount" -ForegroundColor Red
$total = $passCount + $failCount
if ($total -gt 0) {
    $rate = [math]::Round(($passCount / $total) * 100, 2)
    Write-Host "Success Rate: $rate%" -ForegroundColor Cyan
}
Write-Host ""

# Docker status
Write-Host "DOCKER CONTAINERS STATUS:" -ForegroundColor Cyan
Write-Host ""
docker-compose ps
