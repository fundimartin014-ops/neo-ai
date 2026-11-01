import datetime

def check_events():
    now = datetime.datetime.now()

    if now.hour == 6 and now.minute == 0:
        return "Good morning Neo event"

    return None
