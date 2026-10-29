import time
import math
import random
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient,
    QRadialGradient, QPolygonF, QPainterPath, QFont, QCursor
)
from .config import (
    PHYSICS_FPS, WIN_SCAN_INTERVAL_MS, WIND_FORCE_SCALE,
    GRAVITY, SETTINGS
)
from .platform_win import (
    fetch_visible_windows, fetch_desktop_icons, set_window_pass_through
)
from .weather import WeatherEngine, WeatherType
from .physics import SnowLedge, FallingSnowParticle, WaterDrop, PuddleMap
from .entities import (
    PineTree, SantaSleigh, FleeingReindeer, WolfAgent, PenguinAgent
)
from .tray import TrayManager
from .settings import SettingsDialog


class NivalisOverlay(QWidget):
    def __init__(self):
        super().__init__()
        geom = QApplication.primaryScreen().geometry()
        self.sw = geom.width()
        self.sh = geom.height()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setGeometry(0, 0, self.sw, self.sh)
        self.setMouseTracking(True)

        self.weather = WeatherEngine()
        self.ground = SnowLedge(0, self.sh - 2, self.sw, kind="ground")
        self.ground.max_capacity = self.sh * 0.56
        self.puddle = PuddleMap(self.sw, self.sh - 2)

        self.window_ledges: dict[int, SnowLedge] = {}
        self.icon_ledges: list[SnowLedge] = []
        self.visible_win_rects: list[tuple[int, int, int, int]] = []

        self.ambient_flakes: list[dict] = []
        self.falling_snow: list[FallingSnowParticle] = []
        self.drops: list[WaterDrop] = []
        self.trees: list[PineTree] = []
        self.presents: list[dict] = []
        self.particles: list[dict] = []
        self.penguins: list[PenguinAgent] = []
        self.wolves: list[WolfAgent] = []
        self.fleeing_reindeers: list[FleeingReindeer] = []
        self.santa: SantaSleigh | None = None
        self.settings_dlg: SettingsDialog | None = None

        self.active_tool: str | None = None
        self.mouse_pressed = False
        self.last_pos = QPointF(0, 0)
        self.mouse_vel = QPointF(0, 0)
        self.last_tick = time.time()
        self.santa_cd = SETTINGS.santa_min_interval

        self.badge_w = 195
        self.badge_h = 28
        self.sos_w = 48
        self.btn_size = 28

        self.close_btn_rect = QRectF(
            self.sw - self.btn_size - 14,
            self.sh - self.badge_h - 48,
            self.btn_size,
            self.badge_h
        )
        self.sos_btn_rect = QRectF(
            self.close_btn_rect.x() - self.sos_w - 6,
            self.sh - self.badge_h - 48,
            self.sos_w,
            self.badge_h
        )
        self.badge_rect = QRectF(
            self.sos_btn_rect.x() - self.badge_w - 6,
            self.sh - self.badge_h - 48,
            self.badge_w,
            self.badge_h
        )
        self.close_btn_hovered = False
        self.sos_btn_hovered = False

        for _ in range(160):
            self._spawn_ambient_flake(scatter_y=True)

        self.show()
        self.hwnd = int(self.winId())
        set_window_pass_through(self.hwnd, True)

        self.tray = TrayManager(self)

        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(self.sync_environment)
        self.scan_timer.start(WIN_SCAN_INTERVAL_MS)
        self.sync_environment()

        self.loop_timer = QTimer(self)
        self.loop_timer.timeout.connect(self.physics_loop)
        self.loop_timer.start(int(1000 / PHYSICS_FPS))

    def open_settings(self):
        if self.settings_dlg is None:
            self.settings_dlg = SettingsDialog(self)
        self.settings_dlg.show()
        self.settings_dlg.raise_()
        self.settings_dlg.activateWindow()

    def set_active_tool(self, tool_id: str | None):
        self.active_tool = tool_id
        set_window_pass_through(self.hwnd, tool_id is None)

    def force_spawn_santa(self):
        if self.santa is None:
            self.santa = SantaSleigh(self.sw, self.sh)

    def force_spawn_tree(self):
        if len(self.trees) < SETTINGS.tree_max_count:
            rx = random.randint(80, self.sw - 80)
            self.ground.deposit(rx, 45.0, rad=35)
            surf_y = self.ground.y - self.ground.heights[rx]
            self.trees.append(PineTree(rx, surf_y))

    def trigger_penguin_sos(self):
        if self.penguins:
            return
        slots = [0.16, 0.38, 0.62, 0.84]
        for idx, frac in enumerate(slots):
            tx = self.sw * frac
            sx = -50.0 if idx < 2 else self.sw + 50.0
            clamp_x = max(0, min(self.sw - 1, int(sx)))
            sy = self.ground.y - self.ground.heights[clamp_x]
            self.penguins.append(PenguinAgent(sx, tx, sy))

    def close_application(self):
        if self.settings_dlg:
            self.settings_dlg.close()
        QApplication.quit()

    def sync_environment(self):
        if not self.icon_ledges:
            for x1, y1, x2, _ in fetch_desktop_icons(self.sw, self.sh):
                self.icon_ledges.append(SnowLedge(x1, y1, x2, kind="icon"))

        wins = fetch_visible_windows(self.hwnd, self.sw, self.sh)
        self.visible_win_rects = [r for _, r in wins]
        active_ids = set()

        for h, (l, t, r, b) in wins:
            if t < 10 or t > self.sh - 40:
                continue
            active_ids.add(h)
            if h in self.window_ledges:
                lg = self.window_ledges[h]
                if abs(lg.x1 - l) > 10 or abs(lg.y - t) > 10 or abs(lg.x2 - r) > 10:
                    self._avalanche(lg)
                    self.window_ledges[h] = SnowLedge(l, t, r, kind="window")
            else:
                self.window_ledges[h] = SnowLedge(l, t, r, kind="window")

        for dead_h in list(self.window_ledges.keys()):
            if dead_h not in active_ids:
                self._avalanche(self.window_ledges.pop(dead_h))

    def _avalanche(self, ledge: SnowLedge):
        for i in range(0, ledge.width, 6):
            h = ledge.heights[i]
            if h > 1.0:
                self.falling_snow.append(
                    FallingSnowParticle(
                        x=float(ledge.x1 + i),
                        y=float(ledge.y),
                        mass=h,
                        vx=random.uniform(-15.0, 15.0),
                        vy=random.uniform(10.0, 50.0)
                    )
                )

    def _point_occluded(self, x: float, y: float, exclude_rect=None) -> bool:
        for rc in self.visible_win_rects:
            if exclude_rect and rc == exclude_rect:
                break
            if rc[0] <= x <= rc[2] and rc[1] <= y <= rc[3]:
                return True
        return False

    def _spawn_ambient_flake(self, scatter_y=False):
        d = random.uniform(0.3, 1.0)
        w_type = self.weather.current_type

        if w_type == WeatherType.FLUFFY_SNOW:
            r = 1.8 + d * 3.4
            vy = 28.0 + d * 60.0
        elif w_type == WeatherType.FROST_CALM:
            r = 0.9 + d * 1.8
            vy = 20.0 + d * 45.0
        elif w_type == WeatherType.BLIZZARD:
            r = 1.0 + d * 2.6
            vy = 55.0 + d * 110.0
        else:
            r = 1.2 + d * 2.8
            vy = 35.0 + d * 80.0

        self.ambient_flakes.append({
            "x": random.uniform(-30, self.sw + 30),
            "y": random.uniform(-20, self.sh) if scatter_y else random.uniform(-30, -5),
            "r": r,
            "vy": vy,
            "vx_off": random.uniform(-15.0, 15.0),
            "phase": random.uniform(0.0, math.tau),
            "depth": d
        })

    def physics_loop(self):
        now = time.time()
        dt = min(0.05, now - self.last_tick)
        self.last_tick = now

        pos = QCursor.pos()
        gx, gy = float(pos.x()), float(pos.y())
        self.mouse_vel = QPointF((gx - self.last_pos.x()) / max(0.001, dt),
                                 (gy - self.last_pos.y()) / max(0.001, dt))

        self.close_btn_hovered = self.close_btn_rect.contains(gx, gy)
        self.sos_btn_hovered = self.sos_btn_rect.contains(gx, gy)
        over_ui = self.close_btn_hovered or self.sos_btn_hovered or self.badge_rect.contains(
            gx, gy)

        if self.active_tool is None:
            over_santa = (
                self.santa and not self.santa.downed and self.santa.bounding_box().contains(gx, gy)
            )
            set_window_pass_through(self.hwnd, not (over_santa or over_ui))

        if self.santa and not self.santa.downed:
            spd = math.hypot(self.mouse_vel.x(), self.mouse_vel.y())
            if spd > 950.0 and self.santa.bounding_box().contains(gx, gy):
                self._strike_santa(self.mouse_vel.x(), self.mouse_vel.y())

        if self.mouse_pressed and self.active_tool in ("shovel", "saw"):
            self._execute_tool(gx, gy)

        self.last_pos = QPointF(gx, gy)
        self.weather.update()

        penguins_heating = any(pg.state == "heat" for pg in self.penguins)

        target_count = 15 if penguins_heating else int(
            35 + self.weather.intensity * 380)
        while len(self.ambient_flakes) < target_count:
            self._spawn_ambient_flake()

        w_acc = self.weather.wind * WIND_FORCE_SCALE
        win_ledges = list(self.window_ledges.values())

        for f in self.ambient_flakes:
            old_y = f["y"]
            f["phase"] += dt * 2.2
            f["x"] += (w_acc * f["depth"] + math.sin(f["phase"])
                       * 14.0 + f["vx_off"]) * dt
            f["y"] += f["vy"] * dt

            if f["x"] < -40:
                f["x"] = self.sw + 35
            elif f["x"] > self.sw + 40:
                f["x"] = -35

            stuck = False
            fx, fy = f["x"], f["y"]

            if f["depth"] > 0.5:
                for idx, wl in enumerate(win_ledges):
                    if wl.x1 <= fx <= wl.x2:
                        lx = int(fx) - wl.x1
                        sy = wl.y - wl.heights[lx]
                        if old_y <= sy <= fy:
                            w_rc = self.visible_win_rects[idx] if idx < len(
                                self.visible_win_rects) else None
                            if not self._point_occluded(fx, wl.y - 2, exclude_rect=w_rc):
                                if not self.weather.is_thawing and not penguins_heating:
                                    wl.deposit(fx, 0.85, rad=7)
                                stuck = True
                                break

            if not stuck and f["depth"] > 0.65:
                for il in self.icon_ledges:
                    if il.x1 <= fx <= il.x2:
                        lx = int(fx) - il.x1
                        sy = il.y - il.heights[lx]
                        if old_y <= sy <= fy:
                            if not self._point_occluded(fx, il.y):
                                if not self.weather.is_thawing and not penguins_heating:
                                    il.deposit(fx, 0.75, rad=6)
                                stuck = True
                            break

            if not stuck and 0 <= int(fx) < self.sw:
                gy_surf = self.ground.y - self.ground.heights[int(fx)]
                if fy >= gy_surf:
                    if not self.weather.is_thawing and not penguins_heating:
                        self.ground.deposit(fx, 1.1, rad=12)
                    stuck = True

            if stuck or fy > self.sh + 15:
                if len(self.ambient_flakes) > target_count:
                    f["kill"] = True
                else:
                    f["y"] = random.uniform(-25, -5)
                    f["x"] = random.uniform(0, self.sw)

        self.ambient_flakes = [
            f for f in self.ambient_flakes if not f.get("kill")]

        for p in self.falling_snow:
            old_y = p.y
            p.update(dt, w_acc)
            if p.y >= self.sh + 10 or p.x < -20 or p.x > self.sw + 20:
                p.alive = False
                continue

            for wl in win_ledges:
                if wl.x1 <= p.x <= wl.x2:
                    lx = int(p.x) - wl.x1
                    sy = wl.y - wl.heights[lx]
                    if old_y <= sy <= p.y:
                        if not penguins_heating:
                            wl.deposit(p.x, p.mass, rad=7)
                        p.alive = False
                        break
            if not p.alive:
                continue

            for il in self.icon_ledges:
                if il.x1 <= p.x <= il.x2:
                    lx = int(p.x) - il.x1
                    sy = il.y - il.heights[lx]
                    if old_y <= sy <= p.y:
                        if not penguins_heating:
                            il.deposit(p.x, p.mass, rad=5)
                        p.alive = False
                        break
            if not p.alive:
                continue

            if 0 <= int(p.x) < self.sw:
                if p.y >= self.ground.y - self.ground.heights[int(p.x)]:
                    if not penguins_heating:
                        self.ground.deposit(p.x, p.mass, rad=10)
                    p.alive = False

        self.falling_snow = [p for p in self.falling_snow if p.alive]

        self.ground.smooth()
        for wl in win_ledges:
            wl.smooth()
        for il in self.icon_ledges:
            il.smooth()

        if SETTINGS.auto_penguin_sos and not self.penguins:
            max_snow_h = max(self.ground.heights, default=0.0)
            if max_snow_h >= self.sh * SETTINGS.penguin_trigger_ratio:
                self.trigger_penguin_sos()

        if self.weather.is_thawing:
            melt = 3.4 * dt
            for wl in win_ledges:
                for i in range(0, wl.width, 5):
                    if wl.heights[i] > 0.1:
                        wl.heights[i] = max(0.0, wl.heights[i] - melt)
                        if random.random() < 0.005 and len(self.drops) < 90:
                            self.drops.append(WaterDrop(wl.x1 + i, wl.y + 1))

            for il in self.icon_ledges:
                for i in range(0, il.width, 5):
                    if il.heights[i] > 0.1:
                        il.heights[i] = max(0.0, il.heights[i] - melt)
                        if random.random() < 0.004 and len(self.drops) < 90:
                            self.drops.append(WaterDrop(il.x1 + i, il.y + 1))

            for i in range(0, self.ground.width, 4):
                if self.ground.heights[i] > 0.1:
                    self.ground.heights[i] = max(
                        0.0, self.ground.heights[i] - melt)
                    self.puddle.add_water(i, melt * 0.7)

        for d in self.drops:
            d.update(dt)
            if d.y >= self.sh - 4:
                d.alive = False
                self.puddle.add_water(d.x, d.mass * 1.5)
            else:
                for wl in win_ledges:
                    if wl.x1 <= d.x <= wl.x2 and abs(d.y - wl.y) < 4:
                        if random.random() < 0.35:
                            d.alive = False
                            break

        self.drops = [d for d in self.drops if d.alive]
        self.puddle.update(dt, not self.weather.is_thawing)

        self._update_flora(dt)
        self._update_wolves(dt)
        self._update_penguins(dt, win_ledges)
        self._update_fauna(dt)

        for pt in self.particles:
            pt["vy"] += pt.get("grav", GRAVITY * 0.4) * dt
            pt["x"] += pt["vx"] * dt
            pt["y"] += pt["vy"] * dt
            pt["life"] -= dt
        self.particles = [pt for pt in self.particles if pt["life"] > 0]

        for pr in self.presents:
            if not pr["grounded"]:
                pr["vy"] += GRAVITY * dt * 0.4
                pr["x"] += pr["vx"] * dt
                pr["y"] += pr["vy"] * dt
                pr["rot"] += pr["vrot"] * dt
                ix = max(0, min(self.sw - 1, int(pr["x"])))
                if pr["y"] >= self.ground.y - self.ground.heights[ix] - 6:
                    pr["y"] = self.ground.y - self.ground.heights[ix] - 6
                    pr["grounded"] = True
            else:
                pr["life"] -= dt
        self.presents = [pr for pr in self.presents if pr["life"] > 0]

        self.update()

    def _update_flora(self, dt: float):
        penguins_busy = bool(self.penguins)
        if not self.weather.is_thawing and not penguins_busy and len(self.trees) < SETTINGS.tree_max_count and random.random() < 0.03:
            rx = random.randint(80, self.sw - 80)
            if self.ground.heights[rx] > SETTINGS.tree_snow_threshold:
                if all(abs(t.x - rx) > 105 for t in self.trees):
                    surf_y = self.ground.y - self.ground.heights[rx]
                    self.trees.append(PineTree(rx, surf_y))

        for t in self.trees:
            gx = max(0, min(self.sw - 1, int(t.x)))
            t.base_y = self.ground.y - self.ground.heights[gx]
            t.step(dt, SETTINGS.tree_growth_speed,
                   self.weather.is_thawing or penguins_busy)
        self.trees = [t for t in self.trees if t.alpha > 0.05]

    def _update_wolves(self, dt: float):
        lit_trees = [
            t for t in self.trees if t.lights_active and not t.is_falling]
        should_stay = (len(lit_trees) >
                       SETTINGS.wolf_min_lit_trees) and not self.penguins

        if should_stay and len(self.wolves) < 3 and random.random() < 0.05:
            sx = -60.0 if random.random() < 0.5 else self.sw + 60.0
            clamp_x = max(0, min(self.sw - 1, int(sx)))
            sy = self.ground.y - self.ground.heights[clamp_x]
            target = random.choice(lit_trees)
            self.wolves.append(WolfAgent(sx, sy, target))

        for w in self.wolves:
            cx = max(0, min(self.sw - 1, int(w.x)))
            w.y = self.ground.y - self.ground.heights[cx]
            w.step(dt, lit_trees, should_stay, self.sw)
            if w.state in ("run", "exit") and random.random() < 0.25:
                self.particles.append({
                    "x": w.x - w.facing * 12,
                    "y": w.y - 2,
                    "vx": -w.facing * random.uniform(20, 60),
                    "vy": random.uniform(-65, -20),
                    "r": random.uniform(1.8, 3.2),
                    "col": QColor(240, 248, 255, 190),
                    "life": 0.35
                })

        self.wolves = [w for w in self.wolves if w.active]

    def _update_penguins(self, dt: float, win_ledges: list[SnowLedge]):
        if not self.penguins:
            return

        any_heating = False
        for pg in self.penguins:
            clamp_x = max(0, min(self.sw - 1, int(pg.x)))
            pg.y = self.ground.y - self.ground.heights[clamp_x]

            hx_clamp = max(0, min(self.sw - 1, int(pg.heater_x)))
            pg.heater_y = self.ground.y - self.ground.heights[hx_clamp]

            if pg.state == "enter":
                pg.waddle_phase += dt * 12.0
                dx = pg.target_x - pg.x
                if abs(dx) <= 6.0:
                    pg.x = pg.target_x
                    pg.facing = 1 if pg.x < self.sw * 0.5 else -1
                    pg.state = "heat"
                else:
                    step_dir = 1.0 if dx > 0 else -1.0
                    pg.facing = 1 if step_dir > 0 else -1
                    pg.x += step_dir * 165.0 * dt

            elif pg.state == "heat":
                any_heating = True
                pg.waddle_phase += dt * 4.0
                pg.heater_power = min(1.0, pg.heater_power + dt * 1.8)
                if random.random() < 0.45:
                    self.particles.append({
                        "x": pg.heater_x + random.uniform(-10, 10),
                        "y": pg.heater_y - random.uniform(10, 26),
                        "vx": random.uniform(-18, 18),
                        "vy": random.uniform(-90, -45),
                        "grav": -40.0,
                        "r": random.uniform(2.2, 4.5),
                        "col": random.choice([QColor(251, 146, 60, 190), QColor(239, 68, 68, 180), QColor(253, 224, 71, 170)]),
                        "life": 0.55
                    })

            elif pg.state == "boomerang":
                pg.heater_power = max(0.0, pg.heater_power - dt * 2.5)
                standing = [t for t in self.trees if not t.is_falling]

                if pg.boomerang is not None:
                    sliced = pg.boomerang.step(dt, pg.x, pg.y)
                    if sliced is not None:
                        for _ in range(18):
                            self.particles.append({
                                "x": sliced.x + random.uniform(-12, 12),
                                "y": sliced.base_y - 20,
                                "vx": random.uniform(-110, 110),
                                "vy": random.uniform(-130, -20),
                                "r": random.uniform(2.2, 4.0),
                                "col": random.choice([QColor("#b5835a"), QColor("#2d6a4f"), QColor("#fbbf24")]),
                                "life": 0.55
                            })
                    if not pg.boomerang.alive:
                        pg.boomerang = None
                        pg.throw_cooldown = 0.25
                else:
                    if standing:
                        pg.throw_cooldown -= dt
                        if pg.throw_cooldown <= 0.0:
                            targeted_trees = {
                                p.boomerang.target_tree for p in self.penguins
                                if p.boomerang is not None and not p.boomerang.returning
                            }
                            candidates = [
                                t for t in standing if t not in targeted_trees] or standing
                            nearest = min(
                                candidates, key=lambda t: abs(t.x - pg.x))
                            pg.facing = 1 if nearest.x >= pg.x else -1
                            pg.boomerang = Boomerang(
                                pg.x, pg.y - 24.0, nearest)
                    else:
                        pg.state = "exit"

            elif pg.state == "exit":
                pg.waddle_phase += dt * 12.0
                exit_x = -70.0 if pg.x < self.sw * 0.5 else self.sw + 70.0
                step_dir = 1.0 if exit_x > pg.x else -1.0
                pg.facing = 1 if step_dir > 0 else -1
                pg.x += step_dir * 180.0 * dt
                if pg.x <= -60.0 or pg.x >= self.sw + 60.0:
                    pg.active = False

        if any_heating:
            global_melt = 62.0 * dt
            for i in range(self.ground.width):
                if self.ground.heights[i] > 0.0:
                    self.ground.heights[i] = max(
                        0.0, self.ground.heights[i] - global_melt)

            for pg in self.penguins:
                if pg.state == "heat":
                    hx = int(pg.heater_x)
                    for i in range(max(0, hx - 120), min(self.ground.width, hx + 120)):
                        boost = (1.0 - abs(i - hx) / 120.0) * 55.0 * dt
                        self.ground.heights[i] = max(
                            0.0, self.ground.heights[i] - boost)

            for wl in win_ledges:
                for i in range(wl.width):
                    wl.heights[i] = max(0.0, wl.heights[i] - global_melt * 1.2)

            for il in self.icon_ledges:
                for i in range(il.width):
                    il.heights[i] = max(0.0, il.heights[i] - global_melt * 1.2)

            for i in range(self.puddle.width):
                self.puddle.depths[i] = max(
                    0.0, self.puddle.depths[i] - 35.0 * dt)

            ground_clear = max(self.ground.heights, default=0.0) <= 0.6
            wins_clear = all(max(wl.heights, default=0.0)
                             <= 0.6 for wl in win_ledges)
            icons_clear = all(max(il.heights, default=0.0) <=
                              0.6 for il in self.icon_ledges)

            if ground_clear and wins_clear and icons_clear:
                for i in range(self.ground.width):
                    self.ground.heights[i] = 0.0
                for i in range(self.puddle.width):
                    self.puddle.depths[i] = 0.0
                for pg in self.penguins:
                    if pg.state == "heat":
                        pg.state = "boomerang"

        self.penguins = [pg for pg in self.penguins if pg.active]

    def _update_fauna(self, dt: float):
        for r in self.fleeing_reindeers:
            r.step(dt, self.sw, self.sh)
        self.fleeing_reindeers = [r for r in self.fleeing_reindeers if r.alive]

        ready = (
            not SETTINGS.santa_require_lit_tree or
            any(t.lights_active and not t.is_falling for t in self.trees)
        )
        if self.santa is None:
            if ready:
                self.santa_cd -= dt
                if self.santa_cd <= 0:
                    self.santa = SantaSleigh(self.sw, self.sh)
                    self.santa_cd = random.uniform(
                        SETTINGS.santa_min_interval,
                        SETTINGS.santa_min_interval + 15.0
                    )
        else:
            impact = self.santa.step(dt, self.sw, self.sh)
            if self.santa.downed and random.random() < 0.35:
                self.particles.append({
                    "x": self.santa.x + random.uniform(-20, 20),
                    "y": self.santa.y + random.uniform(-10, 10),
                    "vx": random.uniform(-30, 30),
                    "vy": random.uniform(-50, -10),
                    "r": random.uniform(4, 9),
                    "col": QColor(255, 180, 60, 180),
                    "life": 0.5
                })
            if impact:
                cx = max(20, min(self.sw - 20, int(self.santa.x)))
                for _ in range(40):
                    self.falling_snow.append(
                        FallingSnowParticle(
                            x=cx + random.uniform(-35, 35),
                            y=self.sh - 30,
                            mass=random.uniform(2.0, 6.0),
                            vx=random.uniform(-180, 180),
                            vy=random.uniform(-280, -60)
                        )
                    )
                for i in range(max(0, cx - 60), min(self.sw, cx + 60)):
                    self.ground.heights[i] *= 0.3
                for _ in range(4):
                    self.presents.append({
                        "x": cx + random.uniform(-40, 40),
                        "y": self.sh - 40,
                        "vx": random.uniform(-120, 120),
                        "vy": random.uniform(-200, -80),
                        "rot": 0.0,
                        "vrot": random.uniform(-5, 5),
                        "col": random.choice([QColor("#ef4444"), QColor("#10b981"), QColor("#f59e0b")]),
                        "grounded": False,
                        "life": 16.0
                    })
            if not self.santa.active:
                self.santa = None

    def _strike_santa(self, vx: float, vy: float):
        if not self.santa or self.santa.downed:
            return
        spawned_reindeers = self.santa.strike(vx, vy)
        self.fleeing_reindeers.extend(spawned_reindeers)
        for _ in range(22):
            self.particles.append({
                "x": self.santa.x,
                "y": self.santa.y,
                "vx": random.uniform(-160, 160),
                "vy": random.uniform(-160, 100),
                "r": random.uniform(2.5, 5.0),
                "col": QColor(254, 240, 138),
                "life": 0.7
            })

    def _execute_tool(self, gx: float, gy: float):
        if self.active_tool == "shovel":
            lx = max(0, min(self.sw - 1, int(gx)))
            surf_y = self.ground.y - self.ground.heights[lx]
            if gy >= surf_y - 60:
                for i in range(max(0, lx - 36), min(self.sw, lx + 36)):
                    d = 1.0 - (abs(i - lx) / 36.0)
                    self.ground.heights[i] = max(
                        0.0, self.ground.heights[i] - 8.5 * d)
                for _ in range(3):
                    self.particles.append({
                        "x": gx + random.uniform(-15, 15),
                        "y": surf_y,
                        "vx": self.mouse_vel.x() * 0.2 + random.uniform(-80, 80),
                        "vy": random.uniform(-160, -40),
                        "r": random.uniform(2, 4),
                        "col": QColor(240, 245, 255, 200),
                        "life": 0.4
                    })
            else:
                for wl in list(self.window_ledges.values()) + self.icon_ledges:
                    if abs(gy - wl.y) < 45 and wl.x1 <= gx <= wl.x2:
                        cut = wl.erode(gx, rad=24, cut_power=7.0)
                        for cx, cy, mass in cut:
                            self.falling_snow.append(
                                FallingSnowParticle(
                                    x=cx, y=cy + 4, mass=mass,
                                    vx=self.mouse_vel.x() * 0.2 + random.uniform(-40, 40),
                                    vy=random.uniform(20.0, 70.0)
                                )
                            )

        elif self.active_tool == "saw":
            for t in self.trees:
                if t.is_falling:
                    continue
                th = t.max_h * t.growth
                if abs(gx - t.x) < 38 and (t.base_y - th - 15) <= gy <= t.base_y + 10:
                    t.cut_ratio += 0.07
                    for _ in range(4):
                        self.particles.append({
                            "x": t.x + random.uniform(-8, 8),
                            "y": gy,
                            "vx": random.uniform(-70, 70),
                            "vy": random.uniform(-90, -20),
                            "r": random.uniform(2, 3.5),
                            "col": random.choice([QColor("#b5835a"), QColor("#2d6a4f")]),
                            "life": 0.4
                        })
                    if t.cut_ratio >= 1.0:
                        t.is_falling = True
                        t.lights_active = False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.set_active_tool(None)
            self.tray.set_tool(None)

    def mousePressEvent(self, event):
        pos = event.position()
        gx, gy = pos.x(), pos.y()

        if event.button() == Qt.MouseButton.LeftButton and self.close_btn_rect.contains(gx, gy):
            self.close_application()
            return

        if event.button() == Qt.MouseButton.LeftButton and self.sos_btn_rect.contains(gx, gy):
            self.trigger_penguin_sos()
            return

        if event.button() == Qt.MouseButton.LeftButton and self.badge_rect.contains(gx, gy):
            self.open_settings()
            return

        if event.button() == Qt.MouseButton.RightButton and self.active_tool is not None:
            self.set_active_tool(None)
            self.tray.set_tool(None)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.santa and not self.santa.downed and self.santa.bounding_box().contains(gx, gy):
                self._strike_santa(random.uniform(-100, 100), -160.0)
                return
            self.mouse_pressed = True
            self._execute_tool(gx, gy)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_pressed = False

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        self._draw_puddle(p)

        for d in self.drops:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(186, 230, 253, 210))
            p.drawEllipse(QPointF(d.x, d.y), 1.8, 3.4)

        for il in self.icon_ledges:
            if not self._point_occluded((il.x1 + il.x2) * 0.5, il.y):
                self._render_ledge(p, il)

        for wl in self.window_ledges.values():
            self._render_ledge(p, wl)

        self._render_ledge(p, self.ground)

        for t in self.trees:
            self._render_tree(p, t)

        for w in self.wolves:
            self._render_wolf(p, w)

        for pg in self.penguins:
            self._render_penguin(p, pg)

        for pr in self.presents:
            p.save()
            p.translate(pr["x"], pr["y"])
            p.rotate(math.degrees(pr["rot"]))
            p.setPen(QPen(QColor(255, 255, 255, 160), 1))
            p.setBrush(pr["col"])
            p.drawRoundedRect(QRectF(-7, -7, 14, 14), 2, 2)
            p.restore()

        for r in self.fleeing_reindeers:
            p.save()
            p.translate(r.x, r.y)
            if r.direction == -1:
                p.scale(-1, 1)
            self._draw_reindeer_model(p, r.phase, r.is_lead)
            p.restore()

        if self.santa:
            self._render_santa(p, self.santa)

        p.setPen(Qt.PenStyle.NoPen)
        for ps in self.falling_snow:
            p.setBrush(QColor(255, 255, 255, 240))
            p.drawEllipse(QPointF(ps.x, ps.y), ps.radius, ps.radius)

        for f in self.ambient_flakes:
            p.setBrush(QColor(240, 248, 255, int(100 + f["depth"] * 145)))
            p.drawEllipse(QPointF(f["x"], f["y"]), f["r"], f["r"])

        for pt in self.particles:
            p.setBrush(pt["col"])
            p.drawEllipse(QPointF(pt["x"], pt["y"]), pt["r"], pt["r"])

        self._render_tool_indicator(p)
        self._render_bottom_ui(p)

    def _render_ledge(self, p: QPainter, ledge: SnowLedge):
        if max(ledge.heights, default=0) < 0.6:
            return
        poly = QPolygonF()
        poly.append(QPointF(ledge.x1, ledge.y + 2))
        step = 4 if ledge.kind == "ground" else 3
        for i in range(0, ledge.width, step):
            poly.append(QPointF(ledge.x1 + i, ledge.y - ledge.heights[i]))
        poly.append(QPointF(ledge.x2, ledge.y - ledge.heights[-1]))
        poly.append(QPointF(ledge.x2, ledge.y + 2))

        top_y = ledge.y - max(ledge.heights, default=10.0)
        g = QLinearGradient(0, top_y, 0, ledge.y + 3)
        g.setColorAt(0.0, QColor(253, 254, 255, 245))
        g.setColorAt(1.0, QColor(203, 222, 245, 235))
        p.setPen(QPen(QColor(255, 255, 255, 180), 1.0))
        p.setBrush(QBrush(g))
        p.drawPolygon(poly)

    def _draw_puddle(self, p: QPainter):
        poly = QPolygonF()
        poly.append(QPointF(0, self.sh))
        has_water = False
        for x in range(0, self.sw, 4):
            d = self.puddle.depths[x]
            if d > 0.2:
                has_water = True
            poly.append(QPointF(x, self.sh - d))
        poly.append(QPointF(self.sw, self.sh - self.puddle.depths[-1]))
        poly.append(QPointF(self.sw, self.sh))

        if has_water:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(125, 211, 252, 95))
            p.drawPolygon(poly)

    def _render_tree(self, p: QPainter, t: PineTree):
        p.save()
        gx = max(0, min(self.sw - 1, int(t.x)))
        y_pos = self.ground.y - self.ground.heights[gx]
        p.translate(t.x, y_pos)
        p.rotate(math.degrees(t.fall_angle))
        p.setOpacity(max(0.0, t.alpha))

        h = t.max_h * t.growth
        w = h * 0.55

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#452915"))
        p.drawRect(QRectF(-w * 0.08, -h * 0.18, w * 0.16, h * 0.19))

        for i in range(t.tiers):
            fc = i / t.tiers
            tb = -h * (0.14 + fc * 0.68)
            tt = -h * (0.42 + fc * 0.58)
            tw = w * (1.0 - fc * 0.6)
            branch = QPolygonF(
                [QPointF(0, tt), QPointF(-tw * 0.5, tb), QPointF(tw * 0.5, tb)])
            p.setBrush(QColor(18, 86 - i * 8, 48))
            p.drawPolygon(branch)

        if t.lights_active:
            now = time.time()
            cols = [QColor("#f43f5e"), QColor("#fbbf24"),
                    QColor("#34d399"), QColor("#38bdf8")]
            for li in range(12):
                lf = (li + 1) / 13.0
                ly = -h * (0.2 + lf * 0.7)
                lx = math.sin(li * 2.2 + t.seed) * \
                    (w * (1.0 - lf * 0.7) * 0.35)
                c = cols[(li + int(now * 3)) % len(cols)]
                p.setBrush(c)
                p.drawEllipse(QPointF(lx, ly), 3.0, 3.0)

            p.setBrush(QColor("#fde047"))
            p.drawEllipse(QPointF(0, -h), 4.5, 4.5)

        p.restore()

    def _render_wolf(self, p: QPainter, w: WolfAgent):
        p.save()
        bob = abs(math.sin(w.run_phase)) * 3.5 if w.state != "pause" else 0.0
        p.translate(w.x, w.y - bob)
        if w.facing == -1:
            p.scale(-1, 1)

        swing = math.sin(w.run_phase) * 9.0 if w.state != "pause" else 0.0

        # Лапы волка в беге
        p.setPen(QPen(QColor("#334155"), 2.8,
                 Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(-11, -8), QPointF(-15 - swing, 0))
        p.drawLine(QPointF(-7, -8), QPointF(-6 + swing * 0.7, 0))
        p.drawLine(QPointF(10, -8), QPointF(15 + swing, 0))
        p.drawLine(QPointF(6, -8), QPointF(5 - swing * 0.7, 0))

        p.setPen(Qt.PenStyle.NoPen)
        # Пушистый хвост
        tail = QPolygonF([
            QPointF(-13, -13),
            QPointF(-27, -10 + swing * 0.25),
            QPointF(-24, -6 + swing * 0.25),
            QPointF(-12, -9)
        ])
        p.setBrush(QColor("#475569"))
        p.drawPolygon(tail)

        # Туловище и грудь
        p.setBrush(QColor("#64748b"))
        p.drawRoundedRect(QRectF(-15, -16, 28, 10), 4, 4)
        p.setBrush(QColor("#94a3b8"))
        p.drawRoundedRect(QRectF(-10, -11, 20, 4), 2, 2)

        # Шея, голова и морда
        head = QPolygonF([
            QPointF(9, -15),
            QPointF(15, -23),
            QPointF(24, -19),
            QPointF(24, -15),
            QPointF(13, -10)
        ])
        p.setBrush(QColor("#475569"))
        p.drawPolygon(head)

        # Острые уши
        ear1 = QPolygonF(
            [QPointF(13, -21), QPointF(15, -28), QPointF(18, -21)])
        ear2 = QPolygonF(
            [QPointF(10, -20), QPointF(12, -26), QPointF(15, -20)])
        p.setBrush(QColor("#334155"))
        p.drawPolygon(ear2)
        p.setBrush(QColor("#475569"))
        p.drawPolygon(ear1)

        # Янтарный глаз и черный нос
        p.setBrush(QColor("#f59e0b"))
        p.drawEllipse(QPointF(18.5, -19.5), 1.5, 1.5)
        p.setBrush(QColor("#0f172a"))
        p.drawEllipse(QPointF(24.0, -18.0), 1.6, 1.6)

        p.restore()

    def _render_penguin(self, p: QPainter, pg: PenguinAgent):
        if pg.heater_power > 0.05:
            p.save()
            p.translate(pg.heater_x, pg.heater_y)

            glow_r = 45.0 * pg.heater_power
            glow = QRadialGradient(QPointF(0, -14), glow_r)
            glow.setColorAt(0.0, QColor(
                249, 115, 22, int(145 * pg.heater_power)))
            glow.setColorAt(1.0, QColor(249, 115, 22, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(glow))
            p.drawEllipse(QPointF(0, -14), glow_r, glow_r)

            p.setBrush(QColor("#334155"))
            p.drawRoundedRect(QRectF(-12, -26, 24, 22), 4, 4)
            p.setBrush(QColor("#1e293b"))
            p.drawRect(QRectF(-10, -4, 5, 4))
            p.drawRect(QRectF(5, -4, 5, 4))

            coil_col = QColor(251, 146, 60) if int(
                time.time() * 10) % 2 == 0 else QColor(239, 68, 68)
            p.setPen(QPen(coil_col, 2.2, Qt.PenStyle.SolidLine,
                     Qt.PenCapStyle.RoundCap))
            for cy in (-20, -15, -10):
                p.drawLine(-7, cy, 7, cy)
            p.restore()

        p.save()
        p.translate(pg.x, pg.y)
        tilt = math.sin(pg.waddle_phase) * \
            6.0 if pg.state in ("enter", "exit") else 0.0
        p.rotate(tilt)
        if pg.facing == -1:
            p.scale(-1, 1)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#f97316"))
        p.drawEllipse(QPointF(-6, -2), 5.5, 2.8)
        p.drawEllipse(QPointF(6, -2), 5.5, 2.8)

        p.setBrush(QColor("#0f172a"))
        p.drawEllipse(QPointF(0, -18), 13.0, 16.5)
        p.drawEllipse(QPointF(0, -34), 10.5, 10.0)

        p.setBrush(QColor("#f8fafc"))
        p.drawEllipse(QPointF(2, -17), 8.5, 12.5)

        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QPointF(4.5, -36), 2.8, 2.8)
        p.setBrush(QColor("#0f172a"))
        p.drawEllipse(QPointF(5.3, -36), 1.4, 1.4)

        beak = QPolygonF([QPointF(9, -35), QPointF(17, -33), QPointF(9, -31)])
        p.setBrush(QColor("#fb923c"))
        p.drawPolygon(beak)

        p.setBrush(QColor("#ef4444"))
        p.drawRoundedRect(QRectF(-8, -44, 16, 4), 2, 2)
        p.drawEllipse(QPointF(0, -45), 6.0, 4.0)
        p.setBrush(QColor("#fde047"))
        p.drawEllipse(QPointF(-2, -47), 2.5, 2.5)

        p.setBrush(QColor("#1e293b"))
        p.drawEllipse(QPointF(-3, -18), 4.2, 10.5)
        p.restore()

        if pg.boomerang is not None:
            b = pg.boomerang
            p.save()
            p.translate(b.x, b.y)
            p.rotate(math.degrees(b.angle))
            boom_path = QPainterPath()
            boom_path.moveTo(-14, -4)
            boom_path.quadTo(0, -14, 14, -4)
            boom_path.quadTo(17, 0, 12, 3)
            boom_path.quadTo(0, -6, -12, 3)
            boom_path.quadTo(-17, 0, -14, -4)
            p.setPen(QPen(QColor("#fef08a"), 1.4))
            p.setBrush(QColor("#d97706"))
            p.drawPath(boom_path)
            p.restore()

    def _draw_reindeer_model(self, p: QPainter, cycle: float, is_lead: bool):
        bob = math.sin(cycle) * 3.5
        swing = math.sin(cycle) * 7.0

        p.save()
        p.translate(0.0, bob)

        p.setPen(QPen(QColor("#5c2d16"), 2.4,
                 Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(-9, 3), QPointF(-13 - swing, 15))
        p.drawLine(QPointF(-6, 3), QPointF(-5 + swing * 0.6, 15))
        p.drawLine(QPointF(8, 3), QPointF(12 + swing, 14))
        p.drawLine(QPointF(5, 3), QPointF(4 - swing * 0.6, 15))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#854d27"))
        p.drawRoundedRect(QRectF(-13, -6, 25, 11), 5, 5)

        neck = QPolygonF([
            QPointF(6, -4),
            QPointF(14, -15),
            QPointF(19, -12),
            QPointF(12, 2)
        ])
        p.drawPolygon(neck)

        p.setBrush(QColor("#f5ebe6"))
        p.drawEllipse(QPointF(-14, -4), 3.0, 2.0)

        p.setBrush(QColor("#dc2626"))
        p.drawRoundedRect(QRectF(7, -8, 6, 9), 2, 2)
        p.setBrush(QColor("#fbbf24"))
        p.drawEllipse(QPointF(11, -2), 2.0, 2.0)

        p.setBrush(QColor("#854d27"))
        p.drawEllipse(QPointF(17, -15), 6.5, 4.5)
        p.drawEllipse(QPointF(12, -18), 2.2, 3.8)

        antlers = QPainterPath()
        antlers.moveTo(15, -18)
        antlers.lineTo(12, -27)
        antlers.lineTo(8, -29)
        antlers.moveTo(12, -23)
        antlers.lineTo(16, -26)
        antlers.moveTo(17, -18)
        antlers.lineTo(19, -25)
        p.setPen(QPen(QColor("#d6b38c"), 1.6,
                 Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawPath(antlers)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1e293b"))
        p.drawEllipse(QPointF(19, -16), 1.3, 1.3)

        if is_lead:
            glow = QRadialGradient(QPointF(24, -15), 8.0)
            glow.setColorAt(0.0, QColor(255, 50, 50, 230))
            glow.setColorAt(1.0, QColor(255, 50, 50, 0))
            p.setBrush(QBrush(glow))
            p.drawEllipse(QPointF(24, -15), 8.0, 8.0)
            p.setBrush(QColor("#ef4444"))
            p.drawEllipse(QPointF(24, -15), 2.6, 2.6)
        else:
            p.setBrush(QColor("#271206"))
            p.drawEllipse(QPointF(23.5, -15), 1.8, 1.8)

        p.restore()

    def _render_santa(self, p: QPainter, s: SantaSleigh):
        p.save()
        p.translate(s.x, s.y)
        p.rotate(math.degrees(s.angle))
        if s.direction == -1:
            p.scale(-1, 1)

        # Вожжи и олени рисуются вместе с санями только пока сани не подбиты
        if not s.downed:
            reins = QPainterPath()
            reins.moveTo(-14, -15)
            reins.quadTo(12, -2, 34, -10)
            reins.moveTo(34, -10)
            reins.quadTo(58, -2, 82, -11)
            p.setPen(QPen(QColor(253, 224, 71, 200), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(reins)

            for idx, rx in enumerate((30.0, 80.0)):
                p.save()
                p.translate(rx, 0.0)
                self._draw_reindeer_model(
                    p, s.phase * 3.2 + idx * 1.4, is_lead=(idx == 1))
                p.restore()

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#b45309"))
        p.drawEllipse(QPointF(-55, -14), 13, 12)
        p.setBrush(QColor("#3b82f6"))
        p.drawRect(QRectF(-52, -26, 9, 8))
        p.setBrush(QColor("#fde047"))
        p.drawRect(QRectF(-49, -26, 3, 8))

        p.setBrush(QColor("#dc2626"))
        coat = QPainterPath()
        coat.moveTo(-38, -2)
        coat.quadTo(-35, -22, -22, -22)
        coat.quadTo(-12, -20, -12, -2)
        coat.closeSubpath()
        p.drawPath(coat)

        p.setBrush(QColor("#f8fafc"))
        p.drawRoundedRect(QRectF(-30, -21, 14, 4), 2, 2)

        p.setBrush(QColor("#fed7aa"))
        p.drawEllipse(QPointF(-23, -27), 6.0, 6.0)
        p.setBrush(QColor("#f87171"))
        p.drawEllipse(QPointF(-19, -26), 2.2, 1.8)
        p.setBrush(QColor("#0f172a"))
        p.drawEllipse(QPointF(-20, -28.5), 1.2, 1.2)

        beard = QPainterPath()
        beard.moveTo(-26, -24)
        beard.quadTo(-16, -24, -15, -18)
        beard.quadTo(-14, -11, -21, -11)
        beard.quadTo(-28, -12, -26, -24)
        p.setBrush(QColor("#ffffff"))
        p.drawPath(beard)

        hat = QPainterPath()
        hat.moveTo(-29, -30)
        hat.quadTo(-25, -40, -37, -35)
        hat.lineTo(-17, -30)
        hat.closeSubpath()
        p.setBrush(QColor("#dc2626"))
        p.drawPath(hat)

        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(QRectF(-30, -32, 14, 3.5), 1.7, 1.7)
        p.drawEllipse(QPointF(-38, -35), 3.2, 3.2)

        p.setPen(QPen(QColor("#dc2626"), 4.2,
                 Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(-21, -16), QPointF(-13, -15))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#15803d"))
        p.drawEllipse(QPointF(-12, -15), 2.6, 2.6)

        hull = QPainterPath()
        hull.moveTo(-70, -14)
        hull.quadTo(-74, 8, -56, 11)
        hull.lineTo(-12, 11)
        hull.quadTo(2, 11, 6, -6)
        hull.quadTo(0, -4, -6, 1)
        hull.lineTo(-48, 1)
        hull.quadTo(-58, 1, -62, -14)
        hull.closeSubpath()

        hull_grad = QLinearGradient(0, -14, 0, 12)
        hull_grad.setColorAt(0.0, QColor("#e11d48"))
        hull_grad.setColorAt(1.0, QColor("#881337"))
        p.setBrush(QBrush(hull_grad))
        p.setPen(QPen(QColor("#fbbf24"), 1.6))
        p.drawPath(hull)

        runner = QPainterPath()
        runner.moveTo(-74, 17)
        runner.lineTo(4, 17)
        runner.quadTo(15, 17, 14, 6)
        runner.quadTo(13, 1, 8, 4)
        runner.moveTo(-54, 11)
        runner.lineTo(-54, 17)
        runner.moveTo(-20, 11)
        runner.lineTo(-20, 17)
        p.setPen(QPen(QColor("#fcd34d"), 2.2,
                 Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(runner)

        p.restore()

    def _render_tool_indicator(self, p: QPainter):
        if self.active_tool is None:
            return
        gx, gy = self.last_pos.x(), self.last_pos.y()
        p.save()
        p.translate(gx, gy)
        if self.active_tool == "shovel":
            p.setPen(QPen(QColor(56, 189, 248, 190), 1.8, Qt.PenStyle.DashLine))
            p.setBrush(QColor(56, 189, 248, 30))
            p.drawEllipse(QPointF(0, 0), 28, 28)
        elif self.active_tool == "saw":
            p.setPen(QPen(QColor(251, 146, 60, 200), 1.8))
            p.setBrush(QColor(251, 146, 60, 35))
            p.drawEllipse(QPointF(0, 0), 20, 20)
        p.restore()

    def _render_bottom_ui(self, p: QPainter):
        text = self.weather.summary
        font = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
        p.setFont(font)

        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.setBrush(QColor(15, 23, 42, 185))
        p.drawRoundedRect(self.badge_rect, 6, 6)

        p.setPen(QColor(241, 245, 249))
        p.drawText(self.badge_rect, Qt.AlignmentFlag.AlignCenter, text)

        sos_active = bool(self.penguins)
        sos_bg = (
            QColor(234, 88, 12, 230) if (self.sos_btn_hovered or sos_active)
            else QColor(30, 41, 59, 185)
        )
        sos_border = QColor(251, 146, 60) if (
            self.sos_btn_hovered or sos_active) else QColor(255, 255, 255, 40)
        p.setPen(QPen(sos_border, 1))
        p.setBrush(sos_bg)
        p.drawRoundedRect(self.sos_btn_rect, 6, 6)

        p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        p.setPen(QColor(255, 255, 255))
        p.drawText(self.sos_btn_rect, Qt.AlignmentFlag.AlignCenter, "SOS")

        btn_bg = QColor(239, 68, 68, 210) if self.close_btn_hovered else QColor(
            30, 41, 59, 185)
        btn_border = QColor(248, 113, 113) if self.close_btn_hovered else QColor(
            255, 255, 255, 40)

        p.setPen(QPen(btn_border, 1))
        p.setBrush(btn_bg)
        p.drawRoundedRect(self.close_btn_rect, 6, 6)

        p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        p.setPen(QColor(255, 255, 255))
        p.drawText(self.close_btn_rect, Qt.AlignmentFlag.AlignCenter, "✕")
