"""FreeRDP launcher: full desktop or single application (RAIL) windows."""

from __future__ import annotations

import shutil
import socket
import subprocess
import time
from pathlib import Path

from . import config as cfgmod
from . import vbox

CANDIDATES = ("xfreerdp3", "xfreerdp", "wlfreerdp")


class RdpError(RuntimeError):
    pass


def freerdp_bin() -> str:
    for name in CANDIDATES:
        path = shutil.which(name)
        if path:
            return path
    raise RdpError(
        "لم أجد FreeRDP. ثبّته بالأمر:\n  sudo pacman -S freerdp"
    )


def port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_port(host: str, port: int, timeout: float = 180.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_open(host, port):
            return True
        time.sleep(2)
    return False


def ensure_vm_running(cfg: cfgmod.Config, log=print) -> None:
    if not cfg.vm:
        raise RdpError("لم يتم اختيار جهاز VirtualBox بعد (Settings ← VM).")
    if vbox.is_running(cfg.vm):
        return
    if not cfg.start_vm:
        raise RdpError(f"الجهاز {cfg.vm} متوقف. شغّله أو فعّل التشغيل التلقائي.")
    log(f"تشغيل {cfg.vm} …")
    vbox.start_headless(cfg.vm)
    deadline = time.time() + 240
    while time.time() < deadline:
        if port_open(cfg.host, cfg.port):
            return
        time.sleep(3)
    raise RdpError(
        "الجهاز أقلع لكن منفذ RDP ما فتح. تأكد من تفعيل RDP داخل ويندوز "
        "(زر «جهّز الجهاز» في الإعدادات)."
    )


def base_args(cfg: cfgmod.Config) -> list[str]:
    return [
        f"/v:{cfg.host}:{cfg.port}",
        f"/u:{cfg.user}",
        f"/p:{cfg.password}",
        "/cert:tofu",
        "/sec:tls",
        "+clipboard",
        "-wallpaper",
        f"/drive:home,{Path.home()}",
        "+auto-reconnect",
    ]


def build_command(cfg: cfgmod.Config, app: str | None = None,
                  name: str | None = None, size: str = "1600x900") -> list[str]:
    args = [freerdp_bin(), *base_args(cfg)]
    if app:
        title = name or Path(app.replace("\\", "/")).stem
        args += [
            f"/size:{size}",
            f"/wm-class:winbridge-{title}",
            f'/app:program:{app},name:{title},cmd:""',
        ]
    else:
        args += ["/dynamic-resolution", f"/size:{size}"]
    return args


def log_path() -> Path:
    directory = cfgmod.state_dir()
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "freerdp.log"


def launch(cfg: cfgmod.Config, app: str | None = None, name: str | None = None,
           log=print) -> subprocess.Popen:
    """Start FreeRDP detached so it survives the caller (tray/menu) exiting."""
    ensure_vm_running(cfg, log=log)
    command = build_command(cfg, app=app, name=name)
    handle = open(log_path(), "ab", buffering=0)
    handle.write(f"\n=== {' '.join(command[:2])} {time.strftime('%F %T')} ===\n".encode())
    return subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
