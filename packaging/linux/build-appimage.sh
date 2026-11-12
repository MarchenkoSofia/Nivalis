#!/usr/bin/env bash
# Сборка Nivalis-<версия>-<arch>.AppImage.
# Ожидает, что Python с зависимостями из requirements.txt и pyinstaller уже стоят
# (PYTHON=путь/к/python, по умолчанию python3). Результат кладёт в dist/.
set -euo pipefail

ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../.." && pwd)"
PYTHON="${PYTHON:-python3}"
ARCH="${ARCH:-$(uname -m)}"
BUILD="$ROOT/build/appimage"
APPDIR="$BUILD/AppDir"
TOOLS="$BUILD/tools"
VERSION="${VERSION:-$("$PYTHON" -c 'import sys; sys.path.insert(0, sys.argv[1]); from nivalis.config import APP_VERSION; print(APP_VERSION)' "$ROOT")}"

cd "$ROOT"
rm -rf "$APPDIR" "$BUILD/pyinstaller"
mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps" "$TOOLS" "$ROOT/dist"

echo "==> PyInstaller (onedir)"
"$PYTHON" -m PyInstaller --noconfirm --clean --windowed --onedir \
    --name nivalis \
    --collect-submodules Xlib \
    --distpath "$BUILD/pyinstaller/dist" \
    --workpath "$BUILD/pyinstaller/work" \
    --specpath "$BUILD/pyinstaller" \
    main.py
cp -a "$BUILD/pyinstaller/dist/nivalis" "$APPDIR/usr/lib/nivalis"

echo "==> AppDir"
install -m 755 packaging/linux/AppRun "$APPDIR/AppRun"
install -m 644 packaging/linux/nivalis.desktop "$APPDIR/nivalis.desktop"
install -m 644 packaging/linux/nivalis.desktop "$APPDIR/usr/share/applications/nivalis.desktop"
"$PYTHON" packaging/linux/make_icon.py "$APPDIR/nivalis.png" 256
cp "$APPDIR/nivalis.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/nivalis.png"
ln -sf nivalis.png "$APPDIR/.DirIcon"

APPIMAGETOOL="${APPIMAGETOOL:-$TOOLS/appimagetool-$ARCH.AppImage}"
if [ ! -x "$APPIMAGETOOL" ]; then
    echo "==> Скачиваю appimagetool"
    curl -fsSL -o "$APPIMAGETOOL" \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$ARCH.AppImage"
    chmod +x "$APPIMAGETOOL"
fi

OUT="$ROOT/dist/Nivalis-$VERSION-$ARCH.AppImage"
echo "==> appimagetool -> $OUT"
# --appimage-extract-and-run: не требует FUSE на машине сборки (CI, контейнеры).
ARCH="$ARCH" "$APPIMAGETOOL" --appimage-extract-and-run --no-appstream "$APPDIR" "$OUT"
echo "Готово: $OUT"
