"""Small, resolution-independent widget toolkit drawn with pygame."""
import pygame

from .. import theme as T
from ..assets import font


class Scale:
    """Global UI scale, recomputed from the window size every frame."""
    s = 1.0

    @classmethod
    def update(cls, w: int, h: int):
        cls.s = max(0.7, min(2.2, min(min(w, h) / 820, max(w, h) / 1100)))


def px(n: float) -> int:
    return max(1, int(round(n * Scale.s)))


def text_surface(text, size, color=T.TEXT, bold=False):
    return font(px(size), bold).render(str(text), True, color)


def draw_text(surf, text, pos, size=16, color=T.TEXT, bold=False, anchor="topleft"):
    img = text_surface(text, size, color, bold)
    rect = img.get_rect(**{anchor: pos})
    surf.blit(img, rect)
    return rect


def fit_text(text, size, max_w, bold=False):
    f = font(px(size), bold)
    if f.size(text)[0] <= max_w:
        return text
    while text and f.size(text + "…")[0] > max_w:
        text = text[:-1]
    return text + "…"


def wrap_text(text, size, max_w, bold=False):
    f = font(px(size), bold)
    lines = []
    for para in str(text).split("\n"):
        line = ""
        for word in para.split(" "):
            trial = f"{line} {word}".strip()
            if f.size(trial)[0] <= max_w or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def round_rect(surf, color, rect, radius=10, width=0):
    if len(color) == 4:
        tmp = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(tmp, color, tmp.get_rect(), width, border_radius=px(radius))
        surf.blit(tmp, rect.topleft)
    else:
        pygame.draw.rect(surf, color, rect, width, border_radius=px(radius))


def get_clipboard() -> str:
    try:
        text = pygame.scrap.get_text()
        if text:
            return text
    except (pygame.error, AttributeError):
        pass
    try:
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        text = root.clipboard_get()
        root.destroy()
        return text
    except Exception:
        return ""


def set_clipboard(text: str) -> bool:
    try:
        pygame.scrap.put_text(text)
        return True
    except (pygame.error, AttributeError):
        pass
    try:
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        return True
    except Exception:
        return False


class Widget:
    focus = None  # the TextInput that currently has keyboard focus

    def __init__(self):
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.visible = True
        self.enabled = True

    def handle(self, event) -> bool:
        return False

    def draw(self, surf):
        pass


class Label(Widget):
    def __init__(self, text, size=15, color=T.TEXT_DIM, bold=False):
        super().__init__()
        self.text, self.size, self.color, self.bold = text, size, color, bold

    def draw(self, surf):
        if self.visible:
            text = self.text() if callable(self.text) else self.text
            for i, line in enumerate(wrap_text(text, self.size, self.rect.w, self.bold)):
                draw_text(surf, line, (self.rect.x, self.rect.y + i * px(self.size + 5)),
                          self.size, self.color, self.bold)


class Button(Widget):
    STYLES = {
        "primary": (T.ACCENT, T.ACCENT_HOVER, (255, 255, 255)),
        "secondary": (T.SURFACE_3, (66, 72, 86), T.TEXT),
        "danger": (T.DANGER, T.DANGER_HOVER, (255, 255, 255)),
        "ghost": (T.SURFACE_2, T.SURFACE_3, T.TEXT),
        "success": (T.SUCCESS, (135, 205, 135), (20, 30, 20)),
    }

    def __init__(self, text, on_click, style="secondary", size=16, hint=""):
        super().__init__()
        self.text, self.on_click, self.style, self.size, self.hint = text, on_click, style, size, hint
        self.hover = False

    def label(self):
        return self.text() if callable(self.text) else self.text

    def is_enabled(self):
        return self.enabled() if callable(self.enabled) else self.enabled

    def handle(self, event):
        if not self.visible:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            if self.is_enabled():
                self.on_click()
            return True
        return False

    def draw(self, surf):
        if not self.visible:
            return
        base, hover, fg = self.STYLES[self.style]
        enabled = self.is_enabled()
        color = hover if (self.hover and enabled) else base
        if not enabled:
            color, fg = T.SURFACE_2, T.TEXT_FAINT
        round_rect(surf, color, self.rect, 9)
        text = fit_text(self.label(), self.size, self.rect.w - px(12), True)
        draw_text(surf, text, self.rect.center, self.size, fg, True, "center")


