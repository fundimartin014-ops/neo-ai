"""Simple HTTP fetcher with correct content-encoding handling."""
from __future__ import annotations

import gzip
import urllib.request
import zlib

from agents.config import Config

MAX_CHARS = 4096  # truncate AFTER decode, never before


class SimpleBrowser:
    def open_page(self, url: str) -> str:
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": Config.WEB_USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
                    "Accept-Encoding": "gzip, deflate",
                },
            )
            with urllib.request.urlopen(req, timeout=Config.WEB_TIMEOUT) as resp:
                raw = resp.read()                        # read ALL bytes
                cenc = (resp.headers.get("Content-Encoding") or "").lower().strip()
        except Exception as e:
            return f"[browser error] {e}"

        # Decompress complete payload
        try:
            if cenc == "gzip" or (len(raw) > 1 and raw[:2] == b"\x1f\x8b"):
                raw = gzip.decompress(raw)
            elif cenc == "deflate":
                try:
                    raw = zlib.decompress(raw)
                except zlib.error:
                    raw = zlib.decompress(raw, -zlib.MAX_WBITS)
            elif cenc == "br":
                try:
                    import brotli
                    raw = brotli.decompress(raw)
                except ImportError:
                    return "[browser error] brotli encoding but 'brotli' not installed"
        except Exception as e:
            return f"[browser error] decompress failed: {e}"

        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception as e:
            return f"[browser error] decode failed: {e}"

        return text[:MAX_CHARS]

    def search_and_extract(self, query: str) -> str:
        return f"[search:{query}] (install a real search backend to enable)"