import ast

class CodeValidator:

    def is_safe(self, code):

        try:
            tree = ast.parse(code)
        except:
            return False

        # 🔒 forbid dangerous ops
        banned = ["exec", "eval", "__import__", "os.system"]

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if hasattr(node.func, "id") and node.func.id in banned:
                    return False

        return True