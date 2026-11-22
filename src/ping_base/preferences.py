"""Local connection preferences for the ground station."""

import json
from pathlib import Path

PREFERENCES_PATH = Path(__file__).resolve().parents[2] / ".ping-preferences.json"


def loadPort() -> str:
    try:
        port = json.loads(PREFERENCES_PATH.read_text(encoding="utf-8")).get("serialPort")
        return port.strip() if isinstance(port, str) and port.strip() else "COM7"
    except (OSError, ValueError, AttributeError):
        return "COM7"


def loadMapKeys() -> tuple[str, str]:
    try:
        data = json.loads(PREFERENCES_PATH.read_text(encoding="utf-8"))
        return tuple(data.get(key, "") if isinstance(data.get(key, ""), str) else ""
                     for key in ("thunderforestApiKey", "maptilerApiKey"))
    except (OSError, ValueError, AttributeError):
        return "", ""


def savePort(port: str) -> None:
    try:
        settings = json.loads(PREFERENCES_PATH.read_text(encoding="utf-8"))
        if not isinstance(settings, dict):
            settings = {}
    except (OSError, ValueError):
        settings = {}
    settings["serialPort"] = port
    PREFERENCES_PATH.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
