import time
import math
import random
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor


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


class BurrowChamber:
    def __init__(self, chamber_id: str, x: float, y: float, kind: str = "hall", depth_level: int = 1, owner_id: int | None = None):
        self.id = chamber_id
        self.x = x
        self.y = y
        self.radius = 3.0
        self.max_radius = random.uniform(16.0, 22.0)
        self.kind = kind  # "hall", "bedroom", "pantry", "nursery"
        self.depth_level = depth_level
        self.owner_id = owner_id
        self.occupants = 0


class TownTunnelSegment:
    def __init__(self, from_id: str, to_id: str, points: list[list[float]]):
        self.from_id = from_id
        self.to_id = to_id
        self.points = points


def generate_winding_path(
    p1: list[float], p2: list[float],
    ground_y: int, heights: list[float], sw: int,
    is_to_entrance: bool = False
) -> list[list[float]]:
    """Генерирует извилистую органическую цепочку точек, гарантированно проходящую строго под снегом."""
    x1, y1 = p1[0], p1[1]
    x2, y2 = p2[0], p2[1]
    dist = math.hypot(x2 - x1, y2 - y1)
    steps = max(4, int(dist / 9.0))
    pts = []
    seed = random.uniform(0.0, math.tau)
    amp = min(12.0, max(4.0, dist * 0.16))

    # Перпендикулярный вектор для создания изгибов
    nx = -(y2 - y1) / max(1.0, dist)
    ny = (x2 - x1) / max(1.0, dist)

    for i in range(steps + 1):
        t = i / float(steps)
        bx = x1 + (x2 - x1) * t
        by = y1 + (y2 - y1) * t

        # Извилистая синусоида, затухающая на концах тоннеля
        wobble = math.sin(t * math.pi) * \
            (math.sin(t * math.pi * 2.5 + seed) * amp)
        px = bx + nx * wobble
        py = by + ny * wobble

        ix = max(0, min(sw - 1, int(px)))
        snow_surf_y = ground_y - heights[ix]

        # Строго под снегом!
        if is_to_entrance and t >= 0.88:
            # Плавный выход на поверхность снега только у самого устья
            py = min(ground_y - 8.0, py)
        else:
            py = max(snow_surf_y + 16.0, min(ground_y - 8.0, py))

        pts.append([px, py])

    pts[0] = [x1, y1]
    pts[-1] = [x2, y2]
    return pts


class SnowBurrowTown:
    def __init__(self, town_id: int, start_x: float, start_y: float):
        self.town_id = town_id
        self.entrances: dict[str, list[float]] = {"ent_0": [start_x, start_y]}
        self.chambers: dict[str, BurrowChamber] = {}
        self.segments: list[TownTunnelSegment] = []
        self.alive = True
        self.next_ch_id = 0
        self.next_ent_id = 1

    def sync_with_snow(self, ground_y: int, heights: list[float], sw: int):
        for eid, pt in self.entrances.items():
            ix = max(0, min(sw - 1, int(pt[0])))
            surf_y = (ground_y - heights[ix]) + 3.0
            pt[1] = surf_y
            # Привязываем начало тоннелей строго к устью норы
            for seg in self.segments:
                if seg.from_id == eid and seg.points:
                    seg.points[0][1] = surf_y
                if seg.to_id == eid and seg.points:
                    seg.points[-1][1] = surf_y

    def find_safe_entrance(self, px: float, wolf_x: float | None) -> tuple[str, float, float] | None:
        candidates = []
        for eid, pt in self.entrances.items():
            ex, ey = pt[0], pt[1]
            if wolf_x is None:
                candidates.append((eid, ex, ey, abs(ex - px)))
            else:
                away_dir = -1.0 if wolf_x > px else 1.0
                is_safe_dir = (ex - px) * away_dir >= -20.0
                dist_to_wolf = abs(ex - wolf_x)
                if is_safe_dir and dist_to_wolf > 100.0:
                    candidates.append((eid, ex, ey, abs(ex - px)))

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[3])
        best = candidates[0]
        return best[0], best[1], best[2]

    def find_nearest_entrance(self, px: float) -> tuple[str, float, float] | None:
        if not self.entrances:
            return None
        best_id, best_pt = min(self.entrances.items(),
                               key=lambda kv: abs(kv[1][0] - px))
        return best_id, best_pt[0], best_pt[1]

    def find_path(self, start_id: str | None, target_id: str | None) -> list[list[float]]:
        if not start_id or not target_id or start_id == target_id:
            return []

        queue = [[start_id]]
        visited = {start_id}
        found_chain = None

        while queue:
            path = queue.pop(0)
            curr = path[-1]
            if curr == target_id:
                found_chain = path
                break

            for seg in self.segments:
                neighbor = None
                if seg.from_id == curr:
                    neighbor = seg.to_id
                elif seg.to_id == curr:
                    neighbor = seg.from_id

                if neighbor and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])

        if not found_chain:
            return []

        waypoint_line: list[list[float]] = []
        for i in range(len(found_chain) - 1):
            u, v = found_chain[i], found_chain[i + 1]
            for seg in self.segments:
                if seg.from_id == u and seg.to_id == v:
                    for p in seg.points:
                        if not waypoint_line or math.hypot(waypoint_line[-1][0] - p[0], waypoint_line[-1][1] - p[1]) > 0.8:
                            waypoint_line.append([p[0], p[1]])
                    break
                elif seg.from_id == v and seg.to_id == u:
                    for p in reversed(seg.points):
                        if not waypoint_line or math.hypot(waypoint_line[-1][0] - p[0], waypoint_line[-1][1] - p[1]) > 0.8:
                            waypoint_line.append([p[0], p[1]])
                    break

        return waypoint_line


