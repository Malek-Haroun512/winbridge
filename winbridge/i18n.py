"""Tiny gettext-free translation layer (English / العربية)."""

from __future__ import annotations

import os

LANGUAGES = {"en": "English", "ar": "العربية"}

_EN: dict[str, str] = {
    # ---------------------------------------------------------------- generic
    "app_settings": "Settings",
    "btn_refresh": "Refresh",
    "btn_add": "Add",
    "btn_remove": "Remove",
    "btn_write_script": "Write Windows script",
    "btn_test_connection": "Test connection",
    "btn_save": "Save",
    "btn_close": "Close",
    # ------------------------------------------------------------------ tray
    "tray_status": "{app} — {vm} ({state})",
    "tray_status_novm": "{app} — not configured",
    "state_running": "running",
    "state_stopped": "stopped",
    "state_unknown": "unknown",
    "menu_vm": "VM control",
    "menu_vm_shutdown": "Shut down VM",
    "menu_vm_restart": "Restart VM",
    "menu_vm_start": "Start VM",
    "menu_vm_start_gui": "Start with GUI",
    "menu_vm_console": "Open VirtualBox console",
    "menu_vm_prepare": "Prepare host settings",
    "menu_desktop": "Windows desktop",
    "menu_apps": "Applications",
    "menu_no_apps": "No apps yet — Settings",
    "menu_manage_apps": "Manage applications…",
    "menu_usb": "USB devices",
    "usb_no_extpack": "⚠ Extension Pack not installed (USB 1.1 only)",
    "usb_none": "No USB devices detected",
    "usb_error": "Error: {message}",
    "usb_refresh": "Refresh list",
    "usb_detach_all": "Detach all devices",
    "menu_settings": "Settings…",
    "menu_quit": "Quit",
    "notify_vm_started": "{vm} started (headless)",
    "notify_vm_started_gui": "{vm} started with GUI",
    "notify_vm_stopped": "{vm} shut down",
    "notify_vm_restarted": "{vm} restarted",
    "notify_usb_attached": "{device} attached to the VM",
    "notify_usb_detached": "{device} detached",
    "notify_usb_detached_all": "All devices detached",
    "err_choose_vm": "Choose a machine in Settings first.",
    "err_no_virtualbox_gui": "VirtualBox GUI not found. Install it or start it manually.",
    "err_launch": "Couldn't open {name} (exit {code}). See ~/.local/state/winbridge/freerdp.log",
    # -------------------------------------------------------------- settings
    "win_title": "{app} — Settings",
    "group_connection": "VirtualBox connection",
    "lbl_machine": "Machine:",
    "lbl_address": "Address:",
    "lbl_port": "Port:",
    "lbl_user": "User:",
    "lbl_password": "Password:",
    "chk_autostart": "Start the VM headless automatically when an app is opened",
    "group_apps": "Applications",
    "col_name": "Name",
    "col_path": "Path inside Windows",
    "new_app_name": "New application",
    "group_language": "Language",
    "lbl_language": "Interface language:",
    "lang_auto": "Automatic",
    "tip_prepare": "Add the NAT port-forward, enable USB and boot the VM",
    "tip_script": "Creates winbridge-setup.cmd to run once inside Windows",
    "msg_choose_vm": "Choose a VirtualBox machine first.",
    "log_port_open": "✔ RDP port open on {host}:{port}",
    "log_port_closed": "✘ No answer from {host}:{port}",
    "msg_script_saved": "Script saved to:\n{path}\n\n{instructions}",
    "log_preparing": "— Preparing {vm} —",
    "instructions_guest": (
        "Prepare the guest once:\n\n"
        "1. Press \"Start with GUI\" to open the VirtualBox window.\n"
        "2. Log in to Windows.\n"
        "3. Copy `winbridge-setup.cmd` into the guest (drag & drop or a shared\n"
        "   folder) and run it as administrator.\n"
        "4. Come back to WinBridge and press \"Test connection\"."
    ),
    # ------------------------------------------------------------ operations
    "log_starting_vm": "Starting {vm} …",
    "log_stopping_vm": "Stopping the VM to change its settings …",
    "log_acpi_failed": "  ACPI did not work — trying Guest Additions …",
    "err_poweroff_failed": "Could not power off the VM. Shut it down from VirtualBox and retry.",
    "log_adding_forward": "Adding the RDP port-forward …",
    "log_forward_added": "  new rule added",
    "log_forward_exists": "  rule already present",
    "log_usb_enable": "Enabling the USB controller …",
    "log_extpack_missing": "  note: Extension Pack not installed → USB 1.1 only.",
    "log_booting": "Booting the VM …",
    "log_rdp_ready": "RDP ready on {host}:{port}",
    "log_rdp_not_ready": "RDP port is not open yet — run the Windows script inside the guest.",
    "log_waiting_boot": "Waiting for Windows to finish booting ({seconds}s) …",
    "log_provision_service": "Configuring Windows through Guest Additions …",
    "log_provision_console": "Configuring Windows automatically — this takes a few seconds …",
    "log_provision_done": "Windows is configured. No manual steps needed.",
    "log_provision_timeout": (
        "Automatic setup did not finish. Run the generated script inside "
        "Windows once (see below)."
    ),
    "log_setup_complete": "Setup complete. Windows apps will open as normal Linux windows.",
    "cli_setup_manual_help": "Skip the automatic Windows configuration",
    "cli_setup_no_start_help": "Only prepare host settings; do not boot the VM",
    "cli_setup_boot_wait_help": "Seconds to wait for a cold Windows boot (default: 90)",
    "log_script_written": "Windows script: {path}",
    "log_script_failed": "Could not write the script: {message}",
    "log_reusing_session": "Closing the previous connection ({count}) to reuse the session …",
    "log_error": "Error: {message}",
    # ----------------------------------------------------------------- errors
    "err_vboxmanage_missing": "VBoxManage not found in PATH.\nInstall VirtualBox first (e.g. sudo pacman -S virtualbox virtualbox-host-modules-arch).",
    "err_timeout": "VBoxManage timed out: {args}",
    "err_vbox_failed": "VBoxManage {args} failed",
    "err_nat_required": "Machine {vm} does not use NAT on the first adapter. Set its network adapter to NAT and retry.",
    "err_usb_poweroff": "The VM must be powered off to enable USB.",
    "err_freerdp_missing": "FreeRDP not found. Install it with:\n  sudo pacman -S freerdp",
    "err_no_vm_selected": "No VirtualBox machine selected yet (Settings → Machine).",
    "err_vm_stopped": "{vm} is powered off. Start it or enable automatic startup.",
    "err_console_session": (
        "Windows is signed in inside the VirtualBox window, so the remote "
        "session was taken over. Sign out in Windows (or close the VM window) "
        "and try again."
    ),
    "err_bad_credentials": (
        "Windows rejected the user name or password — check them in Settings."
    ),
    "err_rail_allowlist": (
        "Windows blocked the app from starting. Run the Windows setup script "
        "once (Settings → Prepare host settings) so any application is allowed."
    ),
    "err_security_mismatch": (
        "Windows changed its RDP security settings. Open the app again — "
        "WinBridge will renegotiate automatically."
    ),
    "log_retry_security": "Retrying with {mode} security …",
    "err_rdp_port_closed": "The VM booted but the RDP port never opened. Make sure Remote Desktop is enabled inside Windows (Settings → Prepare host, then run the Windows script).",
    "err_rdp_verify": (
        "Windows is running but did not accept the RDP sign-in. Check the user "
        "name and password in Settings. If they are correct, use a stock "
        "Windows 10/11 image: stripped 'Lite' builds often break Remote Desktop."
    ),
    # -------------------------------------------------------------------- cli
    "cli_usb_line": "{mark} {uuid}  {ids}  {label}  [{state}]",
    "cli_usb_no_match": "No USB device matching {target}",
    "cli_usb_no_vm": "No machine configured.",
    "cli_usb_attached": "Attached {device}",
    "cli_usb_detached": "Detached {device}",
    "cli_setup_need_vm": "Specify the machine: winbridge setup --vm <name>",
    "cli_extpack_yes": "installed",
    "cli_extpack_no": "not installed (USB 1.1 only)",
    "cli_vm_running": "yes",
    "cli_vm_stopped": "no",
    "cli_usb_captured": "USB captured: {devices}",
    "cli_tray_help": "Run the taskbar (tray) icon",
    "cli_desktop_help": "Open the Windows desktop",
    "cli_app_help": "Run a Windows app in its own window",
    "cli_app_name_help": "App name from Settings, or an .exe path",
    "cli_usb_help": "Manage USB devices",
    "cli_usb_target_help": "UUID or part of the name",
    "cli_setup_help": "Prepare the machine from the Linux side",
    "cli_setup_vm_help": "VirtualBox machine name",
    "cli_doctor_help": "Check requirements",
    "lbl_vboxmanage": "VBoxManage",
    "lbl_freerdp": "FreeRDP",
    "lbl_extpack": "Extension Pack",
    "lbl_config": "Config",
    "lbl_vm_running": "VM running",
    "lbl_rdp_port": "RDP port open",
    "lbl_rdp_auth": "RDP sign-in",
    "cli_auth_ok": "accepted",
    "cli_auth_fail": "rejected (check credentials; use stock Windows for 'Lite' builds)",
    "lbl_security": "RDP security",
    "common_yes": "yes",
    "common_no": "no",
    "log_warning": "  warning: {message}",
    "usb_controller_present": "already enabled",
    "help_usage": "usage:",
    "help_positional": "positional arguments",
    "help_options": "options",
    "help_help": "show this help message and exit",
    "help_version": "show the version and exit",
    "specific_instructions": "",
}

