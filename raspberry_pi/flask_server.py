from flask import Flask, request, jsonify

def create_app(led, shared_state):
    app = Flask(__name__)

    # ================= Ping =================
    @app.route("/ping", methods=["GET"])
    def ping():
        return jsonify({
            "status": "alive",
            "light_level": shared_state.get("light_level"),
            "education_level": shared_state.get("education_level"),
        }), 200

    # ================= LED ON / OFF =================
    @app.route("/led", methods=["POST"])
    def led_control():
        data = request.get_json() or {}
        state = data.get("state")

        if state == "on":
            led.apply_brightness_level(
                shared_state.get("light_level", 3)
            )
            shared_state["led_on"] = True
            print("[FLASK] LED ON", flush=True)

        elif state == "off":
            led.all_off()
            shared_state["led_on"] = False
            print("[FLASK] LED OFF", flush=True)

        else:
            return jsonify({"error": "invalid state"}), 400

        return jsonify({"result": "ok"}), 200

    # ================= Brightness =================
    @app.route("/brightness", methods=["POST"])
    def set_brightness():
        data = request.get_json() or {}
        level = data.get("light_level")

        try:
            level = int(level)
        except Exception:
            return jsonify({"error": "invalid light_level"}), 400

        if level < 1 or level > 5:
            return jsonify({"error": "light_level must be 1~5"}), 400

        shared_state["light_level"] = level

        if shared_state.get("led_on"):
            led.apply_brightness_level(level)

        print("[FLASK] light_level set to", level, flush=True)

        return jsonify({"light_level": level}), 200

    # ================= Education Level =================
    @app.route("/set_level", methods=["POST"])
    def set_education_level():
        data = request.get_json() or {}
        level = data.get("education_level")

        if level not in ["elementary", "middle", "high"]:
            return jsonify({"error": "invalid education_level"}), 400

        shared_state["education_level"] = level

        print("[FLASK] education_level set to", level, flush=True)

        return jsonify({"education_level": level}), 200

    return app