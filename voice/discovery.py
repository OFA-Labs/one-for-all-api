"""Read-only installed application catalog. Discovery alone never grants access."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import shutil
from collections import defaultdict
from pathlib import Path

from ofa_execution.config import App
from ofa_execution.windows import discover_apps
from ofa_execution.app_policy import allowed

# Fixed script: no transcript, browser path or user text is interpolated.
DISCOVER = r'''
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$shell = New-Object -ComObject WScript.Shell
$links = @()
foreach ($root in @([Environment]::GetFolderPath('StartMenu'), [Environment]::GetFolderPath('CommonStartMenu'))) {
  Get-ChildItem -LiteralPath $root -Filter *.lnk -Recurse | ForEach-Object {
    $s = $shell.CreateShortcut($_.FullName)
    if ($s.TargetPath -and (Test-Path -LiteralPath $s.TargetPath -PathType Leaf)) {
      $links += @{name=$_.BaseName; path=$_.FullName; executable=$s.TargetPath; arguments=$s.Arguments; cwd=$s.WorkingDirectory}
    }
  }
}
@{start=@(Get-StartApps | Select-Object Name, AppID); links=$links} | ConvertTo-Json -Depth 5 -Compress
'''


def app_id(app: App) -> str:
    if app.launch_kind in {"exe", "shortcut", "interactive_command"}:
        identity = str(Path(app.executable).resolve()).casefold()+repr(app.arguments)
        kind = "interactive_command" if app.launch_kind == "interactive_command" else "exe"
    else:
        identity, kind = app.launch_identity.casefold(), app.launch_kind
    return hashlib.sha256((kind + ':' + identity).encode()).hexdigest()[:24]


def split_arguments(raw: str) -> list[str]:
    if not raw: return []
    import ctypes
    from ctypes import wintypes as wt
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    shell.CommandLineToArgvW.argtypes = [wt.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype = ctypes.POINTER(wt.LPWSTR)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    count = ctypes.c_int()
    argv = shell.CommandLineToArgvW('app.exe '+raw, ctypes.byref(count))
    if not argv: raise ValueError("Shortcut arguments could not be validated")
    try: return [argv[i] for i in range(1, count.value)]
    finally: kernel.LocalFree(argv)


def canonicalize(found: list[App]) -> list[App]:
    """Merge exact launch identities; retain distinct products with qualified names."""
    unique: dict[str, App] = {}
    for app in found:
        if not allowed(app, discovered=True): continue
        key = app_id(app)
        if key in unique:
            prior = unique[key]
            prior.aliases = list(dict.fromkeys([*prior.aliases, app.name, *app.aliases]))
        else:
            unique[key] = app.model_copy(deep=True)
    groups = defaultdict(list)
    for app in unique.values(): groups[app.name.casefold()].append(app)
    output = []
    for group in groups.values():
        stores = [a for a in group if a.launch_kind == "aumid"]
        ordinary = [a for a in group if a.launch_kind != "aumid"]
        if len(stores) == 1:
            # The Start Menu's packaged app is canonical for this display name;
            # executable aliases (Notepad, Slack) do not create a second target.
            preferred = stores[0]
            preferred.aliases = list(dict.fromkeys([*preferred.aliases,
                *(alias for app in ordinary for alias in [app.name,*app.aliases])]))
            output.append(preferred)
        elif len(group) > 1:
            for index, app in enumerate(group):
                original = app.name
                qualifier = (app.launch_identity.split("_")[0].removeprefix("Microsoft.")
                             if app.launch_kind == "aumid" else f"desktop {index+1}")
                words = qualifier.replace(".", " ").split()
                prefix = " ".join(word for word in words if word.casefold()!=original.casefold())
                app.name = f"{original} ({qualifier})"
                app.aliases = list(dict.fromkeys([original,*app.aliases, f"{prefix} {original}".strip()]))
                output.append(app)
        else: output.extend(group)
    return sorted(output, key=lambda app: app.name.casefold())


def discover() -> list[App]:
    if os.name != "nt":
        return []
    process = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", DISCOVER],
        capture_output=True, encoding="utf-8-sig", timeout=40, check=True)
    payload = json.loads(process.stdout)
    found: list[App] = []
    for row in payload.get("start", []):
        if re.fullmatch(r"[\w.-]+_[\w]+![\w.-]+", row["AppID"]):
            found.append(App(name=row["Name"], launch_kind="aumid", launch_identity=row["AppID"]))
    for row in payload.get("links", []):
        if Path(row["executable"]).suffix.lower() == ".exe":
            # Resolve shortcuts once; executing a mutable .lnk later could change
            # the validated target. Store the fixed executable/argv instead.
            found.append(App(name=row["name"], executable=row["executable"],
                arguments=split_arguments(row.get("arguments", "")), working_directory=row.get("cwd", "")))
    for row in discover_apps():
        found.append(App(name=Path(row["name"]).stem, executable=row["executable"]))
    # Alias preferences are catalog data. Newly discovered apps need no code branch.
    preferences = {"visual studio code": ["vs code", "vscode", "code editor"],
                   "whatsapp": ["whats app", "व्हाट्सऐप", "व्हाट्सएप"],
                   "claude": ["claude desktop"]}
    for app in found:
        app.aliases = preferences.get(app.name.casefold(), [])
    code, host = shutil.which("claude.exe"), shutil.which("wt.exe")
    if code and host:
        found.append(App(name="Claude Code", executable=code, launch_identity=code,
                         launch_kind="interactive_command", console_host=host, aliases=["claude code cli"]))
    return canonicalize(found)
