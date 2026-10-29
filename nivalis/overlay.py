import time
import math
import random
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient,
    QRadialGradient, QPolygonF, QFont, QCursor
)
from .config import (
    PHYSICS_FPS, WIN_SCAN_INTERVAL_MS, WIND_FORCE_SCALE,
    TREE_SPAWN_SNOW_THRESHOLD, TREE_MAX_COUNT, TREE_TURBO_MULT
)
from .platform_win import (
    fetch_visible_windows, fetch_desktop_icons, set_window_pass_through
)
from .weather import WeatherEngine
from .physics import SnowLedge, FallingSnowParticle, WaterDrop, PuddleMap
from .entities import PineTree, SantaSleigh
from .tray import TrayManager

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
        self.santa: SantaSleigh | None = None

        self.active_tool: str | None = None
        self.turbo_growth = False
        self.mouse_pressed = False
        self.last_pos = QPointF(0, 0)
        self.mouse_vel = QPointF(0, 0)
        self.last_tick = time.time()
        self.santa_cd = 15.0

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

    def set_active_tool(self, tool_id: str | None):
        self.active_tool = tool_id
        if tool_id is not None:
            set_window_pass_through(self.hwnd, False)
        else:
            set_window_pass_through(self.hwnd, True)

    def force_spawn_santa(self):
        if self.santa is None:
            self.santa = SantaSleigh(self.sw, self.sh)

    def close_application(self):
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
        self.ambient_flakes.append({
            "x": random.uniform(-30, self.sw + 30),
            "y": random.uniform(-20, self.sh) if scatter_y else random.uniform(-30, -5),
            "r": 1.2 + d * 2.8,
            "vy": 35.0 + d * 80.0,
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

        if self.active_tool is None:
            over_santa = (self.santa and not self.santa.downed and self.santa.bounding_box().contains(gx, gy))
            set_window_pass_through(self.hwnd, not over_santa)

        if self.santa and not self.santa.downed:
            spd = math.hypot(self.mouse_vel.x(), self.mouse_vel.y())
            if spd > 950.0 and self.santa.bounding_box().contains(gx, gy):
                self._strike_santa(self.mouse_vel.x(), self.mouse_vel.y())

        if self.mouse_pressed and self.active_tool in ("shovel", "saw"):
            self._execute_tool(gx, gy)

        self.last_pos = QPointF(gx, gy)
        self.weather.update()

        target_count = int(35 + self.weather.intensity * 360)
        while len(self.ambient_flakes) < target_count:
            self._spawn_ambient_flake()

        w_acc = self.weather.wind * WIND_FORCE_SCALE
        win_ledges = list(self.window_ledges.values())

        for f in self.ambient_flakes:
            old_y = f["y"]
            f["phase"] += dt * 2.2
            f["x"] += (w_acc * f["depth"] + math.sin(f["phase"]) * 14.0 + f["vx_off"]) * dt
            f["y"] += f["vy"] * dt

            if f["x"] < -40: f["x"] = self.sw + 35
            elif f["x"] > self.sw + 40: f["x"] = -35

            stuck = False
            fx, fy = f["x"], f["y"]

            if f["depth"] > 0.5:
                for idx, wl in enumerate(win_ledges):
                    if wl.x1 <= fx <= wl.x2:
                        lx = int(fx) - wl.x1
                        sy = wl.y - wl.heights[lx]
                        if old_y <= sy <= fy:
                            w_rc = self.visible_win_rects[idx] if idx < len(self.visible_win_rects) else None
                            if not self._point_occluded(fx, wl.y - 2, exclude_rect=w_rc):
                                if not self.weather.is_thawing:
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
                                if not self.weather.is_thawing:
                                    il.deposit(fx, 0.75, rad=6)
                                stuck = True
                            break

            if not stuck and 0 <= int(fx) < self.sw:
                gy_surf = self.ground.y - self.ground.heights[int(fx)]
                if fy >= gy_surf:
                    if not self.weather.is_thawing:
                        self.ground.deposit(fx, 1.1, rad=12)
                    stuck = True

            if stuck or fy > self.sh + 15:
                f["y"] = random.uniform(-25, -5)
                f["x"] = random.uniform(0, self.sw)

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
                        il.deposit(p.x, p.mass, rad=5)
                        p.alive = False
                        break
            if not p.alive:
                continue

            if 0 <= int(p.x) < self.sw:
                if p.y >= self.ground.y - self.ground.heights[int(p.x)]:
                    self.ground.deposit(p.x, p.mass, rad=10)
                    p.alive = False

        self.falling_snow = [p for p in self.falling_snow if p.alive]

        self.ground.smooth()
        for wl in win_ledges: wl.smooth()
        for il in self.icon_ledges: il.smooth()

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
                    self.ground.heights[i] = max(0.0, self.ground.heights[i] - melt)
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
        self._update_fauna(dt)

        for pt in self.particles:
            pt["vy"] += GRAVITY * dt * 0.4
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
        if not self.weather.is_thawing and len(self.trees) < TREE_MAX_COUNT and random.random() < 0.03:
            rx = random.randint(80, self.sw - 80)
            if self.ground.heights[rx] > TREE_SPAWN_SNOW_THRESHOLD:
                if all(abs(t.x - rx) > 130 for t in self.trees):
                    self.trees.append(PineTree(rx, self.sh))

        rate = TREE_TURBO_MULT if self.turbo_growth else 1.0
        for t in self.trees:
            t.step(dt, rate, self.weather.is_thawing)
        self.trees = [t for t in self.trees if t.alpha > 0.05]

    def _update_fauna(self, dt: float):
        ready = any(t.lights_active and not t.is_falling for t in self.trees)
        if self.santa is None:
            if ready:
                self.santa_cd -= dt
                if self.santa_cd <= 0:
                    self.santa = SantaSleigh(self.sw, self.sh)
                    self.santa_cd = random.uniform(20.0, 40.0)
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
        self.santa.strike(vx, vy)
        for _ in range(20):
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
            if gy > self.sh - 140:
                lx = int(gx)
                for i in range(max(0, lx - 32), min(self.sw, lx + 32)):
                    d = 1.0 - (abs(i - lx) / 32)
                    self.ground.heights[i] = max(0.0, self.ground.heights[i] - 7.0 * d)
                for _ in range(3):
                    self.particles.append({
                        "x": gx + random.uniform(-15, 15),
                        "y": self.sh - 10,
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
                if abs(gx - t.x) < 38 and (t.base_y - th - 15) <= gy <= t.base_y:
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

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            gx, gy = pos.x(), pos.y()
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

        for t in self.trees:
            self._render_tree(p, t)

        self._render_ledge(p, self.ground)

        for pr in self.presents:
            p.save()
            p.translate(pr["x"], pr["y"])
            p.rotate(math.degrees(pr["rot"]))
            p.setPen(QPen(QColor(255, 255, 255, 160), 1))
            p.setBrush(pr["col"])
            p.drawRoundedRect(QRectF(-7, -7, 14, 14), 2, 2)
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
        self._render_weather_badge(p)

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

        g = QLinearGradient(0, ledge.y - ledge.max_capacity, 0, ledge.y + 3)
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
        y_pos = self.sh - self.ground.heights[gx] * 0.4
        p.translate(t.x, y_pos)
        p.rotate(math.degrees(t.fall_angle))
        p.setOpacity(max(0.0, t.alpha))

        h = t.max_h * t.growth
        w = h * 0.55

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#452915"))
        p.drawRect(QRectF(-w * 0.08, -h * 0.2, w * 0.16, h * 0.22))

        for i in range(t.tiers):
            fc = i / t.tiers
            tb = -h * (0.15 + fc * 0.68)
            tt = -h * (0.42 + fc * 0.58)
            tw = w * (1.0 - fc * 0.6)
            branch = QPolygonF([QPointF(0, tt), QPointF(-tw * 0.5, tb), QPointF(tw * 0.5, tb)])
            p.setBrush(QColor(18, 86 - i * 8, 48))
            p.drawPolygon(branch)

        if t.lights_active:
            now = time.time()
            cols = [QColor("#f43f5e"), QColor("#fbbf24"), QColor("#34d399"), QColor("#38bdf8")]
            for li in range(12):
                lf = (li + 1) / 13.0
                ly = -h * (0.2 + lf * 0.7)
                lx = math.sin(li * 2.2 + t.seed) * (w * (1.0 - lf * 0.7) * 0.35)
                c = cols[(li + int(now * 3)) % len(cols)]
                p.setBrush(c)
                p.drawEllipse(QPointF(lx, ly), 3.0, 3.0)

            p.setBrush(QColor("#fde047"))
            p.drawEllipse(QPointF(0, -h), 4.5, 4.5)

        p.restore()

    def _render_santa(self, p: QPainter, s: SantaSleigh):
        p.save()
        p.translate(s.x, s.y)
        p.rotate(math.degrees(s.angle))
        if s.direction == -1:
            p.scale(-1, 1)

        p.setPen(QPen(QColor("#fcd34d"), 2.0))
        p.setBrush(QColor("#be123c"))
        p.drawRoundedRect(QRectF(-60, -10, 52, 24), 5, 5)
        p.drawLine(-66, 17, -2, 17)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#d97706"))
        p.drawEllipse(QPointF(-48, -14), 11, 11)
        p.setBrush(QColor("#e11d48"))
        p.drawEllipse(QPointF(-26, -16), 11, 13)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QPointF(-21, -21), 6, 7)
        p.setBrush(QColor("#fecdd3"))
        p.drawEllipse(QPointF(-23, -25), 4, 4)

        p.setPen(QPen(QColor(254, 243, 199, 170), 1.2))
        p.drawLine(-8, -2, 60, -2)

        for rx in (22, 62):
            lp = math.sin(s.phase * 2.5 + rx) * 4.5
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#78350f"))
            p.drawRoundedRect(QRectF(rx - 12, -7 + lp, 24, 12), 3, 3)
            p.drawEllipse(QPointF(rx + 12, -12 + lp), 6, 5)
            if rx == 62:
                p.setBrush(QColor("#ef4444"))
                p.drawEllipse(QPointF(rx + 18, -12 + lp), 3.0, 3.0)

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

    def _render_weather_badge(self, p: QPainter):
        text = self.weather.summary
        font = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
        p.setFont(font)

        badge_w = 150
        badge_h = 28
        badge_x = self.sw - badge_w - 14
        badge_y = self.sh - badge_h - 48

        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.setBrush(QColor(15, 23, 42, 175))
        p.drawRoundedRect(QRectF(badge_x, badge_y, badge_w, badge_h), 6, 6)

        p.setPen(QColor(241, 245, 249))
        p.drawText(
            QRectF(badge_x, badge_y, badge_w, badge_h),
            Qt.AlignmentFlag.AlignCenter,
            text
        )