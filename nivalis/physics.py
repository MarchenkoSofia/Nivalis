import math
import random
from .config import (
    GRAVITY, MAX_WINDOW_SNOW, MAX_ICON_SNOW,
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
            10000.0 if kind == "ground" else
            (MAX_ICON_SNOW if kind == "icon" else MAX_WINDOW_SNOW)
        )
        self.max_slope = 0.04 if kind == "ground" else (
            0.68 if kind == "icon" else 0.56)
        self.heights = [0.0] * self.width
        self.left_spill = 0.0
        self.right_spill = 0.0

    def hill_limit(self, idx: int) -> float:
        if self.kind == "ground":
            return self.max_capacity
        edge_dist = min(idx, self.width - 1 - idx)
        return min(self.max_capacity, edge_dist * self.max_slope * 1.35)

    def deposit(self, gx: float, amount: float, rad: int = 8):
        lx = int(gx) - self.x1
        if not (0 <= lx < self.width):
            return

        r_start = max(0, lx - rad)
        r_end = min(self.width - 1, lx + rad)
        for i in range(r_start, r_end + 1):
            d = abs(i - lx) / (rad + 1)
            add = amount * (math.cos(d * math.pi * 0.5) ** 2)
            limit = self.hill_limit(i)
            new_h = self.heights[i] + add
            if new_h > limit:
                excess = new_h - limit
                self.heights[i] = limit
                if self.kind != "ground":
                    if i < self.width * 0.5:
                        self.left_spill += excess * 0.45
                    else:
                        self.right_spill += excess * 0.45
            else:
                self.heights[i] = new_h

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

    def apply_window_motion(self, dx: int, dy: int) -> list[tuple[float, float, float, float, float]]:
        spilled = []
        self.x1 += dx
        self.x2 += dx
        self.y += dy

        shift = -int(round(dx * 0.7))
        if shift != 0 and self.width > 2:
            new_h = [0.0] * self.width
            for i in range(self.width):
                h = self.heights[i]
                if h <= 0.05:
                    continue
                ni = i + shift
                if 0 <= ni < self.width:
                    new_h[ni] += h
                elif ni < 0:
                    spilled.append((
                        float(self.x1 + random.uniform(-4, 4)),
                        float(self.y + 2),
                        h,
                        dx * 4.0 - random.uniform(15, 45),
                        random.uniform(10, 40)
                    ))
                else:
                    spilled.append((
                        float(self.x2 + random.uniform(-4, 4)),
                        float(self.y + 2),
                        h,
                        dx * 4.0 + random.uniform(15, 45),
                        random.uniform(10, 40)
                    ))
            self.heights = new_h

        shake = math.hypot(dx, dy)
        if dy > 2 or shake > 10:
            peel_factor = min(0.85, max(0.0, dy * 0.06) + shake * 0.012)
            for i in range(0, self.width, 4):
                if self.heights[i] > 1.5:
                    drop_mass = self.heights[i] * peel_factor
                    self.heights[i] -= drop_mass
                    if drop_mass > 0.4:
                        spilled.append((
                            float(self.x1 + i),
                            float(self.y - self.heights[i]),
                            drop_mass * 1.4,
                            dx * 6.0 + random.uniform(-25, 25),
                            min(0.0, dy * 5.0) + random.uniform(5, 35)
                        ))

        return spilled

    def relax_and_roll(self) -> list[tuple[float, float, float, float, float]]:
        spilled = []
        w = self.width
        if w < 3:
            return spilled

        if self.kind == "ground":
            # Рассыпание пиков в ровную снежную полянку без потерь снега на краях экрана
            ms = self.max_slope
            for _ in range(3):
                for i in range(1, w):
                    diff = self.heights[i] - self.heights[i - 1]
                    if diff > ms:
                        slide = (diff - ms) * 0.48
                        self.heights[i] -= slide
                        self.heights[i - 1] += slide

                for i in range(w - 2, -1, -1):
                    diff = self.heights[i] - self.heights[i + 1]
                    if diff > ms:
                        slide = (diff - ms) * 0.48
                        self.heights[i] -= slide
                        self.heights[i + 1] += slide

            # Широкое выравнивание холмов (шаг 6 пикселей)
            step = 6
            for i in range(step, w - step):
                avg_far = (self.heights[i - step] +
                           self.heights[i + step]) * 0.5
                diff = self.heights[i] - avg_far
                if abs(diff) > 0.25:
                    transfer = diff * 0.35
                    self.heights[i] -= transfer
                    self.heights[i - step] += transfer * 0.5
                    self.heights[i + step] += transfer * 0.5

            self.heights[0] = self.heights[1]
            self.heights[w - 1] = self.heights[w - 2]
            return spilled

        ms = self.max_slope
        for i in range(1, w):
            diff = self.heights[i] - self.heights[i - 1]
            if diff > ms:
                slide = (diff - ms) * 0.45
                self.heights[i] -= slide
                self.heights[i - 1] += slide

        for i in range(w - 2, -1, -1):
            diff = self.heights[i] - self.heights[i + 1]
            if diff > ms:
                slide = (diff - ms) * 0.45
                self.heights[i] -= slide
                self.heights[i + 1] += slide

        prev = self.heights[0]
        for i in range(1, w - 1):
            curr = self.heights[i]
            nxt = self.heights[i + 1]
            smoothed = curr * 0.84 + (prev + nxt) * 0.08
            limit = self.hill_limit(i)
            if smoothed > limit:
                overflow = smoothed - limit
                smoothed = limit
                if i < w * 0.5:
                    self.heights[i - 1] += overflow * 0.85
                else:
                    self.heights[i + 1] += overflow * 0.85
            self.heights[i] = smoothed
            prev = curr

        if self.heights[0] > 0.15:
            self.left_spill += self.heights[0]
            self.heights[0] = 0.0
        if self.heights[w - 1] > 0.15:
            self.right_spill += self.heights[w - 1]
            self.heights[w - 1] = 0.0

        if self.left_spill >= 1.1:
            spilled.append((
                float(self.x1 - 2),
                float(self.y + 2),
                min(4.0, self.left_spill),
                random.uniform(-38.0, -10.0),
                random.uniform(15.0, 45.0)
            ))
            self.left_spill = 0.0

        if self.right_spill >= 1.1:
            spilled.append((
                float(self.x2 + 2),
                float(self.y + 2),
                min(4.0, self.right_spill),
                random.uniform(10.0, 38.0),
                random.uniform(15.0, 45.0)
            ))
            self.right_spill = 0.0

        return spilled


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
            dh_l = (self.depths[i] - self.depths[i - 1]) * \
                PUDDLE_DIFFUSION_RATE
            dh_r = (self.depths[i] - self.depths[i + 1]) * \
                PUDDLE_DIFFUSION_RATE
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
