"""agents_farm — exposes one capability of the multi-agent runtime to Neo."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("agents_farm")

_ALIAS = 'farm'


def _delegate(query: str) -> str:
    from skills.agents_skill import _get  # shared singleton
    skill = _get()
    if _ALIAS:
        return skill._dispatch(f"{_ALIAS}: {query}")
    return skill._dispatch(query)


class AgentsFarmClass(object):
    name = "agents_farm"

    def process(self, query: Any = None, expression: Any = None,
                inputs: Any = None, text: Any = None, **kw: Any) -> str:
        q = ""
        for cand in (query, expression, text):
            if isinstance(cand, str) and cand.strip():
                q = cand.strip()
                break
        if not q and isinstance(inputs, str):
            q = inputs.strip()
        if not q and isinstance(inputs, dict):
            for k in ("query", "text", "input", "command"):
                v = inputs.get(k)
                if isinstance(v, str) and v.strip():
                    q = v.strip()
                    break
        return _delegate(q)

    def run(self, query: Any = None, **kw: Any) -> str:
        return self.process(query=query, **kw)

    def handle(self, query: Any = None, **kw: Any) -> str:
        return self.process(query=query, **kw)

    def execute(self, query: Any = None, **kw: Any) -> str:
        return self.process(query=query, **kw)


def run(query: Any = None, **kw: Any) -> str:
    return _delegate(str(query) if query is not None else "")
