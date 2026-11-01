from neofarm.sensors import sensors
from neofarm.milk import milk_records
from neofarm.biogas import biogas_levels
from neofarm.disease import animal_sensors

def daily_summary():
    summary = []
    # Temperature / Humidity
    summary.append(f"Temperature: {sensors['temperature']}°C")
    summary.append(f"Humidity: {sensors['humidity']}%")
    # Water / Feed
    summary.append(f"Water level: {sensors['water_level']}%")
    summary.append(f"Feed level: {sensors['feed_level']}%")
    # Milk production
    for cow, records in milk_records.items():
        if records:
            avg = sum(records[-1:])/1
            summary.append(f"{cow}: Last milk: {records[-1]}L, Avg today: {avg:.1f}L")
    # Biogas
    summary.append(f"Biogas level: {biogas_levels}%")
    # Disease alerts
    for cow, symptoms in animal_sensors.items():
        if symptoms:
            summary.append(f"{cow} symptoms: {', '.join(symptoms)}")
    return "\n".join(summary)
