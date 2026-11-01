from pathlib import Path

# ---- image_analysis_agent ----
p = Path("agents/image_analysis_agent.py")
src = p.read_text(encoding="utf-8")

old = '''    def _resolve_file(self, path_str: str) -> tuple[str | None, str]:
        """Return (resolved_path_or_None, diagnostic_message)."""
        path_str = self._clean_path(path_str)
        if not path_str:
            return None, "empty path"

        p = Path(path_str)
        if not p.exists():
            return None, f"path does not exist: {path_str}"'''

new = '''    def _resolve_file(self, path_str: str) -> tuple[str | None, str]:
        """Return (resolved_path_or_None, diagnostic_message).

        Search order:
          1. path as-is (absolute or relative to cwd)
          2. <project>/sandbox/<name>
          3. <project>/generated_images/<name>
          4. <project>/<name>
        """
        path_str = self._clean_path(path_str)
        if not path_str:
            return None, "empty path"

        # 1. as-is
        candidates = [Path(path_str)]

        # 2-4. common project folders (only if path is not absolute)
        if not Path(path_str).is_absolute():
            here = Path(__file__).resolve().parent.parent
            for sub in ("sandbox", "generated_images", ""):
                candidates.append((here / sub / path_str) if sub else (here / path_str))

        p = None
        for c in candidates:
            try:
                if c.exists():
                    p = c
                    break
            except Exception:
                continue

        if p is None:
            tried = ", ".join(str(c) for c in candidates[:4])
            return None, f"path does not exist (tried: {tried})"'''

if old in src:
    src = src.replace(old, new, 1)
    p.write_text(src, encoding="utf-8")
    print("image_analysis: added sandbox/generated_images/root fallback resolution")
else:
    print("image_analysis: anchor not found — skipping")