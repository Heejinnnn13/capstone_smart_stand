# -*- coding: utf-8 -*-
import threading
import time
import os

from raspberry_pi.led_controller import LedController
from flask_server import create_app
from ocr_subject_led import (
    load_cfg,
    setup_camera,
    ocr_once,
    match_subject,
    apply_subject_calculate,
)

from werkzeug.serving import make_server

YAML_PATH = os.path.join(os.path.dirname(__file__), "subjects.yaml")


class FlaskThread(threading.Thread):
    def __init__(self, app, host="0.0.0.0", port=5000):
        super().__init__(daemon=True)
        self.server = make_server(host, port, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


def ocr_loop(led, shared_state, stop_event):
    cfg = load_cfg()
    last_mtime = os.path.getmtime(YAML_PATH)

    cam = setup_camera()

    current_subject = None
    last_level = shared_state.get("education_level", "middle")

    print("[SYSTEM] OCR loop started", flush=True)

    while not stop_event.is_set():

        
        edu_level = shared_state.get("education_level", "middle")

        try:
            mtime = os.path.getmtime(YAML_PATH)
            if mtime != last_mtime:
                cfg = load_cfg()
                last_mtime = mtime
                current_subject = None
                print("[SYSTEM] YAML reloaded", flush=True)
        except Exception as e:
            print("[ERROR] YAML reload failed:", e, flush=True)

        if edu_level != last_level:
            print(
                f"[SYSTEM] education_level changed {last_level} -> {edu_level}, reset subject",
                flush=True,
            )
            current_subject = None
            last_level = edu_level

        text = ocr_once(cam)
        subject_key = match_subject(text, cfg["subjects"])

        print("[OCR TEXT]", repr(text), flush=True)
        print("[OCR KEY ]", subject_key, flush=True)

        if subject_key and subject_key != current_subject:
            profile_by_level = cfg["levels"].get(edu_level, {})

            if subject_key not in profile_by_level:
                print(
                    f"[OCR] subject '{subject_key}' not defined for level '{edu_level}', keep previous LED",
                    flush=True,
                )
                time.sleep(1)
                continue

            conf = profile_by_level[subject_key]

            pwm = apply_subject_calculate(
                conf,
                cfg["warm_k"],
                cfg["cool_k"],
                cfg["pwm_max"],
                cfg["lux_per_pwm"],
                cfg["lux_min"],
                cfg["lux_max"],
                cfg["rgb_accent_ratio"],
                cfg["high_cct_blue_boost"],
            )

            led.apply_pwm(pwm)
            shared_state["last_subject"] = subject_key
            current_subject = subject_key

            print(
                f"[LED] APPLY subject={subject_key} level={edu_level}",
                flush=True,
            )

        time.sleep(1)
        
def main():
    led = LedController()

    shared_state = {
        "light_level": 3,
        "education_level": "middle",
        "last_subject": None,
        "led_on": False,
    }

    # Flask 
    app = create_app(led, shared_state)
    flask_thread = FlaskThread(app)
    flask_thread.start()

    # OCR 
    stop_event = threading.Event()
    threading.Thread(
        target=ocr_loop,
        args=(led, shared_state, stop_event),
        daemon=True,
    ).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_event.set()
        flask_thread.shutdown()
        led.all_off()
        print("[SYSTEM] Shutdown complete", flush=True)


if __name__ == "__main__":
    main()