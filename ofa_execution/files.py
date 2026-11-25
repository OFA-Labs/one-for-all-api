"""Narrow local text-file operations with exact-version approval/readback."""
from __future__ import annotations

import os
import tempfile

from .contracts import Evidence, ExecutionError, Observation, Outcome


class FileHand:
    def __init__(self, config):
        self.config = config

    def capabilities(self):
        return {"hand": "files", "operations": ["file.read", "file.write"], "max_bytes": 65536}

    def observe(self, step):
        path = self.config.file(step.target.path or "", step.operation == "file.write")
        if step.operation == "file.read" and not path.is_file():
            raise ExecutionError("FILE_NOT_FOUND", "The allowed file does not exist.")
        try:
            text = path.read_text(encoding="utf-8") if path.exists() else None
        except (OSError, UnicodeError) as exc:
            raise ExecutionError("FILE_READ_FAILED", "The file could not be read as UTF-8.") from exc
        return Observation(surface="file", identity={"path": str(path)}, facts={"text": text, "exists": path.exists()})

    def execute(self, step, before, checkpoint):
        if step.operation == "file.write":
            if step.text is None:
                raise ExecutionError("INVALID_ACTION", "File write needs exact text.")
            path = self.config.file(step.target.path or "", True)
            if not path.parent.is_dir():
                raise ExecutionError("PATH_NOT_FOUND", "The permitted parent folder does not exist.")
            if len(step.text.encode()) > 65536:
                raise ExecutionError("FILE_TOO_LARGE", "Text exceeds 64 KiB.")
            # Revalidate immediately before atomic replacement, not just at park.
            if self.observe(step).hash != before.hash:
                raise ExecutionError("READING_CHANGED", "The file changed after approval.")
            checkpoint()
            fd, temporary = tempfile.mkstemp(prefix=".ofa-", dir=path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                    f.write(step.text)
                    f.flush()
                    os.fsync(f.fileno())
                checkpoint()
                if self.observe(step).hash != before.hash:
                    raise ExecutionError("READING_CHANGED", "The file changed before replace.")
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        after = self.observe(step)
        expected = step.text if step.operation == "file.write" else after.facts["text"]
        good = after.facts["text"] == expected
        if step.expect and step.expect.kind == "file_text":
            good = good and after.facts["text"] == step.expect.value
        return Outcome(status="verified" if good else "unknown", observation=after,
                       evidence=[Evidence(tier="A", kind="file_readback", reading_hash=after.hash)])
