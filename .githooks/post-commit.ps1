$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$py311 = "D:\panzubin\download\Conda\envs\py311\python.exe"
$pyScript = Join-Path $repoRoot "scripts\update_project_md.py"
$psScript = Join-Path $repoRoot "scripts\update_project_md.ps1"

if (Test-Path $py311) {
    try {
        & $py311 $pyScript
        exit 0
    }
    catch {
        Write-Warning "py311 script update failed, fallback to PowerShell generator."
    }
}

& powershell -NoProfile -ExecutionPolicy Bypass -File $psScript
