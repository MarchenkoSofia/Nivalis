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


class FleeingReindeer:
    def __init__(self, x: float, y: float, vx: float, vy: float, is_lead: bool):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.is_lead = is_lead
        self.direction = 1 if vx >= 0 else -1
        self.phase = random.uniform(0.0, math.tau)
        self.alive = True

    def step(self, dt: float, screen_w: int, screen_h: int):
        self.phase += dt * 14.0
        self.vy -= 35.0 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.x < -120 or self.x > screen_w + 120 or self.y < -120 or self.y > screen_h + 100:
            self.alive = False


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

    def strike(self, impulse_x: float, impulse_y: float) -> list[FleeingReindeer]:
        if self.downed:
            return []
        self.downed = True
        self.vx = self.vx * 0.35 + impulse_x * 0.25
        self.vy = min(-110.0, impulse_y * 0.25 - 90.0)
        self.ang_vel = (1 if self.vx >= 0 else -1) * random.uniform(5.0, 8.5)

        # Олени отрываются от упряжки и разбегаются в разные стороны
        reindeers = []
        for idx, rx in enumerate((30.0, 80.0)):
            rx_world = self.x + self.direction * rx
            ry_world = self.y
            flee_dir = -self.direction if idx == 0 else self.direction
            rvx = flee_dir * random.uniform(240.0, 340.0)
            rvy = random.uniform(-190.0, -70.0)
            reindeers.append(FleeingReindeer(
                rx_world, ry_world, rvx, rvy, is_lead=(idx == 1)))
        return reindeers

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


class WolfAgent:
    def __init__(self, start_x: float, ground_y: float, target_tree: PineTree):
        self.x = start_x
        self.y = ground_y
        self.target_tree = target_tree
        self.state = "run"
        self.facing = 1 if target_tree.x >= start_x else -1
        self.run_phase = random.uniform(0.0, math.tau)
        self.speed = random.uniform(195.0, 255.0)
        self.pause_timer = 0.0
        self.active = True

    def step(self, dt: float, lit_trees: list[PineTree], should_stay: bool, screen_w: int):
        if not should_stay and self.state != "exit":
            self.state = "exit"

        if self.state == "run":
            self.run_phase += dt * 15.0
            if self.target_tree is None or self.target_tree not in lit_trees:
                if lit_trees:
                    self.target_tree = random.choice(lit_trees)
                else:
                    self.state = "exit"
                    return

            dx = self.target_tree.x - self.x
            if abs(dx) <= 16.0:
                self.state = "pause"
                self.pause_timer = random.uniform(0.5, 1.4)
            else:
                step_dir = 1.0 if dx > 0 else -1.0
                self.facing = 1 if step_dir > 0 else -1
                self.x += step_dir * self.speed * dt

        elif self.state == "pause":
            self.pause_timer -= dt
            if self.pause_timer <= 0.0:
                if len(lit_trees) >= 2:
                    others = [t for t in lit_trees if t is not self.target_tree]
                    self.target_tree = random.choice(
                        others) if others else random.choice(lit_trees)
                    self.state = "run"
                else:
                    self.state = "exit"

        elif self.state == "exit":
            self.run_phase += dt * 15.0
            exit_x = -80.0 if self.x < screen_w * 0.5 else screen_w + 80.0
            step_dir = 1.0 if exit_x > self.x else -1.0
            self.facing = 1 if step_dir > 0 else -1
            self.x += step_dir * (self.speed * 1.15) * dt
            if self.x <= -70.0 or self.x >= screen_w + 70.0:
                self.active = False


class Boomerang:
    def __init__(self, start_x: float, start_y: float, target_tree: PineTree):
        self.x = start_x
        self.y = start_y
        self.target_tree = target_tree
        self.returning = False
        self.angle = 0.0
        self.speed = 460.0
        self.alive = True

    def step(self, dt: float, owner_x: float, owner_y: float) -> PineTree | None:
        self.angle += 24.0 * dt
        sliced_tree = None

        if not self.returning:
            if self.target_tree is None or self.target_tree.is_falling:
                self.returning = True
            else:
                tx = self.target_tree.x
                ty = self.target_tree.base_y - \
                    max(18.0, self.target_tree.max_h *
                        self.target_tree.growth * 0.18)
                dx = tx - self.x
                dy = ty - self.y
                dist = math.hypot(dx, dy)
                if dist <= 24.0:
                    self.target_tree.cut_ratio = 1.0
                    self.target_tree.is_falling = True
                    self.target_tree.lights_active = False
                    sliced_tree = self.target_tree
                    self.returning = True
                else:
                    self.x += (dx / dist) * self.speed * dt
                    self.y += (dy / dist) * self.speed * dt - \
                        math.sin(self.angle * 0.5) * 45.0 * dt
        else:
            dx = owner_x - self.x
            dy = (owner_y - 24.0) - self.y
            dist = math.hypot(dx, dy)
            if dist <= 22.0:
                self.alive = False
            else:
                self.x += (dx / dist) * self.speed * dt
                self.y += (dy / dist) * self.speed * dt

        return sliced_tree


class PenguinAgent:
    def __init__(self, start_x: float, target_x: float, ground_y: float):
        self.x = start_x
        self.y = ground_y
        self.target_x = target_x
        self.state = "enter"
        self.facing = 1 if target_x > start_x else -1
        self.waddle_phase = random.uniform(0.0, math.tau)
        self.heater_power = 0.0
        self.heater_y = ground_y
        self.boomerang: Boomerang | None = None
        self.throw_cooldown = random.uniform(0.15, 0.55)
        self.active = True

    @property
    def heater_x(self) -> float:
        return self.x + self.facing * 28.0
