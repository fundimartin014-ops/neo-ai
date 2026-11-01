import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FibonacciSkill:
    """
    Returns the first n Fibonacci numbers or nth number.
    """

    def __init__(self):
        pass

    def process(self, inputs: dict) -> dict:
        n = int(inputs.get("n", 10))
        seq = [0, 1]
        while len(seq) < n:
            seq.append(seq[-1] + seq[-2])
        logger.info(f"FibonacciSkill({n}): {seq[:n]}")
        return {"sequence": seq[:n]}