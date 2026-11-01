import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FlattenDictSkill:
    """
    Flattens nested dictionaries into a single level.
    """

    def __init__(self):
        pass

    def _flatten(self, d, parent_key='', sep='.'):
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    def process(self, inputs: dict) -> dict:
        data = inputs.get("data", {})
        if not isinstance(data, dict):
            logger.error("FlattenDictSkill: input 'data' not a dict!")
            return {"error": "Not a dictionary."}
        flat = self._flatten(data)
        logger.info(f"FlattenDictSkill result: {flat}")
        return {"result": flat}