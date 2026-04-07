import board
import busio
from adafruit_pca9685 import PCA9685

PWM_MAX = 4095

CH_R, CH_G, CH_B, CH_C, CH_W = 1, 2, 0, 4, 3

CH_MAP = {
    "R": CH_R,
    "G": CH_G,
    "B": CH_B,
    "C": CH_C,
    "W": CH_W,
}


class LedController:
    def __init__(self, frequency=1000):
        i2c = busio.I2C(board.SCL, board.SDA)
        self.pca = PCA9685(i2c)
        self.pca.frequency = frequency
        self.all_off()

    def _set_channel(self, ch: int, value: int):
        value = max(0, min(PWM_MAX, int(value)))
        self.pca.channels[ch].duty_cycle = value

    def apply_pwm(self, pwm_dict: dict):
        for key, ch in CH_MAP.items():
            self._set_channel(ch, pwm_dict.get(key, 0))

    def all_off(self):
        for ch in CH_MAP.values():
            self._set_channel(ch, 0)

    def apply_brightness_level(self, level: int):
        level = max(1, min(5, int(level)))
        duty = int(PWM_MAX * level / 5)
        for ch in CH_MAP.values():
            self._set_channel(ch, duty)