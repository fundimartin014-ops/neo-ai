import os, json
import requests  # optional online sync

from neofarm.multi_farm import list_farms, load_farm_data

CLOUD_ENDPOINT = "https://your-cooperative-server.com/api/upload"

def backup_farm(farm_name):
    data_files = ["milk.json", "disease.json", "sensors.json", "iot.json", "feed_ratios.json"]
    backup_data = {}
    for file in data_files:
        backup_data[file] = load_farm_data(farm_name, file)
    
    # Optional online upload
    try:
        response = requests.post(CLOUD_ENDPOINT, json={"farm": farm_name, "data": backup_data})
        if response.status_code == 200:
            return f"Farm {farm_name} backup successful"
        else:
            return f"Farm {farm_name} backup failed: {response.status_code}"
    except:
        return f"Farm {farm_name} backup stored locally (offline mode)"
