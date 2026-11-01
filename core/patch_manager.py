import shutil
import time

def backup(file_path):
    ts = int(time.time())
    backup_path = f"{file_path}.{ts}.bak"
    shutil.copy(file_path, backup_path)
    return backup_path
