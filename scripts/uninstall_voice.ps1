[CmdletBinding(SupportsShouldProcess)]
param([switch]$RemoveSavedData)
$ErrorActionPreference = 'Stop'
$voiceBase = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'OFA'))
$voiceDestination = [IO.Path]::GetFullPath((Join-Path $voiceBase 'Desktop'))
if (-not $voiceDestination.StartsWith($voiceBase + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid uninstall target.' }
if (Get-Process -Name 'OFA-Desktop' -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($voiceDestination + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) }) { throw 'Quit OFA Desktop before uninstalling.' }
if ($PSCmdlet.ShouldProcess($voiceDestination,'Remove installed OFA Desktop files')) {
    if (Test-Path -LiteralPath $voiceDestination) { Remove-Item -LiteralPath $voiceDestination -Recurse -Force }
    foreach ($voiceFolder in @('Programs','Startup')) {
        $voiceLink = Join-Path ([Environment]::GetFolderPath($voiceFolder)) 'OFA Desktop.lnk'
        if (Test-Path -LiteralPath $voiceLink) { Remove-Item -LiteralPath $voiceLink -Force }
    }
    Remove-ItemProperty -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'OFA Desktop' -ErrorAction SilentlyContinue
}
if ($RemoveSavedData) {
    $voiceData = [IO.Path]::GetFullPath((Join-Path $voiceBase 'voice'))
    if (-not $voiceData.StartsWith($voiceBase + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid data target.' }
    if ($PSCmdlet.ShouldProcess($voiceData,'Remove saved pairing, credentials and desktop permissions')) {
        if (Test-Path -LiteralPath $voiceData) { Remove-Item -LiteralPath $voiceData -Recurse -Force }
    }
}
Write-Output 'Uninstall finished. Saved settings and rollback backups are retained unless explicitly removed.'
