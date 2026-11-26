"""Local diagnostics; --probe-mic explicitly consents to a short device probe."""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sounddevice as sd

from voice.handoff import load_handoff, settings_from_handoff
from voice.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handoff")
    parser.add_argument("--env-file")
    parser.add_argument("--probe-mic", action="store_true")
    args = parser.parse_args()
    failures: list[str] = []
    if args.env_file:
        from dotenv import load_dotenv
        load_dotenv(args.env_file, override=False)
    settings = settings_from_handoff(load_handoff(args.handoff)) if args.handoff else Settings.from_env()
    if sys.version_info[:2] != (3, 12):
        failures.append("PYTHON: install Python 3.12 and recreate only the voice venv")
    try:
        node = subprocess.run(["node", "--version"], check=True, capture_output=True,
                              text=True, timeout=3).stdout.strip()
        if int(node.lstrip("v").split(".")[0]) < 22:
            failures.append("NODE: install the repo-recommended Node 24")
    except (OSError, subprocess.SubprocessError):
        failures.append("NODE: put Node 24 on PATH for the optional web observer")
    if os.name != "nt":
        failures.append("OS: M0 native activation currently requires Windows")
    try:
        sd.check_input_settings(device=settings.input_device, channels=1,
                                dtype="int16", samplerate=settings.input_rate)
        sd.check_output_settings(device=settings.output_device, channels=1,
                                 dtype="int16", samplerate=24000)
        print("AUDIO_FORMATS_OK")
        if args.probe_mic:
            with sd.RawInputStream(samplerate=settings.input_rate, channels=1,
                                   dtype="int16", device=settings.input_device):
                sd.sleep(80)
            print("MIC_PROBE_OK")
        else:
            print("MIC_PERMISSION_UNVERIFIED: rerun with --probe-mic when ready")
    except Exception:
        failures.append("AUDIO: allow desktop microphone access, close exclusive audio apps, or select a supported device/rate")
    with socket.socket() as listener:
        try:
            listener.bind(("127.0.0.1", settings.port))
            print("VOICE_PORT_OK")
        except OSError:
            failures.append("PORT: stop the previous voice host or configure another local port")
    for failure in failures:
        print(failure)
    print("DOCTOR_FAILED" if failures else "DOCTOR_OK")
    raise SystemExit(int(bool(failures)))


if __name__ == "__main__":
    main()
