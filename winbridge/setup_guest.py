"""Prepare host-side VM settings and generate the in-guest setup script."""

from __future__ import annotations

from pathlib import Path

from . import config as cfgmod
from . import vbox

SETUP_SCRIPT = r"""@echo off
setlocal
REM ===================================================================
REM  WinBridge guest setup  (run once, as Administrator, inside Windows)
REM  Enables RDP + RemoteApp (RAIL) + firewall so Linux can run your
REM  Windows apps as native windows.
REM ===================================================================
set "WB_USER=__USER__"
set "WB_PASS=__PASSWORD__"

net session >nul 2>&1
if errorlevel 1 (
  echo [!] This script must run as Administrator.
  echo     Right click ^> "Run as administrator".
  pause
  exit /b 1
)

echo [1/6] Enabling Remote Desktop ...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 0 /f >nul

echo [2/6] Allowing password logon / TLS layer ...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Lsa" /v LimitBlankPasswordUse /t REG_DWORD /d 0 /f >nul
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp" /v UserAuthentication /t REG_DWORD /d __NLA__ /f >nul
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp" /v SecurityLayer /t REG_DWORD /d 1 /f >nul

echo [3/6] Opening firewall ...
netsh advfirewall firewall set rule group="remote desktop" new enable=Yes >nul

echo [4/6] Allowing any application to be published (RAIL) ...
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Terminal Server\TSAppAllowList" /v fDisabledAllowList /t REG_DWORD /d 1 /f >nul

if not "%WB_PASS%"=="" (
  echo [5/6] Setting account password ...
  net user "%WB_USER%" "%WB_PASS%"
  reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultUserName /t REG_SZ /d "%WB_USER%" /f >nul
  reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultPassword /t REG_SZ /d "%WB_PASS%" /f >nul
  reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v AutoAdminLogon /t REG_SZ /d 1 /f >nul
) else (
  echo [5/6] Skipping password change ^(empty password^).
)

echo [6/6] Checking listener ...
netstat -an | findstr ":3389" | findstr LISTENING

echo.
echo Done. You can close this window and return to WinBridge on Linux.
echo The machine name is:
hostname
echo.
pause
"""

INSTRUCTIONS = """\
جهّز النسخة داخل ويندوز:

1. اضغط «تشغيل الجهاز نافذةً» لفتح شاشة VirtualBox.
2. سجّل الدخول إلى ويندوز.
3. انسخ الملف `winbridge-setup.cmd` إلى ويندوز (مثلًا عبر السحب والإفلات
   أو المجلد المشترك) وشغّله كمسؤول (Run as administrator).
4. ارجع إلى WinBridge واضغط «اختبر الاتصال».
"""


def render_guest_script(cfg: cfgmod.Config, nla: bool = False) -> str:
    return (
        SETUP_SCRIPT.replace("__USER__", cfg.user or "Admin")
        .replace("__PASSWORD__", cfg.password or "")
        .replace("__NLA__", "1" if nla else "0")
    )


def write_guest_script(cfg: cfgmod.Config, directory: Path | None = None,
                       nla: bool = False) -> Path:
    target = (directory or cfgmod.config_dir()) / "winbridge-setup.cmd"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_guest_script(cfg, nla=nla), "utf-8", newline="\r\n")
    return target


def prepare_host(vm: str, cfg: cfgmod.Config, log=print) -> None:
    """Apply every host-side setting needed for RDP + USB."""
    if vbox.is_running(vm):
        log("إطفاء الجهاز لتعديل إعداداته …")
        if not vbox.acpi_power_button(vm, timeout=30):
            log("  ACPI لم ينجح — محاولة عبر Guest Additions …")
            if not vbox.guest_shutdown(vm, cfg.user, cfg.password):
                raise vbox.VBoxError(
                    "تعذّر إطفاء الجهاز. أطفئه يدويًا من VirtualBox ثم أعد المحاولة."
                )

    log("إضافة تحويل منفذ RDP …")
    added = vbox.ensure_port_forward(
        vm, cfg.port, guest_port=cfg.guest_port, host_ip=cfg.host
    )
    log("  منفذ جديد أُضيف" if added else "  المنفذ موجود مسبقًا")

    log("تفعيل وحدة USB …")
    try:
        log(f"  {vbox.ensure_usb_controller(vm)}")
    except vbox.VBoxError as exc:
        log(f"  تحذير: {exc}")
    if not vbox.has_usb_extpack():
        log("  ملاحظة: Extension Pack غير مثبّت ← USB 1.1 فقط.")
