"""python -m voice --handoff PATH --consent; local-first Windows companion."""
from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import threading
import sys
from pathlib import Path
from typing import Any

import uvicorn

from .api import create_app
from .bridge import EngineBridge
from .deepgram import DeepgramStt, DeepgramTts
from .events import Events
from .failover import Breaker, SttChain
from .gradium import GradiumStt, GradiumTts
from .handoff import load_handoff, settings_from_handoff
from .hotkey import CapsHook
from .intent import Router
from .overlay import Overlay
from .session import Session
from .speech import Speech
from .tts.ack_cache import AckCache
from .config import Settings
from .discovery import discover, app_id
from .pairing import Pairing, LocalDevelopmentSessionPort
from .protected_store import ProtectedStore
from .capabilities import CapabilityDispatcher, ReasoningGate, Receipt, MissingCapability


async def serve(handoff: Any, consent: bool, overlay: Overlay,
                control: dict[str, Any]) -> None:
    from ofa_execution.browser import BrowserHand
    from ofa_execution.config import App, LocalConfig
    from ofa_execution.engine import Engine
    from ofa_execution.files import FileHand
    from ofa_execution.hotkey import StopHotkey
    from ofa_execution.planner import DeterministicPlanner
    from ofa_execution.windows import DesktopHand
    from ofa_execution.websites import WebsiteHand
    from ofa_execution.slack import SlackHand
    from .runtime import Runtime

    settings = settings_from_handoff(handoff, consent) if handoff else Settings.from_env()
    settings.consent = True  # Native pairing consent is additionally mandatory before arming.
    discovered = discover()
    allowed = [App.model_validate(a) for a in handoff.apps["allowlist"]] if handoff else discovered
    config = LocalConfig(
        apps=allowed,
        browser_command=handoff.execution.get("browser_command", []) if handoff else ([os.environ["OFA_BROWSE_BINARY"],"mcp"] if os.getenv("OFA_BROWSE_BINARY") else []),
        allowed_origins=handoff.execution.get("allowed_origins", []) if handoff else [origin.strip() for origin in os.getenv("OFA_BROWSER_ORIGINS","").split(",") if origin.strip()],
        read_roots=handoff.execution.get("read_roots", []) if handoff else [],
        write_roots=handoff.execution.get("write_roots", []) if handoff else [],
    )
    valid = []
    for app in config.apps:
        try:
            # Ambiguous names remain choices; validate each actual candidate in isolation.
            LocalConfig(apps=[app]).app(app.name)
            valid.append(app)
        except Exception:
            continue
    config.apps = valid
    hands = {"desktop": DesktopHand(config), "browser": BrowserHand(config), "files": FileHand(config),
             "websites":WebsiteHand(config),"slack":SlackHand(config,os.getenv("OFA_SLACK_BOT_TOKEN",""),
                [c.strip() for c in os.getenv("OFA_SLACK_CHANNEL_IDS","").split(",") if c.strip()],team_id=os.getenv("OFA_SLACK_TEAM_ID",""))}
    engine = Engine(config, hands, DeterministicPlanner(config))
    events = Events(settings.mode)
    loop = asyncio.get_running_loop()
    profile = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "OFA/voice/pairing.dat"
    def prompt(origin, fingerprint, answer):
        overlay.request_pairing(origin, fingerprint,
            lambda allowed: loop.call_soon_threadsafe(answer, allowed))
    pairing = Pairing(ProtectedStore(profile), prompt)
    def authorize():
        if not pairing.connected():
            raise PermissionError("Connect the desktop companion first")

    def emit(kind: str, payload: dict[str, Any]) -> None:
        events.emit(kind, payload)
        if kind == "state":
            overlay.emit(payload["state"])
        elif kind in {"error", "question", "reply", "degraded"}:
            overlay.emit(events.latest.get("state", "ERROR"),
                         str(payload.get("text", payload.get("code", ""))))
        elif kind=="task_update":
            session.notify_task(payload)

    stt_providers = {"deepgram": DeepgramStt(settings), "gradium": GradiumStt(settings)}
    tts_providers = {"deepgram": DeepgramTts(settings), "gradium": GradiumTts(settings)}
    stt_breakers = {name: Breaker(settings.cooldown_seconds) for name in stt_providers}
    tts_breakers = {name: Breaker(settings.cooldown_seconds) for name in tts_providers}
    aliases = [(alias, app.name) for app in config.apps for alias in [app.name, *app.aliases]]
    site_rows = handoff.apps.get("sites", []) if handoff else []
    sites = {row["name"]: row["url"] for row in site_rows}
    selected_tts = tts_providers[settings.tts_order[0]]
    identity = settings.english_voice + "|" + settings.hindi_voice + "|" + settings.gradium_voice
    cache = AckCache(selected_tts, settings.cache_dir, identity)
    bridge = EngineBridge(engine, sites, emit)
    def refresh_catalog(rescan=True):
        if rescan:
            config.apps=discover()
            for row in runtime.manual_apps:
                app=App.model_validate(row)
                if not any(a.name.casefold()==app.name.casefold() for a in config.apps): config.apps.append(app)
        session.router=Router([(alias,app.name) for app in config.apps for alias in [app.name,*app.aliases]],settings.language,sites)
    runtime=Runtime(config,bridge,ProtectedStore(profile.with_name("permissions.dat")),overlay,loop,authorize,emit,refresh_catalog)
    dispatcher = CapabilityDispatcher({name:runtime.handle for name in (
        "target.open","website.open","web.search","browser.navigate","window.focus","window.minimize",
        "window.maximize","window.restore","window.close","file.read","file.write_text","file.write_artifact","slack.send_file")}, ReasoningGate(None))
    runtime.dispatcher=dispatcher
    session = Session(
        settings, Router(aliases, settings.language, sites),
        SttChain(settings, stt_providers, stt_breakers, emit),
        Speech(settings, tts_providers, tts_breakers, emit),
        None,  # OFA Engine is not implemented in this iteration.
        bridge, cache, emit, dispatcher, authorize,
    )
    session.runtime=runtime
    refresh_catalog(False)
    stop = asyncio.Event()
    control.update(loop=loop, stop=stop)
    caps = CapsHook(lambda: loop.call_soon_threadsafe(
        lambda: asyncio.create_task(session.toggle())
    ), pairing.connected).start()
    emergency = StopHotkey(lambda: loop.call_soon_threadsafe(
        lambda: asyncio.create_task(session.close("emergency_hotkey"))
    )).start()
    token = os.getenv("OFA_VOICE_TOKEN") or secrets.token_urlsafe(48)
    server = uvicorn.Server(uvicorn.Config(
        create_app(settings, events, session, token, pairing,
                   lambda: [{"id": app_id(app), "name": app.name} for app in config.apps],runtime,stop.set), host="127.0.0.1",
        port=settings.port, access_log=False, log_level="warning",
        ws_max_size=4096, ws_max_queue=8,
    ))
    serving = asyncio.create_task(server.serve())
    emit("capabilities", {"global_hotkey": caps.available, "mode": "live"})
    waiting = asyncio.create_task(stop.wait())
    async def maintain_connection():
        while not stop.is_set():
            if isinstance(pairing.identity, LocalDevelopmentSessionPort):
                pairing.identity.renew()
            if not pairing.connected() and session.machine.state.value != "IDLE":
                await session.close("lease_expired")
            await asyncio.sleep(1)
    maintenance = asyncio.create_task(maintain_connection())
    async def warm_cache():
        try:
            await cache.warm()
        except Exception:
            emit("cache_partial", {"code": "ACK_CACHE_PARTIAL"})
    warming = asyncio.create_task(warm_cache())
    try:
        if not caps.available:
            emit("error", {"code": "GLOBAL_HOOK_UNAVAILABLE"})
        done, _ = await asyncio.wait(
            (serving, waiting), return_when=asyncio.FIRST_COMPLETED
        )
        if serving in done and not stop.is_set():
            emit("error", {"code": "VOICE_SERVER_STOPPED"})
    finally:
        waiting.cancel()
        maintenance.cancel()
        warming.cancel()
        await session.close("host_shutdown")
        caps.close()
        emergency.close()
        server.should_exit = True
        await asyncio.gather(serving, waiting, maintenance, warming, return_exceptions=True)
        await asyncio.to_thread(engine.close)
        for hand in hands.values():
            if hasattr(hand, "close"):
                await asyncio.to_thread(hand.close)
        overlay.emit("SHUTDOWN")


