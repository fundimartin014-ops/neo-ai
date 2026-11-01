import os
import subprocess
import platform


class SystemControl:

    def open_file(self, path):
        try:
            os.startfile(path)
            return f"Opened file: {path}"
        except:
            return None

    def open_app(self, name):

        try:
            if platform.system() == "Windows":
                subprocess.Popen(name)
            else:
                subprocess.Popen([name])

            return f"Opened app: {name}"
        except:
            return None

    def list_files(self, folder):
        try:
            return os.listdir(folder)
        except:
            return None