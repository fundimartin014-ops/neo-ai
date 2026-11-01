from neofarm.autonomous import daily_autonomous_cycle
from neofarm.cloud_sync import backup_farm
from neofarm.dashboard import generate_dashboard
from neofarm.languages import set_language
from neofarm.multi_farm import create_farm, list_farms, switch_farm
from neofarm.self_learning import self_optimize


def main():
    create_farm("Alpha")
    create_farm("Beta")

    print("Available farms:", list_farms())

    switch_farm("Alpha")
    set_language("sw")

    print("=== DASHBOARD ===")
    print(generate_dashboard())

    optimizations = self_optimize()
    print("=== SELF-LEARNING OPTIMIZATIONS ===")
    print(optimizations)

    print(backup_farm("Alpha"))

    switch_farm("Beta")
    print("=== DASHBOARD BETA ===")
    print(generate_dashboard())
    optimizations = self_optimize()
    print(optimizations)
    print(backup_farm("Beta"))


if __name__ == "__main__":
    main()
