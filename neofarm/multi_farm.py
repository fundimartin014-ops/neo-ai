import json
import os

FARMS_DIR = "farms_data"
CURRENT_FARM_FILE = os.path.join(FARMS_DIR, "current_farm.txt")
DEFAULT_FARM = "default"
DATA_FILES = ["milk.json", "disease.json", "sensors.json", "iot.json", "feed_ratios.json"]


def ensure_farms_dir():
    os.makedirs(FARMS_DIR, exist_ok=True)


def get_farm_path(farm_name):
    return os.path.join(FARMS_DIR, farm_name)


def create_farm(farm_name):
    ensure_farms_dir()
    path = get_farm_path(farm_name)
    os.makedirs(path, exist_ok=True)
    for file in DATA_FILES:
        fpath = os.path.join(path, file)
        if not os.path.exists(fpath):
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump({}, f)
    if not os.path.exists(CURRENT_FARM_FILE):
        with open(CURRENT_FARM_FILE, "w", encoding="utf-8") as f:
            f.write(farm_name)


def list_farms():
    ensure_farms_dir()
    farms = [
        name for name in os.listdir(FARMS_DIR)
        if os.path.isdir(get_farm_path(name))
    ]
    if not farms:
        create_farm(DEFAULT_FARM)
        farms = [DEFAULT_FARM]
    return farms


def switch_farm(farm_name):
    create_farm(farm_name)
    with open(CURRENT_FARM_FILE, "w", encoding="utf-8") as f:
        f.write(farm_name)
    return farm_name


def get_current_farm():
    ensure_farms_dir()
    if not os.path.exists(CURRENT_FARM_FILE):
        create_farm(DEFAULT_FARM)
        return DEFAULT_FARM
    with open(CURRENT_FARM_FILE, "r", encoding="utf-8") as f:
        farm_name = f.read().strip() or DEFAULT_FARM
    create_farm(farm_name)
    return farm_name


def load_farm_data(farm_name, file):
    create_farm(farm_name)
    path = os.path.join(get_farm_path(farm_name), file)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_farm_data(farm_name, file, data):
    create_farm(farm_name)
    path = os.path.join(get_farm_path(farm_name), file)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
