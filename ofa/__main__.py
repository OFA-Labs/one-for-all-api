"""OFA entry point.

    python -m ofa [--env-file F]            voice session: Caps Lock toggles, orb top-middle, loopback API
    python -m ofa say "open notepad"        one typed turn (typed text can never approve Tier-2 actions)
    python -m ofa text                      typed REPL
    python -m ofa vault                     open the vault enrollment page
    python -m ofa doctor | audit | memory   diagnostics, audit tail, remembered mappings
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


def run_voice(open_vault: bool = False, voice_enabled: bool = True) -> None:
    from voice.hotkey import CapsHook
    from voice.instance import acquire

    from .orb import NullOrb, Orb
    from .runtime import build_core, build_voice
    from .server import create_app, serve

    if not acquire():
        print("OFA is already running in this Windows session.")
        return
    core = build_core(OfaConfig())
    token = secrets.token_urlsafe(32)
    port = core.cfg.port
    orb = Orb() if voice_enabled else NullOrb()
    state: dict = {}

    async def main():
        loop = asyncio.get_running_loop()
        voice = build_voice(core, orb.set) if voice_enabled else None
        app = create_app(core, voice, token)
        if voice is not None:
            hook = CapsHook(lambda: loop.call_soon_threadsafe(lambda: asyncio.ensure_future(voice.toggle()))).start()
            state["hook"] = hook
        print("OFA ready. Press Caps Lock to talk." if voice else "OFA server ready.")
        print(f"Dashboard: http://127.0.0.1:3000/ofa#port={port}&token={token}")
        print(f"Vault:     http://127.0.0.1:{port}/vault#token={token}")
        if open_vault:
            webbrowser.open(f"http://127.0.0.1:{port}/vault#token={token}")
        await serve(app, port)

    def worker():
        try:
            asyncio.run(main())
        except BaseException as exc:   # surface, never hang silently
            print("OFA stopped:", type(exc).__name__, exc)
        finally:
            orb.close()
    t = threading.Thread(target=worker, name="ofa-core", daemon=True)
    t.start()
    try:
        if isinstance(orb, Orb):
            orb.run()
        else:
            t.join()
    except KeyboardInterrupt:
        pass
    finally:
        if state.get("hook"):
            state["hook"].close()


def main() -> None:
    p = argparse.ArgumentParser(prog="ofa")
    p.add_argument("command", nargs="?", default="run", choices=["run", "say", "text", "vault", "doctor", "audit", "memory", "server"])
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
        run_voice(open_vault=True, voice_enabled=False)
    elif a.command == "server":
        run_voice(voice_enabled=False)
    else:
        run_voice()


if __name__ == "__main__":
    main()
