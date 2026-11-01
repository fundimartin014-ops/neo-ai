trace = []

def log(entry):
    trace.append(entry)

def show():
    return "\n".join(trace)

def clear():
    trace.clear()
