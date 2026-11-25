"""Small stdio MCP client; no remote relay and no model/tool composition."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time

from .contracts import ExecutionError


class McpClient:
    def __init__(self, command, environment=None):
        if not command:
            raise ExecutionError("BROWSER_NOT_CONFIGURED", "Configure the local browse executable command.")
        env = {k: v for k, v in os.environ.items() if k.upper() in
               {"PATH", "SYSTEMROOT", "WINDIR", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "TEMP", "TMP", "PATHEXT"}}
        env.update({"OPENCODE_BROWSER_AUTO_UPDATE": "off", "OPENCODE_BROWSER_TOOLS": "all"})
        env.update(environment or {})
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, encoding="utf-8", env=env,
                                        creationflags=0x08000000 if os.name == "nt" else 0)
        self._lines = queue.Queue()
        self._sequence = 0
        self._lock = threading.Lock()
        self.last_error = None  # Local diagnostic, never included in API/task logs.
        def read():
            try:
                for line in self.process.stdout:
                    self._lines.put(json.loads(line))
            except (ValueError, OSError):
                pass
            finally:
                self._lines.put(None)
        threading.Thread(target=read, daemon=True).start()
        self.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                    "clientInfo": {"name": "ofa-local-execution", "version": "0.1.0"}})
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        self.process.stdin.flush()
        self.tools = {t["name"]: t for t in self.request("tools/list", {})["tools"]}

    def request(self, method, params, timeout=20):
        with self._lock:
            self._sequence += 1
            request_id = self._sequence
            try:
                self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": request_id,
                                                     "method": method, "params": params}) + "\n")
                self.process.stdin.flush()
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    response = self._lines.get(timeout=max(0.01, deadline-time.monotonic()))
                    if response is None:
                        raise ExecutionError("BROWSER_DISCONNECTED", "The local MCP hand exited.")
                    if response.get("id") == request_id:
                        if "error" in response:
                            raise ExecutionError("BROWSER_ERROR", "The browser MCP request failed.")
                        return response["result"]
                raise queue.Empty()
            except (BrokenPipeError, OSError, queue.Empty) as exc:
                raise ExecutionError("BROWSER_DISCONNECTED", "The browser did not return a result; effects must not be retried.") from exc

    def call(self, name, arguments):
        if name not in self.tools:
            if name in {"navigate", "eval", "tabs", "status"} and "execute" in self.tools:
                # browse exposes only execute/status/tabs to some MCP clients.
                # Compile a finite call; neither the name nor code comes from a
                # plan/page. eval expressions originate in our fixed adapter.
                code = "return await browse." + name + "(" + json.dumps(arguments) + ");"
                return self.call("execute", {"code": code})
            raise ExecutionError("BROWSER_SCHEMA_CHANGED", "The pinned browser tool is unavailable.")
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            self.last_error = result
            raise ExecutionError("BROWSER_ERROR", "The local browser refused this operation; inspect pairing/status.")
        if result.get("structuredContent") is not None:
            return result["structuredContent"]
        text = "\n".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")
        try:
            return json.loads(text)
        except ValueError:
            raise ExecutionError("BROWSER_SCHEMA_CHANGED", "Expected structured JSON from the pinned browser tool.")

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
