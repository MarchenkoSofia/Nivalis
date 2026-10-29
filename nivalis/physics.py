import math
import random
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor
from .config import (
    GRAVITY, MAX_WINDOW_SNOW, MAX_ICON_SNOW, MAX_GROUND_SNOW,
    PUDDLE_DIFFUSION_RATE, PUDDLE_DRAIN_EDGE_RATE
)

class SnowLedge:
    def __init__(self, x1: int, y: int, x2: int, kind: str = "window"):
        self.x1 = int(x1)
        self.y = int(y)
        self.x2 = int(x2)
        self.width = max(1, self.x2 - self.x1)
        self.kind = kind
        self.max_capacity = (
            MAX_GROUND_SNOW if kind == "ground" else
            (MAX_ICON_SNOW if kind == "icon" else MAX_WINDOW_SNOW)
        )
        self.heights = [0.0] * self.width

    def deposit(self, gx: float, amount: float, rad: int = 8):
        lx = int(gx) - self.x1
        if 0 <= lx < self.width:
            for i in range(max(0, lx - rad), min(self.width, lx + rad + 1)):
                d = abs(i - lx) / (rad + 1)
                self.heights[i] = min(self.max_capacity, self.heights[i] + amount * (math.cos(d * math.pi * 0.5) ** 2))

    def erode(self, gx: float, rad: int, cut_power: float) -> list[tuple[float, float, float]]:
        lx = int(gx) - self.x1
        released = []
        for i in range(max(0, lx - rad), min(self.width, lx + rad)):
            if self.heights[i] > 0.1:
                d = 1.0 - (abs(i - lx) / rad)
                c = min(self.heights[i], cut_power * d)
                self.heights[i] -= c
                if c > 0.4 and random.random() < 0.6:
                    released.append((float(self.x1 + i), float(self.y), c))
        return released

    def smooth(self):
        if self.width < 3:
            return
        p = self.heights[0]
        for i in range(1, self.width - 1):
            c, n = self.heights[i], self.heights[i + 1]
            self.heights[i] = c * 0.82 + (p + n) * 0.09
            p = c


class FallingSnowParticle:
    def __init__(self, x: float, y: float, mass: float, vx: float = 0.0, vy: float = 20.0):
        self.x = x
        self.y = y
        self.mass = mass
        self.vx = vx
        self.vy = vy
        self.radius = max(1.5, min(5.5, 1.2 + mass * 0.4))
        self.alive = True

    def update(self, dt: float, wind_acc: float):
        self.vx += wind_acc * dt * 0.2
        self.vy += GRAVITY * dt * 0.35
        self.x += self.vx * dt
        self.y += self.vy * dt


class WaterDrop:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.vy = random.uniform(30.0, 70.0)
        self.mass = random.uniform(0.6, 1.4)
        self.alive = True

    def update(self, dt: float):
        self.vy += GRAVITY * dt
        self.y += self.vy * dt


class PuddleMap:
    def __init__(self, screen_w: int, ground_y: int):
        self.width = screen_w
        self.ground_y = ground_y
        self.depths = [0.0] * screen_w

    def add_water(self, x: float, amount: float):
        ix = int(x)
        if 0 <= ix < self.width:
            self.depths[ix] += amount

    def update(self, dt: float, is_freezing: bool):
        w = self.width
        if w < 3:
            return

        new_depths = list(self.depths)
        for i in range(1, w - 1):
            dh_l = (self.depths[i] - self.depths[i - 1]) * PUDDLE_DIFFUSION_RATE
            dh_r = (self.depths[i] - self.depths[i + 1]) * PUDDLE_DIFFUSION_RATE
            flow = (dh_l + dh_r) * dt * 15.0
            new_depths[i] = max(0.0, new_depths[i] - flow)
            new_depths[i - 1] += dh_l * dt * 7.5
            new_depths[i + 1] += dh_r * dt * 7.5

        new_depths[0] *= max(0.0, 1.0 - PUDDLE_DRAIN_EDGE_RATE * dt * 15.0)
        new_depths[w - 1] *= max(0.0, 1.0 - PUDDLE_DRAIN_EDGE_RATE * dt * 15.0)

        evap = (0.25 if is_freezing else 0.08) * dt
        for i in range(w):
            new_depths[i] = max(0.0, new_depths[i] - evap)

        self.depths = new_depths