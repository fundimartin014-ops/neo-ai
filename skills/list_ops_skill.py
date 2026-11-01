import logging
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ListOpsSkill:
    """
    List operations:
      sort, reverse, unique, shuffle, chunk, flatten, sum, mean
    """

    def __init__(self):
        pass

    def _flatten(self, lst):
        out = []
        for x in lst:
            if isinstance(x, list):
                out.extend(self._flatten(x))
            else:
                out.append(x)
        return out

    def process(self, inputs: dict) -> dict:
        data = inputs.get("data", [])
        op = str(inputs.get("operation", "sort")).lower()

        if not isinstance(data, list):
            return {"error": "input 'data' must be a list"}

        try:
            if op == "sort":
                return {"result": sorted(data)}
            if op == "reverse":
                return {"result": data[::-1]}
            if op == "unique":
                seen = []
                for x in data:
                    if x not in seen:
                        seen.append(x)
                return {"result": seen}
            if op == "shuffle":
                copy = list(data)
                random.shuffle(copy)
                return {"result": copy}
            if op == "chunk":
                size = max(1, int(inputs.get("size", 3)))
                return {"result": [data[i:i + size] for i in range(0, len(data), size)]}
            if op == "flatten":
                return {"result": self._flatten(data)}
            if op == "sum":
                return {"result": sum(x for x in data if isinstance(x, (int, float)))}
            if op == "mean":
                nums = [x for x in data if isinstance(x, (int, float))]
                return {"result": sum(nums) / len(nums) if nums else 0}
            return {"error": f"Unknown operation: {op}"}
        except Exception as e:
            logger.error(f"ListOpsSkill error: {e}")
            return {"error": str(e)}