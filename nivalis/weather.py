import os
import time
import math
import psutil

class WeatherEngine:
    def __init__(self):
        self.t0 = time.time()
        self.last_check = self.t0
        self.last_net = psutil.net_io_counters()
        self.intensity = 0.4
        self.wind = 0.1
        self.temperature = -4.0
        self.stochastic_flux = 0.0
        self.forced_thaw_until = 0.0

    def trigger_thaw(self, duration: float = 30.0):
        self.forced_thaw_until = time.time() + duration
        self.temperature = 3.5

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
        d_bytes = (net.bytes_recv - self.last_net.bytes_recv) + (net.bytes_sent - self.last_net.bytes_sent)
        self.last_net = net
        net_flow = min(1.0, math.log1p(d_bytes / max(0.1, dt)) / 15.0)

        quasi_harmonic = (
            0.40 * math.sin(elapsed * 0.0031 * math.pi) +
            0.35 * math.cos(elapsed * 0.0053 * 1.41421356) +
            0.25 * math.sin(elapsed * 0.0017 * 1.61803398)
        )

        if now < self.forced_thaw_until:
            self.temperature = 3.2
        else:
            t_wave = (
                math.sin(elapsed * 0.0018 * math.pi) * 4.2 +
                math.cos(elapsed * 0.0041 * 1.7320508) * 3.1 +
                r_temp * 2.5 - 1.8
            )
            self.temperature = max(-12.0, min(5.0, t_wave))

        if self.is_thawing:
            target_int = max(0.01, 0.08 - self.temperature * 0.015)
        else:
            base = 0.25 + 0.3 * quasi_harmonic + 0.25 * cpu + 0.2 * net_flow + self.stochastic_flux
            target_int = max(0.05, min(1.0, base))

        self.intensity += (target_int - self.intensity) * 0.2
        target_wind = math.sin(elapsed * 0.008 * 2.2360679) * (0.3 + net_flow * 0.8) + r_wind * 0.3
        self.wind += (target_wind - self.wind) * 0.15

    @property
    def is_thawing(self) -> bool:
        return self.temperature > 0.0

    @property
    def summary(self) -> str:
        if self.is_thawing:
            return f"💧 Оттепель +{self.temperature:.1f}°C"
        pct = int(self.intensity * 100)
        prefix = "🌨️ Метель" if pct > 75 else ("❄️ Снег" if pct > 35 else "✨ Легкий снег")
        return f"{prefix} {self.temperature:.1f}°C"