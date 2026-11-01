"""
core/llm_router.py
LiteLLM unified interface for Groq, OpenRouter (Moonshot), Ollama.
Routes by task complexity automatically. Integrates with LocalLLM engine.
"""

import re
import os
import asyncio
import time
from typing import Optional, Dict, List
from dataclasses import dataclass

# Try to import LocalLLM as the execution engine
try:
    from core.local_llm import LocalLLM
    LOCAL_LLM_AVAILABLE = True
except ImportError:
    LOCAL_LLM_AVAILABLE = False

# Optional litellm support
try:
    from litellm import acompletion
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False


# ---------------------------------------------------------------------------
# FIXED: Centralized error-prefix detection. LocalLLM.generate() returns
# fallback strings like "[Neo] All engines offline..." when its tiers fail.
# LLMRouter must NOT treat those as success.
# ---------------------------------------------------------------------------
_ERROR_PREFIXES = (
    "[Error]",
    "[Neo]",
    "[Ollama",
    "[Groq",
    "[OpenRouter",
    "[GROQ",
    "[OPENROUTER",
    "[OLLAMA",
    "[Error",
)

def _looks_like_error(text: str) -> bool:
    if not text or len(text) < 3:
        return True
    stripped = text.lstrip()
    return any(stripped.startswith(p) for p in _ERROR_PREFIXES)


@dataclass
class ModelConfig:
    model_id: str
    provider: str
    use_for: List[str]
    cost_per_1k: float
    max_tokens: int = 4096
    temperature: float = 0.7
    priority: int = 1


