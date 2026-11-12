"""Linux backend: X11 (and XWayland) window discovery via python-xlib.

Native Wayland does not let ordinary clients enumerate other windows, so
under a Wayland session the app runs through XWayland (see main.py) and only
X11/XWayland windows can carry snow. Desktop icons are not supported on Linux.
"""
import os

try:
    from Xlib import X, display as xdisplay
    from Xlib.error import XError, DisplayError, ConnectionClosedError
    _XLIB_OK = True
except Exception:  # python-xlib missing
    _XLIB_OK = False

from PyQt6.QtCore import Qt

_SKIP_TYPES = (
    "_NET_WM_WINDOW_TYPE_DESKTOP",
    "_NET_WM_WINDOW_TYPE_DOCK",
    "_NET_WM_WINDOW_TYPE_TOOLBAR",
    "_NET_WM_WINDOW_TYPE_MENU",
    "_NET_WM_WINDOW_TYPE_SPLASH",
    "_NET_WM_WINDOW_TYPE_DROPDOWN_MENU",
    "_NET_WM_WINDOW_TYPE_POPUP_MENU",
    "_NET_WM_WINDOW_TYPE_TOOLTIP",
    "_NET_WM_WINDOW_TYPE_NOTIFICATION",
    "_NET_WM_WINDOW_TYPE_COMBO",
    "_NET_WM_WINDOW_TYPE_DND",
)


