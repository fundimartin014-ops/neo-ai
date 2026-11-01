animal_sensors = {}

def log_symptom(cow_tag, symptom):
    if cow_tag not in animal_sensors:
        animal_sensors[cow_tag] = []
    animal_sensors[cow_tag].append(symptom)
    return f"Symptom logged for {cow_tag}"

def analyze(cow_tag):
    symptoms = animal_sensors.get(cow_tag, [])
    alerts = []
    for s in symptoms:
        if "cough" in s:
            alerts.append("Possible respiratory issue")
        if "diarrhea" in s:
            alerts.append("Possible digestive issue")
        if "lameness" in s:
            alerts.append("Possible injury")
    if not alerts:
        return "No significant issues detected"
    return ", ".join(alerts)
