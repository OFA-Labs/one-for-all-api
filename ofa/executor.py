"""Executes Actions: classify tier → (Tier 2) spoken approval → consume grant → effect → verify.
This is the only path from the engine to the desktop, files, shell and credential broker (§6, §10.1)."""
from __future__ import annotations

import asyncio
import fnmatch
import os
import re
import subprocess
import time
from pathlib import Path

from .audit import Audit
from .egress import EGRESS, LeakBlocked
from .harness.api import BROWSERS, Harness, HarnessError
from .memory import Memory
from .policy import Action, ApprovalState, ApprovalStore, PolicyDenied, TurnLog, classify_tier
from .vault.broker import Broker, TargetIdentity

TERMINALS = {"windowsterminal.exe", "powershell.exe", "pwsh.exe", "cmd.exe", "wt.exe", "conhost.exe",
             "alacritty.exe", "wezterm-gui.exe", "mintty.exe"}
OUTBOUND = {"send", "post", "forward", "share", "publish", "submit", "apply", "upload", "attach", "comment",
            "approve", "push", "merge", "pay", "purchase", "book", "order", "phone_send"}
SCOPES = {"home": Path.home(), "downloads": Path.home() / "Downloads", "documents": Path.home() / "Documents",
          "desktop": Path.home() / "Desktop", "pictures": Path.home() / "Pictures", "videos": Path.home() / "Videos",
          "onedrive": Path(os.getenv("OneDrive", str(Path.home() / "OneDrive")))}


