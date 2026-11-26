param([switch]$StartOnLogin)
$ErrorActionPreference = 'Stop'
$voiceBundle = Join-Path $PSScriptRoot 'OFA-Desktop'
$voiceBase = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'OFA'))
$voiceDestination = [IO.Path]::GetFullPath((Join-Path $voiceBase 'Desktop'))
if (-not $voiceDestination.StartsWith($voiceBase + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Invalid installation destination.'
}
if (-not (Test-Path -LiteralPath (Join-Path $voiceBundle 'OFA-Desktop.exe'))) {
    throw 'Extract the entire development ZIP before running this installer.'
}
New-Item -ItemType Directory -Path $voiceBase -Force | Out-Null
$voiceRunning = Get-Process -Name 'OFA-Desktop' -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($voiceDestination + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) }
if ($voiceRunning) { throw 'Quit the running OFA Desktop companion before updating. Pairing and speech settings will be retained.' }
$voiceStaged = [IO.Path]::GetFullPath((Join-Path $voiceBase ('Desktop-update-' + [guid]::NewGuid().ToString('N'))))
$voiceBackup = [IO.Path]::GetFullPath((Join-Path $voiceBase ('Desktop-backup-' + [guid]::NewGuid().ToString('N'))))
foreach ($voiceChecked in @($voiceStaged,$voiceBackup)) {
    if (-not $voiceChecked.StartsWith($voiceBase + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid update destination.' }
}
New-Item -ItemType Directory -Path $voiceStaged | Out-Null
Copy-Item -Path (Join-Path $voiceBundle '*') -Destination $voiceStaged -Recurse -Force
if (-not (Test-Path -LiteralPath (Join-Path $voiceStaged 'OFA-Desktop.exe'))) { throw 'Staged companion is incomplete.' }
$voiceOldMoved = $false
try {
    if (Test-Path -LiteralPath $voiceDestination) { Move-Item -LiteralPath $voiceDestination -Destination $voiceBackup; $voiceOldMoved = $true }
    Move-Item -LiteralPath $voiceStaged -Destination $voiceDestination
} catch {
    if ($voiceOldMoved -and -not (Test-Path -LiteralPath $voiceDestination)) { Move-Item -LiteralPath $voiceBackup -Destination $voiceDestination }
    throw
}
$voiceShell = New-Object -ComObject WScript.Shell
$voiceShortcutPath = Join-Path ([Environment]::GetFolderPath('Programs')) 'OFA Desktop.lnk'
$voiceShortcut = $voiceShell.CreateShortcut($voiceShortcutPath)
$voiceShortcut.TargetPath = Join-Path $voiceDestination 'OFA-Desktop.exe'
$voiceShortcut.WorkingDirectory = $voiceDestination
$voiceShortcut.Save()
if ($StartOnLogin) {
    $voiceRunKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
    New-ItemProperty -Path $voiceRunKey -Name 'OFA Desktop' -Value ('"' + (Join-Path $voiceDestination 'OFA-Desktop.exe') + '" --live') -PropertyType String -Force | Out-Null
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'uninstall_voice.ps1') -Destination $voiceBase -Force
Write-Output 'Installed for the current Windows user. Start OFA Desktop from the Start Menu. Pairing and protected settings were retained. Any previous build was kept in the sibling Desktop-backup folder for rollback.'
