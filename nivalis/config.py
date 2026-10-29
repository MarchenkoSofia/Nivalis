APP_NAME = "Nivalis"
APP_VERSION = "1.2.0"

DPI_AWARENESS_CONTEXT = -4
WIN_SCAN_INTERVAL_MS = 500
PHYSICS_FPS = 60

GRAVITY = 750.0
WIND_FORCE_SCALE = 65.0

MAX_WINDOW_SNOW = 32.0
MAX_ICON_SNOW = 16.0
MAX_GROUND_SNOW = 110.0

PUDDLE_DIFFUSION_RATE = 0.38
PUDDLE_DRAIN_EDGE_RATE = 0.18


class RuntimeSettings:
    def __init__(self):
        self.manual_weather = False
        self.manual_temperature = -4.0
        self.temp_offset = 0.0
        self.cpu_chill_gain = 6.0
        self.manual_intensity = 0.45

        self.tree_snow_threshold = 38.0
        self.tree_max_count = 10
        self.tree_growth_speed = 1.0

        self.santa_require_lit_tree = True
        self.santa_min_interval = 20.0


SETTINGS = RuntimeSettings()
