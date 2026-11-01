from neofarm.sensors import read, check_thresholds

# Define device states
devices = {
    "fans": False,
    "heater": False,
    "water_pump": False,
    "feeder": False
}

# Safety thresholds
THRESHOLDS = {
    "temperature_high": 30,
    "temperature_low": 10,
    "water_low": 20,
    "feed_low": 20
}

def auto_action():
    alerts = check_thresholds()
    actions_taken = []

    # Temperature control
    temp = read("temperature")
    if temp > THRESHOLDS["temperature_high"] and not devices["fans"]:
        devices["fans"] = True
        actions_taken.append("Fans turned ON")
    elif temp <= THRESHOLDS["temperature_high"] and devices["fans"]:
        devices["fans"] = False
        actions_taken.append("Fans turned OFF")

    if temp < THRESHOLDS["temperature_low"] and not devices["heater"]:
        devices["heater"] = True
        actions_taken.append("Heater turned ON")
    elif temp >= THRESHOLDS["temperature_low"] and devices["heater"]:
        devices["heater"] = False
        actions_taken.append("Heater turned OFF")

    # Water control
    water = read("water_level")
    if water < THRESHOLDS["water_low"] and not devices["water_pump"]:
        devices["water_pump"] = True
        actions_taken.append("Water pump turned ON")
    elif water >= THRESHOLDS["water_low"] and devices["water_pump"]:
        devices["water_pump"] = False
        actions_taken.append("Water pump turned OFF")

    # Feed control
    feed = read("feed_level")
    if feed < THRESHOLDS["feed_low"] and not devices["feeder"]:
        devices["feeder"] = True
        actions_taken.append("Feeder turned ON")
    elif feed >= THRESHOLDS["feed_low"] and devices["feeder"]:
        devices["feeder"] = False
        actions_taken.append("Feeder turned OFF")

    return actions_taken


def auto_control_devices():
    return auto_action()
