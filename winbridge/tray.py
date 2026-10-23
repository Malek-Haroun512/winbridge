"""System-tray application: launch apps, control the VM, attach USB devices."""

from __future__ import annotations

import fcntl
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import __app_name__, __version__
from . import config as cfgmod, i18n, rdp, setup_guest, vbox
from .config import Config
from .i18n import t


def app_icon() -> QIcon:
    """Draw the WinBridge mark (blue tile + white window + USB stick)."""
    size = 128
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    gradient = QLinearGradient(0, 0, 0, size)
    gradient.setColorAt(0.0, QColor("#2f80ed"))
    gradient.setColorAt(1.0, QColor("#1b4f9c"))
    painter.setBrush(gradient)
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(QRectF(4, 4, size - 8, size - 8), 26, 26)

    painter.setBrush(QColor("#ffffff"))
    painter.drawRoundedRect(QRectF(26, 30, 76, 58), 10, 10)
    painter.setBrush(QColor("#2f80ed"))
    painter.drawRoundedRect(QRectF(34, 44, 60, 36), 6, 6)

    painter.setBrush(QColor("#ffffff"))
    painter.drawRoundedRect(QRectF(54, 88, 20, 22), 4, 4)
    painter.setBrush(QColor("#c8d8ef"))
    painter.drawRect(QRectF(59, 80, 10, 10))

    painter.end()
    return QIcon(pixmap)


