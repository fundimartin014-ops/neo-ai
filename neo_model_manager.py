"""
NEO MODEL MANAGER v2.1
Replaces the old static model list with the 1000+ cloud catalog.
Integrates HybridMerger into the Neo orchestrator.
Updated: Dead model pruning from active list.
"""

import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("neo_model_manager")


class NeoModelManager:
    """
    Cloud-only model manager for NEO.
    - No Ollama, no moondream, no local models.
    - 1000+ cloud models from 20+ providers.
    - Built-in HybridMerger for ensemble outputs.
    """

    def __init__(self):
        self.catalog = None
        self.hybrid = None
        self.active_models: List[Dict] = []
        self.provider_status: Dict[str, bool] = {}

        self._load_catalog()
        self._init_hybrid()
        self._probe_providers()

    def _load_catalog(self):
        """Load the mega models catalog."""
        try:
            from neo_models_catalog import get_all_models, get_active_providers, count_models
            self.catalog = {
                "get_all": get_all_models,
                "get_active": get_active_providers,
                "count": count_models,
            }
            logger.info("[ModelManager] Mega catalog loaded.")
        except ImportError as e:
            logger.error(f"[ModelManager] Failed to load catalog: {e}")
            self.catalog = None

    def _init_hybrid(self):
        """Initialize the Hybrid Output Engine."""
        try:
            from hybrid_merger import HybridMerger
            self.hybrid = HybridMerger()
            logger.info("[ModelManager] HybridMerger initialized.")
        except ImportError as e:
            logger.error(f"[ModelManager] Failed to load HybridMerger: {e}")
            self.hybrid = None

    def _probe_providers(self):
        """Check which providers have API keys configured. Filter dead models."""
        if not self.catalog:
            return

        providers = self.catalog["get_active"]()
        for provider in providers:
            self.provider_status[provider] = True

        # Log status
        active = [p for p, ok in self.provider_status.items() if ok]
        logger.info(f"[ModelManager] Active providers: {len(active)} — {', '.join(active)}")

        # Build active model list (cloud only, no ollama/moondream/dead)
        try:
            from neo_models_catalog import DEAD_MODELS
        except ImportError:
            DEAD_MODELS = set()

        all_models = self.catalog["get_all"]()
        self.active_models = [
            m for m in all_models
            if m.get("provider") != "ollama"  # Explicitly exclude Ollama
            and "moondream" not in m.get("id", "").lower()  # Exclude moondream
            and m.get("id") not in DEAD_MODELS  # Exclude dead models
            and m.get("provider") in self.provider_status  # Only active providers
        ]

        logger.info(f"[ModelManager] Active cloud models: {len(self.active_models)}")

    def get_models_by_purpose(self, purpose: str) -> List[Dict]:
        """Get models for a specific purpose."""
        if not self.catalog:
            return []

        type_map = {
            "chat": "chat",
            "coding": "coding",
            "code": "coding",
            "reasoning": "reasoning",
            "think": "reasoning",
            "vision": "vision",
            "image": "image-gen",
            "image_gen": "image-gen",
            "image_describe": "image-describe",
            "video": "video-gen",
            "video_gen": "video-gen",
            "embed": "embedding",
            "edit": "image-edit",
        }
        mtype = type_map.get(purpose.lower(), purpose)

        from neo_models_catalog import get_models_by_type
        return [m for m in get_models_by_type(mtype) if m.get("provider") in self.provider_status]

    def get_model_by_id(self, model_id: str) -> Optional[Dict]:
        """Find a model by ID."""
        if not self.catalog:
            return None
        from neo_models_catalog import get_model_by_id
        return get_model_by_id(model_id)

    def get_quick_picks(self, purpose: str = "chat", limit: int = 10) -> List[Dict]:
        """Get recommended models for a purpose (fast + reliable)."""
        models = self.get_models_by_purpose(purpose)

        # Priority: free_fast > free > free_tier > free_credit
        tier_order = {"free_fast": 0, "free_no_key": 1, "free": 2, "free_tier": 3, "free_credit": 4}

        # Sort by tier priority, then by context length
        models.sort(key=lambda m: (tier_order.get(m.get("tier"), 99), -m.get("ctx", 0)))

        # Return top picks, one per provider for diversity
        seen_providers = set()
        picks = []
        for m in models:
            prov = m.get("provider")
            if prov not in seen_providers and len(picks) < limit:
                picks.append(m)
                seen_providers.add(prov)
        return picks

    def list_providers(self) -> List[Dict]:
        """Return provider status list for CLI / API consumption."""
        if not self.catalog:
            return []

        tier_map = {
            "groq": "free_fast",
            "openrouter": "free",
            "moonshot": "paid",
            "replicate": "paid",
            "fireworks": "free_credit",
            "deepinfra": "free_credit",
            "gemini": "free",
            "mistral": "free_credit",
            "huggingface": "free",
            "cloudflare": "free",
            "novita": "free_credit",
            "siliconflow": "free_credit",
            "hyperbolic": "free_credit",
            "friendli": "free_credit",
            "inference": "free_credit",
            "segmind": "free_credit",
            "ideogram": "free_credit",
            "clipdrop": "free_credit",
            "deepai": "free_credit",
            "pollinations": "free",
            "ai_horde": "free",
        }

        result = []
        for prov, active in self.provider_status.items():
            key_env = {
                "groq": "GROQ_API_KEY",
                "openrouter": "OPENROUTER_API_KEY",
                "moonshot": "MOONSHOT_API_KEY",
                "replicate": "REPLICATE_API_TOKEN",
                "fireworks": "FIREWORKS_API_KEY",
                "deepinfra": "DEEPINFRA_API_TOKEN",
                "gemini": "GEMINI_API_KEY",
                "mistral": "MISTRAL_API_KEY",
                "huggingface": "HF_TOKEN",
                "cloudflare": "CF_API_TOKEN",
                "novita": "NOVITA_API_KEY",
                "siliconflow": "SILICONFLOW_API_KEY",
                "hyperbolic": "HYPERBOLIC_API_KEY",
                "friendli": "FRIENDLI_API_KEY",
                "inference": "INFERENCE_API_KEY",
                "segmind": "SEGMIND_API_KEY",
                "ideogram": "IDEOGRAM_API_KEY",
                "clipdrop": "CLIPDROP_API_KEY",
                "deepai": "DEEPAI_API_KEY",
                "ai_horde": "AI_HORDE_API_KEY",
            }.get(prov, f"{prov.upper()}_API_KEY")

            result.append({
                "name": prov,
                "has_key": active and bool(os.getenv(key_env)),
                "tier": tier_map.get(prov, "unknown"),
                "key_env": key_env,
                "active": active,
            })
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Return model manager stats."""
        if not self.catalog:
            return {"error": "Catalog not loaded"}

        stats = self.catalog["count"]()
        return {
            "total_catalog": stats["total"],
            "active_models": len(self.active_models),
            "active_providers": len(self.provider_status),
            "provider_status": self.provider_status,
            "by_type": stats["by_type"],
            "by_tier": stats["by_tier"],
        }

    async def hybrid_query(
        self,
        prompt: str,
        purpose: str = "chat",
        strategy: str = "synthesis",
        pool_size: int = 5,
        system: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run a hybrid query: multiple models in parallel, merged output.
        """
        if not self.hybrid:
            return {"error": "HybridMerger not available"}

        auto_pool = purpose.lower().replace(" ", "_")

        result = await self.hybrid.hybrid_generate(
            prompt=prompt,
            auto_pool=auto_pool,
            strategy=strategy,
            pool_size=pool_size,
            system=system,
        )

        return {
            "merged_output": result.merged_output,
            "strategy": result.strategy,
            "prompt": result.prompt,
            "outputs": [
                {
                    "model": o.model_id,
                    "provider": o.provider,
                    "output": o.output,
                    "latency": o.latency,
                    "tokens": o.tokens_used,
                    "error": o.error,
                }
                for o in result.outputs
            ],
            "metadata": result.metadata,
            "merge_latency": result.merge_latency,
        }

    def list_all_models(self, limit: int = 50) -> List[Dict]:
        """List active models with key info."""
        return [
            {
                "id": m["id"],
                "name": m.get("name", m["id"]),
                "provider": m.get("provider"),
                "type": m.get("type"),
                "ctx": m.get("ctx"),
                "tier": m.get("tier"),
                "family": m.get("family"),
            }
            for m in self.active_models[:limit]
        ]

    def print_active_models(self):
        """Print a formatted table of active models."""
        models = self.active_models[:30]
        print("\n" + "=" * 80)
        print(f"  ACTIVE CLOUD MODELS (showing {len(models)} of {len(self.active_models)})")
        print("=" * 80)
        print(f"  {'ID':<45} {'Provider':<15} {'Type':<12} {'Ctx':<8} {'Tier':<15}")
        print("-" * 80)
        for m in models:
            print(f"  {m['id']:<45} {m.get('provider','?'):<15} {m.get('type','?'):<12} {m.get('ctx',0):<8} {m.get('tier','?'):<15}")
        print("=" * 80)


# ── Singleton instance ──
_model_manager: Optional[NeoModelManager] = None

def get_model_manager() -> NeoModelManager:
    global _model_manager
    if _model_manager is None:
        _model_manager = NeoModelManager()
    return _model_manager


# ── Standalone test ──
if __name__ == "__main__":
    import asyncio

    mm = NeoModelManager()
    mm.print_active_models()

    stats = mm.get_stats()
    print(f"\nStats: {json.dumps(stats, indent=2)[:1000]}...")