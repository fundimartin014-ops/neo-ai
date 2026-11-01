from core.memory import remember


def run_trainer(memory=None):
    print("[Trainer] Basic text trainer running...")
    if memory and hasattr(memory, "remember"):
        memory.remember("hello", "Hi, I am your AI trainer.")
    else:
        remember("hello", "Hi, I am your AI trainer.", source="text_trainer")
