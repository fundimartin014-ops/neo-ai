DANGEROUS_KEYWORDS = [
    "delete", "format", "shutdown", "wipe",
    "erase", "rm -rf", "kill", "hack"
]

MODES = {
    "SAFE": {"allow_tasks": False, "allow_web": False},
    "LEARN": {"allow_tasks": False, "allow_web": True},
    "EXECUTE": {"allow_tasks": True, "allow_web": True},
}

current_mode = "SAFE"

def set_mode(mode):
    global current_mode
    if mode in MODES:
        current_mode = mode

def approve(user_input):
    lowered = user_input.lower()
    for word in DANGEROUS_KEYWORDS:
        if word in lowered:
            return False, f"Blocked dangerous keyword: {word}"

    return True, "Approved"

HARDWARE_BLOCKED = ["door", "lock", "gas", "heater"]

def hardware_safe(text):
    return not any(w in text.lower() for w in HARDWARE_BLOCKED)
