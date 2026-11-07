"""Fonts, piece images (rendered from SVG at any size) and sounds."""
import os

import chess
import pygame

from .paths import resource

PIECE_FILES = {
    chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
    chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king",
}

_FONT_CANDIDATES = "segoeui,segoeuivariable,helveticaneue,inter,roboto,ubuntu,dejavusans,arial"
_fonts = {}


def font(size: int, bold: bool = False) -> pygame.font.Font:
    size = max(8, int(size))
    key = (size, bold)
    if key not in _fonts:
        _fonts[key] = pygame.font.SysFont(_FONT_CANDIDATES, size, bold=bold)
    return _fonts[key]


class PieceSet:
    """Caches piece surfaces per pixel size so the board stays crisp when resized."""

    def __init__(self):
        self._cache = {}
        self._raw = {}

    def _load(self, piece: chess.Piece, size: int) -> pygame.Surface:
        name = f"{PIECE_FILES[piece.piece_type]}-{'w' if piece.color else 'b'}.svg"
        path = resource("pieces", name)
        try:
            if hasattr(pygame.image, "load_sized_svg"):
                return pygame.image.load_sized_svg(path, (size, size)).convert_alpha()
            if name not in self._raw:
                self._raw[name] = pygame.image.load(path).convert_alpha()
            return pygame.transform.smoothscale(self._raw[name], (size, size))
        except (pygame.error, FileNotFoundError, OSError):
            return self._fallback(piece, size)

    @staticmethod
    def _fallback(piece: chess.Piece, size: int) -> pygame.Surface:
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        fill = (245, 245, 245) if piece.color else (40, 40, 40)
        ink = (20, 20, 20) if piece.color else (240, 240, 240)
        pygame.draw.circle(surf, fill, (size // 2, size // 2), int(size * 0.4))
        pygame.draw.circle(surf, ink, (size // 2, size // 2), int(size * 0.4), max(1, size // 30))
        label = font(int(size * 0.45), True).render(piece.symbol().upper(), True, ink)
        surf.blit(label, label.get_rect(center=(size // 2, size // 2)))
        return surf

    def get(self, piece: chess.Piece, size: int) -> pygame.Surface:
        size = max(8, int(size))
        key = (piece.piece_type, piece.color, size)
        if key not in self._cache:
            if len(self._cache) > 400:
                self._cache.clear()
            self._cache[key] = self._load(piece, size)
        return self._cache[key]


class Sounds:
    NAMES = ("move", "capture", "castle", "check", "promote", "notify")

    def __init__(self, settings):
        self.settings = settings
        self._sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            for name in self.NAMES:
                path = resource("sound", f"{name}.mp3")
                if os.path.exists(path):
                    self._sounds[name] = pygame.mixer.Sound(path)
        except pygame.error as exc:
            print(f"Sound disabled: {exc}")

    def play(self, name: str):
        if not self.settings["sound"]:
            return
        snd = self._sounds.get(name)
        if snd:
            snd.set_volume(self.settings["volume"] / 100)
            snd.play()

    def for_move(self, board_before: chess.Board, move: chess.Move, board_after: chess.Board):
        if board_after.is_check():
            self.play("check")
        elif move.promotion:
            self.play("promote")
        elif board_before.is_castling(move):
            self.play("castle")
        elif board_before.is_capture(move):
            self.play("capture")
        else:
            self.play("move")
