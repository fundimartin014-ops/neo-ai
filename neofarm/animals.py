animals = {}

def add_animal(tag, animal_type, age):
    animals[tag] = {
        "type": animal_type,
        "age": age,
        "health": "normal"
    }
    return f"{animal_type} {tag} added."

def list_animals():
    return animals
