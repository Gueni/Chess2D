"""The in-game screen: board, player bars, eval bar, move list and controls."""
import time

import chess
import pygame

from .. import theme as T
from ..engine import format_score, white_win_share
from ..game import COLOR_NAMES, Game
from .board_view import BoardView
from .screens import Screen, draw_background
from .widgets import (Button, TextInput, Widget, draw_text, fit_text, px, round_rect, set_clipboard, text_surface,
                      wrap_text)

PIECE_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
START_COUNT = {chess.PAWN: 8, chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 2, chess.QUEEN: 1}


def format_clock(seconds: float) -> str:
    seconds = max(0.0, seconds)
    if seconds < 20:
        return f"{int(seconds // 60)}:{seconds % 60:04.1f}"
    s = int(seconds + 0.999)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class GameScreen(Screen):
    def __init__(self, app, game: Game):
        super().__init__(app)
        self.game = game
        self.view_ply = None            # None = live position
        self.hint_move = None
        self.hint_wanted = False
        self.show_overlay = game.over
        self.move_scroll = 0
        self.follow_moves = True
        self._san_cache = ([], 0)
        self._view_cache = (None, None)
        self.chat_text = ""
        game.listeners.append(self.on_game_event)
        self.board_view = BoardView(app.pieces, app.settings, self.on_board_move, self.movable_color)
        humans = [c for c, p in game.players.items() if p.is_human]
        if game.online:
            self.board_view.flipped = game.local_color == chess.BLACK
        elif humans == [chess.BLACK]:
            self.board_view.flipped = True

        g = game
        self.nav = [
            Button("|<", lambda: self.goto(0), "ghost", 15),
            Button("<", lambda: self.step(-1), "ghost", 15),
            Button(">", lambda: self.step(1), "ghost", 15),
            Button(">|", lambda: self.goto(None), "ghost", 15),
        ]
        self.actions = [
            Button("Undo", self.undo, hint="Ctrl+Z"),
            Button("Hint", self.hint, hint="H"),
            Button("Flip", self.flip, hint="F"),
            Button("Offer draw", self.offer_draw),
            Button("Resign", self.resign, "danger"),
            Button(lambda: "Rematch" if g.online else "New game", self.new_game),
            Button("Save PGN", self.save_pgn, hint="Ctrl+S"),
            Button("Copy FEN", self.copy_fen),
            Button("Menu", self.to_menu, "ghost"),
        ]
        self.actions[0].enabled = lambda: g.can_undo()
        self.actions[1].enabled = lambda: self.analysis_allowed() and not g.over
        self.actions[3].enabled = lambda: not g.over
        self.actions[4].enabled = lambda: not g.over and any(p.is_human for p in g.players.values())
        self.retry_btn = Button("Retry", self.retry, "primary", 14)
        self.accept_btn = Button("Accept", lambda: g.accept_offer(), "success", 14)
        self.decline_btn = Button("Decline", lambda: g.decline_offer(), "ghost", 14)
        self.overlay_buttons = [
            Button(lambda: "Rematch" if g.online else "Play again", self.new_game, "primary"),
            Button("Review", self.close_overlay),
            Button("Menu", self.to_menu, "ghost"),
        ]
        self.chat_input = TextInput("", lambda: self.chat_text, self._set_chat, placeholder="Chat… (Enter to send)",
                                    size=14, max_len=200, on_enter=self.send_chat)
        game.start()

    # ----- helpers -----------------------------------------------------------------
    def analysis_allowed(self) -> bool:
        return not self.game.online and self.app.get_analyzer() is not None

    def is_live(self) -> bool:
        return self.view_ply is None or self.view_ply >= len(self.game.board.move_stack)

    def movable_color(self):
        g = self.game
        if not self.is_live() or not g.human_can_move():
            return None
        if g.online and g.board.turn != g.local_color:
            return None
        return g.board.turn

    def view_board(self) -> chess.Board:
        g = self.game
        if self.is_live():
            return g.board
        key = (self.view_ply, len(g.board.move_stack), g.board.move_stack[-1] if g.board.move_stack else None)
        if self._view_cache[0] != key:
            b = g.board.root()
            for m in g.board.move_stack[: self.view_ply]:
                b.push(m)
            self._view_cache = (key, b)
        return self._view_cache[1]

    def sans(self):
        g = self.game
        stack = g.board.move_stack
        if self._san_cache[1] != len(stack):
            b = g.board.root()
            out = []
            for m in stack:
                out.append(b.san(m))
                b.push(m)
            self._san_cache = (out, len(stack))
        return self._san_cache[0]

    # ----- events from the game --------------------------------------------------------
    def on_game_event(self, event, data):
        if event == "move":
            before, move = data
            self.app.sounds.for_move(before, move, self.game.board)
            self.hint_move = None
            self.hint_wanted = False
            self._san_cache = ([], -1)
            if self.view_ply is not None and self.view_ply >= len(self.game.board.move_stack) - 1:
                self.view_ply = None
            if self.is_live():
                self.board_view.animate(before, move)
            self.follow_moves = True
        elif event == "over":
            self.app.sounds.play("notify")
            self.show_overlay = True
            self.view_ply = None
            self.app.save_autosave(None)
        elif event == "reset":
            self.view_ply = None
            self.hint_move = None
            self.show_overlay = False
            self._san_cache = ([], -1)
            self.board_view.clear_selection()
        elif event == "rematch":
            self.app.online_rematch(self.game)
        elif event == "chat":
            self.app.sounds.play("notify")

    def on_board_move(self, move):
        if self.is_live() and self.game.human_can_move():
            self.game.push(move)

    # ----- actions ------------------------------------------------------------------------
    def goto(self, ply):
        n = len(self.game.board.move_stack)
        self.view_ply = None if ply is None or ply >= n else max(0, ply)
        self.board_view.clear_selection()
        self.hint_move = None

    def step(self, delta):
        n = len(self.game.board.move_stack)
        cur = n if self.view_ply is None else self.view_ply
        self.goto(cur + delta)

    def undo(self):
        self.game.undo()

    def hint(self):
        if self.analysis_allowed() and not self.game.over:
            self.goto(None)
            self.hint_wanted = True

    def flip(self):
        self.board_view.flipped = not self.board_view.flipped

    def retry(self):
        self.game.retry()

    def offer_draw(self):
        cp = None
        analyzer = self.app.get_analyzer() if not self.game.online else None
        if analyzer:
            score, _, depth = analyzer.snapshot(self.game.board)
            if score is not None and depth >= 8:
                cp = score.white().score(mate_score=100000)
        self.game.offer_draw(cp)

    def resign(self):
        self.game.resign()

    def new_game(self):
        if self.game.online:
            self.game.offer_rematch()
        else:
            self.app.restart_game(self.game)

    def close_overlay(self):
        self.show_overlay = False

    def save_pgn(self):
        self.app.save_pgn(self.game)

    def copy_fen(self):
        fen = self.view_board().fen()
        self.game.flash("FEN copied to clipboard" if set_clipboard(fen) else "Could not access the clipboard")

    def to_menu(self):
        self.app.leave_game()

    def _set_chat(self, value):
        self.chat_text = value

    def send_chat(self):
        self.game.send_chat(self.chat_text)
        self.chat_text = ""

    # ----- input ---------------------------------------------------------------------------
    def handle(self, event):
        g = self.game
        if self.show_overlay and g.over:
            for b in self.overlay_buttons:
                if b.handle(event):
                    return
            if event.type == pygame.MOUSEBUTTONDOWN and self.board_view.rect.collidepoint(event.pos):
                return
        if g.error and self.retry_btn.visible and self.retry_btn.handle(event):
            return
        if g.pending_offer and (self.accept_btn.handle(event) or self.decline_btn.handle(event)):
            return
        if g.online and self.chat_input.handle(event):
            return
        for b in self.nav + self.actions:
            if b.handle(event):
                return
        if event.type == pygame.MOUSEWHEEL and self.moves_rect.collidepoint(pygame.mouse.get_pos()):
            self.move_scroll = max(0, self.move_scroll - event.y * px(28))
            self.follow_moves = False
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.moves_rect.collidepoint(event.pos):
            for rect, ply in self._move_hitboxes:
                if rect.collidepoint(event.pos):
                    self.goto(ply)
                    return
        if self.board_view.handle(event):
            return
        if event.type == pygame.KEYDOWN and Widget.focus is None:
            ctrl = event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)
            if event.key == pygame.K_LEFT:
                self.step(-1)
            elif event.key == pygame.K_RIGHT:
                self.step(1)
            elif event.key in (pygame.K_HOME, pygame.K_UP):
                self.goto(0)
            elif event.key in (pygame.K_END, pygame.K_DOWN):
                self.goto(None)
            elif event.key == pygame.K_f:
                self.flip()
            elif event.key == pygame.K_h:
                self.hint()
            elif event.key == pygame.K_z and ctrl:
                self.undo()
            elif event.key == pygame.K_s and ctrl:
                self.save_pgn()
            elif event.key == pygame.K_c and ctrl:
                self.copy_fen()
            elif event.key == pygame.K_ESCAPE:
                if self.board_view.selected is not None or self.board_view.arrows or self.board_view.marks:
                    self.board_view.clear_selection()
                    self.board_view.arrows.clear()
                    self.board_view.marks.clear()
                elif self.show_overlay:
                    self.show_overlay = False

    def update(self):
        g = self.game
        g.update()
        analyzer = self.app.get_analyzer() if (self.analysis_allowed() and
                                               (self.app.settings["eval_bar"] or self.hint_wanted)) else None
        if analyzer:
            analyzer.set_position(self.view_board())
            if self.hint_wanted and self.is_live():
                _score, best, depth = analyzer.snapshot(g.board)
                if best is not None and depth >= 10:
                    self.hint_move, self.hint_wanted = best, False
        self.board_view.set_board(self.view_board())

    def leave(self):
        if self.on_game_event in self.game.listeners:
            self.game.listeners.remove(self.on_game_event)

    # ----- layout & drawing --------------------------------------------------------------
    def layout(self, w, h):
        m = px(16)
        strip_h = px(44)
        gap = px(6)
        show_eval = self.app.settings["eval_bar"] and self.analysis_allowed()
        eval_w = px(22) if show_eval else 0
        eval_gap = px(10) if show_eval else 0
        landscape = w >= h * 1.12
        if landscape:
            panel_w = max(px(300), min(px(440), int(w * 0.32)))
            avail_w = w - 3 * m - panel_w - eval_w - eval_gap
            avail_h = h - 2 * m - 2 * (strip_h + gap)
            size = max(160, min(avail_w, avail_h)) // 8 * 8
            group_w = eval_w + eval_gap + size + m + panel_w
            x0 = max(m, (w - group_w) // 2)
            top = max(m, (h - (size + 2 * (strip_h + gap))) // 2)
            board = pygame.Rect(x0 + eval_w + eval_gap, top + strip_h + gap, size, size)
            panel = pygame.Rect(board.right + m, top, panel_w, size + 2 * (strip_h + gap))
        else:
            avail_w = w - 2 * m - eval_w - eval_gap
            avail_h = int(h * 0.64) - 2 * (strip_h + gap) - m
            size = max(160, min(avail_w, avail_h)) // 8 * 8
            x0 = (w - (size + eval_w + eval_gap)) // 2
            board = pygame.Rect(x0 + eval_w + eval_gap, m + strip_h + gap, size, size)
            ptop = board.bottom + gap + strip_h + m
            panel = pygame.Rect(m, ptop, w - 2 * m, max(px(200), h - ptop - m))
        self.board_view.rect = board
        flipped = self.board_view.flipped
        top_color = chess.WHITE if flipped else chess.BLACK
        self.strips = {
            top_color: pygame.Rect(board.x, board.y - gap - strip_h, size, strip_h),
            not top_color: pygame.Rect(board.x, board.bottom + gap, size, strip_h),
        }
        self.eval_rect = pygame.Rect(board.x - eval_gap - eval_w, board.y, eval_w, size) if show_eval else None
        self.panel = panel
        self.landscape = landscape

        # panel internals
        pad = px(14)
        inner = panel.inflate(-2 * pad, -2 * pad)
        y = inner.y
        status_h = px(78)
        self.status_rect = pygame.Rect(inner.x, y, inner.w, status_h)
        y += status_h + px(10)
        self.offer_rect = None
        if self.game.pending_offer:
            self.offer_rect = pygame.Rect(inner.x, y, inner.w, px(44))
            bw = px(90)
            self.decline_btn.rect = pygame.Rect(self.offer_rect.right - bw - px(6), self.offer_rect.y + px(6), bw, px(32))
            self.accept_btn.rect = self.decline_btn.rect.move(-bw - px(6), 0)
            y += px(54)
        cols = 3
        btn_h = px(38)
        rows = (len(self.actions) + cols - 1) // cols
        actions_h = rows * btn_h + (rows - 1) * px(8)
        nav_h = px(36)
        chat_h = px(150) if self.game.online else 0
        bottom = inner.bottom
        for i, b in enumerate(self.actions):
            r, c = divmod(i, cols)
            bw = (inner.w - (cols - 1) * px(8)) // cols
            b.rect = pygame.Rect(inner.x + c * (bw + px(8)), bottom - actions_h + r * (btn_h + px(8)), bw, btn_h)
        bottom -= actions_h + px(10)
        nw = (inner.w - 3 * px(8)) // 4
        for i, b in enumerate(self.nav):
            b.rect = pygame.Rect(inner.x + i * (nw + px(8)), bottom - nav_h, nw, nav_h)
        bottom -= nav_h + px(10)
        if chat_h:
            self.chat_rect = pygame.Rect(inner.x, bottom - chat_h, inner.w, chat_h)
            self.chat_input.rect = pygame.Rect(self.chat_rect.x, self.chat_rect.bottom - px(36), inner.w, px(36))
            bottom -= chat_h + px(10)
        self.moves_rect = pygame.Rect(inner.x, y, inner.w, max(px(40), bottom - y))
        self.retry_btn.rect = pygame.Rect(self.status_rect.right - px(84), self.status_rect.y + px(10), px(74), px(30))

    def draw(self, surf):
        draw_background(surf)
        w, h = surf.get_size()
        self.layout(w, h)
        g = self.game
        view = self.view_board()
        stack = g.board.move_stack
        n_view = len(stack) if self.is_live() else self.view_ply
        last = stack[n_view - 1] if n_view else None
        self.board_view.draw(surf, last_move=last, hint_move=self.hint_move if self.is_live() else None)
        if self.eval_rect:
            self.draw_eval(surf, view)
        for color, rect in self.strips.items():
            self.draw_strip(surf, color, rect, view)
        if not self.is_live():
            tag = pygame.Rect(0, 0, px(190), px(30))
            tag.midtop = (self.board_view.rect.centerx, self.board_view.rect.y + px(8))
            round_rect(surf, (20, 22, 26, 210), tag, 15)
            draw_text(surf, f"Reviewing move {n_view}/{len(stack)} · End = live", tag.center, 13, T.TEXT, anchor="center")
        self.draw_panel(surf)
        if self.show_overlay and g.over:
            self.draw_overlay(surf)

    def draw_eval(self, surf, view):
        analyzer = self.app.get_analyzer()
        score, _best, depth = analyzer.snapshot(view) if analyzer else (None, None, 0)
        rect = self.eval_rect
        if view.is_checkmate():
            share = 0.0 if view.turn == chess.WHITE else 1.0
            label = "#"
        elif view.is_game_over():
            share, label = 0.5, "½"
        else:
            share = white_win_share(score) if score is not None else getattr(self, "_last_share", 0.5)
            label = format_score(score) if score is not None else ""
        self._last_share = share
        round_rect(surf, (40, 40, 44), rect, 4)
        white_h = int(rect.h * share)
        if self.board_view.flipped:
            wr = pygame.Rect(rect.x, rect.y, rect.w, white_h)
        else:
            wr = pygame.Rect(rect.x, rect.bottom - white_h, rect.w, white_h)
        if white_h:
            round_rect(surf, (238, 238, 238), wr, 4)
        if label:
            img_color = (30, 30, 30) if share >= 0.5 else (230, 230, 230)
            at_bottom = (share >= 0.5) != self.board_view.flipped
            pos = (rect.centerx, rect.bottom - px(4)) if at_bottom else (rect.centerx, rect.y + px(4))
            anchor = "midbottom" if at_bottom else "midtop"
            img = text_surface(label, 11, img_color, True)
            if img.get_width() > rect.w:
                img = pygame.transform.smoothscale(img, (rect.w, int(img.get_height() * rect.w / img.get_width())))
            surf.blit(img, img.get_rect(**{anchor: pos}))

    def draw_strip(self, surf, color, rect, view):
        g = self.game
        player = g.player(color)
        round_rect(surf, T.SURFACE, rect, 10)
        to_move = view.turn == color and not g.over
        if to_move:
            round_rect(surf, T.ACCENT, rect, 10, 2)
        x = rect.x + px(12)
        pygame.draw.circle(surf, (245, 245, 245) if color == chess.WHITE else (25, 25, 25), (x + px(7), rect.centery), px(7))
        pygame.draw.circle(surf, T.TEXT_FAINT, (x + px(7), rect.centery), px(7), 1)
        x += px(22)
        kind = {"human": "", "remote": "online", "stockfish": "engine", "llm": "AI"}.get(player.kind, "")
        if g.online and color == g.local_color:
            kind = "you"
        name_rect = draw_text(surf, fit_text(player.name, 16, rect.w * 0.4, True), (x, rect.centery), 16, T.TEXT,
                              True, "midleft")
        x = name_rect.right + px(8)
        if kind:
            badge = pygame.Rect(x, rect.centery - px(10), px(10) + int(len(kind) * px(7.5)), px(20))
            round_rect(surf, T.SURFACE_3, badge, 10)
            draw_text(surf, kind, badge.center, 11, T.TEXT_DIM, True, "center")
            x = badge.right + px(8)
        if g.thinking and g.board.turn == color and self.is_live():
            dots = "." * (1 + int(time.monotonic() * 3) % 3)
            draw_text(surf, f"thinking{dots}", (x, rect.centery), 13, T.ACCENT, anchor="midleft")
            x += px(70)
        # captured pieces = opponent's pieces missing from the board
        opp = not color
        icon = px(20)
        cap_x = x
        clock_w = px(100) if g.timed else 0
        limit = rect.right - clock_w - px(16)
        for ptype in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN):
            missing = max(0, START_COUNT[ptype] - len(view.pieces(ptype, opp)))
            img = self.app.pieces.get(chess.Piece(ptype, opp), icon)
            for _ in range(missing):
                if cap_x + icon > limit:
                    break
                surf.blit(img, (cap_x, rect.centery - icon // 2))
                cap_x += int(icon * 0.55)
            if missing:
                cap_x += px(4)
        diff = sum(v * (len(view.pieces(t, color)) - len(view.pieces(t, opp))) for t, v in PIECE_VALUES.items())
        if diff > 0 and cap_x + px(30) < limit:
            draw_text(surf, f"+{diff}", (cap_x + px(6), rect.centery), 13, T.TEXT_DIM, True, "midleft")
        if g.timed:
            clock = pygame.Rect(rect.right - clock_w - px(6), rect.y + px(5), clock_w, rect.h - px(10))
            running = g.board.turn == color and not g.over and g.board.ply() >= 2
            secs = g.clocks[color]
            bg = (238, 240, 244) if running else T.SURFACE_2
            fg = (20, 22, 26) if running else T.TEXT_DIM
            if secs < 20:
                bg = T.DANGER if running else (90, 40, 40)
                fg = (255, 255, 255)
            round_rect(surf, bg, clock, 7)
            draw_text(surf, format_clock(secs), clock.center, 18, fg, True, "center")

    def draw_panel(self, surf):
        g = self.game
        round_rect(surf, T.SURFACE, self.panel, 14)
        # status
        sr = self.status_rect
        round_rect(surf, T.SURFACE_2, sr, 10)
        board = g.board
        if g.over:
            title, color = g.result_text(), T.WARNING
        elif g.error:
            title, color = "Problem", T.DANGER
        else:
            title = f"{COLOR_NAMES[board.turn]} to move" + (" · check!" if board.is_check() else "")
            if g.online:
                title = ("Your move" if board.turn == g.local_color else "Opponent's move") + \
                        (" · check!" if board.is_check() else "")
            color = T.TEXT
        draw_text(surf, fit_text(title, 18, sr.w - px(110), True), (sr.x + px(12), sr.y + px(10)), 18, color, True)
        if g.notice and time.monotonic() < g.notice_until:
            sub, sub_color = g.notice, T.ACCENT
        elif g.error:
            sub, sub_color = g.error, T.DANGER
        elif g.last_comment:
            sub, sub_color = "“" + g.last_comment + "”", T.TEXT_DIM
        elif g.thinking:
            sub, sub_color = f"{g.current().name} is thinking…", T.ACCENT
        else:
            tc = g.time_control_label()
            sub = f"{g.player(chess.WHITE).name} vs {g.player(chess.BLACK).name}" + (f" · {tc}" if tc != "-" else "")
            sub_color = T.TEXT_FAINT
        lines = wrap_text(sub, 13, sr.w - px(24))[:2]
        for i, line in enumerate(lines):
            draw_text(surf, line, (sr.x + px(12), sr.y + px(38) + i * px(18)), 13, sub_color)
        self.retry_btn.visible = bool(g.error) and not g.over and not g.online
        if self.retry_btn.visible:
            self.retry_btn.draw(surf)
        if self.offer_rect:
            round_rect(surf, (45, 60, 85), self.offer_rect, 10)
            what = "a draw" if g.pending_offer == "draw" else "a rematch"
            draw_text(surf, f"Opponent offers {what}", (self.offer_rect.x + px(12), self.offer_rect.centery), 14,
                      T.TEXT, True, "midleft")
            self.accept_btn.draw(surf)
            self.decline_btn.draw(surf)
        self.draw_moves(surf)
        if g.online:
            self.draw_chat(surf)
        live = self.is_live()
        n = len(g.board.move_stack)
        cur = n if live else self.view_ply
        self.nav[0].enabled = self.nav[1].enabled = cur > 0
        self.nav[2].enabled = self.nav[3].enabled = not live
        for b in self.nav + self.actions:
            b.draw(surf)

    def draw_moves(self, surf):
        rect = self.moves_rect
        round_rect(surf, T.BG, rect, 10)
        sans = self.sans()
        row_h = px(28)
        rows = (len(sans) + 1) // 2
        content = rows * row_h + px(8)
        max_scroll = max(0, content - rect.h)
        if self.follow_moves:
            self.move_scroll = max_scroll
        self.move_scroll = min(self.move_scroll, max_scroll)
        if self.move_scroll >= max_scroll:
            self.follow_moves = True
        clip = surf.get_clip()
        surf.set_clip(rect)
        current = len(sans) if self.is_live() else self.view_ply
        self._move_hitboxes = []
        num_w = px(44)
        col_w = (rect.w - num_w - px(16)) // 2
        if not sans:
            draw_text(surf, "No moves yet", rect.center, 14, T.TEXT_FAINT, anchor="center")
        for r in range(rows):
            y = rect.y + px(4) + r * row_h - self.move_scroll
            if y + row_h < rect.y or y > rect.bottom:
                continue
            if r % 2:
                pygame.draw.rect(surf, (26, 28, 34), (rect.x, y, rect.w, row_h))
            draw_text(surf, f"{r + 1}.", (rect.x + px(12), y + row_h // 2), 14, T.TEXT_FAINT, anchor="midleft")
            for c in range(2):
                i = r * 2 + c
                if i >= len(sans):
                    break
                cell = pygame.Rect(rect.x + num_w + c * col_w, y + px(2), col_w - px(6), row_h - px(4))
                if i + 1 == current:
                    round_rect(surf, T.ACCENT, cell, 6)
                elif cell.collidepoint(pygame.mouse.get_pos()):
                    round_rect(surf, T.SURFACE_3, cell, 6)
                draw_text(surf, sans[i], (cell.x + px(8), cell.centery), 15,
                          (255, 255, 255) if i + 1 == current else T.TEXT, i + 1 == current, "midleft")
                self._move_hitboxes.append((cell.clip(rect), i + 1))
        surf.set_clip(clip)

    def draw_chat(self, surf):
        rect = self.chat_rect
        round_rect(surf, T.BG, rect, 10)
        area = pygame.Rect(rect.x + px(10), rect.y + px(6), rect.w - px(20), rect.h - px(48))
        lines = []
        for who, text in self.game.chat[-30:]:
            lines += wrap_text(f"{who}: {text}", 13, area.w)
        max_lines = max(1, area.h // px(18))
        clip = surf.get_clip()
        surf.set_clip(area)
        for i, line in enumerate(lines[-max_lines:]):
            draw_text(surf, line, (area.x, area.y + i * px(18)), 13, T.TEXT_DIM)
        if not lines:
            draw_text(surf, "Say hi to your opponent", (area.x, area.y), 13, T.TEXT_FAINT)
        surf.set_clip(clip)
        self.chat_input.draw(surf)

    def draw_overlay(self, surf):
        g = self.game
        b = self.board_view.rect
        dim = pygame.Surface(b.size, pygame.SRCALPHA)
        dim.fill((10, 12, 16, 150))
        surf.blit(dim, b.topleft)
        cw, ch = min(b.w - px(30), px(420)), px(190)
        card = pygame.Rect(0, 0, cw, ch)
        card.center = b.center
        round_rect(surf, T.SURFACE, card, 16)
        round_rect(surf, T.BORDER, card, 16, 1)
        if g.result == "1/2-1/2":
            headline = "Draw"
        else:
            winner = chess.WHITE if g.result == "1-0" else chess.BLACK
            if g.online:
                headline = "You won!" if winner == g.local_color else "You lost"
            else:
                humans = [c for c, p in g.players.items() if p.is_human]
                if len(humans) == 1:
                    headline = "You won!" if winner == humans[0] else f"{g.player(winner).name} wins"
                else:
                    headline = f"{COLOR_NAMES[winner]} wins"
        draw_text(surf, headline, (card.centerx, card.y + px(24)), 28, T.TEXT, True, "midtop")
        draw_text(surf, f"{g.result.replace('1/2', '½')} · {g.reason}", (card.centerx, card.y + px(70)), 15,
                  T.TEXT_DIM, anchor="midtop")
        n = len(self.overlay_buttons)
        bw = (cw - px(40) - (n - 1) * px(10)) // n
        for i, btn in enumerate(self.overlay_buttons):
            btn.rect = pygame.Rect(card.x + px(20) + i * (bw + px(10)), card.bottom - px(64), bw, px(44))
            btn.draw(surf)
