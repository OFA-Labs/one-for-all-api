"""Per-user opt-in startup, using the installed app only."""
from pathlib import Path
import os


def set_startup(enabled):
    import winreg
    app=Path(os.environ["LOCALAPPDATA"])/"OFA/Desktop/OFA-Desktop.exe"
    if enabled and not app.is_file():
        raise ValueError("Install the companion first")
    legacy=Path(os.environ["APPDATA"])/"Microsoft/Windows/Start Menu/Programs/Startup/OFA Desktop.lnk"
    if legacy.is_file(): legacy.unlink()
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
        if enabled: winreg.SetValueEx(key,"OFA Desktop",0,winreg.REG_SZ,'"'+str(app)+'" --live')
        else:
            try: winreg.DeleteValue(key,"OFA Desktop")
            except FileNotFoundError: pass
