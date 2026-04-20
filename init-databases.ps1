param(
    [int]$MaxWaitSeconds = 240
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Database init + migrations" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

function Test-DockerReady {
    try {
        docker ps *> $null
        return $true
    } catch {
        return $false
    }
}

if (-not (Test-DockerReady)) {
    Write-Host "Docker is not running or not accessible." -ForegroundColor Red
    Write-Host "Start Docker Desktop first, then re-run this script." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "[1/5] Starting databases..." -ForegroundColor Cyan
docker compose up -d db-mysql db-postgres

Write-Host ""
Write-Host "[2/5] Waiting for MySQL..." -ForegroundColor Cyan
$mysqlReady = $false
$mysqlChecks = @(
    { docker compose exec -T db-mysql mysqladmin ping -uroot -proot *> $null },
    { docker compose exec -T db-mysql mysqladmin ping -uroot *> $null }
)
$elapsed = 0
while ($elapsed -lt $MaxWaitSeconds) {
    foreach ($check in $mysqlChecks) {
        try {
            & $check
            $mysqlReady = $true
            break
        } catch {
            # try next check
        }
    }

    if ($mysqlReady) {
        Write-Host "MySQL is ready." -ForegroundColor Green
        break
    }

    Start-Sleep -Seconds 2
    $elapsed += 2
}
if (-not $mysqlReady) {
    Write-Host "Timed out waiting for MySQL." -ForegroundColor Red
    docker compose logs db-mysql --tail 80
    exit 1
}

Write-Host ""
Write-Host "[3/5] Waiting for PostgreSQL..." -ForegroundColor Cyan
$elapsed = 0
while ($elapsed -lt $MaxWaitSeconds) {
    try {
        docker compose exec -T db-postgres pg_isready -U postgres *> $null
        Write-Host "PostgreSQL is ready." -ForegroundColor Green
        break
    } catch {
        Start-Sleep -Seconds 2
        $elapsed += 2
    }
}
if ($elapsed -ge $MaxWaitSeconds) {
    Write-Host "Timed out waiting for PostgreSQL." -ForegroundColor Red
    exit 1
}

$services = @(
    "customer-service",
    "book-service",
    "cart-service",
    "order-service",
    "pay-service",
    "ship-service",
    "staff-service",
    "comment-rate-service",
    "manager-service",
    "recommender-ai-service",
    "api-gateway"
)

Write-Host ""
Write-Host "[4/5] Starting application services..." -ForegroundColor Cyan
docker compose up -d --build

Write-Host ""
Write-Host "[5/5] Running migrations..." -ForegroundColor Cyan
foreach ($svc in $services) {
    Write-Host "Migrating $svc..." -ForegroundColor Cyan
    docker compose exec -T $svc python manage.py migrate --noinput
}

Write-Host ""
Write-Host "Seeding default accounts..." -ForegroundColor Cyan

# Important: login checks identities in auth-service, not directly in domain DBs.
# Seed through auth-service register endpoint so auth + service records stay linked.
function Register-AuthUserIfMissing {
    param(
        [string]$Username,
        [string]$Email,
        [SecureString]$PasswordSecure,
        [string]$Role,
        [string]$Department = ""
    )

    $passwordPlain = [System.Net.NetworkCredential]::new("", $PasswordSecure).Password

    $payload = @{
        username = $Username
        email = $Email
        password = $passwordPlain
        role = $Role
    }
    if ($Department) {
        $payload.department = $Department
    }

    try {
        Invoke-RestMethod -Method POST -Uri "http://localhost:8012/api/auth/register/" -ContentType "application/json" -Body ($payload | ConvertTo-Json) *> $null
        Write-Host "auth-service: created $Username ($Role)" -ForegroundColor Green
    } catch {
        # 409 on existing user is expected on reruns.
        $msg = $_.Exception.Message
        if ($msg -match "409") {
            Write-Host "auth-service: $Username already exists" -ForegroundColor Yellow
        } else {
            Write-Host "auth-service: failed to create $Username -> $msg" -ForegroundColor Red
        }
    }
}

Register-AuthUserIfMissing -Username "admin" -Email "admin@bookstore.com" -PasswordSecure (ConvertTo-SecureString "admin123" -AsPlainText -Force) -Role "customer"
Register-AuthUserIfMissing -Username "staffadmin" -Email "staffadmin@bookstore.com" -PasswordSecure (ConvertTo-SecureString "admin123" -AsPlainText -Force) -Role "staff" -Department "operations"
Register-AuthUserIfMissing -Username "manager" -Email "manager@bookstore.com" -PasswordSecure (ConvertTo-SecureString "admin123" -AsPlainText -Force) -Role "manager" -Department "sales"

Write-Host ""
Write-Host "Done." -ForegroundColor Green