class Tray:
    def __init__(self, app: QApplication):
        self.app = app
        self.cfg: Config = cfgmod.load()
        self.icon = QSystemTrayIcon(app_icon(), app)
        self.icon.setToolTip(f"{__app_name__} {__version__}")
        self.menu = QMenu()
        self.menu.aboutToShow.connect(self._rebuild)
        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(self._on_activated)
        self.icon.show()

    # ------------------------------------------------------------------ menu

    def _rebuild(self) -> None:
        self.menu.clear()
        self.cfg = cfgmod.load()
        i18n.set_language(self.cfg.language if self.cfg.language != "auto" else i18n.detect())

        header = QAction(self._status_text(), self.menu)
        header.setEnabled(False)
        self.menu.addAction(header)
        self.menu.addSeparator()

        self._build_vm_menu()

        desktop = QAction(QIcon.fromTheme("video-display"), t("menu_desktop"), self.menu)
        desktop.triggered.connect(self._launch_desktop)
        self.menu.addAction(desktop)

        apps_menu = self.menu.addMenu(QIcon.fromTheme("applications-system"), t("menu_apps"))
        if self.cfg.apps:
            for entry in self.cfg.apps:
                action = QAction(entry.name, self.menu)
                action.triggered.connect(
                    lambda _=False, app=entry: self._launch_app(app.target, app.name)
                )
                apps_menu.addAction(action)
        else:
            empty = QAction(t("menu_no_apps"), apps_menu)
            empty.setEnabled(False)
            apps_menu.addAction(empty)
        apps_menu.addSeparator()
        manage = QAction(QIcon.fromTheme("document-properties"), t("menu_manage_apps"), apps_menu)
        manage.triggered.connect(self._open_settings)
        apps_menu.addAction(manage)

        self._build_usb_menu()

        self.menu.addSeparator()
        settings = QAction(QIcon.fromTheme("preferences-system"), t("menu_settings"), self.menu)
        settings.triggered.connect(self._open_settings)
        self.menu.addAction(settings)

        quit_action = QAction(QIcon.fromTheme("application-exit"), t("menu_quit"), self.menu)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)

    def _build_vm_menu(self) -> None:
        vm_menu = self.menu.addMenu(QIcon.fromTheme("system-run"), t("menu_vm"))
        running = False
        if self.cfg.vm:
            try:
                running = vbox.is_running(self.cfg.vm)
            except vbox.VBoxError:
                running = False

        if running:
            shutdown = QAction(QIcon.fromTheme("system-shutdown"), t("menu_vm_shutdown"), vm_menu)
            shutdown.triggered.connect(self._vm_shutdown)
            vm_menu.addAction(shutdown)

            restart = QAction(QIcon.fromTheme("view-refresh"), t("menu_vm_restart"), vm_menu)
            restart.triggered.connect(self._vm_restart)
            vm_menu.addAction(restart)
        else:
            start = QAction(QIcon.fromTheme("media-playback-start"), t("menu_vm_start"), vm_menu)
            start.triggered.connect(self._vm_start)
            vm_menu.addAction(start)

            start_gui = QAction(
                QIcon.fromTheme("video-display"), t("menu_vm_start_gui"), vm_menu
            )
            start_gui.triggered.connect(self._vm_start_gui)
            vm_menu.addAction(start_gui)

        console = QAction(QIcon.fromTheme("utilities-terminal"), t("menu_vm_console"), vm_menu)
        console.triggered.connect(self._open_vm_console)
        vm_menu.addAction(console)

        prepare = QAction(QIcon.fromTheme("document-properties"), t("menu_vm_prepare"), vm_menu)
        prepare.triggered.connect(self._open_settings)
        vm_menu.addAction(prepare)

    def _status_text(self) -> str:
        if not self.cfg.vm:
            return t("tray_status_novm", app=__app_name__)
        try:
            state = t("state_running") if vbox.is_running(self.cfg.vm) else t("state_stopped")
        except vbox.VBoxError:
            state = t("state_unknown")
        return t("tray_status", app=__app_name__, vm=self.cfg.vm, state=state)

    def _build_usb_menu(self) -> None:
        usb_menu = self.menu.addMenu(QIcon.fromTheme("drive-removable-media-usb"), t("menu_usb"))

        if not vbox.has_usb_extpack():
            warn = QAction(t("usb_no_extpack"), usb_menu)
            warn.setEnabled(False)
            usb_menu.addAction(warn)
            usb_menu.addSeparator()

        try:
            devices = vbox.usb_devices()
        except vbox.VBoxError as exc:
            error = QAction(t("usb_error", message=str(exc)), usb_menu)
            error.setEnabled(False)
            usb_menu.addAction(error)
            devices = []

        if not devices:
            empty = QAction(t("usb_none"), usb_menu)
            empty.setEnabled(False)
            usb_menu.addAction(empty)
        else:
            for device in devices:
                title = device.label
                if device.captured:
                    title = f"✓ {title}"
                action = QAction(title, usb_menu)
                action.setCheckable(True)
                action.setChecked(device.captured)
                action.setToolTip(f"{device.ids} — {device.state}")
                action.triggered.connect(
                    lambda checked, dev=device: self._toggle_usb(dev, checked)
                )
                usb_menu.addAction(action)

        usb_menu.addSeparator()
        refresh = QAction(QIcon.fromTheme("view-refresh"), t("usb_refresh"), usb_menu)
        refresh.triggered.connect(self._rebuild)
        usb_menu.addAction(refresh)

        detach_all = QAction(t("usb_detach_all"), usb_menu)
        detach_all.triggered.connect(self._detach_all)
        usb_menu.addAction(detach_all)

    # --------------------------------------------------------------- actions

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self._launch_desktop()

    def _vm_start(self) -> None:
        if not self.cfg.vm:
            self._notify(t("err_choose_vm"), error=True)
            return
        try:
            vbox.start_headless(self.cfg.vm)
            self._notify(t("notify_vm_started", vm=self.cfg.vm))
            QTimer.singleShot(5000, self._rebuild)
        except vbox.VBoxError as exc:
            self._notify(str(exc), error=True)

    def _vm_start_gui(self) -> None:
        if not self.cfg.vm:
            self._notify(t("err_choose_vm"), error=True)
            return
        try:
            vbox.start_gui(self.cfg.vm)
            self._notify(t("notify_vm_started_gui", vm=self.cfg.vm))
            QTimer.singleShot(5000, self._rebuild)
        except vbox.VBoxError as exc:
            self._notify(str(exc), error=True)

    def _vm_shutdown(self) -> None:
        if not self.cfg.vm:
            return
        try:
            stopped = vbox.acpi_power_button(self.cfg.vm, timeout=30) or vbox.guest_shutdown(
                self.cfg.vm, self.cfg.user, self.cfg.password
            )
            if not stopped:
                raise vbox.VBoxError(t("err_poweroff_failed"))
            self._notify(t("notify_vm_stopped", vm=self.cfg.vm))
        except vbox.VBoxError as exc:
            self._notify(str(exc), error=True)
        QTimer.singleShot(1500, self._rebuild)

    def _vm_restart(self) -> None:
        if not self.cfg.vm:
            return
        try:
            vbox.run(["controlvm", self.cfg.vm, "reset"], check=False)
            self._notify(t("notify_vm_restarted", vm=self.cfg.vm))
            QTimer.singleShot(8000, self._rebuild)
        except vbox.VBoxError as exc:
            self._notify(str(exc), error=True)

    def _open_vm_console(self) -> None:
        if not self.cfg.vm:
            self._notify(t("err_choose_vm"), error=True)
            return
        try:
            subprocess.Popen(["virtualbox"])
        except FileNotFoundError:
            self._notify(t("err_no_virtualbox_gui"), error=True)

    def _notify(self, message: str, error: bool = False) -> None:
        icon = QSystemTrayIcon.Critical if error else QSystemTrayIcon.Information
        self.icon.showMessage(__app_name__, message, icon, 4000)

    def _launch_desktop(self) -> None:
        try:
            proc = rdp.launch(self.cfg, log=lambda _m: None)
        except (rdp.RdpError, vbox.VBoxError) as exc:
            self._notify(str(exc), error=True)
            return
        QTimer.singleShot(5000, lambda: self._verify(proc, t("menu_desktop")))

    def _launch_app(self, target: str, name: str) -> None:
        try:
            proc = rdp.launch(self.cfg, app=target, name=name, log=lambda _m: None)
        except (rdp.RdpError, vbox.VBoxError) as exc:
            self._notify(str(exc), error=True)
            return
        QTimer.singleShot(5000, lambda: self._verify(proc, name))

    def _verify(self, proc, name: str) -> None:
        code = proc.poll()
        if code is not None and code != 0:
            self._notify(t("err_launch", name=name, code=code), error=True)

    def _toggle_usb(self, device: vbox.UsbDevice, attach: bool) -> None:
        if not self.cfg.vm:
            self._notify(t("err_choose_vm"), error=True)
            return
        try:
            if attach:
                if not vbox.is_running(self.cfg.vm):
                    vbox.start_headless(self.cfg.vm)
                    if not rdp.wait_for_port(self.cfg.host, self.cfg.port, timeout=240):
                        raise vbox.VBoxError(t("err_rdp_port_closed"))
                vbox.usb_attach(self.cfg.vm, device.uuid)
                self._notify(t("notify_usb_attached", device=device.label))
            else:
                vbox.usb_detach(self.cfg.vm, device.uuid)
                self._notify(t("notify_usb_detached", device=device.label))
        except (vbox.VBoxError, rdp.RdpError) as exc:
            self._notify(str(exc), error=True)
        QTimer.singleShot(1200, self._rebuild)

    def _detach_all(self) -> None:
        if not self.cfg.vm:
            return
        try:
            for device in vbox.usb_devices():
                if device.captured:
                    vbox.usb_detach(self.cfg.vm, device.uuid)
            self._notify(t("notify_usb_detached_all"))
        except vbox.VBoxError as exc:
            self._notify(str(exc), error=True)
        QTimer.singleShot(1200, self._rebuild)

    def _open_settings(self) -> None:
        from .settings_window import SettingsDialog

        dialog = SettingsDialog(cfgmod.load())
        dialog.exec()
        self.cfg = cfgmod.load()
        i18n.set_language(self.cfg.language if self.cfg.language != "auto" else i18n.detect())
        self._rebuild()

    def run(self) -> int:
        return self.app.exec()


def _lock() -> object | None:
    runtime = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    path = Path(runtime) / "winbridge-tray.lock"
    handle = open(path, "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def main() -> int:
    lock = _lock()
    if lock is None:
        print("WinBridge tray is already running.")
        return 0

    cfg = cfgmod.load()
    i18n.set_language(cfg.language if cfg.language != "auto" else i18n.detect())

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setDesktopFileName("winbridge")
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("No system tray available (StatusNotifierItem).", file=sys.stderr)
        return 2

    tray = Tray(app)
    if not cfg.configured:
        QTimer.singleShot(0, tray._open_settings)
    return tray.run()
