import json

def train(memory=None):
    print("🔁 Training from user feedback logs...")
    try:
        with open("feedback.json", "r", encoding="utf-8") as f:
            feedback = json.load(f)
            for item in feedback:
                print(f"Correction learned: {item['wrong']} → {item['correct']}")
    except Exception as e:
        print(f"Error reading feedback: {e}")


def run_trainer(memory=None):
    train(memory)
