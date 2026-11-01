"""
hybrid_ui.py — Safe Hybrid UI Routes for Neo
Handles missing methods gracefully and sanitizes model IDs.
"""

import logging
from flask import jsonify, request, Response, stream_with_context
import json
import time

logger = logging.getLogger("hybrid_ui")


def register_hybrid_routes(app, model_manager=None):
    """
    Register /hybrid/* routes on the given Flask app.
    model_manager: NeoModelManager instance (optional but recommended)
    """

    @app.route("/hybrid")
    def hybrid_panel():
        """Serve the hybrid web panel HTML."""
        # If you have a hybrid.html, serve it; otherwise return JSON status
        return jsonify({
            "status": "Hybrid Merger Online",
            "endpoints": ["/hybrid/stats", "/hybrid/models", "/hybrid/stream"],
            "model_manager": bool(model_manager)
        })

    @app.route("/hybrid/stats")
    def hybrid_stats():
        """Return hybrid merger + model manager stats."""
        try:
            if not model_manager:
                return jsonify({
                    "error": "Model manager not initialized",
                    "hybrid_available": False
                }), 503

            mm_stats = model_manager.get_stats() if hasattr(model_manager, "get_stats") else {}
            hybrid_available = bool(model_manager.hybrid) if hasattr(model_manager, "hybrid") else False

            return jsonify({
                "hybrid_available": hybrid_available,
                "total_catalog": mm_stats.get("total_catalog", 0),
                "active_models": mm_stats.get("active_models", 0),
                "active_providers": mm_stats.get("active_providers", 0),
                "provider_status": mm_stats.get("provider_status", {}),
                "status": "ok"
            })
        except Exception as e:
            logger.error(f"[HybridUI] Stats error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/hybrid/models")
    def hybrid_models():
        """Return model picks for the hybrid panel."""
        try:
            if not model_manager:
                return jsonify({
                    "error": "Model manager not initialized",
                    "models": []
                }), 503

            purpose = request.args.get("purpose", "chat")
            limit = min(int(request.args.get("limit", 30)), 100)

            picks = []
            if hasattr(model_manager, "get_quick_picks"):
                picks = model_manager.get_quick_picks(purpose, limit=limit)
            else:
                # Fallback: use active_models directly
                all_models = getattr(model_manager, "active_models", [])
                picks = all_models[:limit]

            return jsonify({
                "purpose": purpose,
                "models": [
                    {
                        "id": m.get("id") or m.get("name", "unknown"),
                        "provider": m.get("provider", "unknown"),
                        "type": m.get("type", "chat"),
                        "ctx": m.get("ctx", 0),
                        "tier": m.get("tier", "unknown")
                    }
                    for m in picks
                ],
                "status": "ok"
            })
        except Exception as e:
            logger.error(f"[HybridUI] Models error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/hybrid/stream", methods=["POST"])
    def hybrid_stream():
        """Stream a hybrid query result."""
        data = request.get_json() or {}
        prompt = data.get("prompt", "").strip()
        if not prompt:
            return jsonify({"error": "prompt is required"}), 400

        strategy = data.get("strategy", "synthesis")
        pool_size = min(int(data.get("pool_size", 5)), 10)
        purpose = data.get("purpose", "chat")
        system = data.get("system")

        if not model_manager or not hasattr(model_manager, "hybrid_query"):
            return jsonify({"error": "Hybrid merger not available"}), 503

        def event_stream():
            import asyncio
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(model_manager.hybrid_query(
                    prompt=prompt,
                    purpose=purpose,
                    strategy=strategy,
                    pool_size=pool_size,
                    system=system
                ))
                # Yield metadata
                yield f"data: {json.dumps({'type': 'meta', 'strategy': result.get('strategy'), 'total': result.get('metadata', {}).get('total_models', 0)})}\n\n"
                # Yield merged output in chunks
                text = result.get("merged_output", "")
                chunk_size = 80
                for i in range(0, len(text), chunk_size):
                    yield f"data: {json.dumps({'type': 'token', 'content': text[i:i+chunk_size]})}\n\n"
                    time.sleep(0.02)
                yield f"data: {json.dumps({'type': 'done', 'latency': result.get('merge_latency', 0)})}\n\n"
            except Exception as e:
                logger.error(f"[HybridUI] Stream error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

        return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

    logger.info("[HybridUI] Routes registered: /hybrid, /hybrid/stats, /hybrid/models, /hybrid/stream")
