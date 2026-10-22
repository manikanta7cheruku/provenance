<#
.SYNOPSIS
  Operator helper for Provenance (checkpoint 1.4). Run from anywhere: .\scripts\pv.ps1 <command>

.EXAMPLE
  .\scripts\pv.ps1 up
  .\scripts\pv.ps1 invite you@example.com
  .\scripts\pv.ps1 help
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)][string]$Command = "help",
    [Parameter(Position = 1, ValueFromRemainingArguments = $true)][string[]]$Rest = @()
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Run {
    # Runs a native command and stops the script if it fails.
    param([string]$Exe, [string[]]$Arguments)
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Exe $($Arguments -join ' ') failed with exit code $LASTEXITCODE" }
}

function Require-EnvFile {
    if (-not (Test-Path ".env")) {
        throw "There is no .env file. Copy .env.example to .env and edit it first (see docs/development-setup.md)."
    }
}

function Get-EnvValue {
    param([string]$Name, [string]$Default)
    if (Test-Path ".env") {
        $line = Select-String -Path ".env" -Pattern "^\s*$Name\s*=(.*)$" | Select-Object -First 1
        if ($line) { return $line.Matches[0].Groups[1].Value.Trim() }
    }
    return $Default
}

function Show-Help {
@"
Provenance operator commands

  up                     build and start the whole stack (postgres, migrate, api, worker, mailpit, web)
  down                   stop the stack (data is kept)
  reset                  stop the stack AND DELETE the database volume (asks you to type RESET)
  restart [service]      restart one service (default: worker). Use after editing worker code
  status                 container state, API health and the queue by state
  logs [service]         follow logs (default: all). Example: logs worker
  migrate                run database migrations now
  invite [email]         create a signup invite code (optionally bound to an email)
  admin <email>          give an existing user the ADMIN role
  inbox                  open the local mail inbox (Mailpit) in the browser
  psql                   open a psql shell as the database owner
  queue                  show queue counts, recent tasks and workers
  demo-task [seconds]    enqueue a harmless demo task (crash-recovery lab; default 20 seconds)
  demo-run <email>       create a finished demo run for a user, to try the Runs screen
  ai-check               list usable Gemini models and test one generation and one embedding
  test                   quality gate: ruff, mypy, import-linter, unit tests, web checks
  itest                  integration tests (stops the worker first, restarts it afterwards)
  help                   this text
"@ | Write-Host
}

