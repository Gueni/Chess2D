"""Game controller: rules (via python-chess), turn flow, clocks, results and network sync."""
import queue
import random
import time

import chess

from .players import HumanPlayer, Player, RemotePlayer
from .settings import TIME_CONTROLS

COLOR_NAMES = {chess.WHITE: "White", chess.BLACK: "Black"}


class Game:
    def __init__(self, white: Player, black: Player, time_control: int = 0,
                 board: chess.Board | None = None, comments: list | None = None,
                 connection=None, local_color: chess.Color | None = None,
                 configs: dict | None = None, clocks: list | None = None):
        self.players = {chess.WHITE: white, chess.BLACK: black}
        self.configs = configs or {}
        self.board = board.copy() if board is not None else chess.Board()
        self.comments = list(comments or [""] * len(self.board.move_stack))
        self.comments += [""] * (len(self.board.move_stack) - len(self.comments))
        self.tc_index = time_control
        _label, self.base, self.increment = TIME_CONTROLS[time_control]
        self.clocks = list(clocks) if clocks else [float(self.base)] * 2  # [black, white] by chess.Color
        if clocks:
            self.clocks = [float(clocks[1]), float(clocks[0])]
        self.connection = connection
        self.local_color = local_color
        self.result: str | None = None          # "1-0", "0-1", "1/2-1/2"
        self.reason: str = ""
        self.error: str | None = None           # AI/network problem shown to the user
        self.notice: str | None = None          # transient info message
        self.notice_until = 0.0
        self.pending_offer: str | None = None   # offer received from the remote player
        self.sent_offer: str | None = None
        self.thinking = False
        self.last_comment = ""
        self.listeners = []                      # callables(event, data)
        self._token = 0
        self._ai_queue: "queue.Queue" = queue.Queue()
        self._last_tick = time.monotonic()
        self._remote_flag_since = None
        self.chat: list[tuple[str, str]] = []

    # ----- helpers -------------------------------------------------------
    @property
    def timed(self) -> bool:
        return self.base > 0

    @property
    def online(self) -> bool:
        return self.connection is not None

    @property
    def over(self) -> bool:
        return self.result is not None

    def player(self, color: chess.Color) -> Player:
        return self.players[color]

    def current(self) -> Player:
        return self.players[self.board.turn]

    def human_can_move(self) -> bool:
        return not self.over and self.current().is_human and not self.error

    def both_human_local(self) -> bool:
        return all(p.is_human for p in self.players.values())

    def emit(self, event: str, data=None):
        for fn in list(self.listeners):
            fn(event, data)

    def flash(self, text: str, seconds: float = 3.0):
        self.notice, self.notice_until = text, time.monotonic() + seconds

    def time_control_label(self) -> str:
        return "-" if not self.timed else f"{self.base}+{self.increment}"

    # ----- flow ------------------------------------------------------------
    def start(self):
        self._check_outcome()
        self._request_ai_move()

    def _request_ai_move(self):
        if self.over:
            return
        player = self.current()
        if player.is_human or player.is_remote:
            self.thinking = False
            return
        self.thinking = True
        self.error = None
        token = self._token

        def deliver(move, comment):
            self._ai_queue.put((token, move, comment))

        player.start_thinking(self.board, deliver)

    def retry(self):
        self.error = None
        self._request_ai_move()

    def push(self, move: chess.Move, from_remote: bool = False) -> bool:
        if self.over or move not in self.board.legal_moves:
            return False
        before = self.board.copy(stack=False)
        mover = self.board.turn
        if self.timed and self.board.ply() >= 2:
            self.clocks[mover] += self.increment
        self.board.push(move)
        self.comments.append("")
        self._token += 1
        self.sent_offer = None
        if self.pending_offer == "draw":
            self.pending_offer = None
        if self.online and not from_remote:
            self.connection.send({"type": "move", "uci": move.uci(),
                                  "clocks": [self.clocks[chess.WHITE], self.clocks[chess.BLACK]]})
        self.emit("move", (before, move))
        self._check_outcome()
        self._request_ai_move()
        return True

    def _check_outcome(self):
        outcome = self.board.outcome(claim_draw=True)
        if outcome is None:
            return
        reasons = {
            chess.Termination.CHECKMATE: "checkmate",
            chess.Termination.STALEMATE: "stalemate",
            chess.Termination.INSUFFICIENT_MATERIAL: "insufficient material",
            chess.Termination.SEVENTYFIVE_MOVES: "75-move rule",
            chess.Termination.FIVEFOLD_REPETITION: "fivefold repetition",
            chess.Termination.FIFTY_MOVES: "50-move rule",
            chess.Termination.THREEFOLD_REPETITION: "threefold repetition",
        }
        self.finish(outcome.result(), reasons.get(outcome.termination, "game over"))

    def finish(self, result: str, reason: str):
        if self.over:
            return
        self.result, self.reason = result, reason
        self.thinking = False
        self._token += 1
        self.emit("over", (result, reason))

    def result_text(self) -> str:
        if not self.result:
            return ""
        if self.result == "1/2-1/2":
            return f"Draw · {self.reason}"
        winner = chess.WHITE if self.result == "1-0" else chess.BLACK
        return f"{COLOR_NAMES[winner]} wins · {self.reason}"

    # ----- per-frame update ------------------------------------------------
    def update(self):
        now = time.monotonic()
        dt, self._last_tick = now - self._last_tick, now

        while True:
            try:
                token, move, comment = self._ai_queue.get_nowait()
            except queue.Empty:
                break
            if token != self._token or self.over:
                continue
            self.thinking = False
            if move is None:
                self.error = comment or "The AI could not move."
                continue
            if comment:
                self.last_comment = f"{self.current().name}: {comment}"
            if self.push(move):
                if comment:
                    self.comments[-1] = comment

        if self.online:
            self._poll_network()

        if self.timed and not self.over and self.board.ply() >= 2:
            side = self.board.turn
            self.clocks[side] = max(0.0, self.clocks[side] - dt)
            if self.clocks[side] <= 0:
                self._flag(side, now)

    def _flag(self, side: chess.Color, now: float):
        if self.online and side != self.local_color:
            # The opponent's own client declares its timeout; fall back after a grace period.
            if self._remote_flag_since is None:
                self._remote_flag_since = now
            if now - self._remote_flag_since < 3.0:
                return
        elif self.online:
            self.connection.send({"type": "timeout"})
        winner = not side
        if not self.board.has_insufficient_material(winner):
            self.finish("1-0" if winner == chess.WHITE else "0-1", "time out")
        else:
            self.finish("1/2-1/2", "time out vs insufficient material")

    # ----- actions ------------------------------------------------------------
    def can_undo(self) -> bool:
        return not self.online and len(self.board.move_stack) > 0

    def undo(self):
        """Take back to the previous position where a human is to move."""
        if not self.can_undo():
            return
        self.result, self.reason, self.error = None, "", None
        self._token += 1
        self.thinking = False
        self.board.pop()
        self.comments.pop()
        while (self.board.move_stack and not self.current().is_human
               and any(p.is_human for p in self.players.values())):
            self.board.pop()
            self.comments.pop()
        self.emit("reset", None)
        self._request_ai_move()

    def resign(self, color: chess.Color | None = None):
        if self.over:
            return
        if color is None:
            color = self.local_color if self.online else self.board.turn
            if not self.online and not self.both_human_local():
                humans = [c for c, p in self.players.items() if p.is_human]
                color = humans[0] if humans else self.board.turn
        if self.online:
            self.connection.send({"type": "resign"})
        self.finish("0-1" if color == chess.WHITE else "1-0", f"{COLOR_NAMES[color]} resigned")

    def offer_draw(self, eval_cp_white: int | None = None):
        if self.over:
            return
        if self.online:
            if self.pending_offer == "draw":
                self.accept_offer()
                return
            self.sent_offer = "draw"
            self.connection.send({"type": "offer", "kind": "draw"})
            self.flash("Draw offered")
            return
        ai_colors = [c for c, p in self.players.items() if not p.is_human]
        if not ai_colors:
            self.finish("1/2-1/2", "agreement")
            return
        ai = ai_colors[0]
        if eval_cp_white is None or len(self.board.move_stack) < 30:
            self.flash("Draw declined")
            return
        ai_eval = eval_cp_white if ai == chess.WHITE else -eval_cp_white
        if ai_eval <= 30:
            self.finish("1/2-1/2", "agreement")
        else:
            self.flash("Draw declined")

    def offer_rematch(self):
        if self.online:
            if self.pending_offer == "rematch":
                self.accept_offer()
                return
            self.sent_offer = "rematch"
            self.connection.send({"type": "offer", "kind": "rematch"})
            self.flash("Rematch offered - waiting for opponent")

    def accept_offer(self):
        kind, self.pending_offer = self.pending_offer, None
        if not kind:
            return
        self.connection.send({"type": "accept", "kind": kind})
        self._apply_accept(kind)

    def decline_offer(self):
        kind, self.pending_offer = self.pending_offer, None
        if kind:
            self.connection.send({"type": "decline", "kind": kind})

    def _apply_accept(self, kind: str):
        if kind == "draw":
            self.finish("1/2-1/2", "agreement")
        elif kind == "rematch":
            self.emit("rematch", None)

    def send_chat(self, text: str):
        text = text.strip()[:200]
        if text and self.online:
            self.connection.send({"type": "chat", "text": text})
            self.chat.append(("You", text))

    def _poll_network(self):
        for msg in self.connection.poll():
            kind = msg.get("type")
            remote = self.players[not self.local_color]
            if kind == "move":
                try:
                    move = chess.Move.from_uci(str(msg.get("uci", "")))
                except ValueError:
                    continue
                if self.board.turn == self.local_color or not self.push(move, from_remote=True):
                    self.error = "Opponent sent an invalid move - the games are out of sync."
                    continue
                clocks = msg.get("clocks")
                if isinstance(clocks, list) and len(clocks) == 2:
                    try:
                        self.clocks[chess.WHITE] = float(clocks[0])
                        self.clocks[chess.BLACK] = float(clocks[1])
                    except (TypeError, ValueError):
                        pass
                self._remote_flag_since = None
            elif kind == "resign":
                color = not self.local_color
                self.finish("0-1" if color == chess.WHITE else "1-0", f"{remote.name} resigned")
            elif kind == "timeout":
                side = not self.local_color
                self.clocks[side] = 0.0
                self._remote_flag_since = time.monotonic() - 10
                self._flag(side, time.monotonic())
            elif kind == "offer":
                offer = msg.get("kind")
                if offer in ("draw", "rematch"):
                    if self.sent_offer == offer:      # both offered: treat as accepted
                        self.sent_offer = None
                        self.connection.send({"type": "accept", "kind": offer})
                        self._apply_accept(offer)
                    else:
                        self.pending_offer = offer
            elif kind == "accept":
                offer = msg.get("kind")
                if offer == self.sent_offer:
                    self.sent_offer = None
                    self._apply_accept(offer)
            elif kind == "decline":
                self.sent_offer = None
                self.flash(f"{remote.name} declined the {msg.get('kind', 'offer')}")
            elif kind == "chat":
                self.chat.append((remote.name, str(msg.get("text", ""))[:200]))
                self.emit("chat", None)
            elif kind == "_closed":
                if not self.over:
                    self.finish("1-0" if self.local_color == chess.WHITE else "0-1", "opponent disconnected")
                self.error = "Connection to the opponent was lost."

    # ----- persistence --------------------------------------------------------
    def autosave_data(self) -> dict | None:
        if self.online or self.over or not self.board.move_stack:
            return None
        return {
            "white": self.configs.get(chess.WHITE, {"type": "human"}),
            "black": self.configs.get(chess.BLACK, {"type": "human"}),
            "time_control": self.tc_index,
            "start_fen": self.board.root().fen(),
            "moves": [m.uci() for m in self.board.move_stack],
            "comments": self.comments,
            "clocks": [self.clocks[chess.WHITE], self.clocks[chess.BLACK]],
        }

    def close(self):
        self._token += 1
        for p in self.players.values():
            p.close()
        if self.connection:
            self.connection.close()


def random_color() -> chess.Color:
    return random.choice([chess.WHITE, chess.BLACK])


__all__ = ["Game", "HumanPlayer", "RemotePlayer", "COLOR_NAMES", "random_color"]
