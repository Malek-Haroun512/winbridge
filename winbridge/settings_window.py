"""Settings / first-run window (PySide6)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import __app_name__
from . import config as cfgmod
from . import rdp, setup_guest, vbox
from .config import AppEntry, Config


class Worker(QThread):
    line = Signal(str)
    done = Signal(bool, str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:  # pragma: no cover - thread body
        try:
            self._fn(self.line.emit)
            self.done.emit(True, "")
        except Exception as exc:  # noqa: BLE001 - report to UI
            self.done.emit(False, str(exc))


class SettingsDialog(QDialog):
    def __init__(self, cfg: Config, parent: QWidget | None = None):
        super().__init__(parent)
        self.cfg = cfg
        self.worker: Worker | None = None
        self.setWindowTitle(f"{__app_name__} — الإعدادات")
        self.setMinimumWidth(720)
        self._build()
        self._load()

    # ------------------------------------------------------------------ UI

    def _build(self) -> None:
        outer = QVBoxLayout(self)

        # -- connection -------------------------------------------------
        conn = QGroupBox("الاتصال بجهاز VirtualBox")
        form = QFormLayout(conn)

        vm_row = QHBoxLayout()
        self.vm_combo = QComboBox()
        self.vm_combo.setEditable(True)
        refresh = QPushButton("تحديث")
        refresh.setIcon(QIcon.fromTheme("view-refresh"))
        refresh.clicked.connect(self._reload_vms)
        vm_row.addWidget(self.vm_combo, 1)
        vm_row.addWidget(refresh)
        form.addRow("الجهاز:", vm_row)

        self.host_edit = QLineEdit()
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        host_row = QHBoxLayout()
        host_row.addWidget(self.host_edit, 2)
        host_row.addWidget(QLabel("المنفذ:"))
        host_row.addWidget(self.port_spin)
        form.addRow("العنوان:", host_row)

        self.user_edit = QLineEdit()
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.Password)
        show = QPushButton("👁")
        show.setFixedWidth(32)
        show.setCheckable(True)
        show.toggled.connect(
            lambda on: self.pass_edit.setEchoMode(
                QLineEdit.Normal if on else QLineEdit.Password
            )
        )
        pass_row = QHBoxLayout()
        pass_row.addWidget(self.pass_edit, 1)
        pass_row.addWidget(show)
        form.addRow("المستخدم:", self.user_edit)
        form.addRow("كلمة السر:", pass_row)

        self.start_check = QCheckBox("تشغيل الجهاز تلقائيًا (headless) عند فتح تطبيق")
        form.addRow("", self.start_check)
        outer.addWidget(conn)

        # -- apps --------------------------------------------------------
        apps_box = QGroupBox("التطبيقات")
        apps_layout = QVBoxLayout(apps_box)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["الاسم", "المسار داخل ويندوز"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        apps_layout.addWidget(self.table)

        buttons = QHBoxLayout()
        add = QPushButton("إضافة")
        add.setIcon(QIcon.fromTheme("list-add"))
        remove = QPushButton("حذف")
        remove.setIcon(QIcon.fromTheme("list-remove"))
        add.clicked.connect(lambda: self._add_row("تطبيق جديد", "C:\\Windows\\System32\\notepad.exe"))
        remove.clicked.connect(self._remove_row)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        apps_layout.addLayout(buttons)
        outer.addWidget(apps_box)

        # -- actions -----------------------------------------------------
        actions = QHBoxLayout()
        self.prepare_btn = QPushButton("جهّز الجهاز (المضيف)")
        self.prepare_btn.setToolTip("إضافة تحويل المنفذ + تفعيل USB + إقلاع الجهاز")
        self.prepare_btn.clicked.connect(self._prepare)
        self.script_btn = QPushButton("اكتب سكربت ويندوز")
        self.script_btn.setToolTip("ينشئ winbridge-setup.cmd لتشغيله مرة واحدة داخل ويندوز")
        self.script_btn.clicked.connect(self._write_script)
        self.test_btn = QPushButton("اختبر الاتصال")
        self.test_btn.clicked.connect(self._test)
        actions.addWidget(self.prepare_btn)
        actions.addWidget(self.script_btn)
        actions.addWidget(self.test_btn)
        actions.addStretch(1)
        outer.addLayout(actions)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        self.log_view.setFixedHeight(130)
        outer.addWidget(self.log_view)

        box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Close)
        box.accepted.connect(self._save_and_close)
        box.rejected.connect(self.reject)
        outer.addWidget(box)

    # ------------------------------------------------------------- helpers

    def _load(self) -> None:
        self._reload_vms()
        self.host_edit.setText(self.cfg.host)
        self.port_spin.setValue(self.cfg.port)
        self.user_edit.setText(self.cfg.user)
        self.pass_edit.setText(self.cfg.password)
        self.start_check.setChecked(self.cfg.start_vm)
        for app in self.cfg.apps:
            self._add_row(app.name, app.target, app.icon)

    def _reload_vms(self) -> None:
        current = self.vm_combo.currentText()
        self.vm_combo.clear()
        try:
            names = list(vbox.list_vms())
        except vbox.VBoxError as exc:
            self._log(f"VBoxManage: {exc}")
            names = []
        self.vm_combo.addItems(names)
        wanted = self.cfg.vm or current
        if wanted:
            index = self.vm_combo.findText(wanted)
            if index >= 0:
                self.vm_combo.setCurrentIndex(index)
            else:
                self.vm_combo.setEditText(wanted)

    def _add_row(self, name: str, target: str, icon: str = "") -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        self.table.setItem(row, 1, QTableWidgetItem(target))
        self.table.item(row, 0).setData(Qt.UserRole, icon)

    def _remove_row(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def _collect(self) -> Config:
        apps = []
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            target_item = self.table.item(row, 1)
            if not name_item or not target_item:
                continue
            apps.append(
                AppEntry(
                    name=name_item.text().strip(),
                    target=target_item.text().strip(),
                    icon=(name_item.data(Qt.UserRole) or ""),
                )
            )
        self.cfg.vm = self.vm_combo.currentText().strip()
        self.cfg.host = self.host_edit.text().strip() or "127.0.0.1"
        self.cfg.port = self.port_spin.value()
        self.cfg.user = self.user_edit.text().strip()
        self.cfg.password = self.pass_edit.text()
        self.cfg.start_vm = self.start_check.isChecked()
        self.cfg.apps = apps
        return self.cfg

    def _log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def _busy(self, busy: bool) -> None:
        for widget in (self.prepare_btn, self.script_btn, self.test_btn):
            widget.setEnabled(not busy)

    # ------------------------------------------------------------- actions

    def _prepare(self) -> None:
        cfg = self._collect()
        if not cfg.vm:
            QMessageBox.warning(self, __app_name__, "اختر جهاز VirtualBox أولًا.")
            return
        self._busy(True)
        self._log(f"— تهيئة {cfg.vm} —")

        def job(log):
            setup_guest.prepare_host(cfg.vm, cfg, log=log)
            log("إقلاع الجهاز …")
            vbox.start_headless(cfg.vm)
            if rdp.wait_for_port(cfg.host, cfg.port, timeout=240):
                log(f"RDP جاهز على {cfg.host}:{cfg.port}")
            else:
                log("لم يُفتح منفذ RDP بعد — شغّل سكربت ويندوز داخل الجهاز.")
            try:
                path = setup_guest.write_guest_script(cfg)
                log(f"سكربت ويندوز: {path}")
            except OSError as exc:
                log(f"تعذّر كتابة السكربت: {exc}")

        self.worker = Worker(job, self)
        self.worker.line.connect(self._log)
        self.worker.done.connect(self._worker_done)
        self.worker.start()

    def _write_script(self) -> None:
        cfg = self._collect()
        path = setup_guest.write_guest_script(cfg)
        self._log(f"كُتب: {path}")
        QMessageBox.information(
            self,
            __app_name__,
            f"حُفظ السكربت في:\n{path}\n\n"
            + setup_guest.INSTRUCTIONS,
        )

    def _test(self) -> None:
        cfg = self._collect()
        if rdp.port_open(cfg.host, cfg.port):
            self._log(f"✔ منفذ RDP مفتوح على {cfg.host}:{cfg.port}")
        else:
            self._log(f"✘ لا يوجد رد على {cfg.host}:{cfg.port}")

    def _worker_done(self, ok: bool, message: str) -> None:
        self._busy(False)
        if not ok:
            self._log(f"خطأ: {message}")

    def _save_and_close(self) -> None:
        cfgmod.save(self._collect())
        self.accept()


def open_settings(cfg: Config) -> Config:
    app = QApplication.instance() or QApplication([])
    dialog = SettingsDialog(cfg)
    dialog.exec()
    return cfgmod.load() if cfgmod.CONFIG_PATH.exists() else cfg
