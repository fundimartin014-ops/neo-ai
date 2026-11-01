from neofarm.sensors import check_thresholds, read
from neofarm.milk import average_milk
from neofarm.biogas import check_gas
from neofarm.disease import analyze

def auto_farm_monitor():
    actions = []
    
    # Basic sensors
    for alert in check_thresholds():
        actions.append(f"ALERT: {alert}")

    # Milk check
    for cow_tag in ["COW1", "COW2"]:  # dynamically list your cows
        avg = average_milk(cow_tag)
        if avg < 5:
            actions.append(f"Milk production low for {cow_tag}: {avg}L")

    # Biogas
    gas_status = check_gas()
    actions.append(gas_status)

    # Disease
    for cow_tag in ["COW1", "COW2"]:
        disease_alerts = analyze(cow_tag)
        if disease_alerts != "No significant issues detected":
            actions.append(f"{cow_tag}: {disease_alerts}")

    return actions
