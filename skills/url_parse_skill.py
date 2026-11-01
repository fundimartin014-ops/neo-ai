import logging
from urllib.parse import urlparse, parse_qs, unquote

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class URLParseSkill:
    """
    Parse URL into components + query params + validation.
    """

    def __init__(self):
        pass

    def process(self, inputs: dict) -> dict:
        url = inputs.get("url", "")
        if not url:
            return {"error": "url is required"}
        try:
            parts = urlparse(url)
            query = {k: v if len(v) > 1 else v[0] for k, v in parse_qs(parts.query).items()}
            is_valid = bool(parts.scheme and parts.netloc) or bool(parts.path)
            return {
                "scheme": parts.scheme,
                "netloc": parts.netloc,
                "hostname": parts.hostname,
                "port": parts.port,
                "path": parts.path,
                "path_decoded": unquote(parts.path),
                "params": parts.params,
                "query": query,
                "query_raw": parts.query,
                "fragment": parts.fragment,
                "is_valid": is_valid,
            }
        except Exception as e:
            return {"error": str(e)}