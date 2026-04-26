param(
    [string]$AgentchattrRoot = "c:\Users\claud\source\agentchattr",
    [string]$RoutifyRoot = "c:\Users\claud\Desktop\Routify",
    [string]$ApiBaseUrl = "http://127.0.0.1:8300",
    [int]$TimeoutSeconds = 15
)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptDir 'verify_northstar_governance.py'

& python $pythonScript --agentchattr-root $AgentchattrRoot --routify-root $RoutifyRoot --api-base-url $ApiBaseUrl --timeout-seconds $TimeoutSeconds
$exitCode = $LASTEXITCODE
exit $exitCode