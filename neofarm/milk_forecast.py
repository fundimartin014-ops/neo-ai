from neofarm.milk import milk_records
from neofarm.sensors import sensors

# Example: simple moving average forecast
def forecast_milk(cow_tag, days=3):
    records = milk_records.get(cow_tag, [])
    if len(records) < days:
        return f"Not enough data for {cow_tag} to forecast"
    
    avg_recent = sum(records[-days:]) / days
    # Adjust based on temperature: optimal 20-25°C
    temp = sensors["temperature"]
    if temp > 28:
        avg_recent *= 0.9  # reduce expected milk
    elif temp < 15:
        avg_recent *= 0.85
    return round(avg_recent, 2)
