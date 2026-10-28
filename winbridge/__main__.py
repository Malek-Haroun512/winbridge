"""Command line entry point: ``python -m winbridge <command>``."""

from __future__ import annotations

import argparse
import sys

from . import __app_name__, __version__
from . import config as cfgmod
from . import i18n, rdp, setup_guest, vbox
from .i18n import t


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
            print(t("cli_usb_line", mark=mark, uuid=device.uuid,
                    ids=f"{device.vendor_id}:{device.product_id}",
                    label=device.label, state=device.state))
        return 0

    match = None
    for device in vbox.usb_devices():
        if device.matches(args.target):
            match = device
            break
    if not match:
        print(t("cli_usb_no_match", target=args.target), file=sys.stderr)
        return 1
    if not cfg.vm:
        print(t("cli_usb_no_vm"), file=sys.stderr)
        return 1
    if args.action == "attach":
        vbox.usb_attach(cfg.vm, match.uuid)
        print(t("cli_usb_attached", device=match.label))
    else:
        vbox.usb_detach(cfg.vm, match.uuid)
        print(t("cli_usb_detached", device=match.label))
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    cfg = cfgmod.load()
    if args.vm:
        cfg.vm = args.vm
        cfgmod.save(cfg)
    if not cfg.vm:
        print(t("cli_setup_need_vm"), file=sys.stderr)
        return 1

    setup_guest.prepare_host(cfg.vm, cfg, log=print)
    if args.no_start:
        path = setup_guest.write_guest_script(cfg)
        print(f"\n{t('log_script_written', path=path)}\n")
        print(setup_guest.instructions())
        return 0

    if not vbox.is_running(cfg.vm):
        vbox.start_headless(cfg.vm)
        setup_guest.wait_for_boot(log=print, seconds=args.boot_wait)

    if args.manual:
        path = setup_guest.write_guest_script(cfg)
        print(f"\n{t('log_script_written', path=path)}\n")
        print(setup_guest.instructions())
        return 0

    if not setup_guest.provision(cfg, log=print):
        path = setup_guest.write_guest_script(cfg)
        print(f"\n{t('log_script_written', path=path)}\n")
        print(setup_guest.instructions())
        return 1

    verified = rdp.verify_credentials(cfg, timeout=20)
    if verified is False:
        print(t("err_rdp_verify"), file=sys.stderr)
        return 1
    if verified is True:
        print(t("log_rdp_ready", host=cfg.host, port=cfg.port))
    print(t("log_setup_complete"))
    if verified is None:
        print(t("log_setup_unverified"))
    return 0


def cmd_doctor(_args: argparse.Namespace) -> int:
    print(f"{__app_name__} {__version__}")
    try:
        print(f"{t('lbl_vboxmanage')}: {vbox.vbox_bin()} ({vbox.version()})")
        print(f"VMs: {', '.join(vbox.list_vms()) or '—'}")
    except vbox.VBoxError as exc:
        print(f"{t('lbl_vboxmanage')}: {exc}")
    try:
        print(f"{t('lbl_freerdp')}: {rdp.freerdp_bin()}")
    except rdp.RdpError as exc:
        print(f"{t('lbl_freerdp')}: {exc}")
    print(
        f"{t('lbl_extpack')}: "
        f"{t('cli_extpack_yes') if vbox.has_usb_extpack() else t('cli_extpack_no')}"
    )
    cfg = cfgmod.load()
    print(f"{t('lbl_config')}: {cfgmod.CONFIG_PATH} (vm={cfg.vm or '—'}, port={cfg.port})")
    print(f"{t('lbl_security')}: {cfg.security}")
    if cfg.vm:
        yes, no = t("common_yes"), t("common_no")
        print(f"{t('lbl_vm_running')}: {yes if vbox.is_running(cfg.vm) else no}")
        port_open = rdp.port_open(cfg.host, cfg.port)
        print(f"{t('lbl_rdp_port')}: {yes if port_open else no}")
        if port_open:
            logged_in = rdp.verify_credentials(cfg, timeout=8)
            if logged_in is True:
                auth = t("cli_auth_ok")
            elif logged_in is False:
                auth = t("cli_auth_fail")
            else:
                auth = t("cli_auth_unknown")
            print(f"{t('lbl_rdp_auth')}: {auth}")
        try:
            devices = [d for d in vbox.usb_devices() if d.captured]
            print(t("cli_usb_captured", devices=", ".join(d.label for d in devices) or "—"))
        except vbox.VBoxError:
            pass
    return 0


class _Formatter(argparse.HelpFormatter):
    """Help formatter with a translated ``usage:`` prefix."""

    def add_usage(self, usage, actions, groups, prefix=None):
        if prefix is None:
            prefix = f"{t('help_usage')} "
        return super().add_usage(usage, actions, groups, prefix)


def _localize(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser._positionals.title = t("help_positional")  # noqa: SLF001 - argparse API
    parser._optionals.title = t("help_options")  # noqa: SLF001 - argparse API
    return parser


def _subparser(sub, name: str, **kwargs) -> argparse.ArgumentParser:
    parser = sub.add_parser(
        name, add_help=False, formatter_class=_Formatter, **kwargs
    )
    parser.add_argument("-h", "--help", action="help", help=t("help_help"))
    return _localize(parser)


def main(argv: list[str] | None = None) -> int:
    cfg = cfgmod.load()
    i18n.set_language(cfg.language if cfg.language != "auto" else i18n.detect())

    parser = _localize(argparse.ArgumentParser(
        prog="winbridge",
        description=f"{__app_name__} — Windows apps on Linux via VirtualBox",
        add_help=False,
        formatter_class=_Formatter,
    ))
    parser.add_argument("-h", "--help", action="help", help=t("help_help"))
    parser.add_argument("--version", action="version", version=__version__,
                        help=t("help_version"))
    sub = parser.add_subparsers(dest="command")

    _subparser(sub, "tray", help=t("cli_tray_help"))
    _subparser(sub, "desktop", help=t("cli_desktop_help")).set_defaults(func=cmd_desktop)

    app_parser = _subparser(sub, "app", help=t("cli_app_help"))
    app_parser.add_argument("name", help=t("cli_app_name_help"))
    app_parser.set_defaults(func=cmd_app)

    usb_parser = _subparser(sub, "usb", help=t("cli_usb_help"))
    usb_parser.add_argument("action", choices=["list", "attach", "detach"])
    usb_parser.add_argument("target", nargs="?", default="", help=t("cli_usb_target_help"))
    usb_parser.set_defaults(func=cmd_usb)

    setup_parser = _subparser(sub, "setup", help=t("cli_setup_help"))
    setup_parser.add_argument("--vm", help=t("cli_setup_vm_help"))
    setup_parser.add_argument("--no-start", action="store_true",
                              help=t("cli_setup_no_start_help"))
    setup_parser.add_argument("--manual", action="store_true",
                              help=t("cli_setup_manual_help"))
    setup_parser.add_argument("--boot-wait", type=int, default=90,
                              metavar="SECONDS",
                              help=t("cli_setup_boot_wait_help"))
    setup_parser.set_defaults(func=cmd_setup)

    _subparser(sub, "doctor", help=t("cli_doctor_help")).set_defaults(func=cmd_doctor)

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
