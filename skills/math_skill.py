import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import sympy  # type: ignore
    _HAS_SYMPY = True
except ImportError:
    _HAS_SYMPY = False

# Hard cap on expression length to prevent pathological input
_MAX_EXPR_LEN = 200


class MathSkill:
    """
    Hybrid math:
      1. sympy (symbolic: solve, diff, integrate, simplify)
      2. safe eval (arithmetic only)
    """

    def __init__(self):
        pass

    def _sympy(self, expr):
        if not _HAS_SYMPY:
            return None
        # Detect symbolic patterns
        keywords = ("solve", "diff", "integrate", "simplify", "factor", "expand")
        if not any(k in expr.lower() for k in keywords):
            return None
        try:
            # Very small DSL: "solve x**2 - 4" etc.
            parts = expr.split(maxsplit=1)
            op = parts[0].lower()
            body = parts[1] if len(parts) > 1 else ""

            if op == "solve":
                x = sympy.Symbol("x")
                return str(sympy.solve(sympy.sympify(body), x))
            if op == "diff":
                x = sympy.Symbol("x")
                return str(sympy.diff(sympy.sympify(body), x))
            if op == "integrate":
                x = sympy.Symbol("x")
                return str(sympy.integrate(sympy.sympify(body), x))
            if op == "simplify":
                return str(sympy.simplify(sympy.sympify(body)))
            if op == "factor":
                return str(sympy.factor(sympy.sympify(body)))
            if op == "expand":
                return str(sympy.expand(sympy.sympify(body)))
        except Exception as e:
            logger.debug(f"math: sympy failed: {e}")
        return None

    def _safe_eval(self, expr):
        # Reject anything that isn't pure arithmetic
        if len(expr) > _MAX_EXPR_LEN:
            return None
        if not re.fullmatch(r"[\d\s+\-*/().%]+", expr):
            return None
        try:
            # Convert % to percentage math (handled upstream, but be safe here)
            return eval(expr, {"__builtins__": {}}, {})
        except Exception as e:
            logger.debug(f"math: eval failed: {e}")
        return None

    def process(self, inputs: dict) -> dict:
        expr = inputs.get("expression", "")
        if not expr:
            return {"error": "expression is required"}
        expr = str(expr).strip()
        logger.info(f"MathSkill received: {expr}")

        # Symbolic first
        sym = self._sympy(expr)
        if sym is not None:
            return {"result": sym, "method": "sympy"}

        # Numeric eval
        val = self._safe_eval(expr)
        if val is not None:
            return {"result": val, "method": "eval"}

        return {"error": f"Could not evaluate: {expr!r}"}