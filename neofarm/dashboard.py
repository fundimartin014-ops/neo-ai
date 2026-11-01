from neofarm.milk import milk_records
from neofarm.sensors import sensors
from neofarm.biogas import biogas_levels
from neofarm.disease_predict import predict_disease
from neofarm.iot_automation import devices
import matplotlib.pyplot as plt
import os

def generate_dashboard():
    report = []

    # Sensor summary
    report.append(f"Temperature: {sensors['temperature']}°C")
    report.append(f"Humidity: {sensors['humidity']}%")
    report.append(f"Water level: {sensors['water_level']}%")
    report.append(f"Feed level: {sensors['feed_level']}%")
    report.append(f"Biogas level: {biogas_levels}%\n")

    # Milk production trends
    for cow, records in milk_records.items():
        avg = sum(records)/len(records) if records else 0
        report.append(f"{cow}: Average milk: {avg:.1f} L")
        # Create trend graph
        if records:
            plt.plot(records, marker='o')
            plt.title(f"{cow} Milk Trend")
            plt.xlabel("Day")
            plt.ylabel("Liters")
            filename = f"{cow}_milk_trend.png"
            plt.savefig(filename)
            plt.close()
            report.append(f"Graph saved: {filename}")

    # Disease alerts
    for cow in milk_records.keys():
        alert = predict_disease(cow)
        report.append(f"{cow} Health Alert: {alert}")

    # IoT device status
    for device, state in devices.items():
        report.append(f"{device}: {'ON' if state else 'OFF'}")

    return "\n".join(report)
