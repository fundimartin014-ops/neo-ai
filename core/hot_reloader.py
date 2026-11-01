import importlib
import sys

class HotReloader:

    def reload_module(self, module_name):
        try:
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                __import__(module_name)
            return True
        except Exception as e:
            print("[Reload Error]", e)
            return False