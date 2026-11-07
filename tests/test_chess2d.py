"""Headless tests: rules flow, PGN/legacy import, LLM reply parsing, networking and a UI smoke test.

Run with:  py -m pytest tests   (or)   py tests/test_chess2d.py
"""
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess  # noqa: E402

from chess2d.engine import find_stockfish  # noqa: E402
from chess2d.game import Game  # noqa: E402
from chess2d.llm import parse_reply  # noqa: E402
from chess2d.network import Host, Joiner  # noqa: E402
from chess2d.pgnio import build_pgn, load_game_text  # noqa: E402
from chess2d.players import HumanPlayer, RemotePlayer, StockfishPlayer  # noqa: E402

LEGACY_LOG = """Chess Game Move Log
==================

1. g2g4\td7d5
2. Bf1g2\tBc8xg4
3. f2f3\tBg4h5
4. e2e4\td5xe4
5. f3xe4\tBh5xd1
6. Ke1xd1\tKb8c6
"""


def wait_for(cond, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_legacy_log_import():
    board, _headers, comments = load_game_text(LEGACY_LOG)
    assert len(board.move_stack) == 12
    assert board.move_stack[-1] == chess.Move.from_uci("b8c6")   # old logs used K for knights
    assert len(comments) == 12


def test_pgn_roundtrip():
    board = chess.Board()
    for san in ["e4", "e5", "Nf3", "Nc6", "Bb5"]:
        board.push_san(san)
    pgn = build_pgn(board, "Alice", "Bob", "*", "300+0", ["", "", "", "", "Ruy Lopez"])
    loaded, headers, comments = load_game_text(pgn)
    assert loaded.fen() == board.fen()
    assert headers["White"] == "Alice"
    assert comments[-1] == "Ruy Lopez"


def test_fen_import():
    fen = "8/8/8/4k3/8/8/4K3/7R w - - 0 1"
    board, _, _ = load_game_text(fen)
    assert board.fen() == fen


def test_parse_reply():
    b = chess.Board()
    assert parse_reply(b, "MOVE: e2e4\nCOMMENT: Classic.")[0] == chess.Move.from_uci("e2e4")
    assert parse_reply(b, "MOVE: **Nf3**\nCOMMENT: x")[0] == chess.Move.from_uci("g1f3")
    assert parse_reply(b, "I like d2d4 here")[0] == chess.Move.from_uci("d2d4")
    assert parse_reply(b, "MOVE: e2e5")[0] is None


def test_checkmate_and_undo():
    g = Game(HumanPlayer("A"), HumanPlayer("B"))
    g.start()
    for uci in ["f2f3", "e7e5", "g2g4", "d8h4"]:
        assert g.push(chess.Move.from_uci(uci))
    assert g.result == "0-1" and g.reason == "checkmate"
    g.undo()
    assert g.result is None and len(g.board.move_stack) == 3


def test_stockfish_vs_stockfish():
    path = find_stockfish()
    if not path:
        print("stockfish missing - skipped")
        return
    g = Game(StockfishPlayer(path, 1), StockfishPlayer(path, 2))
    g.start()
    assert wait_for(lambda: (g.update(), len(g.board.move_stack) >= 6 or g.over)[1], 30)
    assert g.error is None
    g.close()


def test_undo_vs_ai_returns_to_human_turn():
    path = find_stockfish()
    if not path:
        return
    g = Game(HumanPlayer("me"), StockfishPlayer(path, 1))
    g.start()
    g.push(chess.Move.from_uci("e2e4"))
    assert wait_for(lambda: (g.update(), len(g.board.move_stack) == 2)[1], 15)
    g.undo()
    assert len(g.board.move_stack) == 0 and g.board.turn == chess.WHITE
    g.close()


def test_network_game():
    host = Host(55123)
    joiner = Joiner("127.0.0.1", 55123)
    assert wait_for(lambda: joiner.done and host.connection is not None)
    assert joiner.error is None
    a = Game(HumanPlayer("host"), RemotePlayer("guest"), connection=host.connection, local_color=chess.WHITE)
    b = Game(RemotePlayer("host"), HumanPlayer("guest"), connection=joiner.connection, local_color=chess.BLACK)
    a.push(chess.Move.from_uci("e2e4"))
    assert wait_for(lambda: (b.update(), len(b.board.move_stack) == 1)[1])
    b.push(chess.Move.from_uci("e7e5"))
    assert wait_for(lambda: (a.update(), len(a.board.move_stack) == 2)[1])
    b.send_chat("gl hf")
    assert wait_for(lambda: (a.update(), bool(a.chat))[1])
    a.offer_draw()
    assert wait_for(lambda: (b.update(), b.pending_offer == "draw")[1])
    b.accept_offer()
    assert wait_for(lambda: (a.update(), a.result == "1/2-1/2")[1])
    assert b.result == "1/2-1/2"
    a.close()
    assert wait_for(lambda: (b.update(), b.error is not None)[1])
    b.close()


def test_ui_smoke():
    import pygame
    from chess2d import settings as settings_mod
    from chess2d.app import App
    from chess2d.ui.screens import HostScreen, JoinScreen, MenuScreen, SettingsScreen, SetupScreen

    settings_mod._PATH = os.path.join(os.path.dirname(__file__), "_settings_test.json")
    try:
        app = App()
        for size in [(1280, 800), (700, 1000), (500, 420), (2560, 1440)]:
            app.surface = pygame.display.set_mode(size, pygame.RESIZABLE)
            for screen_cls in (MenuScreen, SetupScreen, SettingsScreen, HostScreen, JoinScreen):
                app.set_screen(screen_cls(app))
                for _ in range(2):
                    app.screen.update()
                    app.screen.draw(app.surface)
        app.start_game({"type": "human"}, {"type": "stockfish", "level": 1}, 2)
        gs = app.game_screen
        assert gs is not None
        gs.game.push(chess.Move.from_uci("e2e4"))
        for size in [(1280, 800), (700, 1000), (520, 440)]:
            app.surface = pygame.display.set_mode(size, pygame.RESIZABLE)
            for _ in range(30):
                gs.update()
                gs.draw(app.surface)
                time.sleep(0.02)
        # simulate a click-drag move with the mouse once it is White's turn again
        assert wait_for(lambda: (gs.update(), gs.game.board.turn == chess.WHITE)[1], 15)
        gs.draw(app.surface)
        bv = gs.board_view
        src = bv.square_center(chess.G1)
        dst = bv.square_center(chess.F3)
        gs.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=src))
        gs.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=dst, rel=(0, 0), buttons=(1, 0, 0)))
        gs.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=dst))
        assert gs.game.board.move_stack[2] == chess.Move.from_uci("g1f3")
        gs.hint()
        gs.step(-1)
        gs.draw(app.surface)
        gs.goto(None)
        gs.game.resign()
        gs.draw(app.surface)
        app.leave_game()
        app.shutdown()
    finally:
        try:
            os.remove(settings_mod._PATH)
        except OSError:
            pass


if __name__ == "__main__":
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as exc:
                failures += 1
                import traceback
                traceback.print_exc()
                print(f"FAIL {name}: {exc}")
    sys.exit(1 if failures else 0)