class BunnyAgent:
    _global_id_counter = 0

    def __init__(self, start_x: float, y: float, screen_w: int):
        BunnyAgent._global_id_counter += 1
        self.bunny_id = BunnyAgent._global_id_counter

        self.x = start_x
        self.y = y
        self.state = "run"
        self.facing = 1 if (start_x < screen_w * 0.5) else -1
        self.leg_phase = random.uniform(0.0, math.tau)
        self.run_start_x = start_x
        self.run_target_dist = random.uniform(75.0, 150.0)
        self.speed = random.uniform(110.0, 140.0)
        self.state_timer = random.uniform(1.0, 2.5)

        self.current_town: SnowBurrowTown | None = None
        self.current_node_id: str | None = None
        self.home_chamber_id: str | None = None
        self.target_chamber: BurrowChamber | None = None
        self.dest_node_id: str | None = None
        self.tunnel_path: list[list[float]] = []

        # Постепенное копание
        self.digging_town: SnowBurrowTown | None = None
        self.active_segment: TownTunnelSegment | None = None
        self.dig_to_id: str = ""
        self.dig_planned_points: list[list[float]] = []
        self.dig_point_idx = 0
        self.dig_step_timer = 0.0
        self.digging_chamber: BurrowChamber | None = None

        # Социализация
        self.chat_partner: "BunnyAgent | None" = None
        self.chat_cooldown = 0.0
        self.look_dir = self.facing
        self.ear_twitch = 0.0
        self.active = True

    @property
    def is_underground(self) -> bool:
        return self.state in ("in_chamber", "tunnel_walk", "dig", "underground_chat")

    def step(
        self,
        dt: float,
        wolves: list[WolfAgent],
        towns: list[SnowBurrowTown],
        snow_depth: float,
        should_stay: bool,
        all_bunnies: list["BunnyAgent"],
        screen_w: int,
        ground_y: int,
        heights: list[float]
    ) -> tuple[bool, SnowBurrowTown | None]:
        if self.chat_cooldown > 0.0:
            self.chat_cooldown -= dt

        if not should_stay and self.state != "exit":
            self._leave_chamber()
            self.state = "exit"

        # Городок растаял/взорван, пока зайчик сидел в камере: выбираемся наверх,
        # иначе он навсегда застревает под землёй и занимает слот популяции.
        if self.state in ("in_chamber", "underground_chat"):
            town = self.current_town
            chamber_gone = (
                self.target_chamber is not None and town is not None and
                self.target_chamber.id not in town.chambers
            )
            if town is None or not town.alive or chamber_gone:
                self._leave_chamber()
                self.current_town = None
                self.current_node_id = None
                self.tunnel_path = []
                self.chat_partner = None
                self.state = "look_around"
                self.state_timer = random.uniform(0.8, 1.5)

        nearest_wolf = min(wolves, key=lambda w: abs(
            w.x - self.x)) if wolves else None
        wolf_dist = abs(nearest_wolf.x - self.x) if nearest_wolf else 99999.0

        # Умная реакция на волков на поверхности
        if nearest_wolf is not None and not self.is_underground and self.state not in ("flee", "exit"):
            if wolf_dist < 310.0:
                self.chat_partner = None
                self.state = "flee"
            elif wolf_dist < 420.0 and self.state in ("run", "pause", "sniff"):
                self.state = "look_around"
                self.look_dir = 1 if nearest_wolf.x > self.x else -1
                self.state_timer = random.uniform(0.8, 1.5)

        # 1. ОБЩЕНИЕ ЗАЙЧИКОВ
        if self.state in ("chat", "underground_chat"):
            self.state_timer -= dt
            self.ear_twitch = math.sin(time.time() * 14.0) * 0.45
            if self.chat_partner and self.chat_partner.active:
                self.facing = 1 if self.chat_partner.x >= self.x else -1
                self.look_dir = self.facing
            if (self.state == "chat" and wolf_dist < 320.0) or self.state_timer <= 0.0:
                was_underground = (self.state == "underground_chat")
                self.chat_partner = None
                self.chat_cooldown = random.uniform(5.0, 9.0)
                if was_underground:
                    self.state = "in_chamber"
                    self.state_timer = random.uniform(2.0, 4.0)
                else:
                    self._start_running(random.choice([-1, 1]), screen_w)
            return False, None

        if self.chat_cooldown <= 0.0 and wolf_dist > 340.0:
            if self.state in ("run", "pause", "sniff", "look_around"):
                for other in all_bunnies:
                    if (
                        other is not self and other.active and not other.is_underground
                        and other.state in ("run", "pause", "sniff", "look_around")
                        and other.chat_cooldown <= 0.0
                    ):
                        if abs(other.x - self.x) < 30.0 and abs(other.y - self.y) < 16.0:
                            self.state = "chat"
                            other.state = "chat"
                            self.chat_partner = other
                            other.chat_partner = self
                            dur = random.uniform(2.2, 3.5)
                            self.state_timer = dur
                            other.state_timer = dur
                            return False, None

            elif self.state == "in_chamber" and self.target_chamber:
                for other in all_bunnies:
                    if (
                        other is not self and other.active and other.state == "in_chamber"
                        and other.target_chamber is self.target_chamber and other.chat_cooldown <= 0.0
                    ):
                        self.state = "underground_chat"
                        other.state = "underground_chat"
                        self.chat_partner = other
                        other.chat_partner = self
                        dur = random.uniform(2.5, 4.0)
                        self.state_timer = dur
                        other.state_timer = dur
                        return False, None

        # 2. ЖИЗНЬ В ПОДЗЕМНОЙ КАМЕРЕ (СПЯТ СТРОГО 1 НА МЕСТО)
        if self.state == "in_chamber":
            self.state_timer -= dt
            if self.target_chamber:
                self.x = self.target_chamber.x
                self.y = self.target_chamber.y

            if wolf_dist > 280.0 and self.state_timer <= 0.0 and self.current_town and self.current_town.alive:
                # Ветвление городка (рытье новой комнаты или выхода)
                if snow_depth >= 52.0 and len(self.current_town.chambers) < 7 and random.random() < 0.55:
                    self._start_digging_expansion(
                        self.current_town, snow_depth, screen_w, ground_y, heights)
                # Пойти в гости в другую комнату
                elif len(self.current_town.chambers) > 1 and random.random() < 0.45:
                    other_chambers = [
                        c for c in self.current_town.chambers.values() if c.id != self.current_node_id]
                    dest_ch = random.choice(other_chambers)
                    path = self.current_town.find_path(
                        self.current_node_id, dest_ch.id)
                    self._leave_chamber()
                    if path:
                        self.target_chamber = dest_ch
                        self.dest_node_id = dest_ch.id
                        self.tunnel_path = path
                        self.state = "tunnel_walk"
                # Выйти прогуляться на поверхность
                else:
                    safe_ent = self.current_town.find_safe_entrance(
                        self.x, nearest_wolf.x if nearest_wolf else None)
                    if safe_ent:
                        eid, ex, ey = safe_ent
                        path = self.current_town.find_path(
                            self.current_node_id, eid)
                        self._leave_chamber()
                        if path:
                            self.target_chamber = None
                            self.dest_node_id = eid
                            self.tunnel_path = path
                            self.state = "tunnel_walk"
                        else:
                            self.state_timer = 1.5
                    else:
                        self.state_timer = 2.0
            return False, None

        # 3. ФИЗИЧЕСКИЙ БЕГ ПО ИЗВИЛИСТЫМ ТОННЕЛЯМ (БЕЗ ТЕЛЕПОРТАЦИИ)
        elif self.state == "tunnel_walk":
            if not self.current_town or not self.current_town.alive:
                self.current_town = None
                self.state = "run"
                return False, None

            self.leg_phase += dt * 16.0
            if not self.tunnel_path:
                if self.target_chamber and self.target_chamber.id in self.current_town.chambers:
                    self.x = self.target_chamber.x
                    self.y = self.target_chamber.y
                    self.current_node_id = self.target_chamber.id

                    # Проверяем правило: спать строго один на место!
                    can_sleep = (
                        self.target_chamber.kind in ("hall", "pantry", "nursery") or
                        (self.target_chamber.owner_id == self.bunny_id and self.target_chamber.occupants == 0) or
                        (self.target_chamber.owner_id is None and self.target_chamber.occupants == 0)
                    )
                    if can_sleep:
                        if self.target_chamber.owner_id is None and self.target_chamber.kind == "bedroom":
                            self.target_chamber.owner_id = self.bunny_id
                            self.home_chamber_id = self.target_chamber.id
                        self.target_chamber.occupants += 1
                        self.state = "in_chamber"
                        self.state_timer = random.uniform(3.5, 7.0)
                    else:
                        # В гостях: побыл секунду и ушел дальше
                        self.state_timer = random.uniform(1.5, 2.5)
                        self.state = "in_chamber"
                else:
                    # Вышли через устье норы на поверхность
                    if self.dest_node_id and self.dest_node_id in self.current_town.entrances:
                        ent_pt = self.current_town.entrances[self.dest_node_id]
                        self.x, self.y = ent_pt[0], ent_pt[1]
                    self.current_town = None
                    self.current_node_id = None
                    self.dest_node_id = None
                    self.state = "look_around"
                    self.state_timer = random.uniform(1.0, 2.0)
                return False, None

            target_pt = self.tunnel_path[0]
            dx = target_pt[0] - self.x
            dy = target_pt[1] - self.y
            dist = math.hypot(dx, dy)
            step_move = (self.speed * 0.95) * dt

            if dist <= step_move + 1.2:
                self.x = target_pt[0]
                self.y = target_pt[1]
                self.tunnel_path.pop(0)
            else:
                if abs(dx) > 0.2:
                    self.facing = 1 if dx >= 0 else -1
                self.x += (dx / dist) * step_move
                self.y += (dy / dist) * step_move

            return False, None

        # 4. ПОШАГОВОЕ РЫТЬЕ ИЗВИЛИСТЫХ ТОННЕЛЕЙ И КОМНАТ
        elif self.state == "dig":
            self.leg_phase += dt * 24.0
            if not self.digging_town or not self.digging_town.alive:
                self.digging_town = None
                self.digging_chamber = None
                self.active_segment = None
                self.current_town = None
                self.current_node_id = None
                self._start_running(self.facing, screen_w)
                return False, None

            # Фаза расширения круглой комнаты
            if self.digging_chamber is not None:
                ch = self.digging_chamber
                ch.radius = min(ch.max_radius, ch.radius + 8.5 * dt)
                self.x = ch.x + math.sin(time.time() * 10.0) * 2.5
                self.y = ch.y
                if ch.radius >= ch.max_radius:
                    self.target_chamber = ch
                    ch.occupants += 1
                    self.current_node_id = ch.id
                    self.digging_chamber = None
                    self.active_segment = None
                    self.state = "in_chamber"
                    self.state_timer = random.uniform(3.5, 7.0)
                return True, None

            # Фаза бурения извилистого тоннеля точка за точкой
            self.dig_step_timer -= dt
            if self.dig_step_timer <= 0.0 and self.active_segment:
                self.dig_step_timer = random.uniform(0.12, 0.18)
                if self.dig_point_idx < len(self.dig_planned_points):
                    next_pt = self.dig_planned_points[self.dig_point_idx]
                    self.active_segment.points.append(next_pt)
                    self.facing = 1 if next_pt[0] >= self.x else -1
                    self.x, self.y = next_pt[0], next_pt[1]
                    self.dig_point_idx += 1
                else:
                    # Докопали тоннель до конца
                    end_pt = self.active_segment.points[-1]
                    self.x, self.y = end_pt[0], end_pt[1]

                    if self.dig_to_id.startswith("ch_"):
                        ch = self.digging_town.chambers.get(self.dig_to_id)
                        if ch and ch.radius < ch.max_radius - 1.0:
                            self.digging_chamber = ch
                        else:
                            self.target_chamber = ch
                            if ch:
                                ch.occupants += 1
                            self.current_node_id = self.dig_to_id
                            self.active_segment = None
                            self.state = "in_chamber"
                            self.state_timer = random.uniform(2.5, 5.0)
                    else:
                        # Новый выход наверх прокопан — вход активируется
                        surf_y = (
                            ground_y - heights[max(0, min(screen_w - 1, int(self.x)))]) + 3.0
                        self.digging_town.entrances[self.dig_to_id] = [
                            self.x, surf_y]
                        self.active_segment.points[-1] = [self.x, surf_y]
                        self.x, self.y = self.x, surf_y
                        self.current_town = None
                        self.current_node_id = None
                        self.active_segment = None
                        self.state = "look_around"
                        self.state_timer = random.uniform(1.2, 2.0)
                        self._start_running(random.choice([-1, 1]), screen_w)

            return True, None

        # 5. СПАСЕНИЕ ОТ ВОЛКОВ (СТРОГО ПРОЧЬ ОТ ХИЩНИКА)
        elif self.state == "flee":
            self.leg_phase += dt * 24.0
            wolf_x = nearest_wolf.x if nearest_wolf else None
            away_dir = -1 if (wolf_x is not None and wolf_x > self.x) else 1

            # Ищем ближайший безопасный вход в любом из городков
            best_town, best_eid, best_ent_pt, best_d = None, None, None, 99999.0
            for t in towns:
                if not t.alive:
                    continue
                safe_ent = t.find_safe_entrance(self.x, wolf_x)
                if safe_ent:
                    eid, ex, ey = safe_ent
                    d = abs(ex - self.x)
                    if d < best_d:
                        best_d = d
                        best_town = t
                        best_eid = eid
                        best_ent_pt = [ex, ey]

            if best_town is not None and best_d < 320.0 and best_ent_pt:
                dx = best_ent_pt[0] - self.x
                if abs(dx) <= 12.0:
                    self.x, self.y = best_ent_pt[0], best_ent_pt[1]
                    self.current_town = best_town
                    chambers = list(best_town.chambers.values())
                    if chambers:
                        deepest = max(chambers, key=lambda c: c.y)
                        path = best_town.find_path(best_eid, deepest.id)
                        if path:
                            self.target_chamber = deepest
                            self.dest_node_id = deepest.id
                            self.tunnel_path = path
                            self.state = "tunnel_walk"
                            return False, None
                step_dir = 1 if dx > 0 else -1
            else:
                step_dir = away_dir

            self.facing = step_dir
            self.x += self.facing * (self.speed * 1.95) * dt

            if self.x < 30.0 or self.x > screen_w - 30.0:
                self.state = "exit"
            elif wolf_dist > 380.0:
                self.state = "look_around"
                self.state_timer = random.uniform(1.0, 1.8)
            return False, None

        # 6. НЕПРЕРЫВНЫЙ БЕГ ВПЕРЕД (БЕЗ ПОДСКОКОВ НА МЕСТЕ)
        elif self.state == "run":
            self.leg_phase += dt * 16.0
            self.x += self.facing * self.speed * dt

            # Пробегая мимо готового входа, можем заглянуть в городок
            for t in towns:
                if t.alive and t.chambers and random.random() < 0.035:
                    ent_info = t.find_nearest_entrance(self.x)
                    if ent_info and abs(ent_info[1] - self.x) <= 14.0:
                        eid, ex, ey = ent_info
                        dest_ch = random.choice(list(t.chambers.values()))
                        path = t.find_path(eid, dest_ch.id)
                        if path:
                            self.x, self.y = ex, ey
                            self.current_town = t
                            self.current_node_id = eid
                            self.target_chamber = dest_ch
                            self.dest_node_id = dest_ch.id
                            self.tunnel_path = path
                            self.state = "tunnel_walk"
                            return False, None

            if self.x < 70.0 and self.facing == -1:
                self._start_running(1, screen_w)
            elif self.x > screen_w - 70.0 and self.facing == 1:
                self._start_running(-1, screen_w)

            travelled = (self.x - self.run_start_x) * self.facing
            if travelled >= self.run_target_dist:
                self.state = random.choice(["pause", "sniff", "look_around"])
                self.state_timer = random.uniform(0.9, 2.0)

        # 7. ОСТАНОВКИ, ОСМОТР СТОЛБИКОМ И ПРИНЮХИВАНИЕ
        elif self.state == "pause":
            self.state_timer -= dt
            if self.state_timer <= 0.0:
                self.state = random.choice(["run", "look_around", "sniff"])
                self.state_timer = random.uniform(1.0, 2.0)
                if self.state == "run":
                    self._start_running(self.facing, screen_w)

        elif self.state == "look_around":
            self.state_timer -= dt
            self.ear_twitch = math.sin(time.time() * 8.0) * 0.35
            if random.random() < 0.03:
                self.look_dir = -self.look_dir

            if self.state_timer <= 0.0:
                if snow_depth >= 52.0 and 130.0 < self.x < screen_w - 130.0 and random.random() < 0.65:
                    new_town = self._begin_surface_dig(
                        towns, snow_depth, screen_w, ground_y, heights)
                    return False, new_town
                else:
                    new_dir = self.look_dir if random.random() < 0.6 else self.facing
                    self._start_running(new_dir, screen_w)

        elif self.state == "sniff":
            self.state_timer -= dt
            if self.state_timer <= 0.0:
                self._start_running(self.facing, screen_w)

        elif self.state == "exit":
            self.leg_phase += dt * 18.0
            self.x += self.facing * (self.speed * 1.5) * dt
            if self.x <= -60.0 or self.x >= screen_w + 60.0:
                self.active = False

        return False, None

    def _start_running(self, direction: int, screen_w: int):
        if self.x < 90.0:
            direction = 1
        elif self.x > screen_w - 90.0:
            direction = -1
        self.state = "run"
        self.facing = direction
        self.look_dir = direction
        self.run_start_x = self.x
        self.run_target_dist = random.uniform(70.0, 150.0)

    def _leave_chamber(self):
        if self.target_chamber:
            self.target_chamber.occupants = max(
                0, self.target_chamber.occupants - 1)
            self.target_chamber = None

    def _begin_surface_dig(
        self, towns: list[SnowBurrowTown], snow_depth: float,
        screen_w: int, ground_y: int, heights: list[float]
    ) -> SnowBurrowTown | None:
        start_y = self.y + 3.0

        # Ищем ближайший существующий городок
        nearest_town = None
        min_town_dist = 99999.0
        for t in towns:
            if t.alive:
                for pt in t.entrances.values():
                    d = abs(pt[0] - self.x)
                    if d < min_town_dist:
                        min_town_dist = d
                        nearest_town = t

        # Правило 2–3 независимых систем: если городков < 3 и расстояние > 340 px — закладываем НОВЫЙ отдельный городок!
        if len(towns) < 3 and min_town_dist > 340.0:
            new_town = SnowBurrowTown(len(towns) + 1, self.x, start_y)
            ch_id = f"ch_{new_town.next_ch_id}"
            new_town.next_ch_id += 1

            target_depth = min(snow_depth - 16.0, random.uniform(34.0, 48.0))
            target_x = max(80.0, min(screen_w - 80.0, self.x +
                           self.facing * random.uniform(45.0, 75.0)))
            target_y = min(ground_y - 12.0, self.y + target_depth)

            # Первая комната нового городка — своя личная спальня зайчика
            new_ch = BurrowChamber(
                ch_id, target_x, target_y, kind="bedroom", depth_level=1, owner_id=self.bunny_id)
            new_town.chambers[ch_id] = new_ch
            self.home_chamber_id = ch_id

            pts = generate_winding_path(
                [self.x, start_y], [target_x, target_y], ground_y, heights, screen_w)
            seg = TownTunnelSegment("ent_0", ch_id, [pts[0]])
            new_town.segments.append(seg)

            self.current_town = new_town
            self.digging_town = new_town
            self.active_segment = seg
            self.dig_to_id = ch_id
            self.dig_planned_points = pts[1:]
            self.dig_point_idx = 0
            self.dig_step_timer = 0.12
            self.state = "dig"
            return new_town

        # Иначе, если рядом уже есть городок — расширяем его сеть новым входом
        elif nearest_town and nearest_town.alive and nearest_town.chambers:
            town = nearest_town
            if any(abs(pt[0] - self.x) < 95.0 for pt in town.entrances.values()):
                self._start_running(self.facing, screen_w)
                return None

            ent_id = f"ent_{town.next_ent_id}"
            town.next_ent_id += 1
            town.entrances[ent_id] = [self.x, start_y]

            nearest_ch = min(town.chambers.values(), key=lambda c: math.hypot(
                c.x - self.x, c.y - start_y))
            pts = generate_winding_path(
                [self.x, start_y], [nearest_ch.x, nearest_ch.y], ground_y, heights, screen_w)
            seg = TownTunnelSegment(ent_id, nearest_ch.id, [pts[0]])
            town.segments.append(seg)

            self.current_town = town
            self.digging_town = town
            self.active_segment = seg
            self.dig_to_id = nearest_ch.id
            self.dig_planned_points = pts[1:]
            self.dig_point_idx = 0
            self.dig_step_timer = 0.12
            self.state = "dig"
            return None

        return None

    def _start_digging_expansion(
        self, town: SnowBurrowTown, snow_depth: float, screen_w: int, ground_y: int, heights: list[float]
    ):
        if not self.target_chamber:
            return

        from_ch = self.target_chamber
        from_id = from_ch.id
        self._leave_chamber()

        choices = ["width", "depth"]
        if len(town.entrances) < 4 and len(town.chambers) >= 2:
            choices.append("exit")
        expand_type = random.choice(choices)
        side = random.choice([-1, 1])

        if expand_type == "depth":
            ch_id = f"ch_{town.next_ch_id}"
            town.next_ch_id += 1
            t_x = max(90.0, min(screen_w - 90.0, from_ch.x +
                      side * random.uniform(45.0, 85.0)))
            ix = int(t_x)
            surf_y = ground_y - heights[ix]
            t_y = min(ground_y - 12.0, max(surf_y + 36.0,
                      from_ch.y + random.uniform(28.0, 48.0)))
            room_kind = random.choice(["bedroom", "nursery"])
            owner = self.bunny_id if (
                room_kind == "bedroom" and self.home_chamber_id is None) else None
            new_ch = BurrowChamber(ch_id, t_x, t_y, kind=room_kind, depth_level=min(
                3, from_ch.depth_level + 1), owner_id=owner)
            if owner:
                self.home_chamber_id = ch_id
            town.chambers[ch_id] = new_ch
            to_id = ch_id
            pts = generate_winding_path([from_ch.x, from_ch.y], [
                                        t_x, t_y], ground_y, heights, screen_w)

        elif expand_type == "width":
            ch_id = f"ch_{town.next_ch_id}"
            town.next_ch_id += 1
            t_x = max(90.0, min(screen_w - 90.0, from_ch.x +
                      side * random.uniform(75.0, 130.0)))
            ix = int(t_x)
            surf_y = ground_y - heights[ix]
            t_y = max(surf_y + 34.0, min(ground_y - 12.0,
                      from_ch.y + random.uniform(-10.0, 12.0)))
            room_kind = random.choice(["pantry", "hall", "bedroom"])
            owner = self.bunny_id if (
                room_kind == "bedroom" and self.home_chamber_id is None) else None
            new_ch = BurrowChamber(
                ch_id, t_x, t_y, kind=room_kind, depth_level=from_ch.depth_level, owner_id=owner)
            if owner:
                self.home_chamber_id = ch_id
            town.chambers[ch_id] = new_ch
            to_id = ch_id
            pts = generate_winding_path([from_ch.x, from_ch.y], [
                                        t_x, t_y], ground_y, heights, screen_w)

        else:
            # Новый запасной выход наружу
            ent_id = f"ent_{town.next_ent_id}"
            town.next_ent_id += 1
            t_x = max(90.0, min(screen_w - 90.0, from_ch.x +
                      side * random.uniform(65.0, 115.0)))
            ix = int(t_x)
            surf_y = (ground_y - heights[ix]) + 3.0
            to_id = ent_id
            pts = generate_winding_path([from_ch.x, from_ch.y], [
                                        t_x, surf_y], ground_y, heights, screen_w, is_to_entrance=True)

        seg = TownTunnelSegment(from_id, to_id, [pts[0]])
        town.segments.append(seg)

        self.facing = 1 if (pts[-1][0] >= from_ch.x) else -1
        self.digging_town = town
        self.active_segment = seg
        self.dig_to_id = to_id
        self.dig_planned_points = pts[1:]
        self.dig_point_idx = 0
        self.dig_step_timer = 0.12
        self.state = "dig"


