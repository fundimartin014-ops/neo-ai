import requests
from core.device_intents import validate

DEVICE_API = "http://192.168.1.50:9000/device"

def handle(query):
    q = query.lower()

    if "turn on light" in q:
        intent = "light_on"
    elif "turn off light" in q:
        intent = "light_off"
    elif "temperature" in q:
        intent = "read_temperature"
    else:
        return None

    if not validate(intent):
        return "Device action not allowed"

    r = requests.post(DEVICE_API, json={"intent": intent})
    return r.json().get("result")
