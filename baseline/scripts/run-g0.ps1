param(
    [ValidateSet('Build', 'Tests', 'Write', 'Read', 'Database', 'RestartDatabase', 'Lint', 'Workflow')][string]$Phase = 'Build',
    [ValidatePattern('^yibu-g0(?:-[a-z0-9-]+)?$')][string]$ProjectName = 'yibu-g0'
)
$ErrorActionPreference = 'Stop'
if ($env:G0_IMAGE_REGISTRY -and $env:G0_IMAGE_REGISTRY -notin @('public.ecr.aws/docker/library', 'docker.io/library')) {
    throw 'Only the two documented official image sources are allowed; pinned digests must remain unchanged.'
}
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$evidence = Join-Path $root ('evidence/' + $ProjectName)
[System.IO.Directory]::CreateDirectory($evidence) | Out-Null
$env:G0_EVIDENCE_DIR = './evidence/' + $ProjectName
$prefix = @('compose', '--project-name', $ProjectName, '--env-file', '.env.g0', '-f', 'compose.g0.yml', '--progress', 'plain')
switch ($Phase) {
    'Build' { $arguments = $prefix + @('build', 'tests') }
    'Database' { $arguments = $prefix + @('up', '-d', '--wait', 'db') }
    'RestartDatabase' { $arguments = $prefix + @('restart', '--timeout', '10', 'db') }
    'Lint' { $arguments = $prefix + @('run', '--rm', '--no-deps', 'tests', 'ruff', 'check', 'scripts/g0_verify.py', 'scripts/g0_runtime_probe.py', 'scripts/g0_pytest.py', 'scripts/g0_workflow_verify.py', 'g0', 'integration_tests') }
    'Workflow' { $arguments = $prefix + @('run', '--rm', '--no-deps', 'tests', 'python', 'scripts/g0_workflow_verify.py') }
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
$report = @{ phase = $Phase; project = $ProjectName; started_at = $started.ToString('o'); completed_at = [DateTime]::UtcNow.ToString('o'); exit_code = $code; log = $stem + '.log'; kind = 'G0_template_validation_only' }
[System.IO.File]::WriteAllText((Join-Path $evidence ($stem + '.json')), ($report | ConvertTo-Json), $encoding)
Write-Output $log
exit $code
