"""Web fetch agent — defensive URL extraction."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

from agents.base_agent import BaseAgent
from agents.browser import SimpleBrowser

_URL_RE = re.compile(r"https?://[^\s)>\]\"']+", re.I)


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            text = data.strip()
            if text:
                self.parts.append(text)

    @property
    def text(self) -> str:
        return "\n".join(self.parts)


class WebAgent(BaseAgent):
    name = "WebAgent"
    capabilities = ("fetch",)

    def __init__(self, browser: SimpleBrowser = None, **kw):
        super().__init__(**kw)
        self.browser = browser or SimpleBrowser()

    def _first_url(self, text: str) -> str | None:
        t = (text or "").strip()
        if t.startswith(("http://", "https://")):
            return t.split()[0].rstrip(").,;:!?\"'>]")
        m = _URL_RE.search(t)
        return m.group(0).rstrip(").,;:!?\"'>]") if m else None

    def fetch(self, url_or_text: str) -> str:
        url = self._first_url(url_or_text)
        if not url:
            return f"[web] no URL found in input: {(url_or_text or '')[:120]}"

        html = self.browser.open_page(url)
        if html.startswith("[browser error]"):
            return html

        parser = _TextExtractor()
        parser.feed(html)
        return parser.text[:4000] or "(empty page)"

    def run(self, url_or_text: str) -> str:
        return self.fetch(url_or_text)

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "fetch":
            return self.fetch(args[0] if args else "")
        return f"WebAgent - command '{command}' not implemented."