class _X11:
    def __init__(self):
        self.d = xdisplay.Display()
        # Ошибки от окон, закрытых между запросами, — норма; не спамим в stderr.
        self.d.set_error_handler(lambda *a, **k: None)
        self.root = self.d.screen().root
        a = self.d.intern_atom
        self.A_STACK = a("_NET_CLIENT_LIST_STACKING")
        self.A_LIST = a("_NET_CLIENT_LIST")
        self.A_CUR_DESK = a("_NET_CURRENT_DESKTOP")
        self.A_DESK = a("_NET_WM_DESKTOP")
        self.A_TYPE = a("_NET_WM_WINDOW_TYPE")
        self.A_STATE = a("_NET_WM_STATE")
        self.A_HIDDEN = a("_NET_WM_STATE_HIDDEN")
        self.A_SKIP_TB = a("_NET_WM_STATE_SKIP_TASKBAR")
        self.A_SKIP_PAGER = a("_NET_WM_STATE_SKIP_PAGER")
        self.A_STICKY = a("_NET_WM_STATE_STICKY")
        self.A_ABOVE = a("_NET_WM_STATE_ABOVE")
        self.A_FRAME = a("_NET_FRAME_EXTENTS")
        self.A_GTK_FRAME = a("_GTK_FRAME_EXTENTS")
        self.A_NAME = a("_NET_WM_NAME")
        self.skip_types = {a(n) for n in _SKIP_TYPES}

    def _prop(self, win, atom):
        p = win.get_full_property(atom, X.AnyPropertyType)
        return list(p.value) if p is not None else None

    def windows(self, own_id, ox, oy, sw, sh):
        stack = self._prop(self.root, self.A_STACK) or self._prop(self.root, self.A_LIST) or []
        cur = self._prop(self.root, self.A_CUR_DESK)
        cur_desk = cur[0] if cur else None
        out = []
        # _NET_CLIENT_LIST_STACKING идёт снизу вверх, а движку нужен порядок сверху вниз.
        for wid in reversed(stack):
            if wid == own_id:
                continue
            w = self.d.create_resource_object("window", wid)
            try:
                if w.get_attributes().map_state != X.IsViewable:
                    continue
                types = self._prop(w, self.A_TYPE) or []
                if any(t in self.skip_types for t in types):
                    continue
                states = self._prop(w, self.A_STATE) or []
                if self.A_HIDDEN in states or self.A_SKIP_TB in states:
                    continue
                desk = self._prop(w, self.A_DESK)
                if cur_desk is not None and desk and desk[0] not in (cur_desk, 0xFFFFFFFF):
                    continue
                name = self._prop(w, self.A_NAME)
                if not name and not w.get_wm_name():
                    continue
                g = w.get_geometry()
                pos = self.root.translate_coords(w, 0, 0)
                l, t = pos.x, pos.y
                r, b = l + g.width, t + g.height
                gtk = self._prop(w, self.A_GTK_FRAME)
                if gtk and len(gtk) == 4:
                    # Клиентская декорация GTK: окно включает невидимую тень.
                    l += gtk[0]
                    r -= gtk[1]
                    t += gtk[2]
                    b -= gtk[3]
                else:
                    fr = self._prop(w, self.A_FRAME)
                    if fr and len(fr) == 4:
                        l -= fr[0]
                        r += fr[1]
                        t -= fr[2]
                        b += fr[3]
            except (XError, AttributeError, TypeError):
                continue
            l -= ox
            r -= ox
            t -= oy
            b -= oy
            if r - l < 100 or b - t < 50 or r <= 0 or l >= sw or b <= 0 or t >= sh:
                continue
            out.append((wid, (max(0, l), max(0, t), min(sw, r), min(sh, b))))
        return out

    def set_overlay_state(self, wid):
        """Убираем оверлей из панели задач/пейджера и показываем на всех рабочих столах."""
        from Xlib.protocol import event
        for a1, a2 in ((self.A_SKIP_TB, self.A_SKIP_PAGER), (self.A_STICKY, 0)):
            ev = event.ClientMessage(
                window=self.d.create_resource_object("window", wid),
                client_type=self.A_STATE,
                data=(32, [1, a1, a2, 1, 0]),
            )
            self.root.send_event(
                ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
        # Показывать на всех виртуальных рабочих столах.
        ev = event.ClientMessage(
            window=self.d.create_resource_object("window", wid),
            client_type=self.A_DESK,
            data=(32, [0xFFFFFFFF, 1, 0, 0, 0]),
        )
        self.root.send_event(
            ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
        self.d.flush()

    def has_compositor(self) -> bool:
        sel = self.d.intern_atom("_NET_WM_CM_S%d" % self.d.get_default_screen())
        return self.d.get_selection_owner(sel) != X.NONE


_x11 = None
_x11_failed = False


def _get_x11():
    global _x11, _x11_failed
    if _x11 is None and not _x11_failed:
        if not _XLIB_OK or not os.environ.get("DISPLAY"):
            _x11_failed = True
            return None
        try:
            _x11 = _X11()
        except Exception:
            _x11_failed = True
    return _x11


def init_display_awareness():
    pass


def check_environment() -> str | None:
    """Возвращает текст ошибки, если оверлей не сможет нормально работать."""
    x = _get_x11()
    if x is None:
        if not os.environ.get("WAYLAND_DISPLAY"):
            return "Не найден X11-дисплей (переменная DISPLAY не задана)."
        return None
    if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("NIVALIS_SKIP_CM_CHECK"):
        return None
    try:
        if not x.has_compositor():
            return (
                "Не найден композитный менеджер окон (compositor).\n"
                "Без него прозрачный оверлей закроет весь экран чёрным.\n"
                "Включите композитинг (KWin, Mutter, picom, xfwm4 compositor и т.п.)."
            )
    except Exception:
        pass
    return None


def prepare_overlay_window(widget):
    x = _get_x11()
    if x is None:
        return
    try:
        x.set_overlay_state(int(widget.winId()))
    except Exception:
        pass


def fetch_desktop_icons(screen_w: int, screen_h: int) -> list[tuple[int, int, int, int]]:
    return []


def fetch_visible_windows(own_hwnd: int, screen_w: int, screen_h: int,
                          origin: tuple[int, int] = (0, 0)) -> list[tuple[int, tuple[int, int, int, int]]]:
    global _x11
    x = _get_x11()
    if x is None:
        return []
    try:
        return x.windows(own_hwnd, origin[0], origin[1], screen_w, screen_h)
    except (ConnectionClosedError, DisplayError, OSError):
        _x11 = None
        return []
    except XError:
        return []


def set_window_pass_through(widget, transparent: bool):
    wh = widget.windowHandle()
    if wh is not None:
        wh.setFlag(Qt.WindowType.WindowTransparentForInput, transparent)
