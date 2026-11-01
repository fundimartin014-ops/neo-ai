def train(memory=None):
    print("👨‍💻 Training from source code...")
    try:
        with open("example_code.py", "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                if line.strip():
                    print(f"Code pattern noted: {line.strip()}")
    except Exception as e:
        print(f"Error reading codebase: {e}")


def run_trainer(memory=None):
    train(memory)
