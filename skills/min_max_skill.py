import logging
import statistics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MinMaxSkill:
    """Min/max + descriptive statistics for a numeric list."""

    def __init__(self):
        pass

    def process(self, inputs: dict) -> dict:
        numbers = inputs.get("numbers", [])
        if not numbers:
            return {"error": "No numbers provided."}

        try:
            nums = [float(n) for n in numbers]
        except (TypeError, ValueError) as e:
            return {"error": f"Non-numeric input: {e}"}

        result = {
            "min": min(nums),
            "max": max(nums),
            "sum": sum(nums),
            "count": len(nums),
            "mean": statistics.mean(nums),
        }
        if len(nums) > 1:
            result["median"] = statistics.median(nums)
            result["stdev"] = statistics.pstdev(nums)
        logger.info(f"MinMaxSkill: min={result['min']} max={result['max']} mean={result['mean']:.3f}")
        return result