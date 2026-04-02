$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$py311 = "D:\panzubin\download\Conda\envs\py311\python.exe"

function Get-PythonCommand {
    if (Test-Path $py311) {
        return $py311
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $pythonCmd) {
        return $pythonCmd.Source
    }

    throw "Python executable not found. Please activate the py311 environment first."
}

$pythonExe = Get-PythonCommand
$stagedFiles = git diff --cached --name-only --diff-filter=ACMR

if (-not $stagedFiles) {
    exit 0
}

Push-Location $repoRoot
try {
    & $pythonExe -m pre_commit run --config .pre-commit-config.yaml --hook-stage pre-commit --files @stagedFiles
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
