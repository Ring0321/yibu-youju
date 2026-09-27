param([ValidateSet('Build', 'Tests', 'Write', 'Read', 'Database', 'RestartDatabase', 'Lint')][string]$Phase = 'Build')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$evidence = Join-Path $root 'evidence/g0'
[System.IO.Directory]::CreateDirectory($evidence) | Out-Null
$prefix = @('compose', '--env-file', '.env.g0', '-f', 'compose.g0.yml', '--progress', 'plain')
switch ($Phase) {
    'Build' { $arguments = $prefix + @('build', 'tests') }
    'Database' { $arguments = $prefix + @('up', '-d', '--wait', 'db') }
    'RestartDatabase' { $arguments = $prefix + @('restart', '--timeout', '10', 'db') }
    'Lint' { $arguments = $prefix + @('run', '--rm', '--no-deps', 'tests', 'ruff', 'check', 'scripts/g0_verify.py', 'scripts/g0_runtime_probe.py', 'scripts/g0_pytest.py') }
    'Tests' { $arguments = $prefix + @('run', '--rm', '--no-deps', 'tests') }
    'Write' { $arguments = $prefix + @('run', '--rm', '--no-deps', 'tests', 'python', 'scripts/g0_runtime_probe.py', 'write') }
    'Read' { $arguments = $prefix + @('run', '--rm', '--no-deps', 'tests', 'python', 'scripts/g0_runtime_probe.py', 'read') }
}
$started = [DateTime]::UtcNow
$previous = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $lines = & docker @arguments 2>&1
    $code = $LASTEXITCODE
} finally { $ErrorActionPreference = $previous }
$log = ($lines | ForEach-Object { $_.ToString() }) -join "`n"
$log = [regex]::Replace($log, '\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b', '[REDACTED_JWT]')
foreach ($line in [System.IO.File]::ReadAllLines((Join-Path $root '.env.g0'))) {
    $pair = $line -split '=', 2
    if ($pair.Count -eq 2 -and $pair[1].Length -ge 16) { $log = $log.Replace($pair[1], '[REDACTED]') }
}
$encoding = New-Object System.Text.UTF8Encoding($false)
$stem = 'phase-' + $Phase.ToLowerInvariant() + '-' + $started.ToString('yyyyMMddTHHmmssZ')
[System.IO.File]::WriteAllText((Join-Path $evidence ($stem + '.log')), $log, $encoding)
$report = @{ phase = $Phase; started_at = $started.ToString('o'); completed_at = [DateTime]::UtcNow.ToString('o'); exit_code = $code; log = $stem + '.log'; kind = 'G0_template_validation_only' }
[System.IO.File]::WriteAllText((Join-Path $evidence ($stem + '.json')), ($report | ConvertTo-Json), $encoding)
Write-Output $log
exit $code
