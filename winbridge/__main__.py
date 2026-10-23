"""Command line entry point: ``python -m winbridge <command>``."""

from __future__ import annotations

import argparse
import sys

from . import __app_name__, __version__
from . import config as cfgmod
from . import rdp, setup_guest, vbox


def _resolve_app(value: str) -> tuple[str, str]:
    cfg = cfgmod.load()
    for entry in cfg.apps:
        if entry.name.lower() == value.lower():
            return entry.target, entry.name
    return value, value.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]


def cmd_desktop(_args: argparse.Namespace) -> int:
    cfg = cfgmod.load()
    rdp.launch(cfg, log=print)
    return 0


def cmd_app(args: argparse.Namespace) -> int:
    cfg = cfgmod.load()
    target, name = _resolve_app(args.name)
    rdp.launch(cfg, app=target, name=name, log=print)
    return 0


def cmd_usb(args: argparse.Namespace) -> int:
    cfg = cfgmod.load()
    if args.action == "list":
        for device in vbox.usb_devices():
            mark = "✓" if device.captured else " "
            print(f"{mark} {device.uuid}  {device.vendor_id}:{device.product_id}  {device.label}  [{device.state}]")
        return 0

    match = None
    for device in vbox.usb_devices():
        if device.matches(args.target):
            match = device
            break
    if not match:
        print(f"لم أجد جهاز USB مطابقًا لـ {args.target}", file=sys.stderr)
        return 1
    if not cfg.vm:
        print("لم يتم ضبط الجهاز في الإعدادات.", file=sys.stderr)
        return 1
    if args.action == "attach":
        vbox.usb_attach(cfg.vm, match.uuid)
        print(f"وُصل {match.label}")
    else:
        vbox.usb_detach(cfg.vm, match.uuid)
        print(f"فُصل {match.label}")
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    cfg = cfgmod.load()
    if args.vm:
        cfg.vm = args.vm
        cfgmod.save(cfg)
    if not cfg.vm:
        print("حدّد الجهاز: winbridge setup --vm <name>", file=sys.stderr)
        return 1
    setup_guest.prepare_host(cfg.vm, cfg, log=print)
    path = setup_guest.write_guest_script(cfg)
    print(f"\nسكربت ويندوز: {path}\n")
    print(setup_guest.INSTRUCTIONS)
    if not args.no_start:
        vbox.start_headless(cfg.vm)
        if rdp.wait_for_port(cfg.host, cfg.port, timeout=240):
            print(f"RDP جاهز على {cfg.host}:{cfg.port}")
    return 0


def cmd_doctor(_args: argparse.Namespace) -> int:
    print(f"{__app_name__} {__version__}")
    try:
        print(f"VBoxManage: {vbox.vbox_bin()} ({vbox.version()})")
        print(f"VMs: {', '.join(vbox.list_vms()) or '—'}")
    except vbox.VBoxError as exc:
        print(f"VBoxManage: {exc}")
    try:
        print(f"FreeRDP: {rdp.freerdp_bin()}")
    except rdp.RdpError as exc:
        print(f"FreeRDP: {exc}")
    print(f"Extension Pack: {'مثبّت' if vbox.has_usb_extpack() else 'غير مثبّت (USB 1.1 فقط)'}")
    cfg = cfgmod.load()
    print(f"Config: {cfgmod.CONFIG_PATH} (vm={cfg.vm or '—'}, port={cfg.port})")
    if cfg.vm:
        print(f"VM running: {'نعم' if vbox.is_running(cfg.vm) else 'لا'}")
        print(f"RDP port open: {'نعم' if rdp.port_open(cfg.host, cfg.port) else 'لا'}")
        try:
            devices = [d for d in vbox.usb_devices() if d.captured]
            print(f"USB captured: {', '.join(d.label for d in devices) or '—'}")
        except vbox.VBoxError:
            pass
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="winbridge", description=f"{__app_name__} — Windows apps on Linux via VirtualBox")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("tray", help="تشغيل أيقونة شريط المهام")
    sub.add_parser("desktop", help="فتح سطح مكتب ويندوز").set_defaults(func=cmd_desktop)

    app_parser = sub.add_parser("app", help="تشغيل تطبيق ويندوز بنافذة منفصلة")
    app_parser.add_argument("name", help="اسم التطبيق من الإعدادات أو مسار exe")
    app_parser.set_defaults(func=cmd_app)

    usb_parser = sub.add_parser("usb", help="إدارة أجهزة USB")
    usb_parser.add_argument("action", choices=["list", "attach", "detach"])
    usb_parser.add_argument("target", nargs="?", default="", help="UUID أو جزء من الاسم")
    usb_parser.set_defaults(func=cmd_usb)

    setup_parser = sub.add_parser("setup", help="تهيئة الجهاز من جهة لينكس")
    setup_parser.add_argument("--vm", help="اسم جهاز VirtualBox")
    setup_parser.add_argument("--no-start", action="store_true")
    setup_parser.set_defaults(func=cmd_setup)

    sub.add_parser("doctor", help="فحص المتطلبات").set_defaults(func=cmd_doctor)

    args = parser.parse_args(argv)
    if args.command == "tray" or not args.command:
        from .tray import main as tray_main

        return tray_main()
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
