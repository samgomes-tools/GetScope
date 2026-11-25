#!/usr/bin/env bash
# Gera GetScope-<versão>-x86_64.AppImage
# Requisitos: python3 (3.10+), pip install PySide6-Essentials pyinstaller "yt-dlp[default]"
#             appimagetool no PATH (ou APPIMAGETOOL=/caminho/appimagetool)
#             ou, sem appimagetool: mksquashfs (pacote squashfs-tools) + runtime oficial do AppImage
#             (baixado automaticamente, ou RUNTIME=/caminho/runtime-x86_64)
# SKIP_APPIMAGE=1 gera só a pasta AppDir.
set -euo pipefail
cd "$(dirname "$0")"
VERSION=$(python3 -c "import re;print(re.search(r'VERSION = \"(.+?)\"', open('getscope/app.py').read()).group(1))")
TOOL=${APPIMAGETOOL:-appimagetool}
YTDLP=$(python3 -c "import yt_dlp;print(yt_dlp.version.__version__)")
python3 -c "import yt_dlp_ejs" || { echo "Instale: pip install 'yt-dlp[default]'"; exit 1; }
echo "GetScope $VERSION · yt-dlp $YTDLP"

# versão do motor embutido (usada para comparar com o motor atualizado pelo usuário)
printf '# Gerado pelo build.sh\nYTDLP_VERSION = "%s"\n' "$YTDLP" > getscope/_bundled.py

rm -rf build AppDir
pyinstaller --noconfirm --clean --onedir --windowed --name getscope \
  --distpath build/dist --workpath build/work --specpath build \
  --collect-all yt_dlp_ejs --collect-submodules yt_dlp --collect-data certifi \
  --hidden-import getscope._bundled \
  --exclude-module tkinter --exclude-module PySide6.QtNetwork --exclude-module PySide6.QtQml \
  --exclude-module PySide6.QtQuick --exclude-module PySide6.QtPdf --exclude-module PySide6.QtOpenGL \
  run.py

INT=build/dist/getscope/_internal
# Mantém Qt, Python, rede (ssl/crypto), sqlite (cookies do navegador) e as libs que o Arch nomeia
# de forma diferente (ICU); o restante (glib, X11, libstdc++, fontconfig…) vem do sistema.
shopt -s nullglob
for f in "$INT"/*.so*; do
  b=$(basename "$f")
  case "$b" in
    libQt6*|libpyside6*|libshiboken6*|libpython3*|libffi.so*|libbz2.so*|liblzma.so*|libexpat.so*|\
    libicu*|libxcb-cursor*|libxcb-icccm*|libxcb-image*|libxcb-keysyms*|libxcb-render-util*|libxcb-util*|\
    libmpdec*|libssl.so*|libcrypto.so*|libsqlite3.so*|libz.so*) ;;
    *) rm -f "$f" ;;
  esac
done
P=$INT/PySide6/Qt/plugins
rm -f "$P"/platformthemes/libqgtk3.so
for x in libqeglfs libqlinuxfb libqminimal libqminimalegl libqvkkhrdisplay libqvnc; do rm -f "$P/platforms/$x.so"; done
rm -rf "$P"/egldeviceintegrations "$INT"/libQt6EglFS* "$INT"/PySide6/Qt/translations

# ícone a partir do logo desenhado no app
QT_QPA_PLATFORM=offscreen python3 -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from getscope.ui.widgets import logo_pixmap
logo_pixmap(256).save('packaging/getscope.png')"

mkdir -p AppDir/usr/bin AppDir/usr/share/applications AppDir/usr/share/icons/hicolor/256x256/apps
cp -a build/dist/getscope AppDir/usr/bin/
cp packaging/AppRun AppDir/AppRun
chmod +x AppDir/AppRun
cp packaging/getscope.desktop AppDir/getscope.desktop
cp packaging/getscope.desktop AppDir/usr/share/applications/
cp packaging/getscope.png AppDir/getscope.png
cp packaging/getscope.png AppDir/usr/share/icons/hicolor/256x256/apps/
ln -sf getscope.png AppDir/.DirIcon

OUT="GetScope-${VERSION}-x86_64.AppImage"
if [ "${SKIP_APPIMAGE:-0}" = 1 ]; then
  echo "Pronto: AppDir/ (AppImage não gerado)"; exit 0
fi
if command -v "${TOOL%% *}" >/dev/null 2>&1; then
  ARCH=x86_64 $TOOL --no-appstream AppDir "$OUT"
else
  command -v mksquashfs >/dev/null || { echo "Instale appimagetool ou squashfs-tools"; exit 1; }
  RUNTIME=${RUNTIME:-build/runtime-x86_64}
  [ -f "$RUNTIME" ] || curl -fsSL -o "$RUNTIME" \
    https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64
  rm -f build/app.squashfs "$OUT"
  mksquashfs AppDir build/app.squashfs -root-owned -noappend -comp zstd -Xcompression-level 19 -b 1M -quiet
  cat "$RUNTIME" build/app.squashfs > "$OUT"
  chmod +x "$OUT"
fi
echo "Pronto: $OUT"
