#!/usr/bin/env pwsh

# Test Results Array
$results = @()

Write-Host "================================" -ForegroundColor Cyan
Write-Host "BOOKSTORE API TEST SUITE 2026" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

function Test-API {
    param(
        [string]$Method,
        [string]$Url,
        [hashtable]$Headers = @{},
        [string]$Body = $null,
        [string]$TestName = ""
    )
    
    $startTime = Get-Date
    
    try {
        $params = @{
            Uri             = $Url
            Method          = $Method
            Headers         = $Headers
            ContentType     = 'application/json'
            TimeoutSec      = 10
        }
        
        if ($Body) {
            $params.Body = $Body
        }
        
        $response = Invoke-RestMethod @params
        $duration = ((Get-Date) - $startTime).TotalMilliseconds
        
        Write-Host "[PASS] $TestName ($($duration)ms)" -ForegroundColor Green
        return @{
            Status = "PASS"
            Name = $TestName
            Method = $Method
            Url = $Url
            Duration = $duration
            Response = $response
            Error = $null
        }
    }
    catch {
        $duration = ((Get-Date) - $startTime).TotalMilliseconds
        $errorMsg = $_.Exception.Message
        Write-Host "[FAIL] $TestName ($($duration)ms)" -ForegroundColor Red
        Write-Host "  Error: $errorMsg" -ForegroundColor Red
        
        return @{
            Status = "FAIL"
            Name = $TestName
            Method = $Method
            Url = $Url
            Duration = $duration
            Response = $null
            Error = $errorMsg
        }
    }
}

# ==========================================
# STEP 1: REGISTER NEW USER & GET AUTH TOKEN
# ==========================================

Write-Host "`n[STEP 1] Authentication & Token Generation" -ForegroundColor Yellow

# Register new user
$randomId = Get-Random -Minimum 1000 -Maximum 9999
$newUser = @{
    username = "testuser_$randomId"
    email = "testuser$randomId@bookstore.local"
    password = "TestPass@12345"
    first_name = "Test"
    last_name = "User"
} | ConvertTo-Json

$registerTest = Test-API -Method "POST" -Url "http://localhost:8012/api/auth/register/" -Body $newUser -TestName "Register New User"
$results += $registerTest

$userId = $null
$username = $null
if ($registerTest.Status -eq "PASS") {
    $userId = $registerTest.Response.user.id
    $username = $registerTest.Response.user.username
    Write-Host "  [INFO] New User ID: $userId" -ForegroundColor Cyan
    Write-Host "  [INFO] Username: $username" -ForegroundColor Cyan
}

# ==========================================
# STEP 2: TEST WITHOUT TOKEN
# ==========================================

Write-Host "`n[STEP 2] Testing APIs WITHOUT Authentication Token" -ForegroundColor Yellow

$noTokenHeaders = @{}

$testCases_NoToken = @(
    @{ Method = "GET"; Url = "http://localhost:8000/"; Name = "Gateway - Home" },
    @{ Method = "GET"; Url = "http://localhost:8000/health/"; Name = "Gateway - Health" },
    @{ Method = "GET"; Url = "http://localhost:8000/metrics/"; Name = "Gateway - Metrics" },
    @{ Method = "GET"; Url = "http://localhost:8000/api/books/"; Name = "Gateway - Proxy Books" },
    @{ Method = "GET"; Url = "http://localhost:8001/api/customers/"; Name = "Customer - List Customers (No Token)" },
    @{ Method = "GET"; Url = "http://localhost:8002/api/books/"; Name = "Book - List Books (No Token)" },
    @{ Method = "GET"; Url = "http://localhost:8002/api/health/"; Name = "Product - Health" },
    @{ Method = "GET"; Url = "http://localhost:8002/api/books/"; Name = "Product - List All Books" },
    @{ Method = "GET"; Url = "http://localhost:8002/api/books/search/?q=code"; Name = "Product - Search Books" },
    @{ Method = "GET"; Url = "http://localhost:8002/api/books/featured_books/"; Name = "Product - Featured Books" },
    @{ Method = "GET"; Url = "http://localhost:8003/api/carts/1/"; Name = "Cart - Get Cart 1 (No Token)" },
    @{ Method = "GET"; Url = "http://localhost:8004/api/orders/"; Name = "Order - Get Orders (No Token)" },
    @{ Method = "GET"; Url = "http://localhost:8005/api/payments/"; Name = "Payment - Get Payments (No Token)" },
    @{ Method = "GET"; Url = "http://localhost:8006/api/shipments/"; Name = "Shipping - Get Shipments (No Token)" },
    @{ Method = "GET"; Url = "http://localhost:8007/api/staff/"; Name = "Staff - List Staff (No Token)" },
    @{ Method = "GET"; Url = "http://localhost:8008/api/comments/"; Name = "Comment - List Comments (No Token)" },
    @{ Method = "GET"; Url = "http://localhost:8010/api/manager/"; Name = "Manager - Get Manager Data (No Token)" },
    @{ Method = "GET"; Url = "http://localhost:8011/api/v1/recommend/1"; Name = "Recommender - Get Recommendations (No Token)" }
)

foreach ($test in $testCases_NoToken) {
    $result = Test-API -Method $test.Method -Url $test.Url -Headers $noTokenHeaders -TestName $test.Name
    $results += $result
}

# ==========================================
# STEP 3: AUTH SERVICE - CREATE TOKEN
# ==========================================