_AR: dict[str, str] = {
    # ---------------------------------------------------------------- generic
    "app_settings": "الإعدادات",
    "btn_refresh": "تحديث",
    "btn_add": "إضافة",
    "btn_remove": "حذف",
    "btn_write_script": "اكتب سكربت ويندوز",
    "btn_test_connection": "اختبر الاتصال",
    "btn_save": "حفظ",
    "btn_close": "إغلاق",
    # ------------------------------------------------------------------ tray
    "tray_status": "{app} — {vm} ({state})",
    "tray_status_novm": "{app} — لم يُضبط بعد",
    "state_running": "شغّال",
    "state_stopped": "متوقف",
    "state_unknown": "غير معروف",
    "menu_vm": "إدارة الجهاز",
    "menu_vm_shutdown": "إطفاء الجهاز",
    "menu_vm_restart": "إعادة تشغيل الجهاز",
    "menu_vm_start": "تشغيل الجهاز",
    "menu_vm_start_gui": "تشغيل مع واجهة",
    "menu_vm_console": "فتح نافذة VirtualBox",
    "menu_vm_prepare": "تهيئة إعدادات المضيف",
    "menu_desktop": "سطح مكتب ويندوز",
    "menu_apps": "التطبيقات",
    "menu_no_apps": "لا تطبيقات بعد — الإعدادات",
    "menu_manage_apps": "إدارة التطبيقات…",
    "menu_usb": "أجهزة USB",
    "usb_no_extpack": "⚠ Extension Pack غير مثبّت (USB 1.1 فقط)",
    "usb_none": "لا أجهزة USB مكتشفة",
    "usb_error": "خطأ: {message}",
    "usb_refresh": "تحديث القائمة",
    "usb_detach_all": "فصل كل الأجهزة",
    "menu_settings": "الإعدادات…",
    "menu_quit": "خروج",
    "notify_vm_started": "تم تشغيل {vm} (headless)",
    "notify_vm_started_gui": "تم تشغيل {vm} مع واجهة",
    "notify_vm_stopped": "تم إطفاء {vm}",
    "notify_vm_restarted": "أُعيد تشغيل {vm}",
    "notify_usb_attached": "تم وصل {device} بالجهاز",
    "notify_usb_detached": "تم فصل {device}",
    "notify_usb_detached_all": "تم فصل كل الأجهزة",
    "err_choose_vm": "اختر جهازًا في الإعدادات أولًا.",
    "err_no_virtualbox_gui": "لم أجد واجهة VirtualBox. ثبّتها أو شغّلها يدويًا.",
    "err_launch": "تعذّر فتح {name} (رمز {code}). راجع ~/.local/state/winbridge/freerdp.log",
    # -------------------------------------------------------------- settings
    "win_title": "{app} — الإعدادات",
    "group_connection": "الاتصال بجهاز VirtualBox",
    "lbl_machine": "الجهاز:",
    "lbl_address": "العنوان:",
    "lbl_port": "المنفذ:",
    "lbl_user": "المستخدم:",
    "lbl_password": "كلمة السر:",
    "chk_autostart": "تشغيل الجهاز تلقائيًا (headless) عند فتح تطبيق",
    "group_apps": "التطبيقات",
    "col_name": "الاسم",
    "col_path": "المسار داخل ويندوز",
    "new_app_name": "تطبيق جديد",
    "group_language": "اللغة",
    "lbl_language": "لغة الواجهة:",
    "lang_auto": "تلقائي",
    "tip_prepare": "إضافة تحويل المنفذ + تفعيل USB + إقلاع الجهاز",
    "tip_script": "ينشئ winbridge-setup.cmd لتشغيله مرة واحدة داخل ويندوز",
    "msg_choose_vm": "اختر جهاز VirtualBox أولًا.",
    "log_port_open": "✔ منفذ RDP مفتوح على {host}:{port}",
    "log_port_closed": "✘ لا يوجد رد على {host}:{port}",
    "msg_script_saved": "حُفظ السكربت في:\n{path}\n\n{instructions}",
    "log_preparing": "— تهيئة {vm} —",
    "instructions_guest": (
        "جهّز النسخة داخل ويندوز مرة واحدة:\n\n"
        "1. اضغط «تشغيل مع واجهة» لفتح نافذة VirtualBox.\n"
        "2. سجّل الدخول إلى ويندوز.\n"
        "3. انسخ الملف `winbridge-setup.cmd` إلى ويندوز (سحب وإفلات أو مجلد\n"
        "   مشترك) وشغّله كمسؤول (Run as administrator).\n"
        "4. ارجع إلى WinBridge واضغط «اختبر الاتصال»."
    ),
    # ------------------------------------------------------------ operations
    "log_starting_vm": "تشغيل {vm} …",
    "log_stopping_vm": "إطفاء الجهاز لتعديل إعداداته …",
    "log_acpi_failed": "  ACPI لم ينجح — محاولة عبر Guest Additions …",
    "err_poweroff_failed": "تعذّر إطفاء الجهاز. أطفئه يدويًا من VirtualBox ثم أعد المحاولة.",
    "log_adding_forward": "إضافة تحويل منفذ RDP …",
    "log_forward_added": "  منفذ جديد أُضيف",
    "log_forward_exists": "  المنفذ موجود مسبقًا",
    "log_usb_enable": "تفعيل وحدة USB …",
    "log_extpack_missing": "  ملاحظة: Extension Pack غير مثبّت ← USB 1.1 فقط.",
    "log_booting": "إقلاع الجهاز …",
    "log_rdp_ready": "RDP جاهز على {host}:{port}",
    "log_rdp_not_ready": "لم يُفتح منفذ RDP بعد — شغّل سكربت ويندوز داخل الجهاز.",
    "log_waiting_boot": "عم نستنى ويندوز يخلص إقلاع ({seconds} ثانية) …",
    "log_provision_service": "تجهيز ويندوز عبر Guest Additions …",
    "log_provision_console": "تجهيز ويندوز تلقائيًا — بياخد ثواني …",
    "log_provision_done": "ويندوز صار جاهز، بلا أي خطوة يدوية.",
    "log_provision_timeout": (
        "التجهيز التلقائي ما خلص. شغّل السكربت المولّد جوّا ويندوز مرة واحدة "
        "(التفاصيل تحت)."
    ),
    "log_setup_complete": "خلص الإعداد. تطبيقات ويندوز رح تفتح كنوافذ لينكس عادية.",
    "cli_setup_manual_help": "تخطّي تجهيز ويندوز التلقائي",
    "cli_setup_no_start_help": "جهّز إعدادات المضيف فقط؛ لا تشغّل الجهاز",
    "cli_setup_boot_wait_help": "ثواني انتظار إقلاع ويندوز البارد (الافتراضي: 90)",
    "log_script_written": "سكربت ويندوز: {path}",
    "log_script_failed": "تعذّر كتابة السكربت: {message}",
    "log_reusing_session": "إغلاق الاتصال السابق ({count}) لإعادة استخدام الجلسة …",
    "log_error": "خطأ: {message}",
    # ----------------------------------------------------------------- errors
    "err_vboxmanage_missing": "VBoxManage غير موجود في PATH.\nثبّت VirtualBox أولًا (مثال: sudo pacman -S virtualbox virtualbox-host-modules-arch).",
    "err_timeout": "انتهت مهلة VBoxManage: {args}",
    "err_vbox_failed": "فشل VBoxManage {args}",
    "err_nat_required": "الجهاز {vm} لا يستخدم شبكة NAT على المنفذ الأول. عدّل إعدادات الشبكة إلى NAT ثم أعد المحاولة.",
    "err_usb_poweroff": "لتفعيل منفذ USB يجب إطفاء الجهاز أولًا.",
    "err_freerdp_missing": "لم أجد FreeRDP. ثبّته بالأمر:\n  sudo pacman -S freerdp",
    "err_no_vm_selected": "لم يتم اختيار جهاز VirtualBox بعد (الإعدادات ← الجهاز).",
    "err_vm_stopped": "الجهاز {vm} متوقف. شغّله أو فعّل التشغيل التلقائي.",
    "err_console_session": (
        "في جلسة مفتوحة داخل نافذة VirtualBox، فانقطع اتصال RDP. سجّل الخروج "
        "من ويندوز (أو أغلق نافذة الجهاز) وأعد المحاولة."
    ),
    "err_bad_credentials": (
        "ويندوز رفض اسم المستخدم أو كلمة السر — تحقّق منهما في الإعدادات."
    ),
    "err_rail_allowlist": (
        "ويندوز منع تشغيل التطبيق. شغّل سكربت ويندوز مرة واحدة "
        "(الإعدادات ← تهيئة إعدادات المضيف) للسماح بأي تطبيق."
    ),
    "err_security_mismatch": (
        "تغيّرت إعدادات أمان RDP في ويندوز. افتح التطبيق مرة أخرى — "
        "سيُعيد WinBridge التفاوض تلقائيًا."
    ),
    "log_retry_security": "إعادة المحاولة بأمان {mode} …",
    "err_rdp_port_closed": "الجهاز أقلع لكن منفذ RDP ما فتح. تأكد من تفعيل RDP داخل ويندوز (الإعدادات ← جهّز الجهاز، ثم شغّل سكربت ويندوز).",
    "err_rdp_verify": (
        "ويندوز شغّال بس رفض تسجيل الدخول عبر RDP. تأكد من اسم المستخدم "
        "وكلمة المرور بالإعدادات. إذا صحّين، استخدم نسخة ويندوز 10/11 أصلية: "
        "نسخ Lite المقصوصة غالبًا بتكسر Remote Desktop."
    ),
    # -------------------------------------------------------------------- cli
    "cli_usb_line": "{mark} {uuid}  {ids}  {label}  [{state}]",
    "cli_usb_no_match": "لم أجد جهاز USB مطابقًا لـ {target}",
    "cli_usb_no_vm": "لم يتم ضبط الجهاز في الإعدادات.",
    "cli_usb_attached": "وُصل {device}",
    "cli_usb_detached": "فُصل {device}",
    "cli_setup_need_vm": "حدّد الجهاز: winbridge setup --vm <name>",
    "cli_extpack_yes": "مثبّت",
    "cli_extpack_no": "غير مثبّت (USB 1.1 فقط)",
    "cli_vm_running": "نعم",
    "cli_vm_stopped": "لا",
    "cli_usb_captured": "أجهزة USB الموصولة: {devices}",
    "cli_tray_help": "تشغيل أيقونة شريط المهام",
    "cli_desktop_help": "فتح سطح مكتب ويندوز",
    "cli_app_help": "تشغيل تطبيق ويندوز بنافذة منفصلة",
    "cli_app_name_help": "اسم التطبيق من الإعدادات أو مسار exe",
    "cli_usb_help": "إدارة أجهزة USB",
    "cli_usb_target_help": "UUID أو جزء من الاسم",
    "cli_setup_help": "تهيئة الجهاز من جهة لينكس",
    "cli_setup_vm_help": "اسم جهاز VirtualBox",
    "cli_doctor_help": "فحص المتطلبات",
    "lbl_vboxmanage": "VBoxManage",
    "lbl_freerdp": "FreeRDP",
    "lbl_extpack": "Extension Pack",
    "lbl_config": "الإعدادات",
    "lbl_vm_running": "الجهاز يعمل",
    "lbl_rdp_port": "منفذ RDP مفتوح",
    "lbl_rdp_auth": "تسجيل دخول RDP",
    "cli_auth_ok": "مقبول",
    "cli_auth_fail": "مرفوض (تأكد من البيانات؛ استخدم ويندوز أصلي لنسخ Lite)",
    "lbl_security": "أمان RDP",
    "common_yes": "نعم",
    "common_no": "لا",
    "log_warning": "  تحذير: {message}",
    "usb_controller_present": "موجود",
    "help_usage": "الاستخدام:",
    "help_positional": "الوسائط",
    "help_options": "الخيارات",
    "help_help": "عرض هذه المساعدة والخروج",
    "help_version": "عرض الإصدار والخروج",
    "specific_instructions": "",
}

TRANSLATIONS: dict[str, dict[str, str]] = {"en": _EN, "ar": _AR}

_current = "en"


def detect() -> str:
    forced = os.environ.get("WINBRIDGE_LANG", "").strip().lower()
    if forced in TRANSLATIONS:
        return forced
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        if not value:
            continue
        lang = value.split(".")[0].split("_")[0].split("-")[0].lower()
        if lang in TRANSLATIONS:
            return lang
    return "en"


def set_language(lang: str) -> None:
    global _current  # noqa: PLW0603 - module level switch
    _current = lang if lang in TRANSLATIONS else "en"


def language() -> str:
    return _current


def is_rtl() -> bool:
    return _current == "ar"


def t(key: str, **kwargs: object) -> str:
    table = TRANSLATIONS.get(_current, _EN)
    text = table.get(key) or _EN.get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
