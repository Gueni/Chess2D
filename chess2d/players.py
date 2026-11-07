"""Player types. AI players think on a worker thread and deliver their move through a callback."""
import threading

import chess
import chess.engine

from .engine import LEVELS, find_stockfish, open_engine
from .llm import ClaudeBackend, LLMError, OpenAICompatBackend

PLAYER_TYPES = ["human", "stockfish", "claude", "openai"]
PLAYER_TYPE_LABELS = {
    "human": "Human",
    "stockfish": "Stockfish",
    "claude": "Claude (Anthropic)",
    "openai": "LLM (OpenAI-compatible)",
}


class Player:
    is_human = False
    is_remote = False
    kind = "player"

    def __init__(self, name: str):
        self.name = name

    def start_thinking(self, board: chess.Board, deliver):
        """deliver(move | None, comment_or_error: str) is called from any thread."""

    def close(self):
        pass


class HumanPlayer(Player):
    is_human = True
    kind = "human"


class RemotePlayer(Player):
    is_remote = True
    kind = "remote"


class _ThreadedPlayer(Player):
    def __init__(self, name: str):
        super().__init__(name)
        self._lock = threading.Lock()

    def compute(self, board: chess.Board):
        raise NotImplementedError

    def start_thinking(self, board: chess.Board, deliver):
        snapshot = board.copy()

        def work():
            with self._lock:
                try:
                    move, comment = self.compute(snapshot)
                    deliver(move, comment or "")
                except LLMError as exc:
                    deliver(None, str(exc))
                except chess.engine.EngineTerminatedError:
                    deliver(None, f"{self.name} stopped unexpectedly.")
                except Exception as exc:  # never let a worker crash silently
                    deliver(None, f"{self.name} failed: {exc}")

        threading.Thread(target=work, daemon=True, name=f"think-{self.kind}").start()


class StockfishPlayer(_ThreadedPlayer):
    kind = "stockfish"

    def __init__(self, path: str, level: int):
        self.level = max(1, min(len(LEVELS), level))
        label, skill, depth, seconds = LEVELS[self.level - 1]
        super().__init__(f"Stockfish L{self.level}")
        self.limit = chess.engine.Limit(time=seconds, depth=depth)
        self.engine = open_engine(path)
        options = {"Skill Level": skill}
        if self.level >= 9:
            options["Threads"] = 2
        try:
            self.engine.configure(options)
        except chess.engine.EngineError:
            pass

    def compute(self, board):
        result = self.engine.play(board, self.limit)
        return result.move, ""

    def close(self):
        try:
            self.engine.quit()
        except Exception:
            pass


class LLMPlayer(_ThreadedPlayer):
    kind = "llm"

    def __init__(self, name: str, backend):
        super().__init__(name)
        self.backend = backend

    def compute(self, board):
        return self.backend.choose_move(board)


def model_display_name(model: str) -> str:
    """claude-opus-5-5 -> Claude Opus 5.5"""
    parts = model.split("-")
    if len(parts) >= 2 and parts[0] == "claude":
        version = ".".join(p for p in parts[2:] if p.isdigit())
        return f"Claude {parts[1].title()} {version}".strip()
    return model


def describe(cfg: dict, settings) -> str:
    kind = cfg.get("type", "human")
    if kind == "stockfish":
        return f"Stockfish · {LEVELS[cfg.get('level', 5) - 1][0]}"
    if kind == "claude":
        return f"Claude · {settings['claude_model']}"
    if kind == "openai":
        return f"LLM · {settings['openai_model']}"
    return "Human"


def create_player(cfg: dict, settings, human_name: str = "") -> Player:
    """Build a player from a config dict such as {"type": "stockfish", "level": 5}."""
    kind = cfg.get("type", "human")
    if kind == "stockfish":
        path = find_stockfish(settings["stockfish_path"])
        if not path:
            raise LLMError("Stockfish was not found. Set its path in Settings.")
        return StockfishPlayer(path, int(cfg.get("level", 5)))
    if kind == "claude":
        model = settings["claude_model"]
        backend = ClaudeBackend(settings.anthropic_key, model, settings["claude_effort"])
        return LLMPlayer(model_display_name(model), backend)
    if kind == "openai":
        backend = OpenAICompatBackend(settings["openai_base_url"], settings["openai_api_key"], settings["openai_model"])
        return LLMPlayer(settings["openai_model"], backend)
    return HumanPlayer(human_name or settings["player_name"] or "Player")
