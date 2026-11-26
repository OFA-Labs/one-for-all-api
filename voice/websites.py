"""Web addresses/search are separate from installed application discovery."""
from __future__ import annotations

import ipaddress
import re
from collections.abc import Mapping
from urllib.parse import urlencode, urlsplit, urlunsplit


def validate_url(raw: str) -> str:
    if not raw or any(char.isspace() or ord(char) < 32 for char in raw) or "\\" in raw:
        raise ValueError("Invalid web address")
    candidate = raw if "://" in raw else "https://" + raw
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"https", "http"} or parsed.username or parsed.password or not parsed.hostname:
        raise ValueError("Invalid web address")
    host = parsed.hostname.encode("idna").decode("ascii")
    if host.lower().endswith((".localhost", ".local", ".internal")) or host.lower()=="localhost":
        raise ValueError("Private/local addresses require an explicit grant")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Private/local addresses require an explicit grant")
    if "." not in host or any(not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
                              for label in host.split(".")):
        raise ValueError("Use a valid domain; local/private addresses need an explicit grant")
    port = parsed.port
    authority = host + (":" + str(port) if port else "")
    return urlunsplit((parsed.scheme, authority, parsed.path, parsed.query, parsed.fragment))


class WebsiteResolver:
    def __init__(self, bookmarks: Mapping[str, str] | None = None) -> None:
        self.bookmarks = {"youtube": "https://www.youtube.com", "github": "https://github.com",
                          "chatgpt": "https://chatgpt.com", "google": "https://www.google.com"}
        self.bookmarks.update({key.casefold(): value for key, value in (bookmarks or {}).items()})

    def resolve(self, command: str) -> tuple[str, str] | None:
        command = re.sub(r"\s+(?:please|kindly|kripya|ज़रा|जरा)\s*$", "", command.strip(), flags=re.I)
        search = re.fullmatch(r"search (?:for )?(.+?)(?: on google)?", command, re.I)
        if search:
            return "web.search", "https://www.google.com/search?" + urlencode({"q": search[1]})
        match = re.fullmatch(r"(open|go to|navigate to) (.+)", command, re.I)
        if not match:
            return None
        raw = match[2].strip()
        if not any(char in raw for char in '/?#'):
            raw=re.sub(r'\s+dot\s+', '.',raw,flags=re.I)
        # Sentence punctuation after a bare domain is not part of the host.
        if raw.endswith('.') and '/' not in raw and '?' not in raw: raw=raw[:-1]
        target = self.bookmarks.get(raw.casefold(), raw)
        if target == match[2] and "." not in target:
            return None
        return ("browser.navigate" if match[1].casefold() == "navigate to" else "website.open",
                validate_url(target))
