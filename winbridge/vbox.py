"""Minimal wrapper around the VBoxManage command line tool."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field

from . import __app_name__
from .i18n import t


class VBoxError(RuntimeError):
    """Raised when VBoxManage fails or is missing."""


def vbox_bin() -> str:
    exe = shutil.which("VBoxManage")
    if not exe:
        raise VBoxError(t("err_vboxmanage_missing"))
    return exe


def run(args: list[str], timeout: int = 60, check: bool = True) -> str:
    """Run VBoxManage with *args* and return combined output."""
    try:
        proc = subprocess.run(
            [vbox_bin(), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - environment dependent
        raise VBoxError(t("err_timeout", args=" ".join(args))) from exc
    except OSError as exc:
        raise VBoxError(str(exc)) from exc

    output = f"{proc.stdout or ''}{proc.stderr or ''}".strip()
    if check and proc.returncode != 0:
        raise VBoxError(output or t("err_vbox_failed", args=" ".join(args)))
    return output


def version() -> str:
    try:
        return run(["--version"], timeout=15).strip()
    except VBoxError:
        return ""


# --------------------------------------------------------------------------- VMs


def list_vms() -> dict[str, str]:
    """Return ``{name: uuid}`` for registered VMs."""
    vms: dict[str, str] = {}
    for line in run(["list", "vms"]).splitlines():
        match = re.match(r'^"(.+)"\s+\{([0-9a-fA-F-]+)\}$', line.strip())
        if match:
            vms[match.group(1)] = match.group(2)
    return vms


def machine_info(name: str) -> dict[str, str]:
    """Return the ``--machinereadable`` key/value map for *name*."""
    info: dict[str, str] = {}
    for line in run(["showvminfo", name, "--machinereadable"]).splitlines():
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        info[key] = value.strip('"')
    return info


def is_running(name: str) -> bool:
    try:
        return machine_info(name).get("VMState") in ("running", "paused", "stuck")
    except VBoxError:
        return False


def vm_state(name: str) -> str:
    try:
        return machine_info(name).get("VMState", "unknown")
    except VBoxError:
        return "unknown"


def start_headless(name: str) -> None:
    if is_running(name):
        return
    run(["startvm", name, "--type", "headless"], timeout=120)


def start_gui(name: str) -> None:
    if is_running(name):
        return
    run(["startvm", name, "--type", "gui"], timeout=120)


def wait_poweroff(name: str, timeout: int = 90) -> bool:
    import time

    for _ in range(timeout):
        if vm_state(name) == "poweroff":
            return True
        time.sleep(1)
    return False


def acpi_power_button(name: str, timeout: int = 90) -> bool:
    """Ask the guest to shut down gracefully. Returns True when powered off."""
    try:
        run(["controlvm", name, "acpipowerbutton"], timeout=20, check=False)
    except VBoxError:
        return False
    return wait_poweroff(name, timeout)


def guest_shutdown(name: str, user: str, password: str, timeout: int = 90) -> bool:
    """Shut down through Guest Additions (more reliable than ACPI)."""
    if not (user and password):
        return False
    run(
        [
            "guestcontrol", name, "run",
            f"--username={user}", f"--password={password}",
            r"--exe=C:\Windows\System32\shutdown.exe",
            "--timeout=15000", "--", "/s", "/t", "0", "/f",
        ],
        timeout=40, check=False,
    )
    return wait_poweroff(name, timeout)


# ------------------------------------------------------------------ port forward


def ensure_port_forward(vm: str, host_port: int, guest_port: int = 3389,
                        host_ip: str = "127.0.0.1", rule: str = "winbridge-rdp") -> bool:
    """Add a NAT port forward rule if an equivalent one is missing.

    Returns True when a rule was added.
    """
    info = machine_info(vm)
    for key, value in info.items():
        if not key.startswith("Forwarding("):
            continue
        parts = value.split(",")
        if len(parts) >= 6 and parts[1] == "tcp" and parts[5].strip() == str(guest_port):
            return False
    if info.get("nic1") != "nat" and info.get("natnet1", "") == "":
        raise VBoxError(t("err_nat_required", vm=vm))
    suffix = "1" if info.get("nic1") == "nat" else "2"
    run([
        "modifyvm", vm,
        f"--natpf{suffix}", f"{rule},tcp,{host_ip},{host_port},,{guest_port}",
    ])
    return True


# ----------------------------------------------------------------------- USB


def extpacks() -> list[str]:
    out = run(["list", "extpacks"], check=False)
    return [line.strip() for line in out.splitlines() if line.startswith("Pack no.")]


def has_usb_extpack() -> bool:
    """True when the Oracle Extension Pack (USB 2.0/3.0 support) is installed."""
    out = run(["list", "extpacks"], check=False)
    return "Oracle VM VirtualBox Extension Pack" in out


@dataclass
class UsbDevice:
    uuid: str
    vendor_id: str
    product_id: str
    manufacturer: str
    product: str
    state: str
    address: str = ""
    serial: str = ""
    raw: dict[str, str] = field(default_factory=dict)

    @property
    def label(self) -> str:
        name = " ".join(part for part in (self.manufacturer, self.product) if part).strip()
        return name or f"{self.vendor_id}:{self.product_id}"

    @property
    def captured(self) -> bool:
        return self.state.strip().lower() == "captured"

    @property
    def ids(self) -> str:
        vid = self.vendor_id.lower().replace("0x", "")
        pid = self.product_id.lower().replace("0x", "")
        return f"{vid}:{pid}"

    def matches(self, needle: str) -> bool:
        needle = needle.strip().lower().replace("0x", "")
        haystack = " ".join(
            [self.uuid.lower(), self.label.lower(), self.ids, self.serial.lower()]
        )
        return bool(needle) and needle in haystack


def usb_devices() -> list[UsbDevice]:
    """Enumerate host USB devices known to VirtualBox."""
    out = run(["list", "usbhost"], check=False)
    blocks = re.split(r"\n\s*\n", out)
    devices: list[UsbDevice] = []

    def pick(block: str, key: str) -> str:
        match = re.search(rf"^{re.escape(key)}:\s*(.*)$", block, re.MULTILINE)
        return match.group(1).strip() if match else ""

    for block in blocks:
        uuid = pick(block, "UUID")
        if not uuid:
            continue
        raw = {
            "UUID": uuid,
            "VendorId": pick(block, "VendorId").split()[0] if pick(block, "VendorId") else "",
            "ProductId": pick(block, "ProductId").split()[0] if pick(block, "ProductId") else "",
            "Manufacturer": pick(block, "Manufacturer"),
            "Product": pick(block, "Product"),
            "SerialNumber": pick(block, "SerialNumber"),
            "Address": pick(block, "Address"),
            "Current State": pick(block, "Current State"),
        }
        devices.append(
            UsbDevice(
                uuid=uuid,
                vendor_id=raw["VendorId"],
                product_id=raw["ProductId"],
                manufacturer=raw["Manufacturer"],
                product=raw["Product"],
                state=raw["Current State"],
                address=raw["Address"],
                serial=raw["SerialNumber"],
                raw=raw,
            )
        )
    return devices


def usb_attach(vm: str, uuid: str) -> None:
    run(["controlvm", vm, "usbattach", uuid], timeout=60)


def usb_detach(vm: str, uuid: str) -> None:
    run(["controlvm", vm, "usbdetach", uuid], timeout=60)


def ensure_usb_controller(vm: str) -> str:
    """Make sure the VM has a USB controller. Requires a powered-off VM.

    Returns a human readable description of what was enabled.
    """
    if is_running(vm):
        raise VBoxError(t("err_usb_poweroff"))
    info = machine_info(vm)
    if info.get("usb") == "on":
        return t("usb_controller_present")
    extpack = has_usb_extpack()
    args = ["modifyvm", vm, "--usb", "on"]
    desc = "USB 1.1 (OHCI)"
    if extpack:
        args += ["--usbxhci", "on", "--usbehci", "on"]
        desc = "USB 3.0 (xHCI) + USB 2.0 (EHCI)"
    run(args)
    return desc
