def temperature_action(temp):
    if temp > 30:
        return "Temperature high. Recommend turning on fans."
    if temp < 10:
        return "Temperature low. Consider warming."
    return "Temperature normal."
