param([string]$Handoff)
$ErrorActionPreference = 'Stop'
$apiRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $apiRoot
try {
    if (-not (Test-Path -LiteralPath '.venv-voice/Scripts/python.exe')) {
        & py -3.12 -m venv .venv-voice
        if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 with the py launcher.' }
    }
    $voicePython = Join-Path $apiRoot '.venv-voice/Scripts/python.exe'
    function Invoke-VoicePython([string[]]$VoiceArguments) {
        $voicePreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            & $voicePython @VoiceArguments
            $voiceExit = $LASTEXITCODE
        } finally { $ErrorActionPreference = $voicePreference }
        if ($voiceExit -ne 0) { throw "Voice setup tool failed (exit $voiceExit)." }
    }
    Invoke-VoicePython @('-m','pip','install','-r','requirements-voice-dev.lock')
    if ($Handoff) {
        Invoke-VoicePython @('scripts/handoff_check.py','--handoff',$Handoff)
    }
    Invoke-VoicePython @('-m','voice','--fake-demo')
    Write-Output 'SETUP_OK'
} finally {
    Pop-Location
}
