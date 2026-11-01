milk_records = {}

def add_milk(cow_tag, liters):
    if cow_tag not in milk_records:
        milk_records[cow_tag] = []
    milk_records[cow_tag].append(liters)
    return f"{liters}L recorded for {cow_tag}"

def get_milk(cow_tag):
    return milk_records.get(cow_tag, [])

def average_milk(cow_tag):
    data = milk_records.get(cow_tag, [])
    if not data:
        return 0
    return sum(data)/len(data)
