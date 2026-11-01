feeding_plan = {}

def set_feeding(tag, feed, amount):
    feeding_plan[tag] = {
        "feed": feed,
        "amount": amount
    }
    return f"Feeding set for {tag}"

def get_feeding(tag):
    return feeding_plan.get(tag, "No feeding plan")