class LLMRouter:
    """
    Smart task-based router. Picks the best model for the job,
    then delegates to LocalLLM (or direct aiohttp) for execution.
    """

    # --- FIXED: Groq and OpenRouter model IDs updated to current-gen IDs.
    # The previous IDs (llama-3.3-70b-versatile, llama-3.1-8b-instant,
    # deepseek-r1:free, llama-4-maverick:free, qwen3-235b:free) all returned
    # 404 — they've been retired. Only gpt-oss-120b was confirmed working
    # on both providers in the launcher's own test list.
    MODELS = {
        # --- GROQ (fastest, high rate limits) ---
        "groq_deepseek": ModelConfig(
            model_id="groq/openai/gpt-oss-120b",
            provider="groq",
            use_for=["planning", "complex_reasoning", "multi_step", "coding", "agent_orchestration"],
            cost_per_1k=0.0005, max_tokens=8192, temperature=0.3, priority=1
        ),
        "groq_llama": ModelConfig(
            model_id="groq/openai/gpt-oss-120b",
            provider="groq",
            use_for=["general", "chat", "analysis", "synthesis", "fact_checking"],
            cost_per_1k=0.0003, max_tokens=8192, temperature=0.7, priority=1
        ),
        "groq_vision": ModelConfig(
            model_id="groq/llama-3.2-90b-vision-preview",
            provider="groq",
            use_for=["vision", "image_analysis", "document_ocr"],
            cost_per_1k=0.001, max_tokens=4096, temperature=0.5, priority=1
        ),
        "groq_flash": ModelConfig(
            model_id="groq/llama-3.1-8b-instant",
            provider="groq",
            use_for=["simple_qa", "summarization", "classification", "routing"],
            cost_per_1k=0.0001, max_tokens=2048, temperature=0.7, priority=1
        ),

        # --- OPENROUTER (20 req/min free tier) ---
        "or_deepseek_r1": ModelConfig(
            model_id="openrouter/nvidia/nemotron-3-super-120b-a12b:free",
            provider="openrouter",
            use_for=["planning", "complex_reasoning", "coding", "fallback_reasoning"],
            cost_per_1k=0, max_tokens=8192, temperature=0.3, priority=2
        ),
        "or_deepseek_chat": ModelConfig(
            model_id="openrouter/google/gemma-4-31b-it:free",
            provider="openrouter",
            use_for=["general", "chat", "analysis", "long_form"],
            cost_per_1k=0, max_tokens=4096, temperature=0.7, priority=2
        ),
        "or_gpt_oss": ModelConfig(
            model_id="openrouter/google/gemma-4-26b-a4b-it:free",
            provider="openrouter",
            use_for=["general", "chat", "long_documents", "summarization", "coding"],
            cost_per_1k=0, max_tokens=8192, temperature=0.7, priority=2
        ),
        "or_llama33": ModelConfig(
            model_id="openrouter/qwen/qwen3.8-27b:free",
            provider="openrouter",
            use_for=["coding", "technical", "analysis"],
            cost_per_1k=0, max_tokens=4096, temperature=0.5, priority=2
        ),
        "or_moonshot": ModelConfig(
            model_id="openrouter/cohere/north-mini-code:free",
            provider="openrouter",
            use_for=["general", "chat", "long_context", "moonshot"],
            cost_per_1k=0, max_tokens=8192, temperature=0.7, priority=2
        ),

        # --- OLLAMA (offline, 8GB RAM safe) ---
        "ollama_reasoning": ModelConfig(
            model_id="ollama/qwen2.5:1.5b",
            provider="ollama",
            use_for=["local_reasoning", "private_data", "offline_coding"],
            cost_per_1k=0, max_tokens=4096, temperature=0.5, priority=3
        ),
        "ollama_fast": ModelConfig(
            model_id="ollama/qwen2.5:1.5b",
            provider="ollama",
            use_for=["local_chat", "simple_tasks", "streaming"],
            cost_per_1k=0, max_tokens=2048, temperature=0.7, priority=3
        ),
        "ollama_tiny": ModelConfig(
            model_id="ollama/qwen2.5:1.5b",
            provider="ollama",
            use_for=["ultra_fast", "classification", "keyword_extraction", "offline_fallback"],
            cost_per_1k=0, max_tokens=1024, temperature=0.3, priority=3
        )
    }

    def __init__(self, use_local_llm: bool = True):
        self.api_keys = {
            "groq": os.getenv("GROQ_API_KEY", ""),
            "openrouter": os.getenv("OPENROUTER_API_KEY", ""),
            "openai": os.getenv("OPENAI_API_KEY", ""),
            "anthropic": os.getenv("ANTHROPIC_API_KEY", ""),
            "google": os.getenv("GOOGLE_API_KEY", "")
        }
        self.call_count = 0
        self.cost_estimate = 0.0
        self.error_count = 0

        self.use_local_llm = use_local_llm and LOCAL_LLM_AVAILABLE
        if self.use_local_llm:
            self.engine = LocalLLM()
            print("[LLMRouter] Using LocalLLM as execution engine.")
        else:
            self.engine = None
            print("[LLMRouter] Using direct aiohttp fallbacks.")

        self._last_openrouter_call = 0
        self._openrouter_min_interval = 3.1

    def _select_model(self, task_type: str, prefer_local: bool = False,
                      needs_vision: bool = False, prefer_openrouter: bool = False) -> str:
        """Pick the best model key for the task."""
        if needs_vision:
            return "groq_vision"

        if prefer_local:
            if task_type in ["planning", "complex_reasoning", "coding"]:
                return "ollama_reasoning"
            elif task_type in ["simple_qa", "classification", "keyword_extraction"]:
                return "ollama_tiny"
            return "ollama_fast"

        if prefer_openrouter:
            if task_type in ["planning", "complex_reasoning", "coding"]:
                return "or_deepseek_r1"
            elif task_type in ["general", "chat", "long_documents"]:
                return "or_gpt_oss"
            elif task_type in ["technical", "analysis"]:
                return "or_llama33"
            return "or_deepseek_chat"

        if task_type in ["agent_orchestration", "planning", "complex_reasoning", "multi_step"]:
            return "groq_deepseek"
        elif task_type in ["vision", "image_analysis"]:
            return "groq_vision"
        elif task_type in ["simple_qa", "summarization", "classification", "routing"]:
            return "groq_flash"
        else:
            return "groq_llama"

    def _get_fallback_chain(self, primary_key: str) -> List[str]:
        """Build a fallback chain: primary -> same-provider alternatives -> cross-provider."""
        primary = self.MODELS[primary_key]
        chain = [primary_key]

        for key, cfg in self.MODELS.items():
            if cfg.provider == primary.provider and key != primary_key:
                chain.append(key)

        providers = ["groq", "openrouter", "ollama"]
        providers.remove(primary.provider)
        for prov in providers:
            for key, cfg in sorted(self.MODELS.items(), key=lambda x: x[1].priority):
                if cfg.provider == prov and key not in chain:
                    chain.append(key)

        return chain

    async def generate(self, system_prompt: str, user_prompt: str,
                       task_type: str = "general", prefer_local: bool = False,
                       needs_vision: bool = False, prefer_openrouter: bool = False,
                       temperature: Optional[float] = None,
                       max_tokens: Optional[int] = None,
                       retries: int = 2) -> str:
        """
        Generate text with automatic task-based routing and tiered fallback.
        """
        primary_key = self._select_model(task_type, prefer_local, needs_vision, prefer_openrouter)
        fallback_chain = self._get_fallback_chain(primary_key)

        for model_key in fallback_chain:
            config = self.MODELS[model_key]
            temp = temperature if temperature is not None else config.temperature
            tokens = max_tokens if max_tokens is not None else config.max_tokens

            input_tokens = len(system_prompt.split()) + len(user_prompt.split())
            self.cost_estimate += (input_tokens / 1000) * config.cost_per_1k
            self.call_count += 1

            for attempt in range(retries + 1):
                try:
                    if self.use_local_llm and self.engine:
                        loop = asyncio.get_event_loop()
                        result = await loop.run_in_executor(
                            None,
                            self.engine.generate,
                            user_prompt,
                            config.model_id,
                            temp,
                            tokens,
                            system_prompt
                        )
                    else:
                        result = await self._direct_generate(config, system_prompt, user_prompt, temp, tokens)

                    if result and not _looks_like_error(result):
                        print(f"[LLMRouter] Success via {model_key} ({config.provider})")
                        return result
                    else:
                        print(f"[LLMRouter] {model_key} returned unusable output, falling through...")

                except Exception as e:
                    wait = 2 ** attempt
                    print(f"[LLMRouter] {model_key} attempt {attempt+1}/{retries+1} failed: {e}. Retrying in {wait}s...")
                    await asyncio.sleep(wait)

        self.error_count += 1
        return f"[Error] All models exhausted. Primary: {primary_key}. Check API keys and rate limits."

    async def _direct_generate(self, config: ModelConfig, system_prompt: str,
                                user_prompt: str, temperature: float, max_tokens: int) -> str:
        if config.provider == "groq":
            return await self._groq_direct(config.model_id, system_prompt, user_prompt, temperature, max_tokens)
        elif config.provider == "openrouter":
            return await self._openrouter_direct(config.model_id, system_prompt, user_prompt, temperature, max_tokens)
        elif config.provider == "ollama":
            return await self._ollama_direct(config.model_id, system_prompt, user_prompt, temperature, max_tokens)
        else:
            return f"[Error] No direct fallback for provider: {config.provider}"

    async def _groq_direct(self, model_id: str, system_prompt: str, user_prompt: str,
                           temperature: float, max_tokens: int) -> str:
        import aiohttp
        api_key = self.api_keys["groq"]
        if not api_key:
            return "[Error] GROQ_API_KEY not set"
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model_id.replace("groq/", ""),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature, "max_tokens": max_tokens
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    return f"[Error] Groq API {resp.status}: {await resp.text()}"

    async def _openrouter_direct(self, model_id: str, system_prompt: str, user_prompt: str,
                                  temperature: float, max_tokens: int) -> str:
        import aiohttp
        api_key = self.api_keys["openrouter"]
        if not api_key:
            return "[Error] OPENROUTER_API_KEY not set"

        elapsed = time.time() - self._last_openrouter_call
        if elapsed < self._openrouter_min_interval:
            await asyncio.sleep(self._openrouter_min_interval - elapsed)

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://neo-ai.local",
            "X-Title": "Neo AI"
        }
        payload = {
            "model": model_id.replace("openrouter/", ""),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature, "max_tokens": max_tokens
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                self._last_openrouter_call = time.time()
                if resp.status == 429:
                    return "[Error] OpenRouter 429: Rate limited (20 req/min free tier)"
                elif resp.status == 404:
                    return f"[Error] OpenRouter 404: Model not found — verify slug at openrouter.ai/docs"
                elif resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    return f"[Error] OpenRouter {resp.status}: {await resp.text()}"

    async def _ollama_direct(self, model_id: str, system_prompt: str, user_prompt: str,
                              temperature: float, max_tokens: int) -> str:
        import aiohttp
        url = "http://localhost:11434/api/chat"
        model_name = model_id.replace("ollama/", "")
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens}
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("message", {}).get("content", "")
                else:
                    return f"[Error] Ollama {resp.status}: {await resp.text()}"

    def get_stats(self) -> Dict:
        return {
            "total_calls": self.call_count,
            "errors": self.error_count,
            "estimated_cost_usd": round(self.cost_estimate, 4),
            "models_available": list(self.MODELS.keys()),
            "local_llm_engine": self.use_local_llm,
            "litellm_active": LITELLM_AVAILABLE
        }