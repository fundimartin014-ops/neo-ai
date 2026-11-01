import uuid
import os
import sys

def get_machine_id():
    # Windows example: use motherboard + CPU
    try:
        import wmi
        c = wmi.WMI()
        board = c.Win32_BaseBoard()[0].SerialNumber
        cpu = c.Win32_Processor()[0].ProcessorId
        return board + cpu
    except:
        return str(uuid.getnode())

def check_license():
    license_file = os.path.join(sys.path[0], "license.key")
    if not os.path.exists(license_file):
        return False

    with open(license_file, "r") as f:
        licensed_id = f.read().strip()

    if licensed_id != get_machine_id():
        return False

    return True