Write-Host "`n[STEP 3] Auth Service - Getting JWT Token" -ForegroundColor Yellow

$token = $null

try {
    if ($registerTest.Status -eq "PASS" -and $registerTest.Response.access_token) {
        $token = $registerTest.Response.access_token
        Write-Host "[SUCCESS] JWT Token Obtained" -ForegroundColor Green
        Write-Host "  Token: $($token.Substring(0, 50))..." -ForegroundColor Cyan
    }
    else {
        Write-Host "Attempting to get JWT token from Auth Service (port 8012)..." -ForegroundColor Cyan
        
        $loginData = @{
            username = $username
            password = "TestPass@12345"
        } | ConvertTo-Json
        
        $tokenResponse = Invoke-RestMethod -Uri "http://localhost:8012/api/auth/login/" `
            -Method "POST" -Headers @{} -Body $loginData -ContentType "application/json" -TimeoutSec 10
        
        $token = $tokenResponse.access_token
        
        Write-Host "[SUCCESS] JWT Token Obtained" -ForegroundColor Green
        Write-Host "  Token: $($token.Substring(0, 50))..." -ForegroundColor Cyan
    }
}
catch {
    Write-Host "[WARNING] Could not get token from Auth Service" -ForegroundColor Yellow
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Yellow
}

# ==========================================
# STEP 4: TEST WITH TOKEN
# ==========================================

Write-Host "`n[STEP 4] Testing APIs WITH Authentication Token" -ForegroundColor Yellow

if ($token) {
    $withTokenHeaders = @{
        "Authorization" = "Bearer $token"
        "Content-Type" = "application/json"
    }
    
    $testCases_WithToken = @(
        @{ Method = "GET"; Url = "http://localhost:8000/api/carts/1/"; Name = "Gateway - Proxy Cart (With Token)" },
        @{ Method = "GET"; Url = "http://localhost:8001/api/customers/"; Name = "Customer - List Customers (With Token)" },
        @{ Method = "GET"; Url = "http://localhost:8002/api/books/"; Name = "Book - List Books (With Token)" },
        @{ Method = "GET"; Url = "http://localhost:8002/api/health/"; Name = "Product - Health (With Token)" },
        @{ Method = "GET"; Url = "http://localhost:8002/api/books/featured_books/"; Name = "Product - Featured Books (With Token)" },
        @{ Method = "GET"; Url = "http://localhost:8003/api/carts/1/"; Name = "Cart - Get Cart 1 (With Token)" },
        @{ Method = "GET"; Url = "http://localhost:8004/api/orders/"; Name = "Order - Get Orders (With Token)" },
        @{ Method = "GET"; Url = "http://localhost:8005/api/payments/"; Name = "Payment - Get Payments (With Token)" },
        @{ Method = "GET"; Url = "http://localhost:8006/api/shipments/"; Name = "Shipping - Get Shipments (With Token)" },
        @{ Method = "GET"; Url = "http://localhost:8007/api/staff/"; Name = "Staff - List Staff (With Token)" },
        @{ Method = "GET"; Url = "http://localhost:8008/api/comments/"; Name = "Comment - List Comments (With Token)" },
        @{ Method = "GET"; Url = "http://localhost:8010/api/manager/"; Name = "Manager - Get Manager Data (With Token)" },
        @{ Method = "GET"; Url = "http://localhost:8011/health"; Name = "Recommender - Health (With Token)" },
        @{ Method = "GET"; Url = "http://localhost:8011/api/v1/recommend/1"; Name = "Recommender - Recommend (With Token)" }
    )
    
    foreach ($test in $testCases_WithToken) {
        $result = Test-API -Method $test.Method -Url $test.Url -Headers $withTokenHeaders -TestName $test.Name
        $results += $result
    }
} else {
    Write-Host "[WARNING] Skipping token-based tests (token not available)" -ForegroundColor Yellow
}

# ==========================================
# GENERATE TEST REPORT
# ==========================================

Write-Host "`n================================" -ForegroundColor Cyan
Write-Host "TEST REPORT SUMMARY" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

$passCount = ($results | Where-Object { $_.Status -eq "PASS" }).Count
$failCount = ($results | Where-Object { $_.Status -eq "FAIL" }).Count
$totalTests = $results.Count
$passPercentage = if ($totalTests -gt 0) { [math]::Round(($passCount / $totalTests) * 100, 2) } else { 0 }

Write-Host "Total Tests: $totalTests" -ForegroundColor Cyan
Write-Host "Passed: $passCount" -ForegroundColor Green
Write-Host "Failed: $failCount" -ForegroundColor Red
Write-Host "Success Rate: $passPercentage%" -ForegroundColor Cyan

Write-Host "`nDetailed Results:" -ForegroundColor Yellow

foreach ($result in $results) {
    if ($result.Status -eq "PASS") {
        Write-Host "  [OK] $($result.Name)" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] $($result.Name)" -ForegroundColor Red
        Write-Host "    Error: $($result.Error)" -ForegroundColor Red
    }
}

# Save results to file
$reportPath = "test-results-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
$results | ConvertTo-Json | Out-File -FilePath $reportPath -Encoding UTF8
Write-Host "`nTest results saved to: $reportPath" -ForegroundColor Cyan

Write-Host "`n================================" -ForegroundColor Cyan
Write-Host "TEST SUITE COMPLETED" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
