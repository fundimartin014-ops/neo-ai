biogas_levels = 0  # percentage of expected gas

def update_gas(level):
    global biogas_levels
    biogas_levels = level
    return f"Biogas level updated: {level}%"

def check_gas():
    if biogas_levels < 30:
        return "ALERT: Biogas too low. Check digester."
    return f"Biogas level: {biogas_levels}%"
