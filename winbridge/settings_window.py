"""Settings / first-run window (PySide6), bilingual (English / العربية)."""

from __future__ import annotations

from PySide6.QtCore import QLocale, QThread, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
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
from . import config as cfgmod, rdp, setup_guest, vbox, i18n
from .config import AppEntry, Config
from .i18n import t


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
        if i18n.is_rtl():
            self.setLayoutDirection(Qt.RightToLeft)
        self.setWindowTitle(t("win_title", app=__app_name__))
        self.setMinimumWidth(720)
        self._build()
        self._load()

    # ------------------------------------------------------------------ UI

    def _build(self) -> None:
        outer = QVBoxLayout(self)

        # -- connection --------------------------------------------------
        conn = QGroupBox(t("group_connection"))
        form = QFormLayout(conn)

        vm_row = QHBoxLayout()
        self.vm_combo = QComboBox()
        self.vm_combo.setEditable(True)
        refresh = QPushButton(t("btn_refresh"))
        refresh.setIcon(QIcon.fromTheme("view-refresh"))
        refresh.clicked.connect(self._reload_vms)
        vm_row.addWidget(self.vm_combo, 1)
        vm_row.addWidget(refresh)
        form.addRow(t("lbl_machine"), vm_row)

        self.host_edit = QLineEdit()
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        # keep Latin digits for ports even on Arabic/Indic number locales
        self.port_spin.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        host_row = QHBoxLayout()
        host_row.addWidget(self.host_edit, 2)
        host_row.addWidget(QLabel(t("lbl_port")))
        host_row.addWidget(self.port_spin)
        form.addRow(t("lbl_address"), host_row)

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
        form.addRow(t("lbl_user"), self.user_edit)
        form.addRow(t("lbl_password"), pass_row)

        self.start_check = QCheckBox(t("chk_autostart"))
        form.addRow("", self.start_check)
        outer.addWidget(conn)

        # -- language ----------------------------------------------------
        lang_box = QGroupBox(t("group_language"))
        lang_form = QFormLayout(lang_box)
        self.lang_combo = QComboBox()
        self.lang_combo.addItem(t("lang_auto"), "auto")
        for code, label in i18n.LANGUAGES.items():
            self.lang_combo.addItem(label, code)
        lang_form.addRow(t("lbl_language"), self.lang_combo)
        outer.addWidget(lang_box)

        # -- apps --------------------------------------------------------
        apps_box = QGroupBox(t("group_apps"))
        apps_layout = QVBoxLayout(apps_box)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([t("col_name"), t("col_path")])
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(150)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        apps_layout.addWidget(self.table)

        buttons = QHBoxLayout()
        add = QPushButton(t("btn_add"))
        add.setIcon(QIcon.fromTheme("list-add"))
        remove = QPushButton(t("btn_remove"))
        remove.setIcon(QIcon.fromTheme("list-remove"))
        add.clicked.connect(
            lambda: self._add_row(t("new_app_name"), "C:\\Windows\\System32\\notepad.exe")
        )
        remove.clicked.connect(self._remove_row)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        apps_layout.addLayout(buttons)
        outer.addWidget(apps_box)

        # -- actions -----------------------------------------------------
        actions = QHBoxLayout()
        self.prepare_btn = QPushButton(t("menu_vm_prepare"))
        self.prepare_btn.setToolTip(t("tip_prepare"))
        self.prepare_btn.clicked.connect(self._prepare)
        self.script_btn = QPushButton(t("btn_write_script"))
        self.script_btn.setToolTip(t("tip_script"))
        self.script_btn.clicked.connect(self._write_script)
        self.test_btn = QPushButton(t("btn_test_connection"))
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
        box.button(QDialogButtonBox.Save).setText(t("btn_save"))
        box.button(QDialogButtonBox.Close).setText(t("btn_close"))
        box.accepted.connect(self._save_and_close)
        box.rejected.connect(self.reject)
        outer.addWidget(box)

    # -------------------------------------------------------------- helpers

    def _load(self) -> None:
        self._reload_vms()
        self.host_edit.setText(self.cfg.host)
        self.port_spin.setValue(self.cfg.port)
        self.user_edit.setText(self.cfg.user)
        self.pass_edit.setText(self.cfg.password)
        self.start_check.setChecked(self.cfg.start_vm)
        index = self.lang_combo.findData(self.cfg.language)
        self.lang_combo.setCurrentIndex(index if index >= 0 else 0)
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
        self.cfg.language = self.lang_combo.currentData() or "auto"
        return self.cfg

    def _log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def _busy(self, busy: bool) -> None:
        for widget in (self.prepare_btn, self.script_btn, self.test_btn):
            widget.setEnabled(not busy)

    # -------------------------------------------------------------- actions

    def _prepare(self) -> None:
        cfg = self._collect()
        if not cfg.vm:
            QMessageBox.warning(self, __app_name__, t("msg_choose_vm"))
            return
        self._busy(True)
        self._log(t("log_preparing", vm=cfg.vm))

        def job(log):
            setup_guest.prepare_host(cfg.vm, cfg, log=log)
            if not vbox.is_running(cfg.vm):
                log(t("log_booting"))
                vbox.start_headless(cfg.vm)
                setup_guest.wait_for_boot(log=log)
            if setup_guest.provision(cfg, log=log):
                verified = rdp.verify_credentials(cfg, timeout=20)
                if verified is False:
                    log(t("err_rdp_verify"))
                else:
                    log(t("log_setup_complete"))
                    if verified is None:
                        log(t("log_setup_unverified"))
                return
            log(t("log_provision_timeout"))
            try:
                path = setup_guest.write_guest_script(cfg)
                log(t("log_script_written", path=path))
            except OSError as exc:
                log(t("log_script_failed", message=exc))

        self.worker = Worker(job, self)
        self.worker.line.connect(self._log)
        self.worker.done.connect(self._worker_done)
        self.worker.start()

    def _write_script(self) -> None:
        cfg = self._collect()
        path = setup_guest.write_guest_script(cfg)
        self._log(t("log_script_written", path=path))
        QMessageBox.information(
            self,
            __app_name__,
            t("msg_script_saved", path=path, instructions=setup_guest.instructions()),
        )

    def _test(self) -> None:
        cfg = self._collect()

        def job(log):
            if not rdp.port_open(cfg.host, cfg.port):
                log(t("log_port_closed", host=cfg.host, port=cfg.port))
                return
            log(t("log_port_open", host=cfg.host, port=cfg.port))
            result = rdp.verify_credentials(cfg, timeout=15)
            if result is True:
                state = t("cli_auth_ok")
            elif result is False:
                state = t("cli_auth_fail")
            else:
                state = t("cli_auth_unknown")
            log(f"{t('lbl_rdp_auth')}: {state}")

        self._busy(True)
        self.worker = Worker(job, self)
        self.worker.line.connect(self._log)
        self.worker.done.connect(self._worker_done)
        self.worker.start()

    def _worker_done(self, ok: bool, message: str) -> None:
        self._busy(False)
        if not ok:
            self._log(t("log_error", message=message))

    def _save_and_close(self) -> None:
        cfg = self._collect()
        cfgmod.save(cfg)
        i18n.set_language(cfg.language if cfg.language != "auto" else i18n.detect())
        self.accept()


def open_settings(cfg: Config) -> Config:
    app = QApplication.instance() or QApplication([])
    dialog = SettingsDialog(cfg)
    dialog.exec()
    return cfgmod.load() if cfgmod.CONFIG_PATH.exists() else cfg
