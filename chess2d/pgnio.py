"""PGN export/import (including the old Chess2D move-log format) and the autosave file."""
import datetime
import io
import json
import re

import chess
import chess.pgn

from . import APP_NAME, VERSION
from .paths import user_file

AUTOSAVE = "autosave.json"


def build_pgn(board: chess.Board, white: str, black: str, result: str = "*",
              time_control: str = "-", comments: list | None = None, termination: str = "") -> str:
    game = chess.pgn.Game()
    game.headers["Event"] = f"{APP_NAME} game"
    game.headers["Site"] = APP_NAME
    game.headers["Date"] = datetime.date.today().strftime("%Y.%m.%d")
    game.headers["White"] = white
    game.headers["Black"] = black
    game.headers["Result"] = result
    game.headers["TimeControl"] = time_control
    if termination:
        game.headers["Termination"] = termination
    game.headers["Annotator"] = f"{APP_NAME} {VERSION}"
    root = board.root()
    if root.fen() != chess.STARTING_FEN:
        game.setup(root)
    node = game
    for i, move in enumerate(board.move_stack):
        node = node.add_variation(move)
        if comments and i < len(comments) and comments[i]:
            node.comment = comments[i]
    return str(game) + "\n"


_LEGACY_MOVE = re.compile(r"^([KQRBN]?)([a-h][1-8])x?([a-h][1-8])(?:=?([QRBNqrbn]))?[+#]?$")


def _parse_legacy(text: str) -> chess.Board | None:
    """Old Chess2D logs: '1. e2e4\\te7e5', 'Bf1g2', 'O-O' (and K used for knights)."""
    board = chess.Board()
    found = False
    for raw in re.split(r"\s+", text):
        token = raw.strip()
        if not token or re.fullmatch(r"\d+\.+", token) or set(token) <= set("=-"):
            continue
        if token.lower().startswith(("chess", "game", "move", "log")):
            continue
        move = None
        if token.rstrip("+#") in ("O-O", "0-0", "O-O-O", "0-0-0"):
            try:
                move = board.parse_san(token.rstrip("+#").replace("0", "O"))
            except ValueError:
                return None
        else:
            m = _LEGACY_MOVE.match(token)
            if not m:
                try:
                    move = board.parse_san(token)
                except ValueError:
                    return None
            else:
                promo = m.group(4)
                uci = m.group(2) + m.group(3) + (promo.lower() if promo else "")
                move = chess.Move.from_uci(uci)
                if move not in board.legal_moves and not promo:
                    # an unannotated promotion: default to queen
                    queen = chess.Move.from_uci(uci + "q")
                    move = queen if queen in board.legal_moves else move
                if move not in board.legal_moves:
                    return None
        board.push(move)
        found = True
    return board if found else None


def load_game_text(text: str):
    """Return (board, headers dict, comments list). Raises ValueError if nothing parses."""
    text = text.strip()
    if not text:
        raise ValueError("The file is empty.")
    game = chess.pgn.read_game(io.StringIO(text))
    if game is not None and not game.errors and (list(game.mainline_moves()) or "FEN" in game.headers):
        board = game.board()
        comments = []
        for node in game.mainline():
            board.push(node.move)
            comments.append(node.comment or "")
        return board, dict(game.headers), comments
    try:
        board = chess.Board(text.splitlines()[0].strip())
        return board, {}, []
    except ValueError:
        pass
    board = _parse_legacy(text)
    if board is None:
        raise ValueError("Could not read this file as PGN, FEN or a Chess2D move log.")
    return board, {}, [""] * len(board.move_stack)


def save_autosave(data: dict):
    try:
        with open(user_file(AUTOSAVE), "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass


def load_autosave() -> dict | None:
    try:
        with open(user_file(AUTOSAVE), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) and "moves" in data else None
    except (OSError, ValueError):
        return None


def clear_autosave():
    import os
    try:
        os.remove(user_file(AUTOSAVE))
    except OSError:
        pass
