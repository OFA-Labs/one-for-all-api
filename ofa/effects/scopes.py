"""Named folders a user can refer to by voice."""
from __future__ import annotations

import os
from pathlib import Path

SCOPES = {"home": Path.home(), "downloads": Path.home() / "Downloads", "documents": Path.home() / "Documents",
          "desktop": Path.home() / "Desktop", "pictures": Path.home() / "Pictures", "videos": Path.home() / "Videos",
          "onedrive": Path(os.getenv("OneDrive", str(Path.home() / "OneDrive")))}
