"""Shared application policy. A discovered executable is not automatically a GUI app."""
from __future__ import annotations
import re
from pathlib import Path

SENSITIVE = ("password", "keepass", "1password", "bitwarden", "lastpass", "settings",
             "powershell", "terminal", "regedit", "registry editor", "credential",
             "uninstall", "installer", "setup", "updater", "windows security", "defender",
             "antimalware", "mcafee", "administrative tools", "system configuration",
             "task manager", "resource monitor", "memory diagnostics", "recoverydrive",
             "disk cleanup", "odbc data sources", "iscsi initiator", "git bash", "git cmd")
BINARIES = {"cmd", "pwsh", "powershell", "powershell_ise", "wt", "wsl", "wslhost",
            "bash", "sh", "git-bash", "git-cmd", "regedit", "reg", "regsvr32", "mshta",
            "wscript", "cscript", "rundll32", "control", "mmc", "taskmgr", "resmon",
            "dfrgui", "cleanmgr", "recoverydrive", "msconfig", "quickassist", "systemsettings"}
HELPERS = {"msoadfsb", "msoasb", "msoxmled", "sdxhelper", "skypeserver", "ms-teamsupdate",
           "windowspackagemanagerserver", "xboxpcappadminserver", "xboxpcappce", "winget"}


def allowed(app, *, discovered: bool = False) -> bool:
    name = re.sub(r"\s+", " ", app.name.casefold())
    binary = Path(app.executable).stem.casefold()
    if any(word in name or word in Path(app.executable).name.casefold() for word in SENSITIVE):
        return False
    if binary in BINARIES or binary in HELPERS or name in HELPERS:
        return False
    if any(word in name or word in binary for word in ("askpass", "ssh-proxy", "make-data-folder", "shellmcp", "ms-resource:")):
        return False
    if discovered and binary in {"python", "pythonw", "node", "conhost", "openconsole"}:
        return False
    # An interactive Code target is narrowly configured by the native discovery
    # layer; it never accepts a shell command or a browser-provided argument.
    if app.launch_kind == "interactive_command":
        return binary == "claude" and not app.arguments
    return True
