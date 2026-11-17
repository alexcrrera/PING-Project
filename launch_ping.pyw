"""Launch the Windows PINGUIN shortcut without a console."""

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener


dashboardUrl = "http://127.0.0.1:8080"


def dashboardIsRunning():
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(f"{dashboardUrl}/healthz", timeout=1) as response:
            health = json.load(response)
            return health.get("running") is True and "telemetry" in health
    except (URLError, TimeoutError, ValueError):
        return False



def listeningPid(port=8080):
    result = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True,
                            text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 5 and fields[0].upper() == "TCP" and fields[3].upper() == "LISTENING":
            if fields[1].rsplit(":", 1)[-1] == str(port):
                return int(fields[4])
    return None


def processIsPython(pid):
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(buffer))
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
            return False
        return Path(buffer.value).name.lower() in ("python.exe", "pythonw.exe")
    finally:
        kernel32.CloseHandle(handle)


def stopPreviousDashboard():
    if not dashboardIsRunning():
        return
    pid = listeningPid()
    if pid is None or pid == os.getpid() or not processIsPython(pid):
        raise RuntimeError("Could not safely identify the running PINGUIN process on port 8080")
    subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=True,
                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if listeningPid() != pid:
            return
        time.sleep(0.2)
    raise RuntimeError("The previous PINGUIN process did not stop")


def launchDashboard():
    stopPreviousDashboard()
    from ping_base.cli import main

    return main([])


if __name__ == "__main__":
    if sys.stdout is None or sys.stderr is None:
        logPath = Path(sys.executable).resolve().parent.parent / "pinguin-launcher.log"
        with logPath.open("a", encoding="utf-8", buffering=1) as log:
            sys.stdout = sys.stderr = log
            raise SystemExit(launchDashboard())
    raise SystemExit(launchDashboard())
