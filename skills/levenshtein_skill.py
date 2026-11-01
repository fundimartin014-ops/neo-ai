import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LevenshteinSkill:
    """
    Edit distance + similarity metrics:
      - levenshtein (iterative DP)
      - ratio (difflib)
      - hamming (equal-length only)
    """

    def __init__(self):
        pass

    @staticmethod
    def _levenshtein(a, b):
        if a == b:
            return 0
        if not a:
            return len(b)
        if not b:
            return len(a)
        if len(a) < len(b):
            a, b = b, a
        previous = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            current = [i]
            for j, cb in enumerate(b, 1):
                insert = current[j - 1] + 1
                delete = previous[j] + 1
                substitute = previous[j - 1] + (ca != cb)
                current.append(min(insert, delete, substitute))
            previous = current
        return previous[-1]

    @staticmethod
    def _hamming(a, b):
        if len(a) != len(b):
            return None
        return sum(c1 != c2 for c1, c2 in zip(a, b))

    def process(self, inputs: dict) -> dict:
        a = inputs.get("a", "")
        b = inputs.get("b", "")
        lev = self._levenshtein(a, b)
        ham = self._hamming(a, b)

        # Similarity ratio via difflib
        import difflib
        ratio = round(difflib.SequenceMatcher(None, a, b).ratio(), 4)

        logger.info(f"LevenshteinSkill: lev={lev}, hamming={ham}, ratio={ratio}")
        return {
            "distance": lev,
            "hamming": ham,
            "similarity": ratio,
        }