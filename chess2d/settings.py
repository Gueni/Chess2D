"""Persistent user settings stored as JSON in the user data folder."""
import copy
import json
import os

from .paths import user_file

CLAUDE_MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-1"]
CLAUDE_EFFORTS = ["low", "medium", "high", "xhigh", "max"]

TIME_CONTROLS = [
    # (label, base seconds, increment seconds); base 0 means untimed
    ("Unlimited", 0, 0),
    ("Bullet 1+0", 60, 0),
    ("Blitz 3+2", 180, 2),
    ("Blitz 5+0", 300, 0),
    ("Rapid 10+0", 600, 0),
    ("Rapid 15+10", 900, 10),
    ("Classical 30+0", 1800, 0),
]

DEFAULTS = {
    "player_name": "Player",
    "theme": "Walnut",
    "sound": True,
    "volume": 70,
    "show_legal": True,
    "show_coords": True,
    "highlight_last": True,
    "auto_queen": False,
    "eval_bar": True,
    "animations": True,
    "stockfish_path": "",
    "anthropic_api_key": "",
    "claude_model": "claude-opus-5-5",
    "claude_effort": "medium",
    "openai_base_url": "http://localhost:11434/v1",
    "openai_api_key": "",
    "openai_model": "llama3.1",
    "join_host": "127.0.0.1",
    "port": 5555,
    "window": [0, 0],
    "white": {"type": "human", "level": 5},
    "black": {"type": "stockfish", "level": 5},
    "time_control": 0,
    "host_color": 0,
}

_PATH = None


def _path():
    global _PATH
    if _PATH is None:
        _PATH = user_file("settings.json")
    return _PATH


class Settings(dict):
    def __init__(self):
        super().__init__(copy.deepcopy(DEFAULTS))
        try:
            with open(_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, value in data.items():
                if key in DEFAULTS and type(value) is type(DEFAULTS[key]):
                    self[key] = value
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            tmp = _path() + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self, f, indent=2)
            os.replace(tmp, _path())
        except OSError as exc:
            print(f"Could not save settings: {exc}")

    @property
    def anthropic_key(self) -> str:
        return self["anthropic_api_key"].strip() or os.environ.get("ANTHROPIC_API_KEY", "")
