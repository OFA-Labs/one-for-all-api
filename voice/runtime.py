"""Live deterministic actions, native scope upgrades and bounded artifact binding."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from uuid import uuid4

from ofa_execution.contracts import Step, Target, Expectation
from .capabilities import Receipt, MissingCapability
from .orchestrator import approval_choice


class Runtime:
    def __init__(self, config, bridge, store, overlay, loop, authorize, emit, refresh=None):
        self.config, self.bridge, self.store = config, bridge, store
        self.overlay, self.loop, self.authorize, self.emit = overlay, loop, authorize, emit
        self.refresh_catalog = refresh
        saved = store.read()
        self.manual_apps=saved.get("manual_apps",[])[:30]
        from ofa_execution.config import App, LocalConfig
        for row in self.manual_apps:
            try:
                app=App.model_validate(row)
                LocalConfig(apps=[app]).app(app.name)
                if not any(a.name.casefold()==app.name.casefold() for a in config.apps): config.apps.append(app)
            except Exception: continue
        self.window_controls = saved.get("window_controls", False) is True
        # Scopes are device-local and granted via native UI, never arbitrary
        # paths supplied by the website. Disconnect removes these upgrades.
        for name in ("read_roots", "write_roots"):
            setattr(config, name, [str(Path(p).resolve()) for p in saved.get(name, getattr(config,name)) if Path(p).is_dir()][:1])
        self.requests = {}
        self.dispatcher = None
        self.choices = {}

    def status(self):
        return {"window_controls": self.window_controls,
                "read_roots":self.config.read_roots,"write_roots":self.config.write_roots,
                "slack_configured":bool(os.getenv("OFA_SLACK_BOT_TOKEN") and os.getenv("OFA_SLACK_CHANNEL_IDS")),
                "pending":self.bridge.pending}

    def _save(self):
        self.store.write({"window_controls":self.window_controls,"read_roots":self.config.read_roots,
                          "write_roots":self.config.write_roots,"manual_apps":self.manual_apps})

    def revoke(self):
        self.window_controls = False
        self.config.read_roots = []
        self.config.write_roots = []
        self.requests.clear()
        self.choices.clear()
        if self.dispatcher: self.dispatcher.bindings.clear()
        self._save()

    def request_scope(self, kind, origin):
        if kind not in {"windows","read_folder","write_folder","register_app","startup_on","startup_off"}:
            raise ValueError("Unknown desktop permission")
        if any(r["state"]=="pending" for r in self.requests.values()):
            raise ValueError("Complete the current Windows dialog first")
        self.requests = {key:value for key,value in self.requests.items() if value["state"]=="pending"}
        request_id = str(uuid4())
        self.requests[request_id] = {"state":"pending","origin":origin}
        def answered(value):
            def apply():
                result = self.requests.get(request_id)
                if not result: return
                try:
                    self.authorize()
                    if not value:
                        result["state"]="denied"
                        return
                    if kind == "windows": self.window_controls=True
                    elif kind in {"read_folder","write_folder"}:
                        root = str(Path(value).resolve(strict=True))
                        if not Path(root).is_dir(): raise ValueError()
                        setattr(self.config,"write_roots" if kind=="write_folder" else "read_roots",[root])
                    elif kind=="register_app":
                        from ofa_execution.config import App, LocalConfig
                        from ofa_execution.app_policy import allowed
                        app = App(name=Path(value).stem,executable=str(Path(value).resolve()))
                        if not allowed(app,discovered=True): raise ValueError()
                        LocalConfig(apps=[app]).app(app.name)
                        if any(a.name.casefold()==app.name.casefold() for a in self.config.apps):
                            raise ValueError()
                        self.config.apps.append(app)
                        self.manual_apps.append(app.model_dump())
                        if self.refresh_catalog: self.refresh_catalog(False)
                    elif kind.startswith("startup_"):
                        from .startup import set_startup
                        set_startup(kind=="startup_on")
                    self._save()
                    result["state"]="approved"
                except Exception:
                    result["state"]="failed"
            self.loop.call_soon_threadsafe(apply)
        self.overlay.request_scope(kind,origin,answered)
        return {"request_id":request_id,"state":"pending"}

    def poll_scope(self, request_id, origin):
        result = self.requests.get(request_id)
        if not result or result["origin"]!=origin: raise PermissionError()
        return {"state":result["state"]}

    def decide_voice(self, text, confidence):
        pending = self.bridge.pending
        if not pending or pending["state"]!="approval": return False
        choice = approval_choice(text,confidence)
        if choice is None:
            self.emit("question",{"text":"Please approve or reject the exact action in OFA. Unclear speech cannot approve it."})
            return True
        card = pending["approval"]
        self.authorize()
        self.bridge.decide(pending["task_id"], {"approval_id":card["id"],"reading_hash":card["reading_hash"],"approve":choice})
        return True

    def offer_choices(self, options):
        self.choices={str(uuid4()):name for name in options[:10]}
        self.emit("app_choices",{"options":[{"id":key,"label":name} for key,name in self.choices.items()]})

    async def choose_app(self, option_id):
        self.authorize()
        if self.bridge._active: raise PermissionError("Complete pending work first")
        name=self.choices.get(option_id)
        if not name: raise PermissionError("This choice expired. Repeat the open command")
        self.choices.clear()
        self.emit("app_choices",{"options":[]})
        try:
            good=await self.bridge.open(name,str(uuid4()))
            self.emit("reply" if good else "error",{"text":"Application opened and verified." if good else "The application launch was not verified."})
            return good
        except Exception:
            self.emit("error",{"code":"APP_CHOICE_FAILED","text":"This application choice could not be executed. Repeat the command."})
            return False

    def _file(self, filename, write=False):
        filename=re.sub(r'\s+dot\s+', '.',filename,flags=re.I)
        filename=re.sub(r'\.m d$', '.md',filename,flags=re.I)
        if not re.fullmatch(r"[\w .-]+\.(?:md|txt|csv|json)",filename,re.I) or filename.startswith('.') or Path(filename).name!=filename:
            raise MissingCapability("Name one .md, .txt, .csv or .json file in the selected folder")
        roots = self.config.write_roots if write else list(dict.fromkeys(self.config.read_roots+self.config.write_roots))
        if not roots: raise MissingCapability("Choose a read or write folder in Desktop Integration first")
        candidates = [Path(root)/filename for root in roots]
        if not write:
            found = [p for p in candidates if p.is_file()]
            if len(found)!=1: raise MissingCapability("The file is missing or exists in more than one selected folder")
            candidates=found
        return self.config.file(str(candidates[0]),write)

    async def handle(self, action, context, command_id):
        self.authorize()
        capability,args = action.capability,action.args
        if capability=="target.open":
            app = self.config.app(args["target"])
            snapshot=await self.bridge.execute(Step(id=command_id,operation="app.open",target=Target(app=app.name)),command_id)
            browser = app.name if Path(app.executable).stem.lower() in {"chrome","msedge","firefox"} else context.get("browser","")
            return Receipt(snapshot["state"]=="completed",{"browser":browser})
        if capability.startswith("window."):
            if not self.window_controls: raise MissingCapability("Enable window controls in Desktop Integration first")
            app=self.config.app(args["target"])
            step=Step(id=command_id,operation=capability,target=Target(app=app.name),expect=Expectation(kind="changed"))
        elif capability in {"website.open","web.search","browser.navigate"}:
            if capability=="browser.navigate" and self.config.browser_command:
                step=Step(id=command_id,operation="browser.open",url=args["url"])
            else:
                step=Step(id=command_id,operation="website.open",url=args["url"],target=Target(app=context.get("browser") or None))
        elif capability.startswith("file."):
            write=capability!="file.read"
            path=self._file(args["filename"],write)
            text=args.get("text",context.get("generated_text"))
            if write and text is None:
                raise MissingCapability('Supply exact text: write "Hello" to Notes.md, or read a file before saving its text')
            step=Step(id=command_id,operation="file.write" if write else "file.read",target=Target(path=str(path)),
                      text=text if write else None,expect=Expectation(kind="file_text",value=text) if write else None)
        elif capability=="slack.send_file":
            artifact=args.get("artifact","")
            path=(Path(context["artifact_path"]) if artifact.casefold() in {"this file","this markdown file","the markdown file","it","this"} and context.get("artifact_path")
                  else self._file(artifact))
            if context.get("artifact_path")==str(path) and hashlib.sha256(path.read_bytes()).hexdigest()!=context.get("artifact_sha256"):
                raise MissingCapability("The selected file changed. Read it again before requesting a send")
            destination=args.get("destination","").strip()
            channels=[c.strip() for c in os.getenv("OFA_SLACK_CHANNEL_IDS","").split(",") if c.strip()]
            if destination.casefold()=="slack" and len(channels)==1: destination=channels[0]
            step=Step(id=command_id,operation="slack.send_file",target=Target(path=str(path),destination=destination.upper()),expect=Expectation(kind="changed"))
        else:
            raise MissingCapability("This deterministic action is not connected")
        snapshot=await self.bridge.execute(step,command_id)
        if snapshot["state"]!="completed":
            error=snapshot.get("error") or {}
            self.emit("error",{"code":error.get("code","ACTION_NOT_VERIFIED"),"text":error.get("message","The action was not verified")})
            return Receipt(False)
        if step.operation.startswith("file."):
            text=snapshot["observation"]["facts"]["text"]
            path=step.target.path
            self.emit("file_result",{"text":text[:16384],"filename":Path(path).name,"truncated":len(text)>16384})
            return Receipt(True,{"generated_text":text,"artifact_path":path,"artifact_sha256":hashlib.sha256(Path(path).read_bytes()).hexdigest()})
        if step.operation=="website.open":
            self.emit("url_dispatched",{"verification":"dispatch_only","text":"Sent the link to the selected browser. Page loading is not verified."})
            return Receipt(True,{"dispatch_only":"yes"})
        return Receipt(True)
