from neofarm.disease_predict import predict_disease
from neofarm.milk import milk_records
from neofarm.sensors import read

def farm_health_scan():
    report = []
    cows = list(milk_records.keys())  # dynamically get cow list
    for cow in cows:
        health_alert = predict_disease(cow)
        report.append(f"{cow}: {health_alert}")
    return report
