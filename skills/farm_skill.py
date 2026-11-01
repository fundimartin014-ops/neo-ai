from neofarm.animals import add_animal
from neofarm.health import check

def handle(query):
    q = query.lower()

    if "add cow" in q:
        return add_animal("COW1", "cow", 3)

    if "symptom" in q:
        return check(q)

    return None
