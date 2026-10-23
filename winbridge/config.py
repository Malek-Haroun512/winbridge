"""Configuration handling (~/.config/winbridge/config.json)."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_DIR = "winbridge"


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_DIR


def state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / APP_DIR


CONFIG_PATH = config_dir() / "config.json"


@dataclass
class AppEntry:
    name: str
    target: str
    icon: str = ""


@dataclass
class Config:
    vm: str = ""
    host: str = "127.0.0.1"
    port: int = 13389
    guest_port: int = 3389
    user: str = "Admin"
    password: str = ""
    apps: list[AppEntry] = field(default_factory=list)
    start_vm: bool = True
    usb_capture_on_start: bool = False

    # ---------------------------------------------------------------- helpers

    @property
    def configured(self) -> bool:
        return bool(self.vm and self.user)

    def to_json(self) -> dict:
        data = asdict(self)
        data["apps"] = [asdict(app) for app in self.apps]
        return data

    @classmethod
    def from_json(cls, data: dict) -> "Config":
        apps = [AppEntry(**app) for app in data.pop("apps", []) or []]
        known = {f for f in cls.__dataclass_fields__ if f != "apps"}
        cfg = cls(**{k: v for k, v in data.items() if k in known})
        cfg.apps = apps
        return cfg


def load() -> Config:
    if CONFIG_PATH.exists():
        try:
            return Config.from_json(json.loads(CONFIG_PATH.read_text("utf-8")))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return Config()


def save(cfg: Config) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(cfg.to_json(), indent=2, ensure_ascii=False) + "\n", "utf-8"
    )
    os.chmod(CONFIG_PATH, stat.S_IRUSR | stat.S_IWUSR)
