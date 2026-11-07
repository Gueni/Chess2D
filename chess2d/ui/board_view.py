"""Interactive, resizable chess board widget."""
import math

import chess
import pygame

from .. import theme as T
from ..assets import font
from .widgets import px

PROMOTION_ORDER = [chess.QUEEN, chess.KNIGHT, chess.ROOK, chess.BISHOP]


class BoardView:
    def __init__(self, pieces, settings, on_move, movable_color):
        self.pieces = pieces
        self.settings = settings
        self.on_move = on_move              # callback(chess.Move)
        self.movable_color = movable_color  # callable -> chess.Color | None
        self.rect = pygame.Rect(0, 0, 400, 400)
        self.flipped = False
        self.board = chess.Board()
        self.selected = None
        self.drag_from = None
        self.drag_pos = (0, 0)
        self.press_pos = None
        self.promotion = None               # (from_sq, to_sq, color)
        self.arrows = set()                 # {(from, to)}
        self.marks = set()
        self._right_from = None
        self.anim = None                    # (piece, from_sq, to_sq, start_ms, dur_ms)
        self._glow_cache = {}

    # ----- geometry ------------------------------------------------------------
    @property
    def sq(self) -> float:
        return self.rect.w / 8

    def square_xy(self, square):
        f, r = chess.square_file(square), chess.square_rank(square)
        col, row = (7 - f, r) if self.flipped else (f, 7 - r)
        return self.rect.x + col * self.sq, self.rect.y + row * self.sq

    def square_rect(self, square) -> pygame.Rect:
        x, y = self.square_xy(square)
        return pygame.Rect(round(x), round(y), round(x + self.sq) - round(x), round(y + self.sq) - round(y))

    def square_center(self, square):
        x, y = self.square_xy(square)
        return x + self.sq / 2, y + self.sq / 2

    def square_at(self, pos):
        if not self.rect.collidepoint(pos):
            return None
        col = int((pos[0] - self.rect.x) / self.sq)
        row = int((pos[1] - self.rect.y) / self.sq)
        col, row = min(7, col), min(7, row)
        if self.flipped:
            return chess.square(7 - col, row)
        return chess.square(col, 7 - row)

    # ----- state ---------------------------------------------------------------
    def set_board(self, board: chess.Board):
        if board.fen() != self.board.fen():
            self.selected = None
            self.drag_from = None
            self.promotion = None
        self.board = board

    def clear_selection(self):
        self.selected = self.drag_from = self.promotion = None

    def animate(self, board_before: chess.Board, move: chess.Move):
        if not self.settings["animations"]:
            return
        piece = board_before.piece_at(move.from_square)
        if piece and self.drag_from is None:
            self.anim = (piece, move.from_square, move.to_square, pygame.time.get_ticks(), 140)

    def targets(self, square):
        return {m.to_square for m in self.board.legal_moves if m.from_square == square}

    def _try_move(self, from_sq, to_sq) -> bool:
        candidates = [m for m in self.board.legal_moves if m.from_square == from_sq and m.to_square == to_sq]
        if not candidates:
            return False
        if any(m.promotion for m in candidates):
            if self.settings["auto_queen"]:
                self.on_move(chess.Move(from_sq, to_sq, chess.QUEEN))
            else:
                self.promotion = (from_sq, to_sq, self.board.turn)
            self.selected = None
            return True
        self.selected = None
        self.on_move(candidates[0])
        return True

    def _promotion_rects(self):
        from_sq, to_sq, color = self.promotion
        rects = []
        x, y = self.square_xy(to_sq)
        step = self.sq if (y < self.rect.centery) else -self.sq
        for i, _ in enumerate(PROMOTION_ORDER):
            rects.append(pygame.Rect(round(x), round(y + i * step), math.ceil(self.sq), math.ceil(self.sq)))
        return rects

    # ----- input -----------------------------------------------------------------
    def handle(self, event) -> bool:
        movable = self.movable_color()
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self.promotion:
                    for rect, ptype in zip(self._promotion_rects(), PROMOTION_ORDER):
                        if rect.collidepoint(event.pos):
                            from_sq, to_sq, _ = self.promotion
                            self.promotion = None
                            self.on_move(chess.Move(from_sq, to_sq, ptype))
                            return True
                    self.promotion = None
                    return self.rect.collidepoint(event.pos)
                square = self.square_at(event.pos)
                if square is None:
                    return False
                self.arrows.clear()
                self.marks.clear()
                if movable is None or self.board.turn != movable:
                    self.selected = None
                    return True
                if self.selected is not None and square in self.targets(self.selected):
                    self._try_move(self.selected, square)
                    return True
                piece = self.board.piece_at(square)
                if piece and piece.color == movable:
                    self.selected = square
                    self.drag_from = square
                    self.drag_pos = event.pos
                    self.press_pos = event.pos
                else:
                    self.selected = None
                return True
            if event.button == 3:
                self._right_from = self.square_at(event.pos)
                self.selected = self.drag_from = None
                return self._right_from is not None
        elif event.type == pygame.MOUSEMOTION:
            if self.drag_from is not None:
                self.drag_pos = event.pos
                return True
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1 and self.drag_from is not None:
                origin, self.drag_from = self.drag_from, None
                target = self.square_at(event.pos)
                moved = (self.press_pos and math.dist(self.press_pos, event.pos) > self.sq * 0.25)
                if target is not None and target != origin and movable == self.board.turn:
                    if not self._try_move(origin, target):
                        self.selected = None if moved else origin
                return True
            if event.button == 3 and self._right_from is not None:
                start, self._right_from = self._right_from, None
                end = self.square_at(event.pos)
                if end is None:
                    return True
                if end == start:
                    self.marks ^= {start}
                else:
                    self.arrows ^= {(start, end)}
                return True
        return False

    # ----- drawing -----------------------------------------------------------------
    def _glow(self, size):
        if size not in self._glow_cache:
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            c = size / 2
            for i in range(20, 0, -1):
                r = c * i / 20
                alpha = int(210 * (1 - i / 20) ** 0.6) if i < 20 else 0
                pygame.draw.circle(surf, (*T.CHECK_GLOW, alpha), (c, c), r)
            self._glow_cache = {size: surf}
        return self._glow_cache[size]

    def _fill(self, surf, square, rgba):
        r = self.square_rect(square)
        overlay = pygame.Surface(r.size, pygame.SRCALPHA)
        overlay.fill(rgba)
        surf.blit(overlay, r.topleft)

    def _draw_arrow(self, layer, start, end, color, width):
        x1, y1 = self.square_center(start)
        x2, y2 = self.square_center(end)
        x1, y1, x2, y2 = x1 - self.rect.x, y1 - self.rect.y, x2 - self.rect.x, y2 - self.rect.y
        angle = math.atan2(y2 - y1, x2 - x1)
        length = math.hypot(x2 - x1, y2 - y1)
        head = self.sq * 0.42
        shaft_end = length - head
        start_off = self.sq * 0.25
        ux, uy = math.cos(angle), math.sin(angle)
        nx, ny = -uy, ux
        w = width / 2
        sx, sy = x1 + ux * start_off, y1 + uy * start_off
        ex, ey = x1 + ux * shaft_end, y1 + uy * shaft_end
        shaft = [(sx + nx * w, sy + ny * w), (ex + nx * w, ey + ny * w),
                 (ex - nx * w, ey - ny * w), (sx - nx * w, sy - ny * w)]
        hw = head * 0.6
        tip = (x1 + ux * (length - self.sq * 0.12), y1 + uy * (length - self.sq * 0.12))
        head_pts = [tip, (ex + nx * hw, ey + ny * hw), (ex - nx * hw, ey - ny * hw)]
        pygame.draw.polygon(layer, color, shaft)
        pygame.draw.polygon(layer, color, head_pts)

    def draw(self, surf, last_move=None, hint_move=None):
        light, dark = T.BOARD_THEMES.get(self.settings["theme"], T.BOARD_THEMES["Walnut"])
        board = self.board
        size = math.ceil(self.sq)
        # frame shadow
        shadow = self.rect.inflate(px(10), px(10))
        pygame.draw.rect(surf, (12, 13, 16), shadow, border_radius=px(6))
        for square in chess.SQUARES:
            is_light = (chess.square_file(square) + chess.square_rank(square)) % 2 == 1
            pygame.draw.rect(surf, light if is_light else dark, self.square_rect(square))

        if last_move and self.settings["highlight_last"]:
            for square in (last_move.from_square, last_move.to_square):
                self._fill(surf, square, T.LAST_MOVE)
        if self.selected is not None:
            self._fill(surf, self.selected, T.SELECTED)
        if board.is_check():
            king = board.king(board.turn)
            if king is not None:
                surf.blit(self._glow(size), self.square_rect(king).topleft)

        if self.settings["show_coords"]:
            fsize = max(9, int(self.sq * 0.17))
            f = font(fsize, True)
            for i in range(8):
                rank_sq = chess.square(7 if self.flipped else 0, i)
                rr = self.square_rect(rank_sq)
                is_light = (chess.square_file(rank_sq) + i) % 2 == 1
                img = f.render(str(i + 1), True, dark if is_light else light)
                surf.blit(img, (rr.x + px(3), rr.y + px(2)))
                file_sq = chess.square(i, 7 if self.flipped else 0)
                fr = self.square_rect(file_sq)
                is_light = (i + chess.square_rank(file_sq)) % 2 == 1
                img = f.render("abcdefgh"[i], True, dark if is_light else light)
                surf.blit(img, (fr.right - img.get_width() - px(3), fr.bottom - img.get_height()))

        if self.selected is not None and self.settings["show_legal"]:
            for target in self.targets(self.selected):
                cx, cy = self.square_center(target)
                layer = pygame.Surface((size, size), pygame.SRCALPHA)
                if board.piece_at(target) or board.is_en_passant(chess.Move(self.selected, target)):
                    pygame.draw.circle(layer, T.LEGAL_DOT, (size / 2, size / 2), size * 0.48, max(2, int(size * 0.09)))
                else:
                    pygame.draw.circle(layer, T.LEGAL_DOT, (size / 2, size / 2), size * 0.16)
                surf.blit(layer, (cx - size / 2, cy - size / 2))

        if self.drag_from is not None:
            hover = self.square_at(self.drag_pos)
            if hover is not None and hover in self.targets(self.drag_from):
                pygame.draw.rect(surf, (255, 255, 255), self.square_rect(hover), max(2, px(3)))

        anim_active = False
        if self.anim:
            piece, a_from, a_to, start, dur = self.anim
            t = (pygame.time.get_ticks() - start) / dur
            if t >= 1 or board.piece_at(a_to) is None or board.piece_at(a_to).color != piece.color:
                self.anim = None
            else:
                anim_active = True

        piece_size = int(self.sq * 0.92)
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if not piece or square == self.drag_from:
                continue
            if anim_active and square == self.anim[2]:
                continue
            cx, cy = self.square_center(square)
            img = self.pieces.get(piece, piece_size)
            surf.blit(img, img.get_rect(center=(round(cx), round(cy))))

        if self.marks or self.arrows or hint_move:
            layer = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            for square in self.marks:
                cx, cy = self.square_center(square)
                pygame.draw.circle(layer, T.MARK, (cx - self.rect.x, cy - self.rect.y), self.sq * 0.45,
                                   max(2, int(self.sq * 0.07)))
            for start, end in self.arrows:
                self._draw_arrow(layer, start, end, T.ARROW, self.sq * 0.18)
            if hint_move:
                self._draw_arrow(layer, hint_move.from_square, hint_move.to_square, T.HINT_ARROW, self.sq * 0.2)
            surf.blit(layer, self.rect.topleft)

        if anim_active:
            piece, a_from, a_to, start, dur = self.anim
            t = min(1.0, (pygame.time.get_ticks() - start) / dur)
            t = 1 - (1 - t) ** 3
            x1, y1 = self.square_center(a_from)
            x2, y2 = self.square_center(a_to)
            shown = board.piece_at(a_to) or piece
            img = self.pieces.get(shown, piece_size)
            surf.blit(img, img.get_rect(center=(round(x1 + (x2 - x1) * t), round(y1 + (y2 - y1) * t))))

        if self.drag_from is not None:
            piece = board.piece_at(self.drag_from)
            if piece:
                img = self.pieces.get(piece, int(self.sq * 1.05))
                surf.blit(img, img.get_rect(center=self.drag_pos))

        if self.promotion:
            from_sq, to_sq, color = self.promotion
            dim = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            dim.fill((0, 0, 0, 120))
            surf.blit(dim, self.rect.topleft)
            mouse = pygame.mouse.get_pos()
            for rect, ptype in zip(self._promotion_rects(), PROMOTION_ORDER):
                hovered = rect.collidepoint(mouse)
                pygame.draw.rect(surf, (255, 255, 255) if hovered else (225, 228, 235), rect, border_radius=px(8))
                img = self.pieces.get(chess.Piece(ptype, color), int(self.sq * (0.95 if hovered else 0.85)))
                surf.blit(img, img.get_rect(center=rect.center))
