import os
import time
import re
import yaml
import cv2
import pytesseract
from picamera2 import Picamera2

def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v
    
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YAML_PATH = os.path.join(BASE_DIR, "subjects.yaml")


def load_cfg():
    with open(YAML_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    settings = cfg.get("settings") or {}
    constraints = cfg.get("constraints") or {}
    keywords = cfg.get("keywords") or {}
    subjects = cfg.get("subjects") or {}
    levels = cfg.get("levels") or {}

    level = str(settings.get("level", "middle")).strip()
    warm_k = int(settings.get("warm_k", 2700))
    cool_k = int(settings.get("cool_k", 6500))
    pwm_max = int(settings.get("pwm_max", 4095))
    lux_per_pwm = float(settings.get("lux_per_pwm", 0) or 0)
    rgb_accent_ratio = float(settings.get("rgb_accent_ratio", 0.06))
    high_cct_blue_boost = float(settings.get("high_cct_blue_boost", 0.10))

    lux_min = int(constraints.get("lux_min", 300))
    lux_max = int(constraints.get("lux_max", 500))

    profile = levels.get(level) or {}
    default_conf = profile.get("default") or {
        "cct": 4400,
        "lux": 450,
        "pwm": 3000,
        "rgb": [0.0, 0.0, 0.0],
    }

    return {
    "settings": settings,
    "constraints": constraints,
    "subjects": keywords,
    "levels": levels,          
    "warm_k": warm_k,
    "cool_k": cool_k,
    "pwm_max": pwm_max,
    "lux_per_pwm": lux_per_pwm,
    "rgb_accent_ratio": rgb_accent_ratio,
    "high_cct_blue_boost": high_cct_blue_boost,
    "lux_min": lux_min,
    "lux_max": lux_max,
    }


def setup_camera():
    cam = Picamera2()
    config = cam.create_preview_configuration(
        main={"size": (640, 480), "format": "BGR888"}
    )
    cam.configure(config)
    cam.start()
    time.sleep(1.0)
    return cam


def ocr_once(cam):
    frame = cam.capture_array()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    _, th = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    text = pytesseract.image_to_string(
        th, lang="kor+eng", config="--oem 1 --psm 6"
    )
    text = re.sub(r"[^0-9A-Za-z\uac00-\ud7a3\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def match_subject(text, subjects_cfg):
    raw = text.upper()
    nospace = raw.replace(" ", "")

    for subject_key, keywords in subjects_cfg.items():
        for kw in keywords:
            k = kw.upper()
            if k in raw or k in nospace:
                return subject_key
    return None


    raw = text.upper()
    nospace = re.sub(r"\s+", "", text).upper()

    for subject_key, kw_list in (subjects_cfg or {}).items():
        for kw in kw_list:
            k = str(kw).upper()
            if k and (k in raw or k in nospace):
                return subject_key
    return None
    
def cct_to_cw_ratio(target_k, warm_k, cool_k):
    target_k = clamp(int(target_k), warm_k, cool_k)
    mw = 1_000_000 / warm_k
    mc = 1_000_000 / cool_k
    mt = 1_000_000 / target_k
    alpha = (mt - mw) / (mc - mw)
    return clamp(float(alpha), 0.0, 1.0)

def compute_brightness_pwm(conf, lux_per_pwm, lux_min, lux_max, pwm_max):
    lux = float(conf.get("lux", 0) or 0)
    pwm = int(conf.get("pwm", 0) or 0)

    lux = clamp(lux, lux_min, lux_max)
    if lux_per_pwm > 0:
        brightness = int(lux / lux_per_pwm)
    else:
        brightness = pwm

    return int(clamp(brightness, 0, pwm_max)), int(lux)

def apply_subject_calculate(
    conf,
    warm_k,
    cool_k,
    pwm_max,
    lux_per_pwm,
    lux_min,
    lux_max,
    rgb_accent_ratio,
    high_cct_blue_boost,
):
    """
    Returns:
    dict with PWM values per channel
    {
      "R": int, "G": int, "B": int, "C": int, "W": int
    }
    """
    target_k = int(conf.get("cct", 4400))
    rgb = conf.get("rgb") or [0.0, 0.0, 0.0]

    brightness_pwm, _ = compute_brightness_pwm(
        conf, lux_per_pwm, lux_min, lux_max, pwm_max
    )
    
    if target_k <= cool_k:
        alpha = cct_to_cw_ratio(target_k, warm_k, cool_k)
        w_pwm = int((1.0 - alpha) * brightness_pwm)
        c_pwm = int(alpha * brightness_pwm)
        extra_blue = 0
    else:
        w_pwm = 0
        c_pwm = brightness_pwm
        overshoot = clamp(
            (target_k - cool_k) / max(1, (target_k - warm_k)),
            0.0, 1.0
        )
        extra_blue = int(
            brightness_pwm
            * clamp(high_cct_blue_boost, 0.0, 0.25)
            * overshoot
        )
        
    ar = clamp(rgb_accent_ratio, 0.0, 0.15)
    r = int(brightness_pwm * ar * clamp(float(rgb[0]), 0.0, 1.0))
    g = int(brightness_pwm * ar * clamp(float(rgb[1]), 0.0, 1.0))
    b = int(brightness_pwm * ar * clamp(float(rgb[2]), 0.0, 1.0))
    b = int(clamp(b + extra_blue, 0, pwm_max))

    return {"R": r, "G": g, "B": b, "C": c_pwm, "W": w_pwm}