import json

def train(memory=None):
    print("📚 Training from offline dictionary...")
    try:
        with open("dictionary.json", "r", encoding="utf-8") as f:
            dictionary = json.load(f)
            for word, meaning in dictionary.items():
                print(f"Learned word: {word} = {meaning}")
    except Exception as e:
        print(f"Error reading dictionary: {e}")


def run_trainer(memory=None):
    train(memory)
