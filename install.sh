#!/usr/bin/env bash
# WinBridge installer — installs into the current user's home (no root needed).
# Works offline: the isolated venv reuses system PySide6 and links this checkout.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN="${XDG_BIN_HOME:-$HOME/.local/bin}"
VENV="$DATA/winbridge/venv"

say() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }

say "التحقق من المتطلبات"
missing=0
for cmd in VBoxManage python3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    warn "مفقود: $cmd   (sudo pacman -S virtualbox virtualbox-host-modules-arch)"
    missing=1
  fi
done
if ! command -v xfreerdp3 >/dev/null 2>&1 && ! command -v xfreerdp >/dev/null 2>&1; then
  warn "مفقود: FreeRDP   (sudo pacman -S freerdp)"
  missing=1
fi
python3 -c 'import PySide6' 2>/dev/null || { warn "مفقود: PySide6   (sudo pacman -S pyside6)"; missing=1; }
[ "$missing" -eq 1 ] && warn "أكمل المتطلبات ثم أعد تشغيل السكربت (سأكمل التثبيت على أي حال)."

say "إنشاء بيئة Python معزولة في $VENV"
python3 -m venv --system-site-packages "$VENV"

say "ربط الشيفرة المصدرية بـ $SRC"
SITE="$("$VENV/bin/python" -c 'import site; print(site.getsitepackages()[0])')"
echo "$SRC" > "$SITE/winbridge.pth"

say "تثبيت الأمر $BIN/winbridge"
mkdir -p "$BIN"
cat > "$BIN/winbridge" <<EOF
#!/usr/bin/env bash
exec "$VENV/bin/python" -m winbridge "\$@"
EOF
chmod +x "$BIN/winbridge"

say "تثبيت الاختصار والأيقونة"
mkdir -p "$DATA/applications" "$DATA/icons/hicolor/scalable/apps"
install -m644 "$SRC/data/winbridge.desktop" "$DATA/applications/winbridge.desktop"
install -m644 "$SRC/assets/winbridge.svg" "$DATA/icons/hicolor/scalable/apps/winbridge.svg"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$DATA/applications" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "$DATA/icons/hicolor" >/dev/null 2>&1 || true
command -v kbuildsycoca6 >/dev/null 2>&1 && kbuildsycoca6 --noincremental >/dev/null 2>&1 || true

say "تم. جرّب:  winbridge doctor  ثم  winbridge tray"
