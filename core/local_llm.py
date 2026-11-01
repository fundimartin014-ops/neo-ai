# =====================================================================
# core/local_llm.py
# GROQ CLOUD + OPENROUTER (Moonshot) + OLLAMA LOCAL (8GB RAM OPTIMIZED)
# =====================================================================

import re
import os
import logging
import requests
import time

logger = logging.getLogger(__name__)


class LocalLLM:
    """
    Unified LLM wrapper with tiered fallback:
    1. Groq (fastest, free tier)
    2. OpenRouter (includes Moonshot + other free models, 20 req/min limit)
    3. Ollama (offline, 8GB RAM safe)
    """

    def __init__(self, model="qwen2.5:1.5b"):
        # --- Tier 1: Groq (fast, online) ---
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.groq_model = "openai/gpt-oss-120b"
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"

        # --- Tier 2: OpenRouter (Moonshot + free models) ---
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
        self.openrouter_last_call = 0  # For rate limiting

        # --- Tier 3: Ollama (offline, 8GB RAM safe) ---
        self.ollama_model = model
        # --- FIXED: /api/generate 404s on some Ollama builds. /api/chat is the
        # modern endpoint and is what core/services/ollama_service.py already uses.
        self.ollama_url = "http://localhost:11434/api/chat"
        self.ollama_ready = self._check_ollama()
        # Alias for launcher.py, which reads `llm._ollama_ready` (leading underscore).
        self._ollama_ready = self.ollama_ready

        logger.info(
            f"[Neo] LLM: Groq={'Online' if self.groq_key else 'No key'} | "
            f"OpenRouter={'Online' if self.openrouter_key else 'No key'} | "
            f"Ollama={model if self.ollama_ready else 'Offline'}"
        )

    def _check_ollama(self):
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=2)
            models = [m["name"] for m in r.json().get("models", [])]
            return self.ollama_model in models
        except Exception:
            return False

    def _groq_generate(self, prompt: str, system: str, temperature: float,
                        max_tokens: int, model: str = None) -> str:
        """Call Groq API directly."""
        groq_model = model.replace("groq/", "") if model else self.groq_model
        r = requests.post(
            self.groq_url,
            headers={
                "Authorization": f"Bearer {self.groq_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": groq_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens
            },
            timeout=30
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()

    def _openrouter_generate(self, prompt: str, system: str, temperature: float,
                              max_tokens: int, model: str = None) -> str:
        """Call OpenRouter API with rate-limit backoff."""
        # Enforce 20 req/min = 3s minimum between calls
        elapsed = time.time() - self.openrouter_last_call
        if elapsed < 3.0:
            time.sleep(3.0 - elapsed)

        or_model = model.replace("openrouter/", "") if model else "google/gemma-4-31b-it:free"
        r = requests.post(
            self.openrouter_url,
            headers={
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://neo-ai.local",   # Required by OpenRouter
                "X-Title": "Neo AI"
            },
            json={
                "model": or_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens
            },
            timeout=45
        )
        self.openrouter_last_call = time.time()

        if r.status_code == 429:
            raise Exception("Rate limited (429) — OpenRouter free tier: 20 req/min")
        elif r.status_code == 404:
            raise Exception(f"Model not found (404): {or_model}")
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()

    def _ollama_generate(self, prompt: str, system: str, temperature: float,
                          max_tokens: int, model: str = None) -> str:
        """
        Call Ollama local API via /api/chat.

        FIXED: Previous version POSTed to /api/generate with a top-level
        "prompt" field. Some Ollama builds return 404 for that route. The
        /api/chat endpoint is the modern one and matches the OpenAI-style
        messages array. Response shape differs too:
            /api/generate → {"response": "..."}
            /api/chat     → {"message": {"role": "assistant", "content": "..."}}
        """
        ollama_model = model if (model and "/" not in model) else self.ollama_model
        r = requests.post(
            self.ollama_url,   # now http://localhost:11434/api/chat
            json={
                "model": ollama_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_ctx": 2048,
                    "num_predict": max_tokens,
                },
            },
            timeout=60
        )
        r.raise_for_status()
        data = r.json()
        # /api/chat response shape
        return data["message"]["content"].strip()

    def generate(self, prompt: str, model: str = None, temperature: float = 0.1,
                 max_tokens: int = 1024, system: str = None) -> str:
        """
        Unified generate with automatic tiered fallback.

        Args:
            prompt: The user prompt.
            model: Specific model to use. Prefix with provider:
                   'groq/llama-3.3-70b-versatile'
                   'openrouter/deepseek/deepseek-r1:free'
                   'openrouter/moonshotai/moonshot-v1-8k'
                   'qwen2.5:1.5b' (or any Ollama model, no prefix)
                   None = auto-route (Groq → OpenRouter → Ollama)
            temperature: Sampling temperature.
            max_tokens: Max tokens to generate.
            system: Custom system prompt (optional).

        Returns:
            Generated text string.
        """
        default_system = (
            "You are a strictly factual assistant. Base answers ONLY on provided context. "
            "If context contradicts training data, context wins. Keep answers brief."
        )
        system = system or default_system

        # --- Determine routing order ---
        if model and model.startswith("groq/"):
            order = [("groq", model)]
        elif model and model.startswith("openrouter/"):
            order = [("openrouter", model)]
        elif model and "/" not in model:
            # Bare model name = Ollama
            order = [("ollama", model)]
        else:
            # Auto-route: Groq → OpenRouter → Ollama
            order = [("groq", None), ("openrouter", None), ("ollama", None)]

        errors = []

        for provider, provider_model in order:
            try:
                if provider == "groq" and self.groq_key:
                    text = self._groq_generate(prompt, system, temperature, max_tokens, provider_model)
                    if text and len(text) >= 3:
                        logger.info(f"[Neo] Response from Groq ({provider_model or self.groq_model})")
                        return text

                elif provider == "openrouter" and self.openrouter_key:
                    text = self._openrouter_generate(prompt, system, temperature, max_tokens, provider_model)
                    if text and len(text) >= 3:
                        logger.info(f"[Neo] Response from OpenRouter ({provider_model or 'deepseek-r1:free'})")
                        return text

                elif provider == "ollama" and self.ollama_ready:
                    text = self._ollama_generate(prompt, system, temperature, max_tokens, provider_model)
                    if text and len(text) >= 3:
                        logger.info(f"[Neo] Response from Ollama ({provider_model or self.ollama_model})")
                        return text

            except Exception as e:
                err_msg = f"[{provider.upper()} ERROR] {e}"
                logger.warning(err_msg)
                errors.append(err_msg)
                continue

        # All tiers failed
        logger.error(f"[Neo] All LLM engines failed. Errors: {errors}")
        return "[Neo] All engines offline. Check API keys or run 'ollama serve'."