class FireworkRocket:
    def __init__(self, start_x: float, start_y: float, target_x: float, target_y: float, town: SnowBurrowTown, target_key: str):
        self.x = start_x
        self.y = start_y
        self.target_x = target_x
        self.target_y = target_y
        self.town = town
        self.target_key = target_key

        dx = target_x - start_x
        dy = target_y - start_y
        dist = max(1.0, math.hypot(dx, dy))
        self.speed = random.uniform(390.0, 480.0)
        self.vx = (dx / dist) * self.speed
        self.vy = (dy / dist) * self.speed - 120.0
        self.color = random.choice([
            QColor("#ff3366"), QColor("#fbbf24"), QColor("#38bdf8"),
            QColor("#a855f7"), QColor("#34d399"), QColor("#f97316")
        ])
        self.alive = True

    def step(self, dt: float) -> tuple[bool, float, float, QColor]:
        self.vy += 320.0 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt

        if math.hypot(self.target_x - self.x, self.target_y - self.y) <= 24.0 or self.y >= self.target_y + 10.0:
            self.alive = False
            self._erase_target()
            return True, self.target_x, self.target_y, self.color
        return False, self.x, self.y, self.color

    def _erase_target(self):
        if not self.town or not self.town.alive:
            return
        if self.target_key in self.town.chambers:
            del self.town.chambers[self.target_key]
        elif self.target_key in self.town.entrances:
            del self.town.entrances[self.target_key]

        self.town.segments = [
            s for s in self.town.segments
            if s.from_id != self.target_key and s.to_id != self.target_key
        ]
        if not self.town.chambers:
            self.town.segments.clear()
            self.town.entrances.clear()
            self.town.alive = False


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
        self.firework_cd = random.uniform(0.2, 0.6)
        self.boomerang: Boomerang | None = None
        self.throw_cooldown = random.uniform(0.15, 0.55)
        self.active = True

    @property
    def heater_x(self) -> float:
        return self.x + self.facing * 28.0
