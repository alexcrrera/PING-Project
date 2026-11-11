"""Launch the Windows PING taskbar shortcut without a console."""

import json
from pathlib import Path
import sys
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
import webbrowser


dashboardUrl = "http://127.0.0.1:8080"


def dashboardIsRunning():
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(f"{dashboardUrl}/healthz", timeout=1) as response:
            health = json.load(response)
            return health.get("running") is True and "telemetry" in health
    except (URLError, TimeoutError, ValueError):
        return False


def launchDashboard():
    if dashboardIsRunning():
        webbrowser.open(dashboardUrl)
        return 0

    from ping_base.cli import main

    return main(["--serial-port", "COM5", "--baud", "57600"])


if __name__ == "__main__":
    if sys.stdout is None or sys.stderr is None:
        logPath = Path(sys.executable).resolve().parent.parent / "ping-launcher.log"
        with logPath.open("a", encoding="utf-8", buffering=1) as log:
            sys.stdout = sys.stderr = log
            raise SystemExit(launchDashboard())
    raise SystemExit(launchDashboard())