def main() -> None:
    if sys.stdout is None:
        log_dir = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "OFA/voice"
        log_dir.mkdir(parents=True, exist_ok=True)
        sys.stdout = (log_dir / "companion.log").open("a", encoding="utf-8", buffering=1)
    if sys.stderr is None:
        sys.stderr = sys.stdout
    parser = argparse.ArgumentParser()
    parser.add_argument("--handoff")
    parser.add_argument("--consent", action="store_true")
    parser.add_argument("--fake-demo", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--env-file", help="Load credentials locally without displaying or copying them")
    parser.add_argument("--save-speech-credentials", action="store_true",
                        help="Protect the two speech keys with current-user Windows DPAPI")
    parser.add_argument("--configure-only", action="store_true")
    args = parser.parse_args()
    if args.env_file:
        from dotenv import load_dotenv
        load_dotenv(args.env_file, override=False)
    credential_path = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "OFA/voice/credentials.dat"
    credential_store = ProtectedStore(credential_path)
    names = ("DEEPGRAM_API_KEY", "GRADIUM_API_KEY")
    if args.save_speech_credentials:
        credentials = {name: os.getenv(name, "") for name in names}
        if not credentials["DEEPGRAM_API_KEY"]:
            parser.error("Configure DEEPGRAM_API_KEY locally before saving speech settings")
        credential_store.write(credentials)
        print("Speech credentials protected for the current Windows user.", flush=True)
    elif (args.live or os.getenv("VOICE_PROVIDER_MODE") == "live") and not args.fake_demo and credential_path.exists():
        for name, value in credential_store.read().items():
            if name in names and isinstance(value, str) and not os.getenv(name):
                os.environ[name] = value
    if args.configure_only:
        if not args.save_speech_credentials:
            parser.error("--configure-only requires --save-speech-credentials")
        return
    if args.live:
        os.environ["VOICE_PROVIDER_MODE"] = "live"
    if args.fake_demo or os.getenv("VOICE_PROVIDER_MODE", "fake") == "fake":
        from .demo import run
        asyncio.run(run())
        return
    handoff = load_handoff(args.handoff) if args.handoff else None
    from .instance import acquire
    if not acquire():
        print("OFA Desktop is already running in this Windows session.",flush=True)
        return
    control: dict[str, Any] = {}

    def stop() -> None:
        if "loop" in control:
            control["loop"].call_soon_threadsafe(control["stop"].set)

    overlay = Overlay(stop)
    def run_worker() -> None:
        try:
            asyncio.run(serve(handoff, args.consent, overlay, control))
        except BaseException as exc:
            print("VOICE_HOST_FAILED:" + type(exc).__name__, flush=True)
            overlay.emit("ERROR", "Voice host stopped. Check setup and local port.")

    worker = threading.Thread(
        target=run_worker,
        name="ofa-voice-loop", daemon=True,
    )
    worker.start()
    try:
        overlay.run()
    except KeyboardInterrupt:
        stop()
    finally:
        stop()
        worker.join(timeout=5)


if __name__ == "__main__":
    main()
