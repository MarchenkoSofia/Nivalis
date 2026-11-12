#!/usr/bin/env bash
# Запускатор Nivalis для Linux.
# При первом запуске создаёт виртуальное окружение .venv рядом со скриптом
# и ставит зависимости; дальше просто запускает приложение.
#
#   ./nivalis.sh               запустить
#   ./nivalis.sh --background  запустить в фоне и вернуть терминал
#   ./nivalis.sh --reinstall   пересоздать окружение и переустановить зависимости
set -euo pipefail

APP_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
VENV_DIR="$APP_DIR/.venv"
REQ_FILE="$APP_DIR/requirements.txt"
STAMP_FILE="$VENV_DIR/.requirements.sha256"

BACKGROUND=0
REINSTALL=0
APP_ARGS=()
for arg in "$@"; do
    case "$arg" in
        --background|-b) BACKGROUND=1 ;;
        --reinstall) REINSTALL=1 ;;
        -h|--help)
            sed -n '2,8p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) APP_ARGS+=("$arg") ;;
    esac
done

say()  { printf '\033[1;36m[nivalis]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[nivalis]\033[0m %s\n' "$*" >&2; exit 1; }

distro_family() {
    local ids=""
    if [ -r /etc/os-release ]; then
        ids="$(. /etc/os-release; echo "${ID:-} ${ID_LIKE:-}")"
    fi
    case " $ids " in
        *" arch "*|*" cachyos "*|*" manjaro "*|*" endeavouros "*) echo arch ;;
        *" debian "*|*" ubuntu "*) echo debian ;;
        *" fedora "*|*" rhel "*|*" centos "*) echo fedora ;;
        *" opensuse"*|*" suse "*) echo suse ;;
        *) echo unknown ;;
    esac
}

pkg_hint() {
    # $1 debian, $2 arch, $3 fedora, $4 suse
    case "$(distro_family)" in
        debian) echo "sudo apt install $1" ;;
        arch)   echo "sudo pacman -S --needed $2" ;;
        fedora) echo "sudo dnf install $3" ;;
        suse)   echo "sudo zypper install $4" ;;
        *)      echo "установите пакеты: $1 (названия для Debian/Ubuntu)" ;;
    esac
}

# --- Python 3.10+ ---------------------------------------------------------
PYTHON=""
for cand in python3 python3.14 python3.13 python3.12 python3.11 python3.10 python; do
    if command -v "$cand" >/dev/null 2>&1 &&
       "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        PYTHON="$(command -v "$cand")"
        break
    fi
done
[ -n "$PYTHON" ] || fail "Нужен Python 3.10 или новее. $(pkg_hint python3 python python3 python3)"

# --- Системные библиотеки для Qt (xcb) -----------------------------------
if command -v ldconfig >/dev/null 2>&1 && ! ldconfig -p 2>/dev/null | grep 'libxcb-cursor\.so\.0' >/dev/null; then
    say "Внимание: не найдена libxcb-cursor — Qt 6 без неё не запустится под X11/XWayland."
    say "  $(pkg_hint libxcb-cursor0 xcb-util-cursor xcb-util-cursor libxcb-cursor0)"
fi

if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    fail "Не найден графический сеанс (DISPLAY/WAYLAND_DISPLAY не заданы)."
fi
if [ -n "${WAYLAND_DISPLAY:-}" ] && [ -z "${DISPLAY:-}" ]; then
    say "Внимание: сеанс Wayland без XWayland. Снег будет только на «полу», без шапок на окнах."
fi

# --- Виртуальное окружение -----------------------------------------------
if [ "$REINSTALL" = 1 ] && [ -d "$VENV_DIR" ]; then
    say "Удаляю старое окружение..."
    rm -rf "$VENV_DIR"
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
    say "Создаю виртуальное окружение в $VENV_DIR ..."
    if ! "$PYTHON" -m venv "$VENV_DIR" 2>/dev/null; then
        rm -rf "$VENV_DIR"
        fail "Не удалось создать venv. $(pkg_hint python3-venv python python3 python3)"
    fi
fi

req_hash="$(sha256sum "$REQ_FILE" | cut -d' ' -f1)"
if [ ! -f "$STAMP_FILE" ] || [ "$(cat "$STAMP_FILE")" != "$req_hash" ]; then
    say "Устанавливаю зависимости (один раз, может занять минуту)..."
    "$VENV_DIR/bin/python" -m pip install --disable-pip-version-check -q --upgrade pip
    "$VENV_DIR/bin/python" -m pip install --disable-pip-version-check -q -r "$REQ_FILE" \
        || fail "Не удалось установить зависимости. Проверьте интернет и попробуйте ./nivalis.sh --reinstall"
    echo "$req_hash" > "$STAMP_FILE"
fi

# --- Запуск --------------------------------------------------------------
cd "$APP_DIR"
if [ "$BACKGROUND" = 1 ]; then
    LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/nivalis"
    mkdir -p "$LOG_DIR"
    nohup "$VENV_DIR/bin/python" "$APP_DIR/main.py" "${APP_ARGS[@]}" >"$LOG_DIR/nivalis.log" 2>&1 &
    disown
    say "Запущен в фоне (PID $!). Лог: $LOG_DIR/nivalis.log"
else
    exec "$VENV_DIR/bin/python" "$APP_DIR/main.py" "${APP_ARGS[@]}"
fi
