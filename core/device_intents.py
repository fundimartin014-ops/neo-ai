ALLOWED_INTENTS = {
    "light_on",
    "light_off",
    "fan_on",
    "fan_off",
    "read_temperature"
}

def validate(intent):
    return intent in ALLOWED_INTENTS
