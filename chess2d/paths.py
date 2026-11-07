"""Filesystem locations for bundled resources and per-user data."""
import os
import sys

from . import APP_NAME


def resource_dir() -> str:
    """Folder holding bundled assets (pieces, sounds, stockfish)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource(*parts: str) -> str:
    return os.path.join(resource_dir(), *parts)


def user_dir() -> str:
    """Writable per-user folder for settings and saved games."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        path = os.path.join(base, APP_NAME)
    elif sys.platform == "darwin":
        path = os.path.expanduser(f"~/Library/Application Support/{APP_NAME}")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        path = os.path.join(base, APP_NAME.lower())
    os.makedirs(path, exist_ok=True)
    return path


def user_file(name: str) -> str:
    return os.path.join(user_dir(), name)
