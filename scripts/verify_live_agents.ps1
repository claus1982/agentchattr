param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ForwardArgs
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = 'C:/Users/claud/AppData/Local/Programs/Python/Python312/python.exe'
if (-not (Test-Path $pythonExe)) {
    $pythonExe = 'python'
}

$patterns = @(
    'agentchattr\\run\.py',
    'agentchattr\\wrapper_copilot\.py'
)

try {
    $processes = Get-CimInstance Win32_Process | Where-Object {
        $commandLine = $_.CommandLine
        if (-not $commandLine) { return $false }
        foreach ($pattern in $patterns) {
            if ($commandLine -match $pattern) {
                return $true
            }
        }
        return $false
    }

    foreach ($process in $processes) {
        try {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
        } catch {
        }
    }
} catch {
}

& $pythonExe (Join-Path $PSScriptRoot 'verify_live_agents.py') @ForwardArgs
exit $LASTEXITCODE