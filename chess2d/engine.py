"""Stockfish discovery, playing strength levels and a background analyser."""
import os
import platform
import shutil
import subprocess
import sys
import threading

import chess
import chess.engine

from .paths import resource

# (label, Skill Level, depth limit, seconds per move)
LEVELS = [
    ("1 · Beginner (~800)", 0, 1, 0.05),
    ("2 · Novice (~1000)", 2, 2, 0.1),
    ("3 · Casual (~1200)", 4, 4, 0.1),
    ("4 · Club (~1400)", 6, 6, 0.2),
    ("5 · Intermediate (~1600)", 9, 8, 0.3),
    ("6 · Advanced (~1800)", 12, 10, 0.4),
    ("7 · Expert (~2000)", 15, 13, 0.5),
    ("8 · Master (~2300)", 17, 16, 0.8),
    ("9 · Grandmaster (~2600)", 19, None, 1.0),
    ("10 · Maximum (3000+)", 20, None, 2.0),
]


def _bundled_name() -> str:
    system = platform.system()
    if system == "Windows":
        return "stockfish-windows-x86-64-avx2.exe"
    if system == "Darwin":
        return "stockfish-macos-m1-apple-silicon" if platform.machine() == "arm64" else "stockfish-macos-x86-64-avx2"
    return "stockfish-ubuntu-x86-64-avx2"


def find_stockfish(custom: str = "") -> str | None:
    candidates = [custom.strip()] if custom and custom.strip() else []
    candidates.append(resource("stockfish", _bundled_name()))
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return shutil.which("stockfish")


def open_engine(path: str) -> chess.engine.SimpleEngine:
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return chess.engine.SimpleEngine.popen_uci(path, **kwargs)


def format_score(score) -> str:
    if score is None:
        return ""
    white = score.white()
    if white.is_mate():
        mate = white.mate()
        return f"M{abs(mate)}" if mate else "#"
    return f"{white.score() / 100:+.1f}"


def white_win_share(score) -> float:
    """Map an engine score to 0..1 (share of the eval bar that is white)."""
    if score is None:
        return 0.5
    white = score.white()
    if white.is_mate():
        return 1.0 if white > chess.engine.Cp(0) else 0.0
    cp = max(-2000, min(2000, white.score()))
    return 1 / (1 + 10 ** (-cp / 400))


class Analyzer:
    """Continuously analyses the latest position on its own engine process."""

    def __init__(self, path: str):
        self.engine = open_engine(path)
        try:
            self.engine.configure({"Threads": max(1, min(2, (os.cpu_count() or 2) // 2)), "Hash": 64})
        except chess.engine.EngineError:
            pass
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._pending = None
        self._gen = 0
        self._stop = False
        self.fen = None
        self.score = None       # chess.engine.PovScore
        self.best_move = None   # chess.Move
        self.depth = 0
        self._thread = threading.Thread(target=self._run, daemon=True, name="analyzer")
        self._thread.start()

    def set_position(self, board: chess.Board):
        fen = board.fen()
        with self._lock:
            if self.fen == fen:
                return
            self._pending = board.copy()
            self._gen += 1
            self.fen, self.score, self.best_move, self.depth = fen, None, None, 0
        self._wake.set()

    def snapshot(self, board: chess.Board):
        """Return (score, best_move, depth) if the analysis matches this board."""
        with self._lock:
            if self.fen != board.fen():
                return None, None, 0
            return self.score, self.best_move, self.depth

    def _run(self):
        while not self._stop:
            self._wake.wait()
            self._wake.clear()
            if self._stop:
                break
            with self._lock:
                board, gen = self._pending, self._gen
            if board is None or board.is_game_over():
                continue
            try:
                with self.engine.analysis(board, chess.engine.Limit(time=6.0, depth=24)) as analysis:
                    for info in analysis:
                        if self._stop or gen != self._gen:
                            break
                        if "score" in info:
                            with self._lock:
                                if gen == self._gen:
                                    self.score = info["score"]
                                    self.depth = info.get("depth", self.depth)
                                    pv = info.get("pv")
                                    if pv:
                                        self.best_move = pv[0]
            except (chess.engine.EngineError, chess.engine.EngineTerminatedError, RuntimeError):
                break

    def close(self):
        self._stop = True
        self._wake.set()
        try:
            self.engine.quit()
        except Exception:
            pass
