import os
import subprocess

def run_system_command(command):
    """Run OS-level command."""
    try:
        output = subprocess.check_output(command, shell=True, text=True)
        return output.strip()
    except Exception as e:
        return str(e)

def control_iot(device, action):
    """Stub: implement IoT control."""
    return f"[IoT] {device} action {action} executed."