class Executor:
    def __init__(self, harness: Harness, approvals: ApprovalStore, turns: TurnLog, audit: Audit, memory: Memory,
                 broker: Broker | None, speak, listen, epoch, lang=lambda: "en", show=lambda *_: None):
        self.h, self.approvals, self.turns, self.audit, self.memory = harness, approvals, turns, audit, memory
        self.broker, self.speak, self.listen, self.epoch, self.lang, self.show = broker, speak, listen, epoch, lang, show
        self.task = "t0"
        self.last_user_words = ""
        self.plan_approved: str | None = None
        self.effects_this_turn = 0
        self.tier2_this_turn = 0
        self.gate = None
        self._last_tier = 2

    def new_turn(self, task: str, words: str) -> None:
        self.task, self.last_user_words = task, words
        self.plan_approved, self.effects_this_turn, self.tier2_this_turn = None, 0, 0

    # --- context derived from OFA's own reading, never from the model -------------------------
    def describe(self, action: Action) -> Action:
        ref = action.args.get("element")
        snap = self.h.last
        label = role = None
        ctx = action.context
        if ref and snap:
            try:
                el = snap.by_id(ref) if ref[:1] in "uo" and ref[1:].isdigit() else None
                if el:
                    label, role = el.text or el.value or "", el.role
            except HarnessError:
                pass
        if snap:
            proc = snap.process
            if proc in TERMINALS:
                ctx = "terminal"
            elif role in {"edit", "document", "combo box"}:
                ctx = "search" if re.search(r"search|find|address|url|filter|khoj", (label or ""), re.I) else "compose"
            elif ctx is None and action.args.get("op") == "key":
                focused = None
                try:
                    focused = self.h.b.focused_element()
                except Exception:
                    pass
                if focused is not None and focused.role in {"edit", "document"}:
                    ctx = "search" if re.search(r"search|find|address", focused.text or "", re.I) else "compose"
        return action.model_copy(update={"element_label": label or action.element_label,
                                          "element_role": role or action.element_role, "context": ctx})

    # --- main entry -------------------------------------------------------------------------
    async def run(self, action: Action) -> dict:
        result = await self._run(action)
        result.setdefault("tier", self._last_tier)
        return result

    async def _run(self, action: Action) -> dict:
        if self.gate is not None:
            await self.gate()               # spoken "pause" holds here; "stop" changes the epoch
        epoch = self.epoch()
        self._last_tier = 2
        action = self.describe(action)
        if action.verb == "dictate":
            prepared = await self._prepare_dictation(action)
            if isinstance(prepared, dict):
                return prepared
            action = prepared
        tier = classify_tier(action, self.turns, epoch)
        self._last_tier = tier
        effectful = tier >= 1 and action.args.get("op") not in {"screen", "windows", "wait_for", "read_file", "files"}
        if effectful:
            self.effects_this_turn += 1
        if tier == 2:
            self.tier2_this_turn += 1
            if self.plan_needed():
                return {"status": "blocked", "reason": "PLAN_REQUIRED",
                        "detail": "This is a multi-step consequential task: call propose_plan first."}
            idem = action.digest()
            prior = self.memory.ledger_get(idem)
            if prior == "done" and action.verb in OUTBOUND:
                return {"status": "skipped", "reason": "ALREADY_DONE", "detail": "This exact action already succeeded; not repeating it."}
            if prior == "unknown" and action.verb in OUTBOUND:
                return {"status": "blocked", "reason": "OUTCOME_UNKNOWN",
                        "detail": "A previous identical attempt has an unknown outcome. Check the destination first, or ask the user."}
            self.show("approval", action)
            req = await self.approvals.obtain(action, self.speak, self.listen, self.lang())
            self.audit.write("approval", epoch=epoch, task=self.task, tier=2, digest=req.digest, result=req.state.value,
                             handle_ids=[action.handle] if action.handle else [])
            self.show("approval_done", None)
            if req.state != ApprovalState.GRANTED:
                out = {"status": "not_approved", "state": req.state.value}
                if req.state == ApprovalState.MODIFY:
                    out["user_said"] = req.transcript
                return out
            try:
                self.approvals.consume(req.id, action, self.epoch())
            except PolicyDenied as exc:
                return {"status": "refused", "reason": exc.code}
            for dest in action.destinations or [action.target or action.verb]:
                self.memory.ledger_set(self.task, idem, dest, action.verb, "intent")
        elif self.epoch() != epoch:
            return {"status": "cancelled", "reason": "SESSION_STOPPED"}
        if self.epoch() != epoch:
            return {"status": "cancelled", "reason": "SESSION_STOPPED"}
        try:
            result = await asyncio.to_thread(self._dispatch, action)
        except HarnessError as exc:
            result = {"status": "error", "reason": exc.code, "detail": str(exc), "options": exc.options}
        except PolicyDenied as exc:
            result = {"status": "refused", "reason": exc.code}
        except PermissionError as exc:
            result = {"status": "handoff", "reason": "INPUT_BLOCKED", "detail": str(exc)}
        except Exception as exc:   # report honestly; never claim success
            result = {"status": "error", "reason": type(exc).__name__, "detail": str(exc)[:200]}
        result.setdefault("status", "ok")
        if tier == 2:
            idem = action.digest()
            verified = result["status"] == "ok" and result.get("verified", result.get("screen_changed", False))
            state = "done" if verified else ("failed" if result["status"] in {"error", "refused"} else "unknown")
            for dest in action.destinations or [action.target or action.verb]:
                self.memory.ledger_set(self.task, idem, dest, action.verb, state)
            result["outcome"] = state
        self.audit.write("action", epoch=epoch, task=self.task, tier=tier, digest=action.digest(),
                         result=result["status"], detail=action.verb,
                         handle_ids=[action.handle] if action.handle else [])
        result["tier"] = tier
        return result

    def plan_needed(self) -> bool:
        return self.plan_approved is None and (self.tier2_this_turn >= 2 or
                                               (self.tier2_this_turn >= 1 and self.effects_this_turn >= 5))

    async def _prepare_dictation(self, action: Action):
        from .text.dictation import find_span, verbatim
        from .text.translit import apply_script
        mode = action.args.get("mode", "verbatim")
        text = action.payload or ""
        if mode == "verbatim":
            span = find_span(self.last_user_words, text) if text else None
            if text and span is None:
                return {"status": "rejected", "reason": "VERBATIM_MISMATCH",
                        "detail": "text must be copied exactly from the user's words; omit text to ask the user to dictate"}
            if span is None:
                await self.speak("What should I type?")
                heard = await self.listen_dictation(45.0)
                if heard is None or not heard.text.strip():
                    return {"status": "error", "reason": "NO_DICTATION"}
                span = heard.text
                if heard.confidence is not None and heard.confidence < 0.85 and re.search(r"\d|[A-Z][a-z]+", span):
                    await self.speak(f"I heard: {span}. Is that right?")
                    check = await self.listen(8.0)
                    from .policy.lexicon import classify
                    if check is None or classify(check.text) != "YES":
                        return {"status": "error", "reason": "DICTATION_NOT_CONFIRMED"}
            text = verbatim(apply_script(span, self.script()))
        if not text.strip():
            return {"status": "error", "reason": "NOTHING_TO_TYPE"}
        await self.speak("Typing it now.")
        return action.model_copy(update={"payload": text})

    def script(self) -> str:
        return self.memory.get("script", "roman")

    async def listen_dictation(self, timeout: float):
        fn = getattr(self, "_listen_dictation", None) or self.listen
        return await fn(timeout)

    async def approve_plan(self, steps: list[str]) -> dict:
        text = "Here is my plan. " + " ".join(f"{i + 1}. {s.rstrip('.')}." for i, s in enumerate(steps[:12]))
        action = Action(verb="plan", payload="\n".join(steps), args={"op": "plan"})
        req = await self.approvals.obtain(action, self.speak, self.listen, self.lang(),
                                          spoken=text + " Should I go ahead?")
        self.audit.write("plan", epoch=self.epoch(), task=self.task, digest=req.digest, result=req.state.value)
        if req.state == ApprovalState.GRANTED:
            self.approvals.consume(req.id, action, self.epoch())
            self.plan_approved = req.digest
            return {"status": "approved", "note": "Each consequential step will still be confirmed when it happens."}
        out = {"status": req.state.value}
        if req.transcript:
            out["user_said"] = req.transcript
        return out

    # --- effects ----------------------------------------------------------------------------
    def _dispatch(self, a: Action) -> dict:
        op = a.args.get("op")
        h = self.h
        if op == "open":
            t = (a.target or "").strip()
            if re.match(r"^https?://", t, re.I):
                return h.open_url(t)
            if re.match(r"^[\w.-]+\.(com|org|net|in|io|ai|dev|co|app|edu|gov)(/\S*)?$", t, re.I):
                return h.open_url("https://" + t)
            if t.startswith("ms-settings:") or re.match(r"^[a-zA-Z]:[\\/]", t) or t.startswith("\\\\"):
                return h.open_path(t)
            if t.casefold() in SCOPES:
                return h.open_path(str(SCOPES[t.casefold()]))
            return h.open_app(t)
        if op == "windows":
            return {"windows": h.windows()}
        if op == "screen":
            return h.screen(a.target, ocr=a.args.get("ocr"))
        if op in {"focus"}:
            return h.focus(a.args.get("window") or a.target)
        if op in {"close", "minimize", "maximize", "restore"}:
            return h.window_op(a.args.get("window") or a.target, op)
        if op in {"snap_left", "snap_right"}:
            return h.window_op(a.args.get("window") or a.target, op.split("_")[1])
        if op in {"click", "double_click", "right_click"}:
            return h.click(a.args["element"], double=op == "double_click", button="right" if op == "right_click" else "left")
        if op == "drag":
            return h.drag(a.args["element"], a.args.get("to_element"))
        if op in {"type", "replace"}:
            return self._type(a, replace=op == "replace")
        if op == "dictate":
            return self._type(a, replace=False)
        if op == "key":
            return h.key(a.key or "")
        if op in {"scroll_up", "scroll_down"}:
            return h.scroll("up" if op == "scroll_up" else "down", ref=a.args.get("element"))
        if op == "wait_for":
            return h.wait_for_text(a.payload or "", a.args.get("window"))
        if op == "fill_secret":
            return self._fill(a)
        if op == "files":
            return self._files(a)
        if op == "read_file":
            return self._read(a.target or "")
        if op == "write_file":
            p = Path(a.target or "")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(a.payload or "", encoding="utf-8")
            ok = p.read_text(encoding="utf-8") == (a.payload or "")
            self.memory.context["last_file"] = str(p)
            return {"written": str(p), "bytes": p.stat().st_size, "verified": ok}
        if op == "run_command":
            return self._command(a)
        raise HarnessError("UNKNOWN_OP", str(op))

    def _type(self, a: Action, replace: bool) -> dict:
        text = a.payload or ""
        if not text:
            return {"status": "error", "reason": "NOTHING_TO_TYPE"}
        r = self.h.type_text(text, a.args.get("element"), replace=replace)
        rb = r.get("readback")
        if rb is not None:
            r["verified"] = " ".join(text.split()) in " ".join(rb.split())
            if not r["verified"]:
                r["note"] = "the field does not show exactly what was intended"
            r.pop("readback", None)
        else:
            r["verified"] = False
            r["note"] = "this app does not expose the field's text, so the typing could not be read back"
        return r

    def _fill(self, a: Action) -> dict:
        if self.broker is None:
            return {"status": "error", "reason": "VAULT_UNAVAILABLE"}
        el = self.h.element(a.args.get("element") or "")
        proc = self.h.last.process if self.h.last else ""
        if proc in BROWSERS:
            ident = self.h.browser_identity(self.h.last.hwnd) or {}
            identity = TargetIdentity("browser", url=ident.get("url"), tls_ok=ident.get("tls_ok", False),
                                      field_is_password=el.is_password)
        else:
            w = next((w for w in self.h.b.list_windows() if self.h.last and w["hwnd"] == self.h.last.hwnd), {})
            identity = TargetIdentity("app", exe_path=w.get("exe"), publisher=None, field_is_password=el.is_password)
        harness = self.h

        class Inject:
            def set_value(self, ref, value):
                if harness.b.uia_set_value(el, value):
                    return True
                harness._ensure_front()
                harness.b.uia_focus(el) or harness.b.click_at(*el.center())
                harness.b.press("ctrl+a")
                harness.b.type_unicode(value)
                return True

            def field_length(self, ref):
                v = harness.b.uia_value(el)
                return len(v or "")
        res = self.broker.fill(a.handle or "", el.id, identity, Inject(), approved=True)
        if res.ok and self.h.last:
            self.h.filled_refs.add((self.h.last.hwnd, el.id))
        return {"filled": res.ok, "reason": res.reason, "verified": res.ok}

    def _files(self, a: Action) -> dict:
        scope = (a.target or "home").casefold()
        root = SCOPES.get(scope) or Path(a.target or "")
        if not root.exists():
            return {"status": "error", "reason": "SCOPE_NOT_FOUND"}
        words = [w for w in re.split(r"\W+", (a.payload or "").casefold()) if w]
        hits, start = [], time.monotonic()
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in {"node_modules", "AppData", "$Recycle.Bin"}]
            for f in filenames:
                name = f.casefold()
                if all(w in name for w in words) or (words and fnmatch.fnmatch(name, f"*{'*'.join(words)}*")):
                    p = Path(dirpath) / f
                    try:
                        st = p.stat()
                    except OSError:
                        continue
                    hits.append({"name": f, "folder": str(p.parent), "path": str(p), "size": st.st_size,
                                 "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))})
            if len(hits) > 200 or time.monotonic() - start > 8:
                break
        hits.sort(key=lambda x: x["modified"], reverse=True)
        self.memory.context["last_results"] = [h["path"] for h in hits[:10]]
        return {"count": len(hits), "files": hits[:10], "note": "none found" if not hits else
                ("several match: ask which one" if len(hits) > 1 else "one match")}

    def _read(self, path: str) -> dict:
        p = Path(path)
        if not p.is_file():
            return {"status": "error", "reason": "NOT_A_FILE"}
        if p.suffix.lower() in {".env", ".key", ".pem", ".kdbx", ".dat"} or ".env" in p.name.lower():
            return {"status": "refused", "reason": "SECRET_FILE", "detail": "OFA does not read credential files"}
        data = p.read_bytes()[:8192]
        text = data.decode("utf-8", "replace")
        self.memory.context["last_file"] = str(p)
        return {"path": str(p), "text": text, "truncated": p.stat().st_size > 8192}

    def _command(self, a: Action) -> dict:
        cwd = a.target if a.target and os.path.isdir(a.target) else str(Path.home())
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", a.payload or ""],
                             capture_output=True, text=True, timeout=60, cwd=cwd, creationflags=0x08000000)
        text = (out.stdout + ("\n" + out.stderr if out.stderr else ""))[-4000:]
        try:
            EGRESS.guard(text, "tool_output")
        except LeakBlocked:
            text = "[output withheld: it contained a protected value]"
        return {"exit_code": out.returncode, "output": text, "verified": out.returncode == 0}
