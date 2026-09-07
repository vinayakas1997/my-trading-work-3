<#
.SYNOPSIS
  Populate the ./secrets/ files that docker-compose mounts into the services.
  PowerShell equivalent of scripts/setup-secrets.sh (for Windows hosts).

.DESCRIPTION
  For each credential it looks, in order, at: an already-existing secret file
  (kept), the current process environment, then the values in ./.env.

  REQUIRED secrets (vinu_api_key, alpaca_api_key, alpaca_api_secret,
  vinu_llm_api_key) cause a non-zero exit when still empty after populating --
  same "no silent default" discipline vinu_infra.config.require_data_root
  applies to data roots. OPTIONAL secrets (polygon, fmp, tushare, telegram,
  discord) may stay empty.

  Files are written without trailing-newline ambiguity (single trailing LF)
  and the directory is created if missing. Real credentials never reach git
  (repo .gitignore covers .env and secrets/).

.EXAMPLE
  .\scripts\setup-secrets.ps1 -Check   # validate only, writes nothing
  .\scripts\setup-secrets.ps1          # populate + fail if REQUIRED missing
#>
[CmdletBinding()]
param(
  [switch]$Check
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$SecretsDir = if ($env:VINU_SECRETS_DIR) { $env:VINU_SECRETS_DIR } else { Join-Path $Root "secrets" }
$EnvFile = Join-Path $Root ".env"

# secret file name -> legacy env var (matches what code reads from
# /run/secrets/<name>; the env var is the fallback).
$Secrets = [ordered]@{
  vinu_api_key     = "VINU_API_KEY"
  alpaca_api_key   = "ALPACA_API_KEY"
  alpaca_api_secret = "ALPACA_API_SECRET"
  polygon_api_key  = "POLYGON_API_KEY"
  fmp_api_key      = "FMP_API_KEY"
  tushare_token    = "TUSHARE_TOKEN"
  vinu_llm_api_key = "VINU_LLM_API_KEY"
  telegram_token   = "TELEGRAM_TOKEN"
  discord_token    = "DISCORD_TOKEN"
}
$Required = @("vinu_api_key", "alpaca_api_key", "alpaca_api_secret", "vinu_llm_api_key")

function Get-EnvFileValue([string]$Name) {
  $val = [Environment]::GetEnvironmentVariable($Name)
  if ($val) { return $val }
  if (Test-Path -LiteralPath $EnvFile) {
    # last occurrence wins (same as: grep -E "^VAR=" .env | tail -1)
    $line = Get-Content -LiteralPath $EnvFile | Where-Object { $_ -match "^$([regex]::Escape($Name))=" } | Select-Object -Last 1
    if ($line) { return $line.Substring($Name.Length + 1) }
  }
  return ""
}

if (-not $Check) {
  New-Item -ItemType Directory -Path $SecretsDir -Force | Out-Null
}

$missing = @()
foreach ($name in $Secrets.Keys) {
  $file = Join-Path $SecretsDir $name
  $existing = Get-Item -LiteralPath $file -ErrorAction SilentlyContinue | Where-Object { -not $_.PSIsContainer }
  $hasFile = ($null -ne $existing) -and ($existing.Length -gt 0)
  if ($Check) {
    if ($hasFile) {
      $value = "present"
    } else {
      $value = Get-EnvFileValue $Secrets[$name]
    }
    if (-not $value) {
      if ($Required -contains $name) {
        Write-Output "MISSING   $name (required) -- set $($Secrets[$name]) or ./secrets/$name"
        $missing += $name
      } else {
        Write-Output "empty     $name (optional) -- falls back to $($Secrets[$name]) env var"
      }
    } else {
      Write-Output "ok        $name"
    }
    continue
  }

  if ($hasFile) {
    Write-Output "keeping   $name (already populated)"
    continue
  }
  $value = Get-EnvFileValue $Secrets[$name]
  # single trailing LF, like printf '%s\n' in the .sh version
  Set-Content -LiteralPath $file -Value ($value + "`n") -NoNewline -Encoding Ascii
  if ($value) {
    Write-Output "populated $name from $($Secrets[$name])"
  } elseif ($Required -contains $name) {
    Write-Output "MISSING   $name (required) -- set $($Secrets[$name]) or ./secrets/$name"
    $missing += $name
  } else {
    Write-Output "empty     $name (optional) -- falls back to $($Secrets[$name]) env var"
  }
}

Write-Output ""
if ($missing.Count -gt 0) {
  Write-Output "FAILED: $($missing.Count) required secret(s) missing: $($missing -join ' ')"
  Write-Output "set them in .env (or `$env:NAME in this shell) and re-run this script before 'docker compose up'."
  exit 1
}

if ($Check) {
  Write-Output "all required secrets present"
} else {
  Write-Output "secret files ready under $SecretsDir"
  Write-Output "rotate any real value by editing the file and running: docker compose up -d --force-recreate"
}
