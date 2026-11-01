"""Evaluation scoring for AI answers."""
from __future__ import annotations

from typing import Any, Dict


class Evaluator:
    def evaluate(self, result: Any) -> Dict[str, Any]:
        if not isinstance(result, dict):
            raise TypeError("result must be a dict with an 'answer' key")

        answer = result.get("answer", "")
        if not isinstance(answer, str):
            raise TypeError("answer must be a string")

        confidence = 0.7  # baseline

        # Penalise control characters (except common whitespace)
        bad_chars = sum(
            1 for c in answer
            if ord(c) < 32 and c not in "\t\n\r"
        )
        if bad_chars:
            confidence = 0.2
            return {"confidence": confidence, "reason": "control characters detected"}

        # Small bonus for length, capped
        length_bonus = min(len(answer) / 500.0, 0.2)
        confidence = min(confidence + length_bonus, 1.0)

        return {"confidence": round(confidence, 2), "reason": "ok"}