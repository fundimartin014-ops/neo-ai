"""DiseaseAlertAgent — diagnose crop diseases from symptoms or a photo."""
from __future__ import annotations

import re
from typing import Any

from agents.base_agent import BaseAgent
from agents.llm import get_llm


DIAGNOSIS_SYSTEM = """You are a plant pathologist producing a diagnosis for a smallholder farmer.

Input sections:
  CROP         - the crop name (or unknown)
  SYMPTOMS     - visual observations (may come from image analysis)
  SEARCH       - web search results for matching diseases

Produce a markdown diagnosis with this structure:

## Disease Alert - {crop}

### Likely Diagnosis
Name 1-3 candidate diseases, ranked by confidence. One-line reason each.

### Why This Matches
2-3 bullets connecting symptoms to candidates.

### Immediate Actions (next 24h)
2-4 concrete steps the farmer should take today.

### Treatment
Common treatment approach for the top candidate (cultural, biological, or chemical). Real product class, no brand names.

### Prevention
1-2 bullets for next season.

If you cannot confidently name a disease, say so and list the 2 most likely possibilities. Under 350 words."""


class DiseaseAlertAgent(BaseAgent):
    name = "DiseaseAlertAgent"
    capabilities = ("disease_alert",)

    def __init__(self, llm=None, **kw):
        super().__init__(**kw)
        try:
            self.llm = llm or get_llm()
        except Exception:
            self.llm = None

    # ------------------------------------------------------------------ vision
    def _describe_image(self, image_path: str) -> str:
        """Run ImageAnalysisAgent on the image. Returns its formatted description."""
        try:
            from agents.image_analysis_agent import ImageAnalysisAgent
            ia = ImageAnalysisAgent()
            result = ia.analyze(image_path)
            if result.get("error"):
                return f"[vision error] {result['error']}"
            parts = []
            if result.get("labels"):
                parts.append("Visual findings:")
                for l in result["labels"]:
                    parts.append(f"  - {l['name']}")
            if result.get("text"):
                parts.append(f"Text in image: {result['text']}")
            return "\n".join(parts) if parts else "[no visual findings]"
        except Exception as e:
            return f"[vision error] {e}"

    # ----------------------------------------------------------------- search
    def _search(self, crop: str, symptoms: str) -> str:
        from agents.search_agent import SearchAgent
        s = SearchAgent()
        if crop:
            q = f"{crop} disease {symptoms} symptoms treatment Kenya"
        else:
            q = f"plant disease {symptoms} symptoms treatment Kenya"
        try:
            return s.run(q, max_results=4)
        except Exception as e:
            return f"[search error] {e}"

    # ---------------------------------------------------------------- compose
    async def diagnose(self, image_path: str = "", crop: str = "",
                       symptoms: str = "", location: str = "Kenya") -> str:
        if image_path and not symptoms:
            symptoms = self._describe_image(image_path)
        elif image_path and symptoms:
            extra = self._describe_image(image_path)
            symptoms = f"{symptoms}\n\n{extra}"

        if not symptoms:
            return "DiseaseAlertAgent: provide either an image_path or a symptoms description."

        web = self._search(crop, symptoms)

        if not self.llm:
            return (
                f"## Disease Alert - {crop or 'Unknown crop'}\n\n"
                f"### Symptoms\n{symptoms}\n\n"
                f"### Search results\n{web}"
            )

        user = (
            f"CROP: {crop or 'unknown'}\n"
            f"LOCATION: {location}\n\n"
            f"=== SYMPTOMS ===\n{symptoms}\n\n"
            f"=== SEARCH ===\n{web}\n"
        )
        try:
            return await self.llm.chat(
                [{"role": "system", "content": DIAGNOSIS_SYSTEM},
                 {"role": "user", "content": user}],
                temperature=0.3,
            )
        except Exception as e:
            return f"[diagnosis error] {e}\n\nRaw:\n\n{user}"

    # ------------------------------------------------------------------ entry
    async def arun(self, payload: str = "", crop: str = "",
                   image_path: str = "", symptoms: str = "") -> str:
        if payload:
            p = payload.strip()
            # strip outer quotes
            if len(p) >= 2 and p[0] == p[-1] and p[0] in ("\"", "'"):
                p = p[1:-1].strip()
            if p.lower().startswith("image:"):
                image_path = p[6:].strip()
            elif re.search(r"\bsymptoms?\s*:", p, re.I):
                parts = re.split(r"\bsymptoms?\s*:\s*", p, maxsplit=1, flags=re.I)
                before, sym = parts[0].strip(), parts[1].strip()
                if before.lower().startswith("crop:"):
                    crop = before[5:].strip()
                symptoms = sym
            elif p.lower().startswith("crop:"):
                crop = p[5:].strip()
            else:
                # bare path → treat as image
                from pathlib import Path as _P
                if _P(p).exists():
                    image_path = p
                else:
                    symptoms = p

        return await self.diagnose(image_path=image_path, crop=crop, symptoms=symptoms)

    def run(self, payload: str = "", crop: str = "",
            image_path: str = "", symptoms: str = "") -> str:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, self.arun(
                        payload, crop, image_path, symptoms)).result()
            return loop.run_until_complete(self.arun(payload, crop, image_path, symptoms))
        except RuntimeError:
            return asyncio.run(self.arun(payload, crop, image_path, symptoms))

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "diagnose":
            return self.run(payload=args[0] if args else "")
        return f"DiseaseAlertAgent - command '{command}' not implemented."
