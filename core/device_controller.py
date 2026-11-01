try:
    from flask import Flask, jsonify, request
except ImportError:
    Flask = None
    jsonify = None
    request = None

app = Flask(__name__) if Flask else None


if app:
    @app.route("/device", methods=["POST"])
    def device():
        intent = request.json.get("intent")

        if intent == "light_on":
            return jsonify({"result": "Light turned on"})

        if intent == "light_off":
            return jsonify({"result": "Light turned off"})

        if intent == "read_temperature":
            return jsonify({"result": "Temperature is 26C"})

        return jsonify({"result": "Unknown intent"})


def run_server(host="0.0.0.0", port=9000):
    if app is None:
        raise RuntimeError("Flask is required to run the device controller.")
    app.run(host=host, port=port)


if __name__ == "__main__":
    run_server()
