def auto_rules(event):
    if event == "temperature_high":
        return "fan_on"
    return None
