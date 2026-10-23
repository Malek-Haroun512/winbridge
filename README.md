# WinBridge

Run **Windows applications from a VirtualBox VM as if they were native Linux
windows** — no full desktop in the way, no proprietary cloud, no patched
`termsrv.dll`. WinBridge is a small, hackable, MIT-licensed alternative to
WinBoat / WinApps that plugs into a Windows VM **you already have**.

> **البدء السريع (عربي):** ثبّت `virtualbox` + `freerdp` + `PySide6`، ثم
> `./install.sh`، ثم `winbridge tray` من قائمة التطبيقات. من الإعدادات اختر
> جهازك → «جهّز الجهاز (المضيف)» → «اكتب سكربت ويندوز» → شغّل
> `winbridge-setup.cmd` كمسؤول داخل ويندوز مرة واحدة. بعدها كل تطبيق تفتحه
> من الأيقونة بيطلع بنافذة لينكس منفصلة، وقائمة USB بتخليك توصل أجهزتك
> بالجهاز بضغطة.

---

## How it works

```
┌─────────────────────────── Linux ───────────────────────────┐
│  WinBridge (tray / CLI)                                     │
│      │  VBoxManage          │  xfreerdp3                     │
│      ▼                     ▼                                │
│  VirtualBox  ──NAT 127.0.0.1:13389──►  3389 (Windows RDP)   │
│                                   │                         │
│                                   └─ RAIL → single app window
└─────────────────────────────────────────────────────────────┘
```

1. **Host settings** — adds a NAT port-forward (`127.0.0.1:<port>` → guest
   `3389`), enables the VM's USB controller and boots it headless.
2. **Guest settings** — a generated `winbridge-setup.cmd` enables Remote
   Desktop, disables NLA (so plain TLS works even on hosts with a broken
   Kerberos config), opens the firewall and sets `TSAppAllowList\fDisabledAllowList=1`
   so **any** executable can be published as a RemoteApp.
3. **Running apps** — FreeRDP connects with `/app:program:...` (RAIL), so only
   the application window is streamed and it behaves like a normal X11/Wayland
   window: taskbar entry, alt-tab, clipboard, window manager decorations.

Nothing listens on an external interface: the port forward is bound to
`127.0.0.1`.

## Features

- 🖥️ Full Windows desktop in one window, or **one window per app (RAIL)**.
- 🔌 **USB passthrough from the tray** — plug/unplug any host device into the
  VM with a checkbox; state (`Captured`) is read back from VirtualBox.
- 🚀 Auto-starts the VM headless when you open an app, so the tray icon is all
  you need.
- 🧩 App list stored in `~/.config/winbridge/config.json` (name → Windows path).
- 🔐 Credentials stay local; config file is `chmod 600`.
- 🩺 `winbridge doctor` checks every dependency and connection state.
- 🧱 No kernel patches, no RDPWrap, no reverse-engineered binaries.

## Requirements

| Component | Package (Arch/CachyOS) | Notes |
|---|---|---|
| VirtualBox | `virtualbox virtualbox-host-modules-arch` | any recent 7.x |
| FreeRDP 3 | `freerdp` | provides `xfreerdp3` |
| Python + Qt | `python` + `pyside6` (or the bundled venv) | PySide6 ≥ 6.4 |
| Windows VM | Windows 10/11 **Pro/Enterprise** | Home cannot host RDP |

Optional, for USB 2.0/3.0 devices (phones, iPhones, cameras):

- **Oracle VM VirtualBox Extension Pack** (PUEL licence) matching your
  VirtualBox version. Without it the VM only gets a USB 1.1 (OHCI) controller
  — keyboards/mice/serial adapters work, phones usually do not.

## Install

```bash
git clone <your-fork-url> winbridge && cd winbridge
./install.sh          # user-level: venv in ~/.local/share/winbridge
winbridge doctor      # sanity check
winbridge tray        # icon appears in the system tray
```

`install.sh` never uses `sudo`. It creates an isolated venv, a
`~/.local/bin/winbridge` launcher, a `.desktop` entry and installs the icon.

## First-time setup

1. **Create/choose a VM** in VirtualBox with Windows 10/11 Pro and Guest
   Additions. Boot it once and create your user (or let WinBridge use an
   existing one).
2. **Open WinBridge → Settings**, pick the VM, fill user/password (the same
   Windows account), press **«جهّز الجهاز (المضيف)»**. This powers the VM off,
   adds the NAT rule, enables USB, boots it headless and writes
   `~/.config/winbridge/winbridge-setup.cmd`.
3. **Inside Windows** copy that `.cmd` in, right-click → *Run as
   administrator*, wait for `3389 … LISTENING`.
4. Back in Settings press **اختبر الاتصال**. Then open an app from the tray.

Add the apps you want in **Settings → التطبيقات** (name + `C:\full\path.exe`).
They show up in the tray menu and can be launched from the CLI:

```bash
winbridge app 3utools
winbridge app 'C:\Program Files\Some App\app.exe'
winbridge desktop
```

## USB passthrough

Tray icon → **أجهزة USB** → tick a device to attach, untick to detach.

```bash
winbridge usb list
winbridge usb attach 04e8:6860
winbridge usb detach "SAMSUNG_Android"
```

The list is refreshed from `VBoxManage list usbhost` every time the menu
opens. A device that is already `Captured` is shown with `✓`.

> USB 2.0/3.0 needs the Extension Pack. WinBridge detects it and falls back to
> OHCI, showing a warning in the menu instead of failing silently.

## Autostart (optional)

```bash
mkdir -p ~/.config/autostart
cp ~/.local/share/applications/winbridge.desktop ~/.config/autostart/
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Kerberos … ATHENA.MIT.EDU` in logs | The guest script sets `UserAuthentication=0`; make sure you ran it. WinBridge connects with `/sec:tls`. |
| `RAIL_EXEC_E_NOT_IN_ALLOWLIST` | `fDisabledAllowList` not applied — rerun the guest script as Administrator. |
| Window never appears but the app runs | A second RDP session kicked the first. Windows client SKUs allow **one** interactive session — use the full desktop for multitasking, or one app at a time. |
| `No system tray available` | Your desktop needs a StatusNotifierItem host (KDE/GNOME with AppIndicator extension). |
| VM won't power off for host setup | Shut it down from VirtualBox, then run *جهّز الجهاز* again. |

Logs: `~/.local/state/winbridge/freerdp.log` and `journalctl --user`.

## Development

```bash
python3 -m winbridge doctor
python3 -m winbridge tray
python3 -m pip install -e .   # editable install
```

Layout:

```
winbridge/
├── config.py          # JSON config (~/.config/winbridge)
├── vbox.py            # VBoxManage wrapper (VMs, NAT, USB)
├── rdp.py             # FreeRDP command builder + launcher
├── setup_guest.py     # host prep + generated Windows script
├── tray.py            # QSystemTrayIcon UI
├── settings_window.py # Qt settings dialog
└── __main__.py        # CLI
```

## License

MIT — see [LICENSE](LICENSE). VirtualBox is Oracle's; the Extension Pack is
PUEL-licensed and is *not* redistributed here.
