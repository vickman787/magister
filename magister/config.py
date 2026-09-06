from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def bootstrap() -> None:
    load_dotenv(ROOT / ".env")


def _config_dir() -> Path:
    override = os.getenv("MAGISTER_CONFIG_DIR")
    return Path(override) if override else ROOT / "config"


def load_settings() -> dict:
    return _load_yaml(_config_dir() / "settings.yaml")


def load_risk_limits() -> dict:
    return _load_yaml(_config_dir() / "risk_limits.yaml")


def data_dir() -> Path:
    override = os.getenv("MAGISTER_DATA_DIR")
    path = Path(override) if override else ROOT / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}
