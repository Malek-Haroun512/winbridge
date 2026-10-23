"""System-tray application: launch apps, attach USB devices, open settings."""

from __future__ import annotations

import fcntl
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from . import __app_name__, __version__
from . import config as cfgmod, rdp, setup_guest, vbox
from .config import Config


def app_icon() -> QIcon:
    """Draw the WinBridge mark (blue tile + white window + USB dot)."""
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

    # window frame
    painter.setBrush(QColor("#ffffff"))
    painter.drawRoundedRect(QRectF(26, 30, 76, 58), 10, 10)
    painter.setBrush(QColor("#2f80ed"))
    painter.drawRoundedRect(QRectF(34, 44, 60, 36), 6, 6)

    # USB stick
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

    # ------------------------------------------------------------- menu

    def _rebuild(self) -> None:
        self.menu.clear()
        self.cfg = cfgmod.load()

        header = QAction(self._status_text(), self.menu)
        header.setEnabled(False)
        self.menu.addAction(header)
        self.menu.addSeparator()

        # -- VM power controls
        vm_menu = self.menu.addMenu(
            QIcon.fromTheme("system-run"), "إدارة الجهاز"
        )
        if self.cfg.vm:
            try:
                running = vbox.is_running(self.cfg.vm)
            except vbox.VBoxError:
                running = False
        else:
            running = False

        if running:
            self_shutdown = QAction(
                QIcon.fromTheme("system-shutdown"), "إطفاء الجهاز", vm_menu
            )
            self_shutdown.triggered.connect(self._vm_shutdown)
            vm_menu.addAction(self_shutdown)

            restart = QAction(
                QIcon.fromTheme("view-refresh"), "إعادة تشغيل الجهاز", vm_menu
            )
            restart.triggered.connect(self._vm_restart)
            vm_menu.addAction(restart)
        else:
            start = QAction(
                QIcon.fromTheme("media-playback-start"), "تشغيل الجهاز", vm_menu
            )
            start.triggered.connect(self._vm_start)
            vm_menu.addAction(start)
            start_gui = QAction(
                QIcon.fromTheme("media-playback-start"), "تشغيل مع واجهة", vm_menu
            )
            start_gui.triggered.connect(self._vm_start_gui)
            vm_menu.addAction(start_gui)

        open_vm = QAction(
            QIcon.fromTheme("utilities-terminal"), "فتح نافذة الجهاز", vm_menu
        )
        open_vm.triggered.connect(self._open_vm_console)
        vm_menu.addAction(open_vm)

        prepare = QAction(
            QIcon.fromTheme("document-properties"), "تهيئة إعدادات المضيف", vm_menu
        )
        prepare.triggered.connect(self._open_settings)
        vm_menu.addAction(prepare)

        desktop = QAction(QIcon.fromTheme("video-display"), "سطح مكتب ويندوز", self.menu)
        desktop.triggered.connect(self._launch_desktop)
        self.menu.addAction(desktop)

        apps_menu = self.menu.addMenu(QIcon.fromTheme("applications-system"), "التطبيقات")
        if self.cfg.apps:
            for entry in self.cfg.apps:
                action = QAction(entry.name, self.menu)
                action.triggered.connect(
                    lambda _=False, app=entry: self._launch_app(app.target, app.name)
                )
                apps_menu.addAction(action)
        else:
            empty = QAction("لا تطبيقات بعد — الإعدادات", apps_menu)
            empty.setEnabled(False)
            apps_menu.addAction(empty)
        apps_menu.addSeparator()
        manage = QAction(QIcon.fromTheme("document-properties"), "إدارة التطبيقات…", apps_menu)
        manage.triggered.connect(self._open_settings)
        apps_menu.addAction(manage)

        self._build_usb_menu()

        self.menu.addSeparator()
        settings = QAction(QIcon.fromTheme("preferences-system"), "الإعدادات…", self.menu)
        settings.triggered.connect(self._open_settings)
        self.menu.addAction(settings)

        quit_action = QAction(QIcon.fromTheme("application-exit"), "خروج", self.menu)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)

    def _status_text(self) -> str:
        vm = self.cfg.vm or "بدون جهاز"
        if self.cfg.vm:
            try:
                state = "شغّال" if vbox.is_running(self.cfg.vm) else "متوقف"
            except vbox.VBoxError:
                state = "غير معروف"
            return f"{__app_name__} — {vm} ({state})"
        return f"{__app_name__} — اضبط الإعدادات"

    def _build_usb_menu(self) -> None:
        usb_menu = self.menu.addMenu(QIcon.fromTheme("drive-removable-media-usb"), "أجهزة USB")

        if not vbox.has_usb_extpack():
            warn = QAction("⚠ Extension Pack غير مثبّت (USB 1.1 فقط)", usb_menu)
            warn.setEnabled(False)
            usb_menu.addAction(warn)
            usb_menu.addSeparator()

        try:
            devices = vbox.usb_devices()
        except vbox.VBoxError as exc:
            error = QAction(f"خطأ: {exc}", usb_menu)
            error.setEnabled(False)
            usb_menu.addAction(error)
            devices = []

        if not devices:
            empty = QAction("لا أجهزة USB مكتشفة", usb_menu)
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
                action.setToolTip(f"{device.vendor_id}:{device.product_id} — {device.state}")
                action.triggered.connect(
                    lambda checked, dev=device: self._toggle_usb(dev, checked)
                )
                usb_menu.addAction(action)

        usb_menu.addSeparator()
        refresh = QAction(QIcon.fromTheme("view-refresh"), "تحديث القائمة", usb_menu)
        refresh.triggered.connect(self._rebuild)
        usb_menu.addAction(refresh)

        detach_all = QAction("فصل كل الأجهزة", usb_menu)
        detach_all.triggered.connect(self._detach_all)
        usb_menu.addAction(detach_all)

    # ---------------------------------------------------------- actions

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self._launch_desktop()

    def _vm_start(self) -> None:
        if not self.cfg.vm:
            self._notify("اختر جهازًا في الإعدادات أولًا.", error=True)
            return
        try:
            vbox.start_headless(self.cfg.vm)
            self._notify(f"تم تشغيل {self.cfg.vm} headless")
            QTimer.singleShot(5000, self._rebuild)
        except vbox.VBoxError as exc:
            self._notify(str(exc), error=True)

    def _vm_start_gui(self) -> None:
        if not self.cfg.vm:
            self._notify("اختر جهازًا في الإعدادات أولًا.", error=True)
            return
        try:
            vbox.start_gui(self.cfg.vm)
            self._notify(f"تم تشغيل {self.cfg.vm} مع واجهة")
            QTimer.singleShot(5000, self._rebuild)
        except vbox.VBoxError as exc:
            self._notify(str(exc), error=True)

    def _vm_shutdown(self) -> None:
        if not self.cfg.vm:
            return
        try:
            log_msg = [None]
            def log(m: str) -> None:
                log_msg[0] = m
            setup_guest.prepare_host(self.cfg.vm, self.cfg, log=log)
            self._notify(f"تم إطفاء {self.cfg.vm}")
            QTimer.singleShot(1000, self._rebuild)
        except vbox.VBoxError as exc:
            self._notify(str(exc), error=True)

    def _vm_restart(self) -> None:
        if not self.cfg.vm:
            return
        try:
            vbox.run(["controlvm", self.cfg.vm, "reset"], check=False)
            self._notify(f"أُعيد تشغيل {self.cfg.vm}")
            QTimer.singleShot(8000, self._rebuild)
        except vbox.VBoxError as exc:
            self._notify(str(exc), error=True)

    def _open_vm_console(self) -> None:
        if not self.cfg.vm:
            self._notify("اختر جهازًا في الإعدادات أولًا.", error=True)
            return
        try:
            subprocess.Popen(["virtualbox"])
        except FileNotFoundError:
            self._notify("لم أجد VirtualBox GUI. ثبّته أو شغّله يدويًا.")

    def _notify(self, message: str, error: bool = False) -> None:
        icon = QSystemTrayIcon.Critical if error else QSystemTrayIcon.Information
        self.icon.showMessage(__app_name__, message, icon, 4000)

    def _launch_desktop(self) -> None:
        try:
            proc = rdp.launch(self.cfg, log=lambda _m: None)
        except (rdp.RdpError, vbox.VBoxError) as exc:
            self._notify(str(exc), error=True)
            return
        QTimer.singleShot(5000, lambda: self._verify(proc, "سطح المكتب"))

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
            self._notify(
                f"تعذّر فتح {name} (رمز {code}). راجع ~/.local/state/winbridge/freerdp.log",
                error=True,
            )

    def _toggle_usb(self, device: vbox.UsbDevice, attach: bool) -> None:
        if not self.cfg.vm:
            self._notify("اختر جهازًا في الإعدادات أولًا.", error=True)
            return
        try:
            if attach:
                if not vbox.is_running(self.cfg.vm):
                    vbox.start_headless(self.cfg.vm)
                    if not rdp.wait_for_port(self.cfg.host, self.cfg.port, timeout=240):
                        raise vbox.VBoxError("الجهاز يعمل لكن RDP لم يجهز بعد.")
                vbox.usb_attach(self.cfg.vm, device.uuid)
                self._notify(f"تم وصل {device.label} بالجهاز")
            else:
                vbox.usb_detach(self.cfg.vm, device.uuid)
                self._notify(f"تم فصل {device.label}")
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
            self._notify("تم فصل كل الأجهزة")
        except vbox.VBoxError as exc:
            self._notify(str(exc), error=True)
        QTimer.singleShot(1200, self._rebuild)

    def _open_settings(self) -> None:
        from .settings_window import SettingsDialog

        dialog = SettingsDialog(cfgmod.load())
        dialog.exec()
        self.cfg = cfgmod.load()
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

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setDesktopFileName("winbridge")
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("No system tray available (StatusNotifierItem).", file=sys.stderr)
        return 2

    tray = Tray(app)
    if not cfgmod.load().configured:
        QTimer.singleShot(0, tray._open_settings)
    return tray.run()
