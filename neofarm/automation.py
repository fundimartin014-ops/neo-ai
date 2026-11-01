from neofarm.sensors import read, update, check_thresholds

def auto_actions():
    alerts = check_thresholds()
    actions = []

    # Temperature control
    temp = read("temperature")
    if temp > 30:
        actions.append("Turn on fans")
    if temp < 10:
        actions.append("Turn on heater")

    # Water / feed control
    water = read("water_level")
    feed = read("feed_level")
    if water < 20:
        actions.append("Refill water tank")
    if feed < 20:
        actions.append("Refill feed hopper")

    return actions
