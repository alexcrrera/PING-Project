"""Run the digital-twin GUI independently of the ground station."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PING digital twin / NiceGUI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    from nicegui import ui
    from .view import configure_twin_page

    configure_twin_page()
    ui.run(host=args.host, port=args.port, reload=False, native=False,
           show=not args.no_browser, title="PING / Digital twin", dark=True,
           favicon="◒", show_welcome_message=False,
           binding_refresh_interval=.1, reconnect_timeout=5.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
