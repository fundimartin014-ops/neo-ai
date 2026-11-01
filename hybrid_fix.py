"""hybrid_fix.py — fix env_key/env key-name mismatch + verbose error capture."""
import ast, re
from pathlib import Path

p = Path("hybrid_merger.py")
src = p.read_text(encoding="utf-8")
changes = []

# Fix 1: read both keys
if 'model_config.get("env_key")' in src:
    src = src.replace(
        'env_key = model_config.get("env_key")',
        'env_key = model_config.get("env_key") or model_config.get("env")',
    )
    changes.append("env_key → env_key or env")

# Fix 2: add base_url fallback from provider
anchor = '        url = f"{base_url}/chat/completions"'
if anchor in src and "base_url_fallback" not in src:
    fallback = '''        # Fallback: infer base_url from provider if missing
        if not base_url:
            _provider_urls = {
                "groq": "https://api.groq.com/openai/v1",
                "openrouter": "https://openrouter.ai/api/v1",
                "deepinfra": "https://api.deepinfra.com/v1/openai",
                "mistral": "https://api.mistral.ai/v1",
                "fireworks": "https://api.fireworks.ai/inference/v1",
                "novita": "https://api.novita.ai/v3/openai",
                "hyperbolic": "https://api.hyperbolic.xyz/v1",
                "siliconflow": "https://api.siliconflow.cn/v1",
                "friendli": "https://api.friendli.ai/serverless/v1",
            }
            base_url = _provider_urls.get(provider, "")
'''
    src = src.replace(anchor, fallback + anchor, 1)
    changes.append("base_url fallback added")

# Fix 3: add errors dict to metadata so launcher debug can print them
old_meta = '''            metadata={
                "total_models": len(resolved_models),
                "successful": len([o for o in normalized if not o.error]),
                "failed": len([o for o in normalized if o.error]),
                "total_latency": time.time() - start,
                "cache_key": cache_key,
            }'''
new_meta = '''            metadata={
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
            }'''
if old_meta in src:
    src = src.replace(old_meta, new_meta, 1)
    changes.append("errors + successes captured in metadata")

if not changes:
    print("No changes needed (already patched?)")
else:
    ast.parse(src)
    p.write_text(src, encoding="utf-8")
    print("Patched hybrid_merger.py:")
    for c in changes:
        print(f"  • {c}")