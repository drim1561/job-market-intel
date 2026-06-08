# Loads .env (located next to this script) into the current PowerShell session as
# environment variables, so terraform and dbt can read them.
# Usage:  .\load-env.ps1   (from the project root)
#    or:  & "C:\Users\Teddy\Desktop\job-market-intel\load-env.ps1"   (from anywhere)
$envFile = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $envFile)) {
    Write-Error "No .env found at $envFile"
    return
}
Get-Content $envFile | Where-Object { $_ -match '^\s*[^#].+=' } | ForEach-Object {
    $k, $v = $_ -split '=', 2
    [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim())
}
Write-Host "Loaded environment variables from $envFile"
