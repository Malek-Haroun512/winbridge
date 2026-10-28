"""Prepare host-side VM settings and generate the in-guest setup script."""

from __future__ import annotations

import http.server
import tempfile
import threading
import time
from pathlib import Path

from . import config as cfgmod
from . import vbox
from .i18n import t

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
) else (
  echo [5/6] Skipping password change ^(empty password^).
)
REM Never store the password or log the console in automatically: WinBridge
REM opens its own RDP session, and a second auto-logon would bump it off.
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v AutoAdminLogon /t REG_SZ /d 0 /f >nul
reg delete "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultPassword /f >nul 2>&1

echo [6/6] Checking listener ...
netstat -an | findstr ":3389" | findstr LISTENING

echo.
echo Done. You can close this window and return to WinBridge on Linux.
echo The machine name is:
hostname
echo.
__NOTIFY__
__PAUSE__
"""


def instructions() -> str:
    """Guest preparation steps, in the active interface language."""
    return t("instructions_guest")


def render_guest_script(cfg: cfgmod.Config, nla: bool = True,
                        interactive: bool = True,
                        notify_port: int | None = None) -> str:
    """Render the guest script.

    ``interactive`` keeps the final "press any key" prompt (manual run);
    ``notify_port`` makes the script call back to the host when it finishes so
    the automated provisioning can tell whether it really ran.
    """
    pause = "pause" if interactive else "rem done"
    notify = ""
    if notify_port:
        # PowerShell is present on every supported Windows build, while
        # curl.exe is missing from some stripped-down images.
        notify = (
            f'powershell -NoProfile -ExecutionPolicy Bypass -Command "'
            f"iwr http://10.0.2.2:{notify_port}/done -UseBasicParsing "
            f'-TimeoutSec 5 | Out-Null" >nul 2>&1'
        )
    return (
        SETUP_SCRIPT.replace("__USER__", cfg.user or "Admin")
        .replace("__PASSWORD__", cfg.password or "")
        .replace("__NLA__", "1" if nla else "0")
        .replace("__PAUSE__", pause)
        .replace("__NOTIFY__", notify)
    )


def write_guest_script(cfg: cfgmod.Config, directory: Path | None = None,
                       nla: bool = True, interactive: bool = True,
                       notify_port: int | None = None) -> Path:
    target = (directory or cfgmod.config_dir()) / "winbridge-setup.cmd"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        render_guest_script(cfg, nla=nla, interactive=interactive,
                            notify_port=notify_port),
        "utf-8", newline="\r\n",
    )
    return target


def prepare_host(vm: str, cfg: cfgmod.Config, log=print) -> None:
    """Apply every host-side setting needed for RDP + USB.

    A running VM is only shut down when something really has to change; when
    the port forward and USB controller are already in place ``winbridge
    setup`` can provision the guest without an extra reboot.
    """
    info = vbox.machine_info(vm)
    forward_ok = vbox.port_forward_exists(
        vm, cfg.port, guest_port=cfg.guest_port, host_ip=cfg.host
    )
    usb_ok = info.get("usb") == "on"
    must_change = not (forward_ok and usb_ok)

    if must_change and vbox.is_running(vm):
        log(t("log_stopping_vm"))
        if not vbox.acpi_power_button(vm, timeout=30):
            log(t("log_acpi_failed"))
            if not vbox.guest_shutdown(vm, cfg.user, cfg.password):
                raise vbox.VBoxError(t("err_poweroff_failed"))

    if forward_ok:
        log(t("log_forward_exists"))
    else:
        log(t("log_adding_forward"))
        added = vbox.ensure_port_forward(
            vm, cfg.port, guest_port=cfg.guest_port, host_ip=cfg.host
        )
        log(t("log_forward_added") if added else t("log_forward_exists"))

    if usb_ok:
        log(f"  {t('usb_controller_present')}")
    else:
        log(t("log_usb_enable"))
        try:
            log(f"  {vbox.ensure_usb_controller(vm)}")
        except vbox.VBoxError as exc:
            log(t("log_warning", message=exc))
    if not vbox.has_usb_extpack():
        log(t("log_extpack_missing"))


# --------------------------------------------------------------- automatic setup

# Scancodes (set 1) used to drive the Windows console without Guest Additions.
SC_ENTER = ("1c", "9c")
SC_ESC = ("01", "81")
SC_SPACE = ("39", "b9")
SC_WIN_L = ("e0", "5b", "26", "a6", "e0", "db")
SC_WIN_X = ("e0", "5b", "2d", "ad", "e0", "db")
SC_ALT_Y = ("38", "15", "95", "b8")
SC_KEY_A = ("1e", "9e")
SC_CTRL_A = ("1d", "1e", "9e", "9d")
SC_DELETE = ("e0", "53", "e0", "d3")


class _SetupServer(http.server.ThreadingHTTPServer):
    """Serves the guest script and records the "done" call-back."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, bind: str = "127.0.0.1"):
        super().__init__((bind, 0), _SetupHandler)
        self.payload = b""
        self.done = threading.Event()

    @property
    def port(self) -> int:
        return self.server_address[1]

    def serve_forever_in_thread(self) -> threading.Thread:
        thread = threading.Thread(target=self.serve_forever, daemon=True)
        thread.start()
        return thread


class _SetupHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server API
        if self.path.startswith("/done"):
            self.server.done.set()  # type: ignore[attr-defined]
            body = b"ok"
        else:
            body = self.server.payload  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence the default stderr logging
        pass


def guest_control_ready(vm: str) -> bool:
    """True when Guest Additions are running and can execute processes."""
    level, version = vbox.guest_additions(vm)
    return level >= 2 and bool(version)


