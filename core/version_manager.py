import os
import shutil
import time

class VersionManager:

    def __init__(self, base_dir="versions"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def snapshot(self, file_path):
        if not os.path.exists(file_path):
            return None
        ts = int(time.time())
        name = os.path.basename(file_path)
        dest = os.path.join(self.base_dir, f"{name}.{ts}.bak")
        shutil.copy2(file_path, dest)
        return dest

    def rollback(self, file_path):
        name = os.path.basename(file_path)
        backups = sorted(
            [f for f in os.listdir(self.base_dir) if f.startswith(name + ".")],
            reverse=True
        )
        if not backups:
            return False
        latest = os.path.join(self.base_dir, backups[0])
        shutil.copy2(latest, file_path)
        return True