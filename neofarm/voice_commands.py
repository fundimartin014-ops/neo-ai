from neofarm.voice_input import listen
from neofarm.languages import translate_command
from neofarm.dashboard import generate_dashboard
from neofarm.self_learning import optimize_feed
from neofarm.autonomous import run_daily_once

def handle_voice(language="en"):
    text = listen(language)
    cmd = translate_command(text)

    if "dashboard" in cmd:
        return generate_dashboard()

    if "optimize" in cmd or "feed" in cmd:
        optimize_feed()
        return "Feed optimization complete"

    if "run" in cmd or "autonomy" in cmd:
        run_daily_once()
        return "Daily autonomy executed"

    return f"I heard: {text}"
