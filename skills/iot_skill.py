from neofarm.iot_automation import auto_action

def handle(query):
    q = query.lower()
    if "check devices" in q:
        actions = auto_action()
        if actions:
            return "Actions taken:\n" + "\n".join(actions)
        return "All devices are within normal ranges"
    return None
