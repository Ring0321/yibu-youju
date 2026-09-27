$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root '.env.g0'
if (Test-Path -LiteralPath $target) {
    Write-Output 'Existing isolated G0 configuration retained; no secrets printed.'
    exit 0
}
function New-Secret {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
}
$lines = @(
    'G0_DB_PASSWORD=' + (New-Secret)
    'SECRET_KEY=' + (New-Secret)
    'FIRST_SUPERUSER_PASSWORD=' + (New-Secret)
)
[System.IO.File]::WriteAllLines($target, $lines, (New-Object System.Text.UTF8Encoding($false)))
Write-Output 'Created random local-only G0 credentials; ignored by Git and Docker build context.'
