from neofarm.sensors import read, check_thresholds, update

def handle(query):
    q = query.lower()

    if "temperature" in q:
        return f"Temperature: {read('temperature')}°C"

    if "humidity" in q:
        return f"Humidity: {read('humidity')}%"

    if "water" in q:
        return f"Water level: {read('water_level')}%"

    if "feed" in q:
        return f"Feed level: {read('feed_level')}%"

    # Check thresholds automatically
    alerts = check_thresholds()
    if alerts:
        return "ALERTS: " + ", ".join(alerts)

    return None