def _run_via_guestcontrol(cfg: cfgmod.Config, script: Path, log,
                          done: threading.Event | None = None) -> bool:
    """Copy the script into Windows and run it elevated through Guest Additions.

    Guest Additions start processes with the caller's filtered token, so a
    normal administrator would hit UAC.  A one-shot scheduled task with
    ``/rl HIGHEST`` runs the script with the full token without a prompt.
    """
    remote = r"C:\Windows\Temp\winbridge-setup.cmd"
    task = "WinBridgeSetup"
    credentials = [f"--username={cfg.user}", f"--password={cfg.password}"]
    log(t("log_provision_service"))
    try:
        vbox.run(
            ["guestcontrol", cfg.vm, "copyto", *credentials, str(script), remote],
            timeout=60,
        )
        for args in (
            [
                "/create", "/tn", task, "/tr", remote,
                "/sc", "once", "/st", "00:00", "/rl", "HIGHEST",
                "/ru", cfg.user, "/rp", cfg.password, "/f",
            ],
            ["/run", "/tn", task],
        ):
            output = vbox.run(
                [
                    "guestcontrol", cfg.vm, "run", *credentials,
                    r"--exe=C:\Windows\System32\schtasks.exe",
                    "--timeout=60000", "--wait-stdout", "--wait-stderr",
                    "--", *args,
                ],
                timeout=90, check=False,
            )
            if "guest execution service is not ready" in output.lower():
                return False
            if "access is denied" in output.lower():
                # The account is not an administrator: the console route
                # (which can accept UAC) is the only option.
                return False
    except vbox.VBoxError as exc:
        log(f"  {exc}")
        return False

    success = bool(done and done.wait(150))
    # Remove the one-shot task; the running copy keeps going.
    vbox.run(
        [
            "guestcontrol", cfg.vm, "run", *credentials,
            r"--exe=C:\Windows\System32\schtasks.exe",
            "--timeout=30000",
            "--", "/delete", "/tn", task, "/f",
        ],
        timeout=45, check=False,
    )
    return success


def wait_for_boot(log=print, seconds: int = 90) -> None:
    """Give a freshly started Windows time to reach the logon screen.

    There is no reliable host-side "boot finished" signal without Guest
    Additions, so this is deliberately a fixed, conservative wait.  The
    console automation needs a live logon screen; typing earlier is lost.
    """
    log(t("log_waiting_boot", seconds=seconds))
    time.sleep(seconds)


def _type(vm: str, text: str) -> None:
    vbox.keyboard_text(vm, text)


def _press(vm: str, *codes: str) -> None:
    vbox.keyboard_scancode(vm, *codes)


def _open_admin_shell(cfg: cfgmod.Config) -> None:
    """Bring Windows to an elevated PowerShell (Win+X, A).

    Locking first makes the flow identical whether Windows is sitting at the
    logon screen or on an unlocked desktop: the password always lands in the
    credential box instead of the Start-menu search or the active app.  The
    spaces/selection keys clear the field in case a keystroke was consumed by
    the lock-screen wallpaper.  Finally accept the UAC prompt.
    """
    _press(cfg.vm, *SC_ESC)            # close menus and error dialogs
    time.sleep(1.0)
    _press(cfg.vm, *SC_WIN_L)          # lock (no-op at the logon screen)
    time.sleep(2.0)
    _press(cfg.vm, *SC_SPACE)          # dismiss the lock-screen wallpaper
    time.sleep(1.0)
    _press(cfg.vm, *SC_CTRL_A)         # clear any stray characters
    _press(cfg.vm, *SC_DELETE)
    time.sleep(0.5)
    if cfg.password:
        _type(cfg.vm, cfg.password)
    _press(cfg.vm, *SC_ENTER)          # sign in / unlock
    time.sleep(12.0)
    _press(cfg.vm, *SC_WIN_X)
    time.sleep(2.5)
    _press(cfg.vm, *SC_KEY_A)          # "Terminal/PowerShell (Admin)"
    time.sleep(4.5)
    _press(cfg.vm, *SC_ALT_Y)          # "Yes" on the UAC consent dialog
    time.sleep(6.0)


def _console_bootstrap(cfg: cfgmod.Config, port: int, log) -> None:
    log(t("log_provision_console"))
    _open_admin_shell(cfg)
    name = "winbridge-setup.cmd"
    remote = rf"C:\Windows\Temp\{name}"
    _type(
        cfg.vm,
        f"iwr http://10.0.2.2:{port}/{name} -OutFile {remote} -UseBasicParsing",
    )
    _press(cfg.vm, *SC_ENTER)
    time.sleep(5.0)
    _type(cfg.vm, remote)
    _press(cfg.vm, *SC_ENTER)


def provision(cfg: cfgmod.Config, log=print, timeout: int = 240) -> bool:
    """Configure Windows without anyone touching the VM.

    Returns True when the guest script really ran inside Windows.
    """
    if not cfg.vm:
        return False
    if not (cfg.user and cfg.password):
        return False

    server = _SetupServer()
    server.serve_forever_in_thread()
    workdir = tempfile.TemporaryDirectory(prefix="winbridge-")
    try:
        script = write_guest_script(
            cfg, directory=Path(workdir.name), interactive=False,
            notify_port=server.port,
        )
        server.payload = script.read_bytes()

        if guest_control_ready(cfg.vm) and _run_via_guestcontrol(
            cfg, script, log, done=server.done
        ):
            log(t("log_provision_done"))
            return True

        _console_bootstrap(cfg, server.port, log)
        if server.done.wait(timeout):
            log(t("log_provision_done"))
            return True
        log(t("log_provision_timeout"))
        return False
    finally:
        server.shutdown()
        server.server_close()
        workdir.cleanup()