switch ($Command.ToLower()) {
    "help" { Show-Help }

    "up" {
        Require-EnvFile
        Run "docker" @("compose", "up", "-d", "--build")
        Write-Host ""
        Write-Host "Web:    http://localhost:5173"
        Write-Host "API:    http://localhost:8000/api/docs"
        Write-Host "Inbox:  http://localhost:8025   (emails sent by the worker)"
        Write-Host "Check:  .\scripts\pv.ps1 status"
    }

    "down" { Run "docker" @("compose", "down") }

    "reset" {
        $answer = Read-Host "This deletes the local database. Type RESET to continue"
        if ($answer -ne "RESET") { Write-Host "Cancelled."; break }
        Run "docker" @("compose", "down", "-v")
        Write-Host "Database volume removed. Run: .\scripts\pv.ps1 up"
    }

    "restart" {
        $service = if ($Rest.Count -gt 0) { $Rest[0] } else { "worker" }
        Run "docker" @("compose", "restart", $service)
    }

    "status" {
        Run "docker" @("compose", "ps")
        Write-Host ""
        try {
            $health = Invoke-RestMethod -Uri "http://localhost:8000/readyz" -TimeoutSec 5
            Write-Host "API ready: $($health.ready)  database: $($health.checks.database)  migrations: $($health.checks.migrations)"
        } catch {
            Write-Host "API readiness: not reachable ($($_.Exception.Message))"
        }
        Write-Host ""
        $owner = Get-EnvValue "POSTGRES_USER" "provenance"
        $db = Get-EnvValue "POSTGRES_DB" "provenance"
        Run "docker" @("compose", "exec", "-T", "postgres", "psql", "-U", $owner, "-d", $db, "-c",
            "SELECT state, count(*) AS tasks FROM tasks GROUP BY state ORDER BY state")
    }

    "logs" {
        $arguments = @("compose", "logs", "-f", "--tail", "100")
        if ($Rest.Count -gt 0) { $arguments += $Rest[0] }
        Run "docker" $arguments
    }

    "migrate" { Run "docker" @("compose", "run", "--rm", "migrate") }

    "invite" {
        $arguments = @("compose", "exec", "api", "python", "-m", "pv_api.cli", "create-invite")
        if ($Rest.Count -gt 0) { $arguments += @("--email", $Rest[0]) }
        Run "docker" $arguments
    }

    "admin" {
        if ($Rest.Count -lt 1) { throw "Usage: .\scripts\pv.ps1 admin <email>" }
        Run "docker" @("compose", "exec", "api", "python", "-m", "pv_api.cli", "promote-admin", "--email", $Rest[0])
    }

    "inbox" { Start-Process "http://localhost:8025" }

    "psql" {
        $owner = Get-EnvValue "POSTGRES_USER" "provenance"
        $db = Get-EnvValue "POSTGRES_DB" "provenance"
        Run "docker" @("compose", "exec", "postgres", "psql", "-U", $owner, "-d", $db)
    }

    "queue" {
        $owner = Get-EnvValue "POSTGRES_USER" "provenance"
        $db = Get-EnvValue "POSTGRES_DB" "provenance"
        $sql = @"
SELECT state, count(*) AS tasks, min(run_after) FILTER (WHERE state IN ('queued','retry_scheduled')) AS oldest_due FROM tasks GROUP BY state ORDER BY state;
SELECT id, task_type, state, attempts, max_attempts, left(coalesce(last_error, ''), 60) AS last_error, updated_at FROM tasks ORDER BY updated_at DESC LIMIT 10;
SELECT worker_id, last_seen_at, tasks_processed FROM worker_heartbeats ORDER BY last_seen_at DESC;
"@
        Run "docker" @("compose", "exec", "-T", "postgres", "psql", "-U", $owner, "-d", $db, "-c", $sql)
    }

    "demo-task" {
        $seconds = if ($Rest.Count -gt 0) { $Rest[0] } else { "20" }
        Run "docker" @("compose", "exec", "worker", "python", "-m", "pv_worker.cli", "enqueue-demo", "--seconds", $seconds)
    }

    "demo-run" {
        if ($Rest.Count -lt 1) { throw "Usage: .\scripts\pv.ps1 demo-run <email>" }
        Run "docker" @("compose", "exec", "api", "python", "-m", "pv_api.cli", "seed-demo-run", "--email", $Rest[0])
    }

    "ai-check" { Run "uv" @("run", "python", "-m", "pv_llm.check") }

    "test" {
        Run "uv" @("run", "ruff", "check", ".")
        Run "uv" @("run", "ruff", "format", "--check", ".")
        Run "uv" @("run", "mypy")
        Run "uv" @("run", "lint-imports")
        Run "uv" @("run", "pytest")
        Push-Location "apps/web"
        try {
            Run "npm" @("run", "check:boundaries")
            Run "npm" @("run", "check:states")
            Run "npm" @("run", "typecheck")
            Run "npm" @("run", "build")
        } finally { Pop-Location }
        Write-Host "Quality gate passed."
    }

    "itest" {
        # A running worker would send and erase the queued email payloads that the tests read.
        Write-Host "Stopping the worker for the integration tests..."
        & docker compose stop worker 2>&1 | Out-Null
        try {
            Run "uv" @("run", "pytest", "-m", "integration")
        } finally {
            Write-Host "Starting the worker again..."
            & docker compose start worker 2>&1 | Out-Null
        }
    }

    default {
        Write-Host "Unknown command: $Command" -ForegroundColor Yellow
        Show-Help
        exit 1
    }
}
