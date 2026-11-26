"""Slack external upload with immutable bytes, explicit destination and no retries.

API protocol: docs.slack.dev/reference/methods/files.getUploadURLExternal/,
files.completeUploadExternal/ and files.info/. Credentials never reach the UI.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from urllib.parse import urlsplit

import httpx

from .contracts import Evidence, ExecutionError, Observation, Outcome


class SlackHand:
    def __init__(self, config, token="", channels=(), transport=None, team_id=""):
        self.config, self.token = config, token
        self.channels = set(channels)
        self.team_id = team_id
        self.team = None
        self.client = httpx.Client(transport=transport, timeout=20, follow_redirects=False, trust_env=False)

    def capabilities(self):
        return {"operations": ["slack.send_file"], "configured": bool(self.token and self.channels)}

    def observe(self, step):
        if not self.token:
            raise ExecutionError("SLACK_NOT_CONFIGURED", "Configure OFA_SLACK_BOT_TOKEN locally; live Slack is deferred.")
        channel = step.target.destination or ""
        if not re.fullmatch(r"[CG][A-Z0-9]{8,30}", channel) or channel not in self.channels:
            raise ExecutionError("SLACK_DESTINATION_DENIED", "Select a locally permitted Slack channel ID.")
        if self.team is None:
            try:
                identity=self._api("auth.test",{})
            except httpx.HTTPError as exc:
                raise ExecutionError("SLACK_IDENTITY_UNAVAILABLE","Slack workspace identity could not be checked.") from None
            if not re.fullmatch(r"T[A-Z0-9]+",identity.get("team_id","")) or self.team_id and identity["team_id"]!=self.team_id:
                raise ExecutionError("SLACK_WORKSPACE_DENIED","Slack workspace does not match the local connection.")
            self.team={"team_id":identity["team_id"],"name":str(identity.get("team",""))[:100]}
        path = self.config.file(step.target.path or "")
        if not path.is_file():
            raise ExecutionError("FILE_NOT_FOUND", "The selected allowed file does not exist.")
        with path.open("rb") as stream: data=stream.read(65537)
        if len(data)>65536: raise ExecutionError("FILE_TOO_LARGE","Text file exceeds 64 KiB.")
        try: data.decode("utf-8")
        except UnicodeError as exc: raise ExecutionError("FILE_ENCODING","Select a UTF-8 text file.") from exc
        return Observation(surface="slack", identity={"path": str(path), "channel": channel,"workspace":self.team},
            facts={"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "filename": path.name})

    def _api(self, method, data, get=False):
        headers = {"Authorization": "Bearer " + self.token}
        response = (self.client.get("https://slack.com/api/" + method, params=data, headers=headers) if get
                    else self.client.post("https://slack.com/api/" + method, data=data, headers=headers))
        response.raise_for_status()
        body = response.json()
        if not body.get("ok"):
            raise ExecutionError("SLACK_API_REJECTED", "Slack rejected the request. Check bot scopes and channel membership locally.")
        return body

    def execute(self, step, before, checkpoint):
        if self.observe(step).hash != before.hash:
            raise ExecutionError("READING_CHANGED", "The file or destination changed after approval.")
        with self.config.file(step.target.path or "").open("rb") as stream: data=stream.read(65537)
        if hashlib.sha256(data).hexdigest() != before.facts["sha256"]:
            raise ExecutionError("READING_CHANGED", "The selected bytes changed.")
        checkpoint()
        # No retry wrapper around any mutation. A lost completion reply means
        # unknown, not permission to send the file again.
        try:
            upload = self._api("files.getUploadURLExternal", {"filename": before.facts["filename"], "length": str(len(data))})
            parsed = urlsplit(upload.get("upload_url", ""))
            if parsed.scheme != "https" or parsed.hostname != "files.slack.com" or parsed.port not in (None,443) or parsed.username or parsed.password or not parsed.path.startswith("/upload/"):
                raise ExecutionError("SLACK_UPLOAD_URL_DENIED", "Slack returned an untrusted upload address.")
            file_id = upload.get("file_id", "")
            if not re.fullmatch(r"F[A-Z0-9]+", file_id):
                raise ExecutionError("SLACK_RESPONSE_INVALID", "Slack returned an invalid file identity.")
            checkpoint()
            response = self.client.post(upload["upload_url"], content=data, headers={"Content-Type":"application/octet-stream"})
            response.raise_for_status()
            checkpoint()
            self._api("files.completeUploadExternal", {"files":json.dumps([{"id":file_id,"title":before.facts["filename"]}]),
                                                       "channel_id": before.identity["channel"]})
            for _ in range(4):
                checkpoint()
                info = self._api("files.info", {"file": file_id}, get=True).get("file", {})
                channels = set(info.get("channels", [])) | set(info.get("groups", []))
                for shares in info.get("shares", {}).values():
                    if isinstance(shares, dict): channels.update(shares)
                if info.get("id") == file_id and info.get("size") == len(data) and before.identity["channel"] in channels:
                    after = before.model_copy(deep=True)
                    after.facts.update(file_id=file_id, shared=True)
                    return Outcome(status="verified",observation=after,evidence=[Evidence(tier="A",kind="slack_file_share_readback",reading_hash=after.hash)])
                time.sleep(.2)
        except httpx.HTTPError:
            pass  # Suppress request URLs/token-bearing headers in public errors.
        return Outcome(status="unknown", observation=before)

    def close(self):
        self.client.close()
