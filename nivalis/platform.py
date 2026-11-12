"""Выбор платформенного бэкенда (Windows / Linux)."""
import sys

if sys.platform == "win32":
    from .platform_win import (  # noqa: F401
        init_display_awareness, check_environment, prepare_overlay_window,
        fetch_desktop_icons, fetch_visible_windows, set_window_pass_through,
    )
else:
    from .platform_linux import (  # noqa: F401
        init_display_awareness, check_environment, prepare_overlay_window,
        fetch_desktop_icons, fetch_visible_windows, set_window_pass_through,
    )
