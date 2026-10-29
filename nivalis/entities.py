import math
import random
from PyQt6.QtCore import QRectF

class PineTree:
    def __init__(self, x: float, base_y: float):
        self.x = x
        self.base_y = base_y
        self.growth = 0.03
        self.max_h = random.uniform(115.0, 160.0)
        self.tiers = random.choice([4, 5])
        self.seed = random.randint(10, 9999)
        self.lights_active = False
        self.cut_ratio = 0.0
        self.is_falling = False
        self.fall_angle = 0.0
        self.fall_speed = 0.0
        self.fall_dir = random.choice([-1, 1])
        self.alpha = 1.0

    def step(self, dt: float, rate_mult: float, thaw: bool):
        if self.is_falling:
            self.fall_speed += 5.0 * dt
            self.fall_angle += self.fall_speed * self.fall_dir * dt
            if abs(self.fall_angle) > 1.3:
                self.alpha -= 0.8 * dt
            return

        if not thaw and self.growth < 1.0:
            self.growth = min(1.0, self.growth + 0.00065 * dt * rate_mult)
            if self.growth >= 0.98:
                self.lights_active = True


class SantaSleigh:
    def __init__(self, screen_w: int, screen_h: int):
        self.direction = random.choice([-1, 1])
        self.x = -240.0 if self.direction == 1 else screen_w + 240.0
        self.y = random.uniform(80.0, max(120.0, screen_h * 0.28))
        self.base_y = self.y
        self.vx = self.direction * random.uniform(150.0, 210.0)
        self.vy = 0.0
        self.phase = random.uniform(0.0, math.tau)
        self.downed = False
        self.angle = 0.0
        self.ang_vel = 0.0
        self.active = True

    def bounding_box(self) -> QRectF:
        return QRectF(self.x - 110, self.y - 36, 220, 72)

    def strike(self, impulse_x: float, impulse_y: float):
        if self.downed:
            return
        self.downed = True
        self.vx = self.vx * 0.35 + impulse_x * 0.3
        self.vy = min(-120.0, impulse_y * 0.3 - 100.0)
        self.ang_vel = (1 if self.vx >= 0 else -1) * random.uniform(5.0, 8.5)

    def step(self, dt: float, screen_w: int, screen_h: int) -> bool:
        if not self.downed:
            self.phase += dt * 3.0
            self.x += self.vx * dt
            self.y = self.base_y + math.sin(self.phase) * 12.0
            if (self.direction == 1 and self.x > screen_w + 280) or (self.direction == -1 and self.x < -280):
                self.active = False
            return False
        else:
            self.vy += 600.0 * dt
            self.x += self.vx * dt
            self.y += self.vy * dt
            self.angle += self.ang_vel * dt
            if self.y >= screen_h - 28:
                self.active = False
                return True
            return False