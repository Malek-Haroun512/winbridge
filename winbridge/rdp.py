"""FreeRDP launcher: full desktop or single application (RAIL) windows."""

from __future__ import annotations

import os
import shutil
import signal
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


def _cmdline(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as handle:
            return handle.read().replace(b"\0", b" ").decode("utf-8", "replace")
    except OSError:
        return ""


def client_pids(cfg: cfgmod.Config) -> list[int]:
    """FreeRDP processes already connected (or connecting) to this VM."""
    needle = f"{cfg.host}:{cfg.port}"
    pids = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid == os.getpid():
            continue
        line = _cmdline(pid)
        if "freerdp" in line and needle in line:
            pids.append(pid)
    return pids


def stop_clients(cfg: cfgmod.Config, log=print, timeout: float = 4.0) -> int:
    """Terminate existing FreeRDP clients so the Windows session can be reused.

    Windows client SKUs allow a single interactive session per user: a second
    connection takes the session over and the previous client is dropped.  We do
    that deliberately, once, before connecting instead of letting both clients
    fight.  A SIGTERM'd client leaves the session *disconnected* (apps keep
    running), so the next connection resumes it and republishes every window.
    """
    pids = client_pids(cfg)
    if not pids:
        return 0
    log(f"إغلاق الاتصال السابق ({len(pids)}) لإعادة استخدام الجلسة …")
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not client_pids(cfg):
            return len(pids)
        time.sleep(0.2)
    for pid in client_pids(cfg):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    time.sleep(0.5)
    return len(pids)


def launch(cfg: cfgmod.Config, app: str | None = None, name: str | None = None,
           log=print) -> subprocess.Popen:
    """Start FreeRDP detached so it survives the caller (tray/menu) exiting."""
    ensure_vm_running(cfg, log=log)
    if stop_clients(cfg, log=log):
        time.sleep(1.0)
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