class Toggle(Widget):
    def __init__(self, label, get, set_, size=16):
        super().__init__()
        self.label, self.get, self.set, self.size = label, get, set_, size

    def handle(self, event):
        if self.visible and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 \
                and self.rect.collidepoint(event.pos):
            self.set(not self.get())
            return True
        return False

    def draw(self, surf):
        if not self.visible:
            return
        draw_text(surf, self.label, (self.rect.x, self.rect.centery), self.size, T.TEXT, anchor="midleft")
        w, h = px(46), px(24)
        track = pygame.Rect(self.rect.right - w, self.rect.centery - h // 2, w, h)
        on = self.get()
        round_rect(surf, T.ACCENT if on else T.SURFACE_3, track, 12)
        knob_x = track.right - h // 2 if on else track.x + h // 2
        pygame.draw.circle(surf, (255, 255, 255), (knob_x, track.centery), h // 2 - px(3))


class Selector(Widget):
    """A value picker with < > arrows; clicking the value also cycles forward."""

    def __init__(self, label, options, get, set_, size=16):
        super().__init__()
        self.label, self.options, self.get, self.set, self.size = label, options, get, set_, size
        self.hover = None

    def _opts(self):
        return self.options() if callable(self.options) else self.options

    def _boxes(self):
        bw = min(px(330), int(self.rect.w * (0.62 if self.label else 1)))
        box = pygame.Rect(self.rect.right - bw, self.rect.y, bw, self.rect.h)
        a = px(34)
        return box, pygame.Rect(box.x, box.y, a, box.h), pygame.Rect(box.right - a, box.y, a, box.h)

    def handle(self, event):
        if not self.visible:
            return False
        box, left, right = self._boxes()
        if event.type == pygame.MOUSEMOTION:
            self.hover = "l" if left.collidepoint(event.pos) else "r" if right.collidepoint(event.pos) else \
                "b" if box.collidepoint(event.pos) else None
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3) and box.collidepoint(event.pos):
            n = len(self._opts())
            step = -1 if (left.collidepoint(event.pos) or event.button == 3) else 1
            self.set((self.get() + step) % n)
            return True
        elif event.type == pygame.MOUSEWHEEL:
            if box.collidepoint(pygame.mouse.get_pos()):
                self.set((self.get() - event.y) % len(self._opts()))
                return True
        return False

    def draw(self, surf):
        if not self.visible:
            return
        if self.label:
            draw_text(surf, self.label, (self.rect.x, self.rect.centery), self.size, T.TEXT, anchor="midleft")
        box, left, right = self._boxes()
        round_rect(surf, T.SURFACE_3 if self.hover else T.SURFACE_2, box, 9)
        round_rect(surf, T.BORDER, box, 9, 1)
        for r, ch, key in ((left, "‹", "l"), (right, "›", "r")):
            draw_text(surf, ch, r.center, self.size + 6, T.ACCENT if self.hover == key else T.TEXT_DIM, True,
                      "center")
        opts = self._opts()
        value = opts[self.get() % len(opts)] if opts else ""
        value = fit_text(value, self.size, box.w - left.w * 2 - px(6))
        draw_text(surf, value, box.center, self.size, T.TEXT, anchor="center")


class TextInput(Widget):
    def __init__(self, label, get, set_, masked=False, placeholder="", size=16, max_len=300, on_enter=None):
        super().__init__()
        self.label, self.get, self.set = label, get, set_
        self.masked, self.placeholder, self.size, self.max_len = masked, placeholder, size, max_len
        self.on_enter = on_enter
        self.reveal = False

    def _box(self):
        if not self.label:
            return self.rect.copy()
        bw = min(px(330), int(self.rect.w * 0.62))
        return pygame.Rect(self.rect.right - bw, self.rect.y, bw, self.rect.h)

    @property
    def focused(self):
        return Widget.focus is self

    def handle(self, event):
        if not self.visible:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._box().collidepoint(event.pos):
                Widget.focus = self
                pygame.key.start_text_input()
                return True
            if self.focused:
                Widget.focus = None
            return False
        if not self.focused:
            return False
        value = self.get()
        if event.type == pygame.TEXTINPUT:
            self.set((value + event.text)[: self.max_len])
            return True
        if event.type == pygame.KEYDOWN:
            ctrl = event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)
            if event.key == pygame.K_BACKSPACE:
                self.set("" if ctrl else value[:-1])
            elif event.key == pygame.K_v and ctrl:
                clip = get_clipboard().replace("\r", "").replace("\n", " ").strip()
                self.set((value + clip)[: self.max_len])
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                Widget.focus = None
                if self.on_enter:
                    self.on_enter()
            elif event.key in (pygame.K_ESCAPE, pygame.K_TAB):
                Widget.focus = None
            return True
        return False

    def draw(self, surf):
        if not self.visible:
            return
        if self.label:
            draw_text(surf, self.label, (self.rect.x, self.rect.centery), self.size, T.TEXT, anchor="midleft")
        box = self._box()
        round_rect(surf, T.SURFACE_2, box, 9)
        round_rect(surf, T.ACCENT if self.focused else T.BORDER, box, 9, 2 if self.focused else 1)
        value = self.get()
        shown = ("•" * len(value) if (self.masked and value) else value)
        color = T.TEXT
        if not value and not self.focused:
            shown, color = self.placeholder, T.TEXT_FAINT
        f = font(px(self.size))
        inner = box.inflate(-px(20), 0)
        while shown and f.size(shown)[0] > inner.w - px(8):
            shown = shown[1:]
        rect = draw_text(surf, shown, (inner.x, box.centery), self.size, color, anchor="midleft")
        if self.focused and (pygame.time.get_ticks() // 500) % 2 == 0:
            x = rect.right + px(2) if value else inner.x
            pygame.draw.line(surf, T.TEXT, (x, box.y + px(8)), (x, box.bottom - px(8)), px(2))


class Form:
    """A vertical, scrollable list of widgets laid out inside a rectangle."""

    def __init__(self, rows):
        self.rows = rows     # list of (widget, height_units) or ("header", text)
        self.scroll = 0
        self.area = pygame.Rect(0, 0, 0, 0)
        self.content_h = 0

    def widgets(self):
        return [r[0] for r in self.rows if not isinstance(r[0], str)]

    def layout(self, area: pygame.Rect):
        self.area = area
        y = 0
        for row in self.rows:
            if isinstance(row[0], str):
                y += px(14) if y else 0
                row_h = px(30)
            else:
                widget, units = row
                if not widget.visible:
                    continue
                row_h = px(units)
                widget.rect = pygame.Rect(area.x, area.y + y - self.scroll, area.w, row_h)
            y += row_h + px(10)
        self.content_h = y
        self.scroll = max(0, min(self.scroll, max(0, self.content_h - area.h)))

    def handle(self, event):
        if event.type == pygame.MOUSEWHEEL and self.area.collidepoint(pygame.mouse.get_pos()):
            # let selectors consume the wheel first
            for w in self.widgets():
                if isinstance(w, Selector) and w.visible and w.handle(event):
                    return True
            self.scroll = max(0, min(self.scroll - event.y * px(40), max(0, self.content_h - self.area.h)))
            return True
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP) and not self.area.collidepoint(event.pos):
            if event.type == pygame.MOUSEBUTTONDOWN and isinstance(Widget.focus, TextInput) \
                    and Widget.focus in self.widgets():
                Widget.focus = None
            return False
        for w in self.widgets():
            if w.visible and w.handle(event):
                return True
        return False

    def draw(self, surf):
        clip = surf.get_clip()
        surf.set_clip(self.area)
        y = 0
        for row in self.rows:
            if isinstance(row[0], str):
                y += px(14) if y else 0
                draw_text(surf, row[0].upper(), (self.area.x, self.area.y + y - self.scroll + px(8)), 13,
                          T.ACCENT, True)
                y += px(30) + px(10)
            else:
                widget, units = row
                if widget.visible:
                    widget.draw(surf)
                    y += px(units) + px(10)
        surf.set_clip(clip)
        if self.content_h > self.area.h:
            track = pygame.Rect(self.area.right + px(8), self.area.y, px(4), self.area.h)
            thumb_h = max(px(30), int(self.area.h * self.area.h / self.content_h))
            thumb_y = track.y + int((track.h - thumb_h) * self.scroll / max(1, self.content_h - self.area.h))
            round_rect(surf, T.SURFACE_3, track, 2)
            round_rect(surf, T.TEXT_FAINT, pygame.Rect(track.x, thumb_y, track.w, thumb_h), 2)
