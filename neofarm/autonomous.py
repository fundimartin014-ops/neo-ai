import time

try:
    import schedule
except ImportError:
    schedule = None

from neofarm.self_learning import self_optimize
from neofarm.dashboard import generate_dashboard
from neofarm.iot_automation import auto_control_devices
from neofarm.multi_farm import list_farms, switch_farm
from neofarm.cloud_sync import backup_farm


def daily_autonomous_cycle():
    farms = list_farms()
    for farm in farms:
        switch_farm(farm)
        self_optimize()
        auto_control_devices()
        dashboard = generate_dashboard()
        with open(f"{farm}_daily_report.txt", "w", encoding="utf-8") as f:
            f.write(dashboard)
        backup_farm(farm)
        print(f"[NeoFarm] Daily autonomous cycle complete for {farm}")


def run_daily_once():
    daily_autonomous_cycle()


def run_scheduler():
    if schedule is None:
        raise RuntimeError("The schedule package is required to run the NeoFarm scheduler.")
    schedule.every().day.at("05:00").do(daily_autonomous_cycle)
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    run_scheduler()
