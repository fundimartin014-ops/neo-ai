def train(memory=None):
    print("⚖️ Training from AI rules...")
    rules = [
        "Always respond politely.",
        "Answer clearly and briefly.",
        "Only use verified information."
    ]
    for rule in rules:
        print(f"Rule learned: {rule}")


def run_trainer(memory=None):
    train(memory)
