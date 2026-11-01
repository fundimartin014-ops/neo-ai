import importlib.util
import os

class RuntimeEvolver:

    def __init__(self, llm, validator, version_manager, reloader):
        self.llm = llm
        self.validator = validator
        self.version_manager = version_manager
        self.reloader = reloader

    def improve_module(self, module_path, module_name):

        if not os.path.exists(module_path):
            return False

        with open(module_path, "r", encoding="utf-8") as f:
            code = f.read()

        prompt = f"""
Improve this Python module for robustness, performance, and clarity.
Return ONLY valid Python code.

{code}
"""

        try:
            improved = self.llm.generate(prompt)
        except:
            return False

        if not improved or not self.validator.is_safe(improved):
            print("[Neo] Unsafe improvement rejected")
            return False

        # snapshot
        backup = self.version_manager.snapshot(module_path)

        # write new code
        try:
            with open(module_path, "w", encoding="utf-8") as f:
                f.write(improved)
        except Exception as e:
            print("[Write Error]", e)
            return False

        # hot reload
        if not self.reloader.reload_module(module_name):
            print("[Neo] Reload failed → rolling back")
            self.version_manager.rollback(module_path)
            return False

        print(f"[Neo] Module upgraded safely: {module_name}")
        return True
    