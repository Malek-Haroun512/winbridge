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
from .i18n import t

CANDIDATES = ("xfreerdp3", "xfreerdp", "wlfreerdp")


class RdpError(RuntimeError):
    pass


def freerdp_bin() -> str:
    for name in CANDIDATES:
        path = shutil.which(name)
        if path:
            return path
    raise RdpError(t("err_freerdp_missing"))


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
        raise RdpError(t("err_no_vm_selected"))
    if vbox.is_running(cfg.vm):
        return
    if not cfg.start_vm:
        raise RdpError(t("err_vm_stopped", vm=cfg.vm))
    log(t("log_starting_vm", vm=cfg.vm))
    vbox.start_headless(cfg.vm)
    deadline = time.time() + 240
    while time.time() < deadline:
        if port_open(cfg.host, cfg.port):
            return
        time.sleep(3)
    raise RdpError(t("err_rdp_port_closed"))


SECURITY_MODES = ("nla", "tls")
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
NEGOTIATION_ERRORS = (
    "HYBRID_REQUIRED_BY_SERVER",
    "HYBRID_NOT_ALLOWED_BY_SERVER",
    "SSL_REQUIRED_BY_SERVER",
    "Protocol Security Negotiation Failure",
)


def base_args(cfg: cfgmod.Config, security: str | None = None) -> list[str]:
    # A NAT forward bound to loopback cannot be intercepted, and Windows
    # generates a fresh self-signed certificate on every installation, so
    # /cert:tofu would block the first connection after a reinstall.
    cert = "/cert:ignore" if cfg.host in LOOPBACK_HOSTS else "/cert:tofu"
    args = [
        f"/v:{cfg.host}:{cfg.port}",
        f"/u:{cfg.user}",
        f"/p:{cfg.password}",
        cert,
        "+clipboard",
        "-wallpaper",
        f"/drive:home,{Path.home()}",
        "+auto-reconnect",
    ]
    if security in SECURITY_MODES:
        args.append(f"/sec:{security}")
    return args


def build_command(cfg: cfgmod.Config, app: str | None = None,
                  name: str | None = None, size: str = "1600x900",
                  security: str | None = None) -> list[str]:
    args = [freerdp_bin(), *base_args(cfg, security=security)]
    if app:
        title = name or Path(app.replace("\\", "/")).stem
        args += [
            f"/size:{size}",
            f"/wm-class:winbridge-{title}",
            f"/app:program:{app},name:{title}",
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
    log(t("log_reusing_session", count=len(pids)))
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


def current_attempt_log(lines: int = 160) -> str:
    """FreeRDP log for the most recent launch only."""
    try:
        text = log_path().read_text("utf-8", "replace")
    except OSError:
        return ""
    chunk = "\n".join(text.splitlines()[-lines:])
    blocks = chunk.split("\n=== ")
    return blocks[-1] if blocks else chunk


def diagnose() -> str:
    """Return a translation key describing the last connection failure."""
    tail = current_attempt_log()
    if "RAIL_EXEC_E_NOT_IN_ALLOWLIST" in tail:
        return "err_rail_allowlist"
    if "LOGON_FAILURE" in tail or "ERRCONNECT_LOGON_FAILURE" in tail:
        return "err_bad_credentials"
    if "RPC_INITIATED_DISCONNECT" in tail:
        return "err_console_session"
    if any(marker in tail for marker in NEGOTIATION_ERRORS):
        return "err_security_mismatch"
    return ""


def _spawn(cfg: cfgmod.Config, app: str | None, name: str | None,
           security: str | None) -> subprocess.Popen:
    command = build_command(cfg, app=app, name=name, security=security)
    handle = open(log_path(), "ab", buffering=0)
    handle.write(f"\n=== {' '.join(command[:2])} {time.strftime('%F %T')} ===\n".encode())
    return subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def _exited_within(proc: subprocess.Popen, seconds: float) -> int | None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if proc.poll() is not None:
            return proc.returncode
        time.sleep(0.2)
    return None


def _remember_security(cfg: cfgmod.Config, mode: str) -> None:
    if cfg.security == mode:
        return
    cfg.security = mode
    try:
        cfgmod.save(cfg)
    except OSError:
        pass


def _negotiation_failed() -> bool:
    tail = current_attempt_log()
    return any(marker in tail for marker in NEGOTIATION_ERRORS)


def launch(cfg: cfgmod.Config, app: str | None = None, name: str | None = None,
           log=print) -> subprocess.Popen:
    """Start FreeRDP detached so it survives the caller (tray/menu) exiting.

    Windows 10/11 enforces NLA out of the box, while a guest prepared by
    WinBridge's script accepts plain TLS.  Instead of hard-coding one mode we
    try both once, keep the one that works in the config, and from then on
    connect straight away.
    """
    ensure_vm_running(cfg, log=log)
    if stop_clients(cfg, log=log):
        time.sleep(1.0)

    if cfg.security in SECURITY_MODES:
        # Remembered from an earlier run: connect immediately.
        return _spawn(cfg, app, name, cfg.security)

    proc = None
    for index, mode in enumerate(("nla", "tls")):
        proc = _spawn(cfg, app, name, mode)
        if index == 1:
            return proc
        if _exited_within(proc, 4.0) is None:
            _remember_security(cfg, mode)
            return proc
        if not _negotiation_failed():
            return proc
        log(t("log_retry_security", mode="tls"))
    return proc  # pragma: no cover - the loop always returns
