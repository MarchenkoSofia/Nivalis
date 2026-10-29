import os
import time
import math
import psutil
from .config import SETTINGS


class WeatherType:
    FROST_CALM = "frost_calm"
    FLUFFY_SNOW = "fluffy_snow"
    SNOWSTORM = "snowstorm"
    BLIZZARD = "blizzard"
    SLEET = "sleet"
    THAW = "thaw"


class WeatherEngine:
    def __init__(self):
        self.t0 = time.time()
        self.last_check = self.t0
        self.last_net = psutil.net_io_counters()
        self.intensity = 0.45
        self.wind = 0.1
        self.temperature = -5.0
        self.stochastic_flux = 0.0
        self.forced_thaw_until = 0.0
        self.current_type = WeatherType.FLUFFY_SNOW

    def trigger_thaw(self, duration: float = 30.0):
        self.forced_thaw_until = time.time() + duration
        self.temperature = 3.5

    def force_sync(self):
        if SETTINGS.manual_weather:
            self.temperature = SETTINGS.manual_temperature
            self.intensity = SETTINGS.manual_intensity
            self._categorize()

    def update(self):
        now = time.time()
        dt = now - self.last_check
        if dt < 1.0:
            return
        self.last_check = now
        elapsed = now - self.t0

        raw = os.urandom(4)
        r_wind = (int.from_bytes(raw[:2], "little") / 65535.0) - 0.5
        r_temp = (int.from_bytes(raw[2:], "little") / 65535.0) - 0.5
        self.stochastic_flux = self.stochastic_flux * 0.94 + r_wind * 0.25

        cpu = psutil.cpu_percent(interval=None) / 100.0
        net = psutil.net_io_counters()
        d_bytes = (net.bytes_recv - self.last_net.bytes_recv) + \
            (net.bytes_sent - self.last_net.bytes_sent)
        self.last_net = net
        net_flow = min(1.0, math.log1p(d_bytes / max(0.1, dt)) / 15.0)

        if SETTINGS.manual_weather:
            self.temperature = 3.2 if now < self.forced_thaw_until else SETTINGS.manual_temperature
            target_int = 0.04 if self.is_thawing else SETTINGS.manual_intensity
            self.intensity += (target_int - self.intensity) * 0.35
        else:
            quasi_harmonic = (
                0.38 * math.sin(elapsed * 0.0031 * math.pi) +
                0.32 * math.cos(elapsed * 0.0053 * 1.41421356) +
                0.30 * math.sin(elapsed * 0.0017 * 1.61803398)
            )

            if now < self.forced_thaw_until:
                self.temperature = 3.2
            else:
                t_wave = (
                    math.sin(elapsed * 0.0018 * math.pi) * 3.8 +
                    math.cos(elapsed * 0.0041 * 1.7320508) * 2.8 +
                    r_temp * 2.0 - 2.0 -
                    (cpu * SETTINGS.cpu_chill_gain) +
                    SETTINGS.temp_offset
                )
                self.temperature = max(-18.0, min(8.0, t_wave))

            if self.is_thawing:
                target_int = max(0.01, 0.08 - self.temperature * 0.015)
            else:
                cpu_storm_bonus = cpu * 0.35
                base = 0.25 + 0.25 * quasi_harmonic + cpu_storm_bonus + \
                    0.15 * net_flow + self.stochastic_flux
                target_int = max(0.06, min(1.0, base))

            self.intensity += (target_int - self.intensity) * 0.2

        wind_amp = 0.4 + (0.8 if self.temperature < -
                          7.0 else 0.2) + net_flow * 0.7
        target_wind = math.sin(elapsed * 0.009 * 2.236) * \
            wind_amp + r_wind * 0.4
        self.wind += (target_wind - self.wind) * 0.15

        self._categorize()

    def _categorize(self):
        t = self.temperature
        w = abs(self.wind)
        i = self.intensity

        if t > 0.3:
            self.current_type = WeatherType.THAW
        elif -0.8 <= t <= 0.3:
            self.current_type = WeatherType.SLEET
        elif t < -7.0 and w > 0.45 and i > 0.55:
            self.current_type = WeatherType.BLIZZARD
        elif t < -8.0 and w <= 0.4:
            self.current_type = WeatherType.FROST_CALM
        elif i > 0.65 or w > 0.55:
            self.current_type = WeatherType.SNOWSTORM
        else:
            self.current_type = WeatherType.FLUFFY_SNOW

    @property
    def is_thawing(self) -> bool:
        return self.temperature > 0.0

    @property
    def summary(self) -> str:
        t_str = f"{self.temperature:+.1f}°C"
        labels = {
            WeatherType.THAW: f"💧 Оттепель {t_str}",
            WeatherType.SLEET: f"🌧️ Мокрый снег {t_str}",
            WeatherType.BLIZZARD: f"🌪️ Буран {t_str}",
            WeatherType.FROST_CALM: f"✨ Мороз и штиль {t_str}",
            WeatherType.SNOWSTORM: f"🌨️ Метель {t_str}",
            WeatherType.FLUFFY_SNOW: f"❄️ Снегопад {t_str}",
        }
        return labels.get(self.current_type, f"❄️ {t_str}")
