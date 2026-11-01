"""
NEO HYBRID OUTPUT ENGINE v1.3
Runs multiple cloud models in parallel and merges their outputs into one unified response.

Merge Strategies:
  - synthesis    : Combine all unique insights into one coherent response
  - consensus    : Extract only points all models agree on
  - debate       : Show conflicting viewpoints and reconcile them
  - ensemble     : Weighted voting on facts (confidence scoring)
  - cascade      : Chain outputs from one model to refine another
  - best_of_all  : Extract the best paragraph/section from each output
  - parallel     : Return all outputs with a meta-summary

Changelog:
  v1.3 — Added ollama to provider URL map (OpenAI-compatible endpoint on
         localhost:11434). Updated seed pool.
  v1.2 — Provider→env_key inference inside _call_model, so entries from
         neo_model_health (which only carry provider+id) authenticate
         correctly. Fixed outcome recorder to look at ModelOutput.error,
         not just Exception types.

Usage:
    from hybrid_merger import HybridMerger
    merger = HybridMerger()
    result = await merger.hybrid_generate(
        prompt="Explain quantum computing",
        auto_pool="chat",
        strategy="synthesis",
    )
"""

import asyncio
import os
import json
import time
import hashlib
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import logging
import neo_model_health as nmh

logger = logging.getLogger("hybrid_merger")


# Map provider name -> env var holding its API key. Used to authenticate
# pool entries that only carry {"provider", "id"}.
_PROVIDER_ENV = {
    "groq":         "GROQ_API_KEY",
    "openrouter":   "OPENROUTER_API_KEY",
    "deepinfra":    "DEEPINFRA_API_TOKEN",
    "mistral":      "MISTRAL_API_KEY",
    "fireworks":    "FIREWORKS_API_KEY",
    "novita":       "NOVITA_API_KEY",
    "hyperbolic":   "HYPERBOLIC_API_KEY",
    "siliconflow":  "SILICONFLOW_API_KEY",
    "friendli":     "FRIENDLI_API_KEY",
    "gemini":       "GEMINI_API_KEY",
    "huggingface":  "HF_TOKEN",
    "cloudflare":   "CF_API_TOKEN",
    "replicate":    "REPLICATE_API_TOKEN",
    "pollinations": "POLLINATIONS_API_KEY",
    "ai_horde":     "AI_HORDE_API_KEY",
    "deepai":       "DEEPAI_API_KEY",
    "segmind":      "SEGMIND_API_KEY",
    "ideogram":     "IDEOGRAM_API_KEY",
    "clipdrop":     "CLIPDROP_API_KEY",
    "inference":    "INFERENCE_API_KEY",
    # ollama is local — no key needed. Absence here means api_key stays None
    # and the Authorization header is simply omitted, which Ollama accepts.
}

# Map provider name -> default base URL. Used when a pool entry has no
# base_url. All values point at OpenAI-compatible endpoints.
_PROVIDER_URL = {
    "groq":         "https://api.groq.com/openai/v1",
    "openrouter":   "https://openrouter.ai/api/v1",
    "ollama":       "http://localhost:11434/v1",
    "deepinfra":    "https://api.deepinfra.com/v1/openai",
    "mistral":      "https://api.mistral.ai/v1",
    "fireworks":    "https://api.fireworks.ai/inference/v1",
    "novita":       "https://api.novita.ai/v3/openai",
    "hyperbolic":   "https://api.hyperbolic.xyz/v1",
    "siliconflow":  "https://api.siliconflow.cn/v1",
    "friendli":     "https://api.friendli.ai/serverless/v1",
    "gemini":       "https://generativelanguage.googleapis.com/v1beta/openai",
    "deepseek":     "https://api.deepseek.com/v1",
    "together":     "https://api.together.xyz/v1",
    "perplexity":   "https://api.perplexity.ai",
}


@dataclass
class ModelOutput:
    """Result from a single model call."""
    model_id: str
    provider: str
    output: str
    latency: float
    tokens_used: int = 0
    error: Optional[str] = None
    raw_response: Any = None


