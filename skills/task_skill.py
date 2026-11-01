from core.tasks import run_system_command

def handle(query):
    if query.startswith("run "):
        return run_system_command(query.replace("run ", ""))
    return None
