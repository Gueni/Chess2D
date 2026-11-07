"""Menu, setup, settings and online lobby screens."""
import random
import threading
import time

import chess
import pygame

from .. import APP_NAME, VERSION
from .. import theme as T
from ..engine import LEVELS, find_stockfish
from ..llm import ClaudeBackend, LLMError, OpenAICompatBackend
from ..network import DEFAULT_PORT, PROTOCOL_VERSION, Host, Joiner, local_addresses
from ..pgnio import load_autosave
from ..players import PLAYER_TYPE_LABELS, PLAYER_TYPES
from ..settings import CLAUDE_EFFORTS, CLAUDE_MODELS, TIME_CONTROLS
from .widgets import Button, Form, Label, Selector, TextInput, Toggle, Widget, draw_text, px, round_rect, wrap_text


class Screen:
    def __init__(self, app):
        self.app = app

    def handle(self, event):
        pass

    def update(self):
        pass

    def draw(self, surf):
        pass

    def leave(self):
        pass


def draw_background(surf):
    surf.fill(T.BG)
    w, h = surf.get_size()
    glow = pygame.Surface((w, max(1, h // 2)), pygame.SRCALPHA)
    for i in range(12):
        alpha = int(18 * (1 - i / 12))
        pygame.draw.ellipse(glow, (*T.ACCENT, alpha),
                            (w * (0.1 + i * 0.02), -h * 0.35 + i * 6, w * (0.8 - i * 0.04), h * 0.7))
    surf.blit(glow, (0, 0))


def card_rect(surf, width=620, top=None, bottom_pad=40):
    w, h = surf.get_size()
    cw = min(w - px(32), px(width))
    top = px(110) if top is None else top
    return pygame.Rect((w - cw) // 2, top, cw, h - top - px(bottom_pad))


def draw_header(surf, title, subtitle=""):
    w = surf.get_width()
    draw_text(surf, title, (w // 2, px(38)), 32, T.TEXT, True, "midtop")
    if subtitle:
        draw_text(surf, subtitle, (w // 2, px(80)), 15, T.TEXT_DIM, anchor="midtop")


class FormScreen(Screen):
    """A titled card holding a scrollable form and a row of buttons."""
    title = ""
    subtitle = ""

    def __init__(self, app):
        super().__init__(app)
        self.form = Form([])
        self.buttons: list[Button] = []
        self.status = ""
        self.status_color = T.TEXT_DIM

    def layout(self, surf):
        card = card_rect(surf)
        btn_h = px(46)
        status_h = px(26) if self.status else 0
        self.card = card
        inner = card.inflate(-px(48), -px(40))
        form_area = pygame.Rect(inner.x, inner.y, inner.w, inner.h - btn_h - px(16) - status_h)
        self.form.layout(form_area)
        n = len(self.buttons)
        gap = px(10)
        bw = (inner.w - gap * (n - 1)) // max(1, n)
        for i, b in enumerate(self.buttons):
            b.rect = pygame.Rect(inner.x + i * (bw + gap), inner.bottom - btn_h, bw, btn_h)
        self.status_pos = (inner.x, inner.bottom - btn_h - px(10) - status_h)

    def handle(self, event):
        for b in self.buttons:
            if b.handle(event):
                return
        self.form.handle(event)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and Widget.focus is None:
            self.back()

    def back(self):
        from_menu = MenuScreen(self.app)
        self.app.set_screen(from_menu)

    def draw(self, surf):
        draw_background(surf)
        draw_header(surf, self.title, self.subtitle)
        self.layout(surf)
        round_rect(surf, T.SURFACE, self.card, 16)
        round_rect(surf, T.BORDER, self.card, 16, 1)
        self.form.draw(surf)
        if self.status:
            draw_text(surf, self.status, self.status_pos, 14, self.status_color)
        for b in self.buttons:
            b.draw(surf)


# ----------------------------------------------------------------------------------------------
class MenuScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.autosave = load_autosave()
        s = self.app.settings
        items = []
        if self.autosave:
            items.append(Button("Continue last game", self.continue_game, "success"))
        items += [
            Button("Play vs Stockfish", lambda: self.setup({"type": "human"}, {"type": "stockfish", "level": s["black"].get("level", 5)}), "primary"),
            Button("Play vs Claude", lambda: self.setup({"type": "human"}, {"type": "claude"}), "primary"),
            Button("Two players · this device", lambda: self.setup({"type": "human"}, {"type": "human"})),
            Button("Online · Host a game", lambda: app.set_screen(HostScreen(app))),
            Button("Online · Join a game", lambda: app.set_screen(JoinScreen(app))),
            Button("Custom match (AI vs AI, LLMs…)", lambda: self.setup(None, None)),
            Button("Open PGN / move log…", app.open_pgn),
            Button("Settings", lambda: app.set_screen(SettingsScreen(app)), "ghost"),
            Button("Quit", app.quit, "ghost"),
        ]
        self.items = items
        self.preview = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4")

    def setup(self, white, black):
        if white is not None:
            self.app.settings["white"] = dict(white)
            self.app.settings["black"] = dict(black)
        self.app.set_screen(SetupScreen(self.app))

    def continue_game(self):
        self.app.resume_autosave(self.autosave)

    def handle(self, event):
        for b in self.items:
            if b.handle(event):
                return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.quit()

    def draw(self, surf):
        draw_background(surf)
        w, h = surf.get_size()
        wide = w > h * 1.15 and w > px(900)
        bh, gap = px(46), px(10)
        col_w = min(px(380), w - px(40))
        total = len(self.items) * (bh + gap)
        if wide:
            board_size = min(int(h * 0.62), int(w * 0.42))
            block_w = board_size + px(70) + col_w
            x0 = (w - block_w) // 2
            title_y = max(px(30), (h - max(board_size, total) - px(120)) // 2)
            board_rect = pygame.Rect(x0, title_y + px(110), board_size, board_size)
            col_x = board_rect.right + px(70)
            y = title_y + px(110) + max(0, (board_size - total) // 2)
            self._draw_preview(surf, board_rect)
            tx = x0
        else:
            col_x = (w - col_w) // 2
            title_y = px(30)
            y = title_y + px(110)
            tx = col_x
        anchor = "topleft"
        draw_text(surf, APP_NAME, (tx, title_y), 46, T.TEXT, True, anchor)
        draw_text(surf, "Stockfish · Claude & LLMs · Online multiplayer", (tx, title_y + px(60)), 16,
                  T.TEXT_DIM, anchor=anchor)
        for b in self.items:
            b.rect = pygame.Rect(col_x, y, col_w, bh)
            b.draw(surf)
            y += bh + gap
        draw_text(surf, f"v{VERSION}", (w - px(12), h - px(10)), 12, T.TEXT_FAINT, anchor="bottomright")

    def _draw_preview(self, surf, rect):
        light, dark = T.BOARD_THEMES.get(self.app.settings["theme"], T.BOARD_THEMES["Walnut"])
        sq = rect.w / 8
        pygame.draw.rect(surf, (12, 13, 16), rect.inflate(px(10), px(10)), border_radius=px(6))
        for s in chess.SQUARES:
            f, r = chess.square_file(s), chess.square_rank(s)
            x, y = rect.x + f * sq, rect.y + (7 - r) * sq
            sr = pygame.Rect(round(x), round(y), round(x + sq) - round(x), round(y + sq) - round(y))
            pygame.draw.rect(surf, light if (f + r) % 2 else dark, sr)
            p = self.preview.piece_at(s)
            if p:
                img = self.app.pieces.get(p, int(sq * 0.92))
                surf.blit(img, img.get_rect(center=sr.center))


# ----------------------------------------------------------------------------------------------
def player_rows(app, key):
    s = app.settings

    def get_type():
        return PLAYER_TYPES.index(s[key].get("type", "human"))

    def set_type(i):
        s[key]["type"] = PLAYER_TYPES[i]

    type_sel = Selector("Player", [PLAYER_TYPE_LABELS[t] for t in PLAYER_TYPES], get_type, set_type)
    level_sel = Selector("Strength", [l[0] for l in LEVELS],
                         lambda: s[key].get("level", 5) - 1,
                         lambda i: s[key].__setitem__("level", i + 1))
    return type_sel, level_sel


class SetupScreen(FormScreen):
    title = "New game"
    subtitle = "Pick who plays each side. Any mix works: you vs AI, AI vs AI, Claude vs Stockfish…"

    def __init__(self, app):
        super().__init__(app)
        s = app.settings
        self.w_type, self.w_level = player_rows(app, "white")
        self.b_type, self.b_level = player_rows(app, "black")
        self.info = Label(self._info, 14, T.WARNING)
        tc = Selector("Time control", [t[0] for t in TIME_CONTROLS],
                      lambda: s["time_control"], lambda i: s.__setitem__("time_control", i))
        self.form = Form([
            ("White",), (self.w_type, 44), (self.w_level, 44),
            ("Black",), (self.b_type, 44), (self.b_level, 44),
            ("Game",), (tc, 44), (self.info, 44),
        ])
        self.buttons = [Button("Back", self.back, "ghost"), Button("Swap sides", self.swap),
                        Button("Start game", self.start, "primary")]

    def _info(self):
        s = self.app.settings
        kinds = {s["white"]["type"], s["black"]["type"]}
        notes = []
        if "claude" in kinds and not s.anthropic_key:
            notes.append("Claude needs an Anthropic API key (Settings, or ANTHROPIC_API_KEY).")
        if "openai" in kinds:
            notes.append(f"LLM player uses {s['openai_model']} at {s['openai_base_url']}.")
        if "stockfish" in kinds and not find_stockfish(s["stockfish_path"]):
            notes.append("Stockfish executable not found - set its path in Settings.")
        return "  ".join(notes)

    def swap(self):
        s = self.app.settings
        s["white"], s["black"] = s["black"], s["white"]

    def update(self):
        s = self.app.settings
        self.w_level.visible = s["white"]["type"] == "stockfish"
        self.b_level.visible = s["black"]["type"] == "stockfish"

    def start(self):
        s = self.app.settings
        s.save()
        self.app.start_game(dict(s["white"]), dict(s["black"]), s["time_control"])


# ----------------------------------------------------------------------------------------------
class SettingsScreen(FormScreen):
    title = "Settings"
    subtitle = "Saved automatically"

    def __init__(self, app):
        super().__init__(app)
        s = app.settings
        themes = list(T.BOARD_THEMES)

        def setter(key):
            return lambda v: s.__setitem__(key, v)

        def tog(label, key):
            return Toggle(label, lambda: s[key], setter(key))

        def text(label, key, **kw):
            return TextInput(label, lambda: s[key], setter(key), **kw)

        volumes = list(range(0, 101, 10))
        detected = find_stockfish(s["stockfish_path"]) or "not found"
        self.test_label = Label("", 14, T.TEXT_DIM)
        self.port_input = TextInput("Port", lambda: str(s["port"]), self._set_port, max_len=5)
        self.form = Form([
            ("Profile",),
            (text("Your name", "player_name", max_len=24), 44),
            ("Board",),
            (Selector("Board theme", themes, lambda: themes.index(s["theme"]) if s["theme"] in themes else 0,
                      lambda i: s.__setitem__("theme", themes[i])), 44),
            (tog("Show coordinates", "show_coords"), 40),
            (tog("Show legal moves", "show_legal"), 40),
            (tog("Highlight last move", "highlight_last"), 40),
            (tog("Animate moves", "animations"), 40),
            (tog("Always promote to queen", "auto_queen"), 40),
            (tog("Evaluation bar (offline games)", "eval_bar"), 40),
            ("Sound",),
            (tog("Sound effects", "sound"), 40),
            (Selector("Volume", [f"{v}%" for v in volumes], lambda: volumes.index(s["volume"]) if s["volume"] in volumes else 7,
                      lambda i: s.__setitem__("volume", volumes[i])), 44),
            ("Stockfish",),
            (text("Custom engine path", "stockfish_path", placeholder="bundled Stockfish"), 44),
            (Label(f"In use: {detected}", 13, T.TEXT_FAINT), 34),
            ("Claude · Anthropic API",),
            (text("API key", "anthropic_api_key", masked=True, placeholder="or set ANTHROPIC_API_KEY"), 44),
            (Selector("Model", CLAUDE_MODELS, lambda: CLAUDE_MODELS.index(s["claude_model"]) if s["claude_model"] in CLAUDE_MODELS else 0,
                      lambda i: s.__setitem__("claude_model", CLAUDE_MODELS[i])), 44),
            (Selector("Thinking effort", CLAUDE_EFFORTS, lambda: CLAUDE_EFFORTS.index(s["claude_effort"]) if s["claude_effort"] in CLAUDE_EFFORTS else 1,
                      lambda i: s.__setitem__("claude_effort", CLAUDE_EFFORTS[i])), 44),
            (Label("Higher effort plays better but each move takes longer and costs more. "
                   "Get a key at console.anthropic.com. It is stored in your local settings file.", 13,
                   T.TEXT_FAINT), 40),
            (Button("Test Claude connection", lambda: self.test("claude")), 42),
            ("Other LLM · OpenAI-compatible API",),
            (text("Base URL", "openai_base_url", placeholder="http://localhost:11434/v1"), 44),
            (text("API key", "openai_api_key", masked=True, placeholder="empty for local servers"), 44),
            (text("Model", "openai_model", placeholder="llama3.1, gpt-5, qwen3..."), 44),
            (Label("Works with Ollama (localhost:11434/v1), LM Studio (localhost:1234/v1), OpenAI, "
                   "OpenRouter, Groq, Gemini and other OpenAI-compatible endpoints.", 13, T.TEXT_FAINT), 40),
            (Button("Test LLM connection", lambda: self.test("openai")), 42),
            (self.test_label, 40),
            ("Online",),
            (self.port_input, 44),
            (Label("To play over the internet the host must forward this TCP port on their router "
                   "(or use a VPN such as Tailscale/ZeroTier). On a LAN it just works.", 13, T.TEXT_FAINT), 40),
        ])
        self.buttons = [Button("Done", self.back, "primary")]

    def _set_port(self, value):
        digits = "".join(ch for ch in value if ch.isdigit())[:5]
        self.app.settings["port"] = int(digits) if digits else 0

    def test(self, which):
        s = self.app.settings
        self.test_label.text = "Testing…"
        self.test_label.color = T.TEXT_DIM

        def run():
            started = time.monotonic()
            try:
                if which == "claude":
                    backend = ClaudeBackend(s.anthropic_key, s["claude_model"], "low")
                else:
                    backend = OpenAICompatBackend(s["openai_base_url"], s["openai_api_key"], s["openai_model"])
                move, comment = backend.choose_move(chess.Board())
                elapsed = time.monotonic() - started
                self.test_label.text = f"OK - {backend.label} replied {move.uci()} in {elapsed:.1f}s. {comment}"
                self.test_label.color = T.SUCCESS
            except LLMError as exc:
                self.test_label.text = str(exc)
                self.test_label.color = T.DANGER
            except Exception as exc:
                self.test_label.text = f"Failed: {exc}"
                self.test_label.color = T.DANGER

        threading.Thread(target=run, daemon=True).start()

    def back(self):
        if not (1 <= self.app.settings["port"] <= 65535):
            self.app.settings["port"] = DEFAULT_PORT
        self.app.settings.save()
        self.app.set_screen(MenuScreen(self.app))


# ----------------------------------------------------------------------------------------------
class _OnlineScreen(FormScreen):
    def __init__(self, app):
        super().__init__(app)
        self.conn = None
        self.waiting_since = None

    def _port(self):
        p = self.app.settings["port"]
        return p if 1 <= p <= 65535 else DEFAULT_PORT

    def fail(self, text):
        self.status, self.status_color = text, T.DANGER
        if self.conn:
            self.conn.close()
        self.conn = None


class HostScreen(_OnlineScreen):
    title = "Host an online game"
    subtitle = "Share your address with your opponent, then wait for them to join."
    COLORS = ["White", "Black", "Random"]

    def __init__(self, app):
        super().__init__(app)
        s = app.settings
        self.host = None
        self.addresses = local_addresses()
        self.addr_label = Label(lambda: "Your address: " + "   ".join(f"{a}:{self._port()}" for a in self.addresses),
                                15, T.TEXT)
        self.form = Form([
            ("You",),
            (TextInput("Your name", lambda: s["player_name"], lambda v: s.__setitem__("player_name", v), max_len=24), 44),
            (Selector("You play", self.COLORS, lambda: s["host_color"], lambda i: s.__setitem__("host_color", i)), 44),
            (Selector("Time control", [t[0] for t in TIME_CONTROLS], lambda: s["time_control"],
                      lambda i: s.__setitem__("time_control", i)), 44),
            (TextInput("Port", lambda: str(s["port"]), self._set_port, max_len=5), 44),
            ("Connection",),
            (self.addr_label, 30),
            (Label("Same Wi-Fi/LAN: use the address above. Internet: forward the port on your router "
                   "and give your public IP, or use Tailscale/ZeroTier. Allow Chess2D through the "
                   "Windows firewall when asked.", 13, T.TEXT_FAINT), 60),
        ])
        self.host_btn = Button(lambda: "Cancel" if self.host else "Start hosting", self.toggle, "primary")
        self.buttons = [Button("Back", self.back, "ghost"), self.host_btn]

    def _set_port(self, value):
        digits = "".join(ch for ch in value if ch.isdigit())[:5]
        self.app.settings["port"] = int(digits) if digits else 0

    def toggle(self):
        if self.host:
            self.host.cancel()
            self.host = None
            self.status = "Stopped hosting."
            self.status_color = T.TEXT_DIM
            return
        try:
            self.host = Host(self._port())
        except OSError as exc:
            self.fail(f"Cannot listen on port {self._port()}: {exc.strerror or exc}")
            return
        self.app.settings.save()
        self.status, self.status_color = f"Waiting for an opponent on port {self._port()}…", T.ACCENT

    def update(self):
        if not self.host:
            return
        if self.host.error and self.host.error != "cancelled":
            self.fail(f"Hosting failed: {self.host.error}")
            self.host = None
            return
        if self.conn is None and self.host.connection:
            self.conn = self.host.connection
            self.waiting_since = time.monotonic()
            self.status = "Opponent connected - starting…"
        if self.conn:
            for msg in self.conn.poll():
                if msg["type"] == "hello":
                    if msg.get("version") != PROTOCOL_VERSION:
                        self.conn.send({"type": "error", "text": f"Version mismatch (host uses {VERSION})."})
                        self.fail("The opponent runs an incompatible Chess2D version.")
                        self.host = None
                        return
                    s = self.app.settings
                    choice = s["host_color"]
                    color = chess.WHITE if choice == 0 else chess.BLACK if choice == 1 else \
                        random.choice([chess.WHITE, chess.BLACK])
                    name = str(msg.get("name", "Opponent"))[:24] or "Opponent"
                    self.conn.send({"type": "setup", "name": s["player_name"] or "Host",
                                    "guest_color": "black" if color == chess.WHITE else "white",
                                    "time_control": s["time_control"]})
                    conn, self.conn, self.host = self.conn, None, None
                    self.app.start_online_game(conn, color, name, s["time_control"])
                    return
                if msg["type"] == "_closed":
                    self.fail("The opponent disconnected.")
                    self.host = None
                    return
            if time.monotonic() - self.waiting_since > 15:
                self.fail("The opponent did not complete the handshake.")
                self.host = None

    def back(self):
        if self.host:
            self.host.cancel()
        if self.conn:
            self.conn.close()
        self.app.settings.save()
        super().back()


class JoinScreen(_OnlineScreen):
    title = "Join an online game"
    subtitle = "Enter the host's address (IP or hostname)."

    def __init__(self, app):
        super().__init__(app)
        s = app.settings
        self.joiner = None
        self.form = Form([
            ("You",),
            (TextInput("Your name", lambda: s["player_name"], lambda v: s.__setitem__("player_name", v), max_len=24), 44),
            ("Host",),
            (TextInput("Host address", lambda: s["join_host"], lambda v: s.__setitem__("join_host", v.strip()),
                       placeholder="192.168.1.20", on_enter=self.connect), 44),
            (TextInput("Port", lambda: str(s["port"]), self._set_port, max_len=5), 44),
        ])
        self.buttons = [Button("Back", self.back, "ghost"), Button("Connect", self.connect, "primary")]

    def _set_port(self, value):
        digits = "".join(ch for ch in value if ch.isdigit())[:5]
        self.app.settings["port"] = int(digits) if digits else 0

    def connect(self):
        if self.joiner or self.conn:
            return
        s = self.app.settings
        host = s["join_host"].strip()
        if host.count(":") == 1:
            host, _, port = host.partition(":")
            if port.isdigit():
                s["port"] = int(port)
                s["join_host"] = host
        if not host:
            self.fail("Enter the host address.")
            return
        s.save()
        self.joiner = Joiner(host, self._port())
        self.status, self.status_color = f"Connecting to {host}:{self._port()}…", T.ACCENT

    def update(self):
        if self.joiner and self.joiner.done:
            joiner, self.joiner = self.joiner, None
            if joiner.error:
                self.fail(joiner.error)
                return
            self.conn = joiner.connection
            self.conn.send({"type": "hello", "name": self.app.settings["player_name"] or "Guest",
                            "version": PROTOCOL_VERSION})
            self.waiting_since = time.monotonic()
            self.status = "Connected - waiting for the host…"
        if self.conn:
            for msg in self.conn.poll():
                if msg["type"] == "setup":
                    color = chess.WHITE if msg.get("guest_color") == "white" else chess.BLACK
                    tc = msg.get("time_control", 0)
                    tc = tc if isinstance(tc, int) and 0 <= tc < len(TIME_CONTROLS) else 0
                    name = str(msg.get("name", "Host"))[:24] or "Host"
                    conn, self.conn = self.conn, None
                    self.app.start_online_game(conn, color, name, tc)
                    return
                if msg["type"] == "error":
                    self.fail(str(msg.get("text", "The host refused the connection.")))
                    return
                if msg["type"] == "_closed":
                    self.fail("The host closed the connection.")
                    return
            if self.conn and time.monotonic() - self.waiting_since > 15:
                self.fail("The host did not respond.")

    def back(self):
        if self.conn:
            self.conn.close()
        self.app.settings.save()
        super().back()


def draw_message_lines(surf, text, rect, size=15, color=T.TEXT):
    y = rect.y
    for line in wrap_text(text, size, rect.w):
        draw_text(surf, line, (rect.x, y), size, color)
        y += px(size + 6)
    return y
