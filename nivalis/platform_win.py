import ctypes
from ctypes import wintypes
import win32gui
import win32con

DWMWA_CLOAKED = 14
LVM_FIRST = 0x1000
LVM_GETITEMCOUNT = LVM_FIRST + 4
LVM_GETITEMRECT = LVM_FIRST + 14
LVIR_BOUNDS = 0
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
MEM_COMMIT = 0x1000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04

def init_display_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

def is_window_cloaked(hwnd: int) -> bool:
    cloaked = ctypes.c_int(0)
    res = ctypes.windll.dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd),
        ctypes.c_uint(DWMWA_CLOAKED),
        ctypes.byref(cloaked),
        ctypes.sizeof(cloaked)
    )
    return res == 0 and cloaked.value != 0

def find_desktop_listview() -> int:
    progman = win32gui.FindWindow("Progman", None)
    def_view = win32gui.FindWindowEx(progman, 0, "SHELLDLL_DefView", None)
    if not def_view:
        def _enum(hwnd, out):
            if win32gui.GetClassName(hwnd) == "WorkerW":
                v = win32gui.FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None)
                if v:
                    out.append(v)
            return True
        found = []
        win32gui.EnumWindows(_enum, found)
        if found:
            def_view = found[0]
    if def_view:
        return win32gui.FindWindowEx(def_view, 0, "SysListView32", None)
    return 0

def fetch_desktop_icons(screen_w: int, screen_h: int) -> list[tuple[int, int, int, int]]:
    rects = []
    lv = find_desktop_listview()
    if lv:
        try:
            cnt = win32gui.SendMessage(lv, LVM_GETITEMCOUNT, 0, 0)
            if 0 < cnt <= 300:
                pid = wintypes.DWORD()
                ctypes.windll.user32.GetWindowThreadProcessId(lv, ctypes.byref(pid))
                proc = ctypes.windll.kernel32.OpenProcess(
                    PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE,
                    False, pid.value
                )
                if proc:
                    try:
                        mem = ctypes.windll.kernel32.VirtualAllocEx(
                            proc, None, ctypes.sizeof(wintypes.RECT), MEM_COMMIT, PAGE_READWRITE
                        )
                        if mem:
                            try:
                                rc = wintypes.RECT()
                                for i in range(cnt):
                                    rc.left = LVIR_BOUNDS
                                    ctypes.windll.kernel32.WriteProcessMemory(
                                        proc, mem, ctypes.byref(rc), ctypes.sizeof(wintypes.RECT), None
                                    )
                                    if win32gui.SendMessage(lv, LVM_GETITEMRECT, i, mem):
                                        ctypes.windll.kernel32.ReadProcessMemory(
                                            proc, mem, ctypes.byref(rc), ctypes.sizeof(wintypes.RECT), None
                                        )
                                        w = rc.right - rc.left
                                        h = rc.bottom - rc.top
                                        if 24 <= w <= 250 and 24 <= h <= 250:
                                            if 0 <= rc.left < screen_w and 0 <= rc.top < screen_h:
                                                pad = max(4, w // 8)
                                                rects.append((rc.left + pad, rc.top + 2, rc.right - pad, rc.bottom))
                            finally:
                                ctypes.windll.kernel32.VirtualFreeEx(proc, mem, 0, MEM_RELEASE)
                    finally:
                        ctypes.windll.kernel32.CloseHandle(proc)
        except Exception:
            pass
    return rects

def fetch_visible_windows(own_hwnd: int, screen_w: int, screen_h: int) -> list[tuple[int, tuple[int, int, int, int]]]:
    wins = []
    ignored = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "NotifyIconOverflowWindow"}
    
    def _cb(hwnd, _):
        if hwnd == own_hwnd or not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
            return True
        if is_window_cloaked(hwnd):
            return True
        if win32gui.GetClassName(hwnd) in ignored:
            return True
        ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if ex & win32con.WS_EX_TOOLWINDOW:
            return True
        if not win32gui.GetWindowText(hwnd):
            return True
        try:
            l, t, r, b = win32gui.GetWindowRect(hwnd)
        except Exception:
            return True
        l += 7
        r -= 7
        w, h = r - l, b - t
        if w < 100 or h < 50 or r <= 0 or l >= screen_w or b <= 0 or t >= screen_h:
            return True
        wins.append((hwnd, (max(0, l), max(0, t), min(screen_w, r), min(screen_h, b))))
        return True

    win32gui.EnumWindows(_cb, None)
    return wins

def set_window_pass_through(hwnd: int, transparent: bool):
    ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    if transparent:
        ex |= win32con.WS_EX_TRANSPARENT | win32con.WS_EX_LAYERED
    else:
        ex &= ~win32con.WS_EX_TRANSPARENT
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex)