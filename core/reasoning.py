trace_log = []

def log(step):
    trace_log.append(step)

def get_trace():
    return "\n".join(trace_log)

def clear():
    trace_log.clear()
