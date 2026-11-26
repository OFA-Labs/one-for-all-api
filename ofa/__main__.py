"""OFA entry point.

    python -m ofa --env-file .env             the assistant: your companion panel, Caps Lock, web pages
    python -m ofa say "open notepad"          one typed turn (typed text can never approve Tier-2 actions)
    python -m ofa text                        typed REPL
    python -m ofa vault                       open the local vault page (only needed to add secrets)
    python -m ofa doctor | audit | memory     diagnostics, audit tail, remembered mappings
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import secrets
import sys
import threading
import webbrowser

from .config import OfaConfig, load_env_file


def _core():
    from .runtime import build_core
    return build_core(OfaConfig())


def doctor() -> None:
    from . import live_budget
    from .harness import win
    from .vault.pm import detect
    from .vault.unlock import HelloVerifier
    cfg = OfaConfig()
    try:
        import sounddevice as sd
        mics = sum(1 for d in sd.query_devices() if d["max_input_channels"] > 0)
    except Exception:
        mics = 0
    print(json.dumps({"os": platform.platform(), "python": platform.python_version(), "keys_set": cfg.names_set(),
                      "engine": cfg.engine, "model": cfg.groq_model, "microphones": mics,
                      "uia": importable("comtypes"), "ocr_languages": win.ocr_languages(),
                      "windows_hello": HelloVerifier().available(), "password_managers": list(detect()),
                      "live_calls_used": live_budget.used()}, indent=1))


def importable(name: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(name) is not None


async def one_turn(text: str) -> None:
    core = _core()
    res = await core.orchestrator.handle(text)
    print(json.dumps({"status": res.status, "spoken": res.spoken, "actions": res.actions}, ensure_ascii=False, indent=1))


async def repl() -> None:
    core = _core()
    print("OFA typed mode. Consequential actions need a spoken yes, so they will not run here. Ctrl+C to quit.")
    while True:
        text = await asyncio.to_thread(input, "you> ")
        if not text.strip():
            continue
        res = await core.orchestrator.handle(text)
        print("ofa>", res.spoken, f"[{res.status}]")


def run_companion(env_file: str | None) -> None:
    """Start the Windows companion (native panel, Caps Lock, pairing, web pages) with OFA as its brain."""
    from voice.__main__ import main as companion_main
    sys.argv = ["ofa", "--live", *(["--env-file", env_file] if env_file else [])]
    companion_main()


def run_vault() -> None:
    from .runtime import build_core
    from .server import create_app, serve
    core = build_core(OfaConfig())
    token = secrets.token_urlsafe(32)
    url = f"http://127.0.0.1:{core.cfg.port}/vault#token={token}"
    print("Vault: " + url + "   (Ctrl+C to close)")
    threading.Timer(1.0, webbrowser.open, (url,)).start()
    try:
        asyncio.run(serve(create_app(core, token), core.cfg.port))
    except KeyboardInterrupt:
        pass


def main() -> None:
    p = argparse.ArgumentParser(prog="ofa")
    p.add_argument("command", nargs="?", default="run", choices=["run", "say", "text", "vault", "doctor", "audit", "memory"])
    p.add_argument("rest", nargs="*")
    p.add_argument("--env-file", default=os.getenv("OFA_ENV_FILE"))
    a = p.parse_args()
    load_env_file(a.env_file)
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if a.command == "doctor":
        doctor()
    elif a.command == "say":
        asyncio.run(one_turn(" ".join(a.rest)))
    elif a.command == "text":
        asyncio.run(repl())
    elif a.command == "audit":
        core = _core()
        for e in core.audit.entries(int(a.rest[0]) if a.rest else 20):
            print(json.dumps(e, ensure_ascii=False))
        print("chain_ok:", core.audit.verify_chain())
    elif a.command == "memory":
        core = _core()
        if a.rest[:1] == ["forget"] and len(a.rest) > 1:
            print("deleted:", core.memory.forget(" ".join(a.rest[1:])))
        elif a.rest[:1] == ["clear"]:
            core.memory.delete_all()
            print("all memory deleted")
        else:
            print(json.dumps({"profile": core.memory.profile(), "mappings": core.memory.mappings()}, indent=1, ensure_ascii=False))
    elif a.command == "vault":
        run_vault()
    else:
        run_companion(a.env_file)


if __name__ == "__main__":
    main()
