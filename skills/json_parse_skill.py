import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JSONParseSkill:
    """
    Parse + optionally query with a dotted path.
    Inputs:
      text  (required: JSON string)
      path  (optional: "users.0.name")
    """

    def __init__(self):
        pass

    def _walk(self, obj, path):
        cur = obj
        for part in path.split("."):
            if isinstance(cur, list):
                try:
                    cur = cur[int(part)]
                except (ValueError, IndexError):
                    return None
            elif isinstance(cur, dict):
                if part not in cur:
                    return None
                cur = cur[part]
            else:
                return None
        return cur

    def process(self, inputs: dict) -> dict:
        text = inputs.get("text", "")
        if not text:
            return {"error": "text is required"}
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"JSONParseSkill parse error: {e}")
            return {"error": f"Invalid JSON: {e}"}

        result = {"parsed": obj, "pretty": json.dumps(obj, indent=2)}
        path = inputs.get("path")
        if path:
            sub = self._walk(obj, str(path))
            result["query"] = sub
        return result