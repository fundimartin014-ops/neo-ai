import requests

from neofarm.multi_farm import get_current_farm, load_farm_data, save_farm_data

ESP32_URL = "http://192.168.4.1"

sensors = {
    "temperature": 24,
    "humidity": 60,
    "water_level": 75,
    "feed_level": 70,
}

THRESHOLDS = {
    "temperature_high": 30,
    "temperature_low": 10,
    "water_low": 20,
    "feed_low": 20,
}


def read_sensors():
    farm = get_current_farm()
    try:
        response = requests.get(ESP32_URL, timeout=3)
        data = response.json()
        store = load_farm_data(farm, "sensors.json")
        store.setdefault("readings", []).append(data)
        store["latest"] = data
        save_farm_data(farm, "sensors.json", store)
        sensors.update(data)
        return data
    except Exception:
        return {"error": "Sensor offline"}


def read(name):
    return sensors.get(name, 0)


def update(name, value):
    sensors[name] = value
    farm = get_current_farm()
    store = load_farm_data(farm, "sensors.json")
    store.setdefault("latest", {})[name] = value
    save_farm_data(farm, "sensors.json", store)
    return sensors


def check_thresholds():
    alerts = []
    temp = read("temperature")
    water = read("water_level")
    feed = read("feed_level")

    if temp > THRESHOLDS["temperature_high"]:
        alerts.append("Temperature too high")
    if temp < THRESHOLDS["temperature_low"]:
        alerts.append("Temperature too low")
    if water < THRESHOLDS["water_low"]:
        alerts.append("Water level low")
    if feed < THRESHOLDS["feed_low"]:
        alerts.append("Feed level low")
    return alerts
