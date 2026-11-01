import os
import subprocess
import webbrowser

class SystemAgent:

    def __init__(self):
        self.allowed_paths = ["C:\\Users\\fundi\\Documents"]
        self.allowed_apps = ["notepad", "calc"]

    def open_file(self, path):
        if not any(path.startswith(p) for p in self.allowed_paths):
            return "Access denied."

        try:
            os.startfile(path)
            return f"Opened {path}"
        except Exception as e:
            return str(e)

    def open_url(self, url):
        try:
            webbrowser.open(url)
            return f"Opened {url}"
        except Exception as e:
            return str(e)

    def run_command(self, cmd):
        safe_commands = ["dir", "echo", "whoami"]

        if not any(cmd.startswith(c) for c in safe_commands):
            return "Command blocked."

        try:
            return subprocess.check_output(cmd, shell=True).decode()
        except Exception as e:
            return str(e)