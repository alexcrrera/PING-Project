"""Persist vehicle parameters across browser sessions and app restarts."""

from __future__ import annotations

from dataclasses import asdict, fields
import json
from math import isfinite
import os
from pathlib import Path
from uuid import uuid4

from .model import DigitalTwin, TwinConfig


DEFAULT_SETTINGS_PATH = Path(__file__).resolve().parents[2] / "vehicle-settings.json"


class VehicleSettings:
    def __init__(self, path: Path = DEFAULT_SETTINGS_PATH) -> None:
        self.path = Path(path)

    def load(self) -> TwinConfig:
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(saved, dict):
                raise ValueError("Settings must be an object")
            allowed = {field.name for field in fields(TwinConfig)}
            values = {key: value for key, value in saved.items() if key in allowed}
            # Earlier versions stored wheel track directly. Preserve the same
            # wheel position when introducing an outward joint offset.
            if "joint_offset_m" not in values and "track_m" in saved:
                try:
                    old_track = float(saved["track_m"])
                    body_width = float(values.get("body_width_m", TwinConfig().body_width_m))
                    if isfinite(old_track) and isfinite(body_width) and old_track >= body_width:
                        values["joint_offset_m"] = (old_track - body_width) / 2
                except (TypeError, ValueError):
                    pass
            twin = DigitalTwin()
            twin.configure(**values)
            return twin.config
        except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError, ValueError):
            return TwinConfig()

    def save(self, config: TwinConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