@dataclass
class HybridResult:
    """Final merged result from the Hybrid Engine."""
    strategy: str
    prompt: str
    outputs: List[ModelOutput]
    merged_output: str
    merge_latency: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class HybridMerger:
    """
    Hybrid Output Engine for NEO.

    Runs N models in parallel, then synthesizes their outputs into one.
    Cloud orchestration with self-healing pool selection.
    """

    # Merger / synthesizer models. Only IDs confirmed live on this key.
    MERGER_MODELS = [
        {"provider": "groq", "model": "openai/gpt-oss-120b",
         "base_url": "https://api.groq.com/openai/v1",
         "env": "GROQ_API_KEY"},
        {"provider": "openrouter", "model": "nvidia/nemotron-3-super-120b-a12b:free",
         "base_url": "https://openrouter.ai/api/v1",
         "env": "OPENROUTER_API_KEY"},
        {"provider": "openrouter", "model": "openai/gpt-oss-120b:free",
         "base_url": "https://openrouter.ai/api/v1",
         "env": "OPENROUTER_API_KEY"},
    ]

    # Groq IDs currently live on the free tier. Anything outside this set
    # that comes from the catalog gets dropped and recorded as dead.
    _LIVE_GROQ_MODELS = {
        "openai/gpt-oss-120b",
        "llama-3.3-70b-versatile",
        "qwen-2.5-coder-32b",
    }

    _GROQ_FALLBACK = "openai/gpt-oss-120b"

    def __init__(self, max_workers: int = 10, timeout: float = 60.0):
        self.max_workers = max_workers
        self.timeout = timeout
        self._session = None
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._cache: Dict[str, HybridResult] = {}

        try:
            from neo_models_catalog import (
                get_all_models, get_models_by_type, get_model_by_id,
            )
            self.catalog = {
                "get_all": get_all_models,
                "by_type": get_models_by_type,
                "by_id": get_model_by_id,
            }
        except ImportError:
            self.catalog = None
            logger.warning(
                "neo_models_catalog not found. HybridMerger running in manual mode."
            )

    # ------------------------------------------------------------------
    # pool helpers
    # ------------------------------------------------------------------

    def _get_curated_pool(self, n: int) -> List[Dict]:
        """
        Return up to n live candidates from neo_model_health, as dicts.
        Computed fresh on every call so it reflects the latest known-good
        and dead sets.
        """
        try:
            pool = nmh.get_pool(n)
        except Exception as e:
            logger.warning(f"[HybridMerger] get_pool failed: {e}")
            return []
        out = []
        for entry in pool:
            if isinstance(entry, dict) and entry.get("provider") and entry.get("id"):
                out.append(entry)
        return out

    def _is_available(self, model: Dict) -> bool:
        """True if the model is not dead and not throttled."""
        prov = model.get("provider", "")
        mid = model.get("id", "")
        if not prov or not mid:
            return False
        try:
            if nmh.is_dead(prov, mid):
                return False
            if nmh.is_throttled(prov, mid):
                return False
        except Exception:
            pass
        return True

    # ------------------------------------------------------------------
    # HTTP call helpers
    # ------------------------------------------------------------------

    def _get_api_key(self, env_var: Optional[str]) -> Optional[str]:
        if not env_var:
            return None
        return os.getenv(env_var)

    def _resolve_model(self, model_hint: str) -> Optional[Dict]:
        """Resolve a model hint to a full model config."""
        if self.catalog:
            m = self.catalog["by_id"](model_hint)
            if m:
                return m
            all_models = self.catalog["get_all"]()
            for m in all_models:
                if (model_hint.lower() in m["id"].lower()
                        or model_hint.lower() in m.get("name", "").lower()):
                    return m
        return None

    def _build_openai_payload(self, prompt: str, model_id: str,
                              system: Optional[str] = None) -> Dict:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return {
            "model": model_id,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048,
            "stream": False,
        }

    async def _call_model(self, model_config: Dict, prompt: str,
                          system: Optional[str] = None) -> ModelOutput:
        """Call a single cloud model via OpenAI-compatible API."""
        import aiohttp

        provider = model_config.get("provider", "unknown")
        model_id = model_config["id"]
        base_url = model_config.get("base_url", "")

        # ---- env_key inference --------------------------------------
        # Catalog entries carry env_key/env. Pool entries from
        # neo_model_health only carry provider+id, so we look the env
        # var up by provider name. Missing env_key for a provider that
        # doesn't need auth (ollama) is fine — api_key stays None and
        # the Authorization header is simply omitted.
        env_key = (model_config.get("env_key")
                   or model_config.get("env")
                   or _PROVIDER_ENV.get(provider))

        api_key = self._get_api_key(env_key)
        if env_key and not api_key:
            return ModelOutput(
                model_id=model_id, provider=provider,
                output="", latency=0,
                error=f"Missing API key: {env_key}",
            )

        # ---- Cloudflare account_id substitution ---------------------
        if "{account_id}" in base_url:
            account_id = os.getenv("CF_ACCOUNT_ID", "")
            base_url = base_url.replace("{account_id}", account_id)

        # ---- base_url inference -------------------------------------
        if not base_url:
            base_url = _PROVIDER_URL.get(provider, "")

        if not base_url:
            return ModelOutput(
                model_id=model_id, provider=provider,
                output="", latency=0,
                error=f"No base_url for provider '{provider}'",
            )

        url = f"{base_url}/chat/completions"
        payload = self._build_openai_payload(prompt, model_id, system)
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        start = time.time()
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        return ModelOutput(
                            model_id=model_id, provider=provider,
                            output="", latency=time.time() - start,
                            error=f"HTTP {resp.status}: {text[:300]}",
                        )
                    data = await resp.json()
                    content = (data["choices"][0]["message"]["content"]
                               if "choices" in data else str(data))
                    tokens = data.get("usage", {}).get("total_tokens", 0)
                    return ModelOutput(
                        model_id=model_id, provider=provider,
                        output=content.strip(), latency=time.time() - start,
                        tokens_used=tokens, raw_response=data,
                    )
        except asyncio.TimeoutError:
            return ModelOutput(
                model_id=model_id, provider=provider,
                output="", latency=time.time() - start, error="Timeout",
            )
        except Exception as e:
            return ModelOutput(
                model_id=model_id, provider=provider,
                output="", latency=time.time() - start, error=str(e)[:200],
            )

    async def _call_merger(self, prompt: str, system: str) -> Optional[str]:
        """Call the merger/synthesizer model. Tries multiple fallbacks."""
        import aiohttp

        for merger in self.MERGER_MODELS:
            api_key = self._get_api_key(merger["env"])
            if not api_key:
                continue

            url = f"{merger['base_url']}/chat/completions"
            payload = {
                "model": merger["model"],
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 4096,
                "stream": False,
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }

            try:
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, json=payload, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return data["choices"][0]["message"]["content"].strip()
            except Exception:
                continue

        return None

    # ------------------------------------------------------------------
    # strategy prompt builders
    # ------------------------------------------------------------------

    def _build_synthesis_prompt(self, outputs: List[ModelOutput],
                                original_prompt: str) -> str:
        sections = []
        for i, out in enumerate(outputs, 1):
            sections.append(
                f"--- MODEL {i}: {out.provider}/{out.model_id} ---\n{out.output}\n"
            )
        body = "\n".join(sections)
        return f"""You are a Hybrid Synthesis Engine. Your job is to read outputs from multiple AI models and produce ONE unified, coherent response that captures the best of all worlds.

ORIGINAL USER QUERY:
{original_prompt}

MODEL OUTPUTS:
{body}

INSTRUCTIONS:
1. Read all model outputs carefully.
2. Identify unique insights, facts, or perspectives from each.
3. Resolve any contradictions by noting the consensus view or presenting both sides fairly.
4. Combine everything into ONE well-structured, comprehensive response.
5. Do NOT mention that this is a merged output. Write as if you are the sole author.
6. Use markdown formatting where appropriate.

SYNTHESIZED RESPONSE:"""

    def _build_consensus_prompt(self, outputs: List[ModelOutput],
                                original_prompt: str) -> str:
        sections = []
        for i, out in enumerate(outputs, 1):
            sections.append(f"--- MODEL {i} ---\n{out.output}\n")
        body = "\n".join(sections)
        return f"""You are a Consensus Extractor. Read the following model outputs and extract ONLY the points that appear to be agreed upon by most models.

QUERY: {original_prompt}

{body}

INSTRUCTIONS:
1. List only facts/claims that 2+ models agree on.
2. Note any significant disagreements separately.
3. Provide a concise consensus answer.

CONSENSUS:"""

    def _build_debate_prompt(self, outputs: List[ModelOutput],
                             original_prompt: str) -> str:
        sections = []
        for i, out in enumerate(outputs, 1):
            sections.append(
                f"--- MODEL {i}: {out.provider}/{out.model_id} ---\n{out.output}\n"
            )
        body = "\n".join(sections)
        return f"""You are a Debate Moderator. Multiple AI models have answered the same query. Your job is to identify disagreements, reconcile them, and present a balanced final view.

QUERY: {original_prompt}

{body}

INSTRUCTIONS:
1. Identify areas of AGREEMENT across models.
2. Identify areas of DISAGREEMENT.
3. For disagreements, present each side fairly.
4. Provide your own reconciled conclusion based on the evidence.
5. Use markdown with clear sections.

RECONCILED RESPONSE:"""

    def _build_ensemble_prompt(self, outputs: List[ModelOutput],
                               original_prompt: str) -> str:
        sections = []
        for i, out in enumerate(outputs, 1):
            sections.append(
                f"--- MODEL {i}: {out.provider}/{out.model_id} ---\n{out.output}\n"
            )
        body = "\n".join(sections)
        return f"""You are an Ensemble Fact-Checker. Multiple models answered the same query. Assign confidence scores and produce a weighted consensus.

QUERY: {original_prompt}

{body}

INSTRUCTIONS:
1. Extract all factual claims from each output.
2. For each claim, note how many models support it (confidence score).
3. Flag any claims that only one model made as "Low Confidence".
4. Produce a final answer with confidence annotations like [High], [Medium], [Low].

ENSEMBLE RESPONSE:"""

    def _build_best_of_all_prompt(self, outputs: List[ModelOutput],
                                  original_prompt: str) -> str:
        sections = []
        for i, out in enumerate(outputs, 1):
            sections.append(
                f"--- MODEL {i}: {out.provider}/{out.model_id} ---\n{out.output}\n"
            )
        body = "\n".join(sections)
        return f"""You are a Curator. Multiple models answered the same query. Extract the single best paragraph or section from EACH model, then weave them into one flowing narrative.

QUERY: {original_prompt}

{body}

INSTRUCTIONS:
1. From each model output, pick the BEST paragraph/section.
2. Combine these best parts into ONE coherent response.
3. Smooth transitions between sections.
4. Do NOT mention the source models in the final text.

CURATED RESPONSE:"""

    def _build_parallel_prompt(self, outputs: List[ModelOutput],
                               original_prompt: str) -> str:
        sections = []
        for i, out in enumerate(outputs, 1):
            sections.append(
                f"--- MODEL {i}: {out.provider}/{out.model_id} ---\n{out.output}\n"
            )
        body = "\n".join(sections)
        return f"""You are a Meta-Summarizer. Multiple models answered the same query. Provide a brief meta-summary, then list all outputs.

QUERY: {original_prompt}

{body}

INSTRUCTIONS:
1. Write a 2-3 sentence meta-summary of common themes.
2. Then list each model's key contribution as a bullet point.

META-SUMMARY:"""

    # ------------------------------------------------------------------
    # strategy dispatch
    # ------------------------------------------------------------------

    async def _apply_strategy(self, outputs: List[ModelOutput],
                              strategy: str, original_prompt: str) -> str:
        valid = [o for o in outputs if not o.error and o.output]
        if not valid:
            return "[HybridMerger] All models failed."

        if strategy == "cascade":
            current = valid[0].output
            for _ in valid[1:]:
                refine_prompt = (
                    f"Improve and refine the following response to the query: "
                    f"{original_prompt}\n\nCURRENT RESPONSE:\n{current}\n\n"
                    f"REFINED RESPONSE:"
                )
                merged = await self._call_merger(
                    refine_prompt,
                    "You are a refinement engine. Improve clarity, accuracy, and depth.",
                )
                if merged:
                    current = merged
            return current

        builders = {
            "synthesis": self._build_synthesis_prompt,
            "consensus": self._build_consensus_prompt,
            "debate": self._build_debate_prompt,
            "ensemble": self._build_ensemble_prompt,
            "best_of_all": self._build_best_of_all_prompt,
            "parallel": self._build_parallel_prompt,
        }
        builder = builders.get(strategy, self._build_synthesis_prompt)
        meta_prompt = builder(valid, original_prompt)

        system = ("You are the NEO Hybrid Synthesis Engine. "
                  "You merge multiple AI outputs into one superior response.")
        merged = await self._call_merger(meta_prompt, system)
        if merged:
            return merged

        fallback = f"# Hybrid Output ({strategy})\n\n"
        for o in valid:
            fallback += f"## {o.provider}/{o.model_id}\n{o.output}\n\n"
        return fallback

    # ------------------------------------------------------------------
    # main entry point
    # ------------------------------------------------------------------

    async def hybrid_generate(
        self,
        prompt: str,
        model_pool: Optional[List[str]] = None,
        strategy: str = "synthesis",
        auto_pool: Optional[str] = None,
        pool_size: int = 5,
        system: Optional[str] = None,
        use_cache: bool = True,
    ) -> HybridResult:
        """Generate a hybrid response by running multiple models and merging outputs."""

        cache_key = hashlib.sha256(
            f"{prompt}:{strategy}:{','.join(model_pool or [])}:{auto_pool}:{pool_size}".encode()
        ).hexdigest()
        if use_cache and cache_key in self._cache:
            logger.info("[HybridMerger] Cache hit")
            return self._cache[cache_key]

        resolved_models: List[Dict] = []

        if model_pool:
            for hint in model_pool:
                m = self._resolve_model(hint)
                if m:
                    resolved_models.append(m)
        elif auto_pool and self.catalog:
            pool_map = {
                "chat": "chat", "coding": "coding", "reasoning": "reasoning",
                "vision": "vision", "image_gen": "image-gen",
                "video_gen": "video-gen", "embedding": "embedding",
                "image_edit": "image-edit", "image_describe": "image-describe",
            }
            mtype = pool_map.get(auto_pool, auto_pool)
            candidates = self.catalog["by_type"](mtype)

            free_models = [m for m in candidates
                           if m.get("tier") in ("free", "free_fast", "free_no_key")]
            tier_models = [m for m in candidates if m.get("tier") == "free_tier"]
            credit_models = [m for m in candidates if m.get("tier") == "free_credit"]

            selected, seen_families = [], set()
            for source in (free_models, tier_models, credit_models):
                for m in source:
                    fam = m.get("family", "unknown")
                    if fam not in seen_families and len(selected) < pool_size:
                        selected.append(m)
                        seen_families.add(fam)
                if len(selected) >= pool_size:
                    break
            resolved_models = selected[:pool_size]

        # ── Filter dead / non-live models ──
        filtered = []
        for _m in resolved_models:
            _prov = _m.get("provider", "")
            _mid = _m.get("id", "")
            if _prov == "groq" and (_mid not in self._LIVE_GROQ_MODELS):
                logger.info(f"[HybridMerger] Dropping non-live Groq model '{_mid}'")
                try:
                    nmh.record_dead("groq", _mid)
                except Exception:
                    pass
                continue
            if not self._is_available(_m):
                logger.info(
                    f"[HybridMerger] Skipping unavailable '{_prov}/{_mid}'"
                )
                continue
            filtered.append(_m)
        resolved_models = filtered

        # ── Diversity check ──
        if not model_pool:
            _unique = {(m.get("provider"), m.get("id")) for m in resolved_models}
            if len(_unique) < 2:
                logger.warning(
                    f"[HybridMerger] Catalog gave {len(_unique)} unique model(s), "
                    f"swapping to curated pool for real diversity"
                )
                resolved_models = self._get_curated_pool(max(pool_size, 2))
                _unique = {(m.get("provider"), m.get("id")) for m in resolved_models}
                logger.info(
                    f"[HybridMerger] Curated pool selected: {sorted(_unique)}"
                )

        # ── Pad from known-good pool if short ──
        if not model_pool and len(resolved_models) < pool_size:
            _have = {(m.get("provider"), m.get("id")) for m in resolved_models}
            for _cand in self._get_curated_pool(pool_size):
                _ck = (_cand.get("provider"), _cand.get("id"))
                if _ck in _have:
                    continue
                resolved_models.append(_cand)
                _have.add(_ck)
                if len(resolved_models) >= pool_size:
                    break

        if not resolved_models:
            return HybridResult(
                strategy=strategy, prompt=prompt,
                outputs=[],
                merged_output="[HybridMerger] No models resolved.",
                merge_latency=0,
                metadata={"error": "No models available"},
            )

        logger.info(
            f"[HybridMerger] Running {len(resolved_models)} models "
            f"with strategy={strategy}"
        )

        start = time.time()
        tasks = [self._call_model(m, prompt, system) for m in resolved_models]
        outputs = await asyncio.gather(*tasks, return_exceptions=True)

        # ── Record outcomes ──
        # _call_model swallows exceptions and returns ModelOutput with
        # .error set, so we check both kinds of failure.
        for _m, _out in zip(resolved_models, outputs):
            _prov = _m.get("provider", "?")
            _mid = _m.get("id", "?")
            try:
                _err = None
                if isinstance(_out, Exception):
                    _err = str(_out)
                elif _out is not None and getattr(_out, "error", None):
                    _err = _out.error

                if not _err:
                    nmh.record_success(_prov, _mid)
                    continue

                _low = _err.lower()
                if "missing api key" in _low:
                    # Config problem, not the model's fault. Leave state alone.
                    pass
                elif ("429" in _err or "rate limit" in _low
                      or "too many requests" in _low
                      or "invalid api key" in _low):
                    nmh.record_throttled(_prov, _mid)
                elif ("404" in _err or "not_found" in _low
                      or "does not exist" in _low
                      or "decommission" in _low
                      or "no longer supported" in _low
                      or "unavailable" in _low):
                    nmh.record_dead(_prov, _mid)
                # Other errors: leave state untouched, retry next time.
            except Exception:
                pass

        # ── Normalize outputs ──
        normalized = []
        for i, result in enumerate(outputs):
            if isinstance(result, Exception):
                normalized.append(ModelOutput(
                    model_id=resolved_models[i]["id"],
                    provider=resolved_models[i].get("provider", "unknown"),
                    output="", latency=0, error=str(result),
                ))
            else:
                normalized.append(result)

        merge_start = time.time()
        merged = await self._apply_strategy(normalized, strategy, prompt)
        merge_latency = time.time() - merge_start

        result = HybridResult(
            strategy=strategy,
            prompt=prompt,
            outputs=normalized,
            merged_output=merged,
            merge_latency=merge_latency,
            metadata={
                "total_models": len(resolved_models),
                "successful": len([o for o in normalized if not o.error]),
                "failed": len([o for o in normalized if o.error]),
                "total_latency": time.time() - start,
                "cache_key": cache_key,
                "errors": {
                    f"{o.provider}/{o.model_id}": o.error
                    for o in normalized if o.error
                },
                "successes": {
                    f"{o.provider}/{o.model_id}": f"{len(o.output)} chars, {o.latency:.2f}s"
                    for o in normalized if not o.error
                },
            },
        )

        if use_cache:
            self._cache[cache_key] = result

        return result

    async def hybrid_chat(
        self,
        messages: List[Dict[str, str]],
        model_pool: Optional[List[str]] = None,
        strategy: str = "synthesis",
        auto_pool: str = "chat",
        pool_size: int = 5,
    ) -> HybridResult:
        """Hybrid chat with message history support."""
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt_parts.append(f"[{role.upper()}]: {content}")
        flat_prompt = "\n".join(prompt_parts)
        return await self.hybrid_generate(
            prompt=flat_prompt,
            model_pool=model_pool,
            strategy=strategy,
            auto_pool=auto_pool,
            pool_size=pool_size,
        )

    def get_available_strategies(self) -> List[str]:
        return ["synthesis", "consensus", "debate", "ensemble",
                "best_of_all", "parallel", "cascade"]

    def clear_cache(self):
        self._cache.clear()

    def get_cache_stats(self) -> Dict:
        return {"entries": len(self._cache), "keys": list(self._cache.keys())}


# ── CLI / Standalone test ──
async def main():
    merger = HybridMerger()

    print("=" * 60)
    print("  NEO HYBRID OUTPUT ENGINE v1.3")
    print("=" * 60)
    print(f"  Strategies: {merger.get_available_strategies()}")
    print()

    result = await merger.hybrid_generate(
        prompt="Explain the concept of emergence in complex systems in 3 paragraphs.",
        auto_pool="chat",
        pool_size=3,
        strategy="synthesis",
    )

    print(f"Strategy: {result.strategy}")
    print(f"Models run: {result.metadata['total_models']}")
    print(f"Successful: {result.metadata['successful']}")
    print(f"Failed: {result.metadata['failed']}")
    print(f"Total latency: {result.metadata['total_latency']:.2f}s")
    print(f"Merge latency: {result.merge_latency:.2f}s")
    print()
    print("--- MERGED OUTPUT ---")
    print(result.merged_output[:2000])
    print("...")


if __name__ == "__main__":
    asyncio.run(main())