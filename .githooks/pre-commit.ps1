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

$pythonFiles = @($stagedFiles | Where-Object { $_ -match "\.py$" })

Push-Location $repoRoot
try {
    if ($pythonFiles.Count -eq 0) {
        exit 0
    }

    & $pythonExe -m black --config black.toml @pythonFiles
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $pythonExe -m ruff check --fix @pythonFiles
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    git add -- @pythonFiles
    exit 0
}
finally {
    Pop-Location
}
