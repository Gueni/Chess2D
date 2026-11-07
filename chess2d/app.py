"""Application shell: window, main loop, screen switching and game lifecycle."""
import os
import sys
import time

import chess
import chess.engine
import pygame

from . import APP_NAME, VERSION
from . import theme as T
from .engine import Analyzer, find_stockfish
from .game import Game
from .llm import LLMError
from .paths import resource
from .pgnio import build_pgn, clear_autosave, load_game_text, save_autosave
from .players import HumanPlayer, RemotePlayer, create_player
from .settings import Settings
from .assets import PieceSet, Sounds
from .ui.widgets import Scale, Widget, draw_text, px, round_rect, wrap_text


def _enable_dpi_awareness():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def _file_dialog(save: bool, **options) -> str:
    try:
        import tkinter
        from tkinter import filedialog
        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        fn = filedialog.asksaveasfilename if save else filedialog.askopenfilename
        path = fn(parent=root, **options)
        root.destroy()
        return path or ""
    except Exception as exc:
        print(f"File dialog unavailable: {exc}")
        return ""


class App:
    def __init__(self):
        _enable_dpi_awareness()
        pygame.init()
        self.settings = Settings()
        pygame.display.set_caption(f"{APP_NAME}")
        try:
            pygame.display.set_icon(pygame.image.load(resource("chess.ico")))
        except (pygame.error, FileNotFoundError):
            pass
        size = tuple(self.settings["window"])
        if size[0] < 640 or size[1] < 480:
            desk = pygame.display.get_desktop_sizes()[0] if hasattr(pygame.display, "get_desktop_sizes") else (1600, 900)
            size = (int(desk[0] * 0.72), int(desk[1] * 0.78))
        self.windowed_size = size
        self.surface = pygame.display.set_mode(size, pygame.RESIZABLE)
        pygame.key.set_repeat(350, 35)
        self.pieces = PieceSet()
        self.sounds = Sounds(self.settings)
        self._analyzer = None
        self._analyzer_failed = False
        self.screen = None
        self.game_screen = None
        self.running = True
        self.toast_text, self.toast_until = "", 0.0
        self.fullscreen = False
        from .ui.screens import MenuScreen
        self.set_screen(MenuScreen(self))

    # ----- services -------------------------------------------------------------------
    def get_analyzer(self):
        if self._analyzer is None and not self._analyzer_failed:
            path = find_stockfish(self.settings["stockfish_path"])
            try:
                self._analyzer = Analyzer(path) if path else None
            except Exception as exc:
                print(f"Analyzer unavailable: {exc}")
                self._analyzer = None
            self._analyzer_failed = self._analyzer is None
        return self._analyzer

    def toast(self, text: str, seconds: float = 4.0):
        self.toast_text, self.toast_until = text, time.monotonic() + seconds

    def set_screen(self, screen):
        if self.screen:
            self.screen.leave()
        Widget.focus = None
        self.screen = screen

    def quit(self):
        self.running = False

    # ----- games ------------------------------------------------------------------------
    def _make_players(self, white_cfg, black_cfg):
        players = {}
        try:
            for color, cfg in ((chess.WHITE, white_cfg), (chess.BLACK, black_cfg)):
                name = self.settings["player_name"] if cfg.get("type") == "human" else ""
                if cfg.get("type") == "human" and white_cfg.get("type") == black_cfg.get("type") == "human":
                    name = f"{self.settings['player_name'] or 'Player'} ({'White' if color else 'Black'})"
                players[color] = create_player(cfg, self.settings, name)
            return players
        except (LLMError, OSError, chess.engine.EngineError) as exc:
            for p in players.values():
                p.close()
            self.toast(str(exc))
            return None

    def start_game(self, white_cfg, black_cfg, tc, board=None, comments=None, clocks=None):
        players = self._make_players(white_cfg, black_cfg)
        if not players:
            return
        game = Game(players[chess.WHITE], players[chess.BLACK], tc, board=board, comments=comments,
                    configs={chess.WHITE: white_cfg, chess.BLACK: black_cfg}, clocks=clocks)
        self._show_game(game)

    def _show_game(self, game):
        from .ui.game_screen import GameScreen
        self._close_current_game(save=False)
        self.game_screen = GameScreen(self, game)
        self.set_screen(self.game_screen)

    def restart_game(self, game: Game):
        cfg = game.configs
        white = cfg.get(chess.WHITE, {"type": "human"})
        black = cfg.get(chess.BLACK, {"type": "human"})
        humans = [c for c, p in game.players.items() if p.is_human]
        if len(humans) == 1:          # vs AI: swap colours for the next game
            white, black = black, white
        self.start_game(dict(white), dict(black), game.tc_index)

    def start_online_game(self, conn, local_color, remote_name, tc):
        me = HumanPlayer(self.settings["player_name"] or "You")
        them = RemotePlayer(remote_name)
        white, black = (me, them) if local_color == chess.WHITE else (them, me)
        game = Game(white, black, tc, connection=conn, local_color=local_color)
        self._show_game(game)
        self.sounds.play("notify")

    def online_rematch(self, game: Game):
        conn, game.connection = game.connection, None
        remote = game.player(not game.local_color)
        self.start_online_game(conn, not game.local_color, remote.name, game.tc_index)

    def resume_autosave(self, data: dict):
        try:
            board = chess.Board(data.get("start_fen", chess.STARTING_FEN))
            for uci in data["moves"]:
                board.push_uci(uci)
        except (ValueError, KeyError, TypeError):
            clear_autosave()
            self.toast("The saved game could not be restored.")
            return
        tc = data.get("time_control", 0)
        self.start_game(data.get("white", {"type": "human"}), data.get("black", {"type": "human"}),
                        tc if isinstance(tc, int) else 0, board=board, comments=data.get("comments"),
                        clocks=data.get("clocks"))

    def save_autosave(self, game):
        data = game.autosave_data() if game else None
        if data:
            save_autosave(data)
        else:
            clear_autosave()

    def _close_current_game(self, save=True):
        if self.game_screen:
            game = self.game_screen.game
            if save:
                self.save_autosave(game)
            self.game_screen.leave()
            game.close()
            self.game_screen = None

    def leave_game(self):
        from .ui.screens import MenuScreen
        self._close_current_game(save=True)
        self.set_screen(MenuScreen(self))

    # ----- files ------------------------------------------------------------------------
    def save_pgn(self, game: Game):
        path = _file_dialog(True, defaultextension=".pgn", initialfile=f"chess2d_{time.strftime('%Y%m%d_%H%M')}.pgn",
                            filetypes=[("PGN files", "*.pgn"), ("All files", "*.*")], title="Save game as PGN")
        if not path:
            return
        pgn = build_pgn(game.board, game.player(chess.WHITE).name, game.player(chess.BLACK).name,
                        game.result or "*", game.time_control_label(), game.comments, game.reason)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(pgn)
            game.flash(f"Saved {os.path.basename(path)}")
            self.sounds.play("notify")
        except OSError as exc:
            game.flash(f"Could not save: {exc.strerror}")

    def open_pgn(self):
        path = _file_dialog(False, filetypes=[("Chess games", "*.pgn *.txt *.fen"), ("All files", "*.*")],
                            title="Open a PGN, FEN or Chess2D move log")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                board, headers, comments = load_game_text(f.read())
        except (OSError, ValueError) as exc:
            self.toast(str(exc))
            return
        human = {"type": "human"}
        self.start_game(dict(human), dict(human), 0, board=board, comments=comments)
        if self.game_screen:
            g = self.game_screen.game
            g.players[chess.WHITE].name = headers.get("White", "White") or "White"
            g.players[chess.BLACK].name = headers.get("Black", "Black") or "Black"
            self.game_screen.goto(0)
            g.flash(f"Loaded {os.path.basename(path)} · use ← → to step through, or play on from the end")

    # ----- main loop ---------------------------------------------------------------------
    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.surface = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.surface = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)

    def run(self):
        clock = pygame.time.Clock()
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
                    self.windowed_size = (max(480, event.w), max(400, event.h))
                elif event.type == pygame.KEYDOWN and (event.key == pygame.K_F11 or (
                        event.key == pygame.K_RETURN and event.mod & pygame.KMOD_ALT)):
                    self.toggle_fullscreen()
                    continue
                try:
                    self.screen.handle(event)
                except Exception as exc:   # keep the app alive, report the problem
                    self.toast(f"Error: {exc}")
                    import traceback
                    traceback.print_exc()
            self.surface = pygame.display.get_surface()
            Scale.update(*self.surface.get_size())
            self.screen.update()
            self.screen.draw(self.surface)
            self._draw_toast()
            pygame.display.flip()
            clock.tick(60)
        self.shutdown()

    def _draw_toast(self):
        if not self.toast_text or time.monotonic() > self.toast_until:
            return
        w, h = self.surface.get_size()
        max_w = min(w - px(40), px(640))
        lines = wrap_text(self.toast_text, 15, max_w - px(32))
        rect = pygame.Rect(0, 0, max_w, px(22) * len(lines) + px(24))
        rect.midbottom = (w // 2, h - px(24))
        round_rect(self.surface, (52, 40, 44), rect, 12)
        round_rect(self.surface, T.DANGER, rect, 12, 1)
        for i, line in enumerate(lines):
            draw_text(self.surface, line, (rect.x + px(16), rect.y + px(12) + i * px(22)), 15, T.TEXT)

    def shutdown(self):
        self._close_current_game(save=True)
        if not self.fullscreen:
            self.settings["window"] = list(self.windowed_size)
        self.settings.save()
        if self._analyzer:
            self._analyzer.close()
        pygame.quit()


def selftest() -> int:
    """Non-interactive check used after packaging: chess2d.exe --selftest (writes selftest.log)."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    lines, ok = [], True
    try:
        import anthropic
        import requests  # noqa: F401
        lines.append(f"anthropic {anthropic.__version__}")
        path = find_stockfish()
        lines.append(f"stockfish {path}")
        from .players import StockfishPlayer
        player = StockfishPlayer(path, 3)
        move, _ = player.compute(chess.Board())
        player.close()
        lines.append(f"engine move {move.uci()}")
        app = App()
        from .ui.screens import SettingsScreen
        app.set_screen(SettingsScreen(app))
        app.screen.draw(app.surface)
        img = app.pieces.get(chess.Piece(chess.KING, chess.WHITE), 64)
        lines.append(f"svg piece {img.get_size()} sounds {len(app.sounds._sounds)}")
        app.running = False
        pygame.quit()
    except Exception as exc:
        ok = False
        lines.append(f"FAILED: {exc!r}")
    lines.append("OK" if ok else "ERROR")
    out = os.path.join(os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else ".", "selftest.log")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    App().run()
