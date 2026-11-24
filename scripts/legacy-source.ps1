param([ValidateSet("start","stop")][string]$Action = "start")
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$legacy = (Resolve-Path (Join-Path $root "../lab")).Path
$exe = Join-Path $legacy "bin/rustfs.exe"
$marker = Join-Path $root "tmp/legacy-source.pid"
if ($Action -eq "stop") {
    if (Test-Path -LiteralPath $marker) {
        $process = Get-Process -Id ([int](Get-Content -LiteralPath $marker)) -ErrorAction SilentlyContinue
        if ($process -and $process.Path -eq $exe -and $process.CommandLine -like "*127.0.0.1:19020*") {
            Stop-Process -Id $process.Id
        }
    }
    return
}
if (Get-Process -Name rustfs -ErrorAction SilentlyContinue) {
    throw "Existing RustFS process. Use its S3 endpoint as LEGACY_ENDPOINT instead of opening the same disks twice."
}
$keys = Get-Content -Raw -LiteralPath (Join-Path $legacy ".credentials.json") | ConvertFrom-Json
$env:RUSTFS_ACCESS_KEY = $keys.access
$env:RUSTFS_SECRET_KEY = $keys.secret
$env:RUSTFS_VOLUMES = "./disks/disk{1...4}"
$env:RUSTFS_STORAGE_CLASS_STANDARD = "EC:2"
$env:RUSTFS_UNSAFE_BYPASS_DISK_CHECK = "true"
$env:RUSTFS_OBS_LOG_DIRECTORY = Join-Path $root "tmp/legacy-logs"
$env:RUSTFS_OBS_LOGGER_LEVEL = "warn"
$env:RUST_LOG = "warn"
$proc = Start-Process -FilePath $exe -ArgumentList "server","--address","127.0.0.1:19020" -WorkingDirectory $legacy -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $root "tmp/legacy.stdout") -RedirectStandardError (Join-Path $root "tmp/legacy.stderr")
Set-Content -LiteralPath $marker -Value $proc.Id
Write-Output "Lab 2 S3 source http://127.0.0.1:19020, PID $($proc.Id)"
