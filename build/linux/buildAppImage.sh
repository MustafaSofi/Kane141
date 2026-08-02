#!/bin/bash
# Builds Kane141 into a .AppImage using PyInstaller + appimagetool.
# Run this from the repo root: ./build/linux/buildAppImage.sh
set -e

APP_NAME="Kane141"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
APPDIR="$ROOT_DIR/$APP_NAME.AppDir"
APPIMAGETOOL="$ROOT_DIR/build/linux/appimagetool.AppImage"

cd "$ROOT_DIR"

echo "==> Installing PyInstaller (if needed)"
pip install --quiet pyinstaller

echo "==> Cleaning old build artifacts"
rm -rf build/Kane141 "$DIST_DIR/$APP_NAME" "$APPDIR"

echo "==> Freezing the app with PyInstaller"
pyinstaller --noconfirm "$APP_NAME.spec"

if [ ! -d "$DIST_DIR/$APP_NAME" ]; then
    echo "ERROR: PyInstaller did not produce dist/$APP_NAME — check the output above."
    exit 1
fi

echo "==> Assembling AppDir"
mkdir -p "$APPDIR/usr/bin"
cp -r "$DIST_DIR/$APP_NAME/"* "$APPDIR/usr/bin/"

cat > "$APPDIR/AppRun" << EOF
#!/bin/bash
HERE="\$(dirname "\$(readlink -f "\${0}")")"
exec "\$HERE/usr/bin/$APP_NAME" "\$@"
EOF
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/$APP_NAME.desktop" << EOF
[Desktop Entry]
Name=$APP_NAME
Exec=$APP_NAME
Icon=$APP_NAME
Type=Application
Categories=Game;
Terminal=false
EOF

if [ -f "$ROOT_DIR/$APP_NAME.png" ]; then
    cp "$ROOT_DIR/$APP_NAME.png" "$APPDIR/$APP_NAME.png"
else
    echo "WARNING: no icon found at $ROOT_DIR/$APP_NAME.png — the AppImage will have a blank icon."
fi

echo "==> Fetching appimagetool (if needed)"
if [ ! -f "$APPIMAGETOOL" ]; then
    wget -O "$APPIMAGETOOL" "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$APPIMAGETOOL"
fi

echo "==> Building the AppImage"
mkdir -p "$DIST_DIR"
"$APPIMAGETOOL" "$APPDIR" "$DIST_DIR/$APP_NAME-x86_64.AppImage"

echo ""
echo "==> Done: $DIST_DIR/$APP_NAME-x86_64.AppImage"
