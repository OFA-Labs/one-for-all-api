param()
$ErrorActionPreference = 'Stop'
$voiceRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $voiceRoot
try {
    $voicePython = Join-Path $voiceRoot '.venv-voice/Scripts/python.exe'
    function Invoke-VoicePython([string[]]$VoiceArguments) {
        $voicePreference = $ErrorActionPreference
        try {
            # Windows PowerShell 5 treats ordinary native stderr progress as an
            # ErrorRecord when redirected. The process exit code is authoritative.
            $ErrorActionPreference = 'Continue'
            & $voicePython @VoiceArguments
            $voiceExit = $LASTEXITCODE
        } finally { $ErrorActionPreference = $voicePreference }
        if ($voiceExit -ne 0) { throw "Voice build tool failed (exit $voiceExit)." }
    }
    Invoke-VoicePython @('-m','pip','install','-r','requirements-voice-dev.lock')
    Invoke-VoicePython @('-m','PyInstaller','--noconfirm','--onedir','--windowed','--name','OFA-Desktop','--paths',$voiceRoot,'--collect-all','comtypes','--collect-all','hassil','--collect-data','unicode_rbnf','--add-data','voice/assets;voice/assets','scripts/voice_entry.py')
    Copy-Item -LiteralPath 'scripts/install_voice.ps1' -Destination 'dist/install_voice.ps1'
    Copy-Item -LiteralPath 'scripts/uninstall_voice.ps1' -Destination 'dist/uninstall_voice.ps1'
    Compress-Archive -Path 'dist/OFA-Desktop', 'dist/install_voice.ps1', 'dist/uninstall_voice.ps1' -DestinationPath 'dist/OFA-Desktop-Windows.zip' -Force
    Write-Output 'Development bundle: dist/OFA-Desktop-Windows.zip (unsigned)'
} finally { Pop-Location }
