param(
    [string]$PythonBin = "__PYTHON_BIN__",
    [string]$RepoRoot = "__REPO_ROOT__",
    [string]$ConfigPath = "__CONFIG_PATH__",
    [string]$WorkingDirectory = "__WORKING_DIR__"
)

$ErrorActionPreference = "Stop"

Set-Location -Path $WorkingDirectory

$mainScript = Join-Path $RepoRoot "tools/rime-userdb-sync/main.py"
$arguments = @(
    $mainScript,
    "--config",
    $ConfigPath,
    "sync"
)

& $PythonBin @arguments
exit $LASTEXITCODE
