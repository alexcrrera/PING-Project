"""Locate locally licensed Suisse fonts; never bundle them with the project."""

from __future__ import annotations

import os
from pathlib import Path


def find_suisse(font_dir: str | Path | None = None) -> dict[str, Path]:
    roots = [Path(font_dir)] if font_dir else []
    roots += [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Windows/Fonts",
        Path.home() / "AppData/Local/Microsoft/Windows/Fonts",
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
        Path.home() / ".local/share/fonts",
        Path.home() / "Library/Fonts",
    ]
    found = {}
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.iterdir():
            name = path.stem.lower().replace("-", "").replace("_", "").replace(" ", "")
            if "suisse" not in name or path.suffix.lower() not in {".ttf", ".otf", ".woff", ".woff2"}:
                continue
            for weight in ("light", "medium"):
                if weight in name and "italic" not in name and "intl" in name:
                    found.setdefault(weight, path)
    return found


def register_fonts(font_dir: str | Path | None = None) -> tuple[str, bool]:
    from nicegui import app

    fonts = find_suisse(font_dir)
    css = []
    for weight, path in fonts.items():
        url = app.add_static_file(local_file=path, url_path=f"/fonts/suisse-{weight}{path.suffix}")
        css.append(f"@font-face {{font-family:Suisse;src:url('{url}');font-weight:{300 if weight == 'light' else 500};font-style:normal;font-display:swap;}}")
    return "\n".join(css), len(fonts) == 2
