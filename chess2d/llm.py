"""Language-model chess opponents: Claude (Anthropic SDK) and any OpenAI-compatible server."""
import random
import re

import chess
import chess.pgn

SYSTEM_PROMPT = (
    "You are a strong chess player playing a real game inside a desktop chess app. "
    "Look for checks, captures and threats for both sides before choosing a move. "
    "Always reply in exactly the format the user asks for."
)

# Claude models that accept the server-side refusal fallback ("default" routing).
_FALLBACK_MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-1", "claude-opus-5")

MAX_ATTEMPTS = 3


class LLMError(Exception):
    """Raised when the model cannot be reached or configured."""


def movetext(board: chess.Board) -> str:
    game = chess.pgn.Game.from_board(board)
    text = str(game.mainline_moves())
    return text if text else "(no moves yet)"


def build_prompt(board: chess.Board) -> str:
    side = "White" if board.turn == chess.WHITE else "Black"
    legal = " ".join(m.uci() for m in board.legal_moves)
    return (
        f"You are playing {side}. It is your move.\n\n"
        f"Moves so far: {movetext(board)}\n"
        f"Current position (FEN): {board.fen()}\n\n"
        f"Board (uppercase = White, lowercase = Black, rank 8 at top):\n{board}\n\n"
        f"Your legal moves in UCI notation: {legal}\n\n"
        "Choose the best move. Reply with exactly two lines and nothing else:\n"
        "MOVE: <one move from the legal list, in UCI notation>\n"
        "COMMENT: <one short, friendly sentence about your move, at most 20 words>"
    )


_MOVE_RE = re.compile(r"MOVE\s*[:\-]\s*\**\s*([A-Za-z0-9=+#\-]+)", re.IGNORECASE)
_COMMENT_RE = re.compile(r"COMMENT\s*[:\-]\s*(.+)", re.IGNORECASE)


def parse_reply(board: chess.Board, text: str):
    """Return (move or None, comment) from a model reply. Accepts UCI or SAN."""
    comment = ""
    cm = _COMMENT_RE.search(text or "")
    if cm:
        comment = cm.group(1).strip().strip("*").strip()[:200]
    candidates = []
    mm = _MOVE_RE.search(text or "")
    if mm:
        candidates.append(mm.group(1))
    candidates += re.findall(r"\b[a-h][1-8][a-h][1-8][qrbn]?\b", text or "")
    for token in candidates:
        token = token.strip().rstrip(".,")
        for parser in (board.parse_uci, board.parse_san):
            try:
                move = parser(token if parser is board.parse_san else token.lower())
            except ValueError:
                continue
            if move in board.legal_moves:
                return move, comment
    return None, comment


class _ChatBackend:
    """Shared retry loop: ask, validate the move, tell the model what was wrong, ask again."""

    label = "LLM"

    def ask(self, messages) -> tuple[str, object]:
        raise NotImplementedError

    def choose_move(self, board: chess.Board):
        messages = [{"role": "user", "content": build_prompt(board)}]
        last_reply = ""
        for _ in range(MAX_ATTEMPTS):
            text, assistant_content = self.ask(messages)
            last_reply = text
            move, comment = parse_reply(board, text)
            if move is not None:
                return move, comment
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({
                "role": "user",
                "content": "That is not one of the legal moves listed. Pick one move from this list: "
                           + " ".join(m.uci() for m in board.legal_moves)
                           + "\nReply again with exactly:\nMOVE: <uci>\nCOMMENT: <sentence>",
            })
        move = random.choice(list(board.legal_moves))
        snippet = (last_reply or "").strip().replace("\n", " ")[:80]
        return move, f"({self.label} gave no legal move; played a random move. Last reply: {snippet!r})"


class ClaudeBackend(_ChatBackend):
    def __init__(self, api_key: str, model: str, effort: str):
        try:
            import anthropic
        except ImportError as exc:
            raise LLMError("The 'anthropic' package is not installed (pip install anthropic).") from exc
        self.anthropic = anthropic
        self.model = model
        self.effort = effort
        self.label = model
        self.use_fallbacks = model in _FALLBACK_MODELS
        try:
            self.client = anthropic.Anthropic(api_key=api_key or None, timeout=180.0, max_retries=2)
        except Exception as exc:
            raise LLMError(f"Could not create the Claude client: {exc}") from exc

    def _create(self, messages):
        params = dict(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=messages,
            output_config={"effort": self.effort},
        )
        if self.use_fallbacks:
            try:
                return self.client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params)
            except self.anthropic.BadRequestError as exc:
                if "fallback" not in str(exc).lower():
                    raise
                self.use_fallbacks = False   # account or model without fallback support
        return self.client.messages.create(**params)

    def ask(self, messages):
        a = self.anthropic
        try:
            response = self._create(messages)
        except a.AuthenticationError as exc:
            raise LLMError("Claude rejected the API key. Set it in Settings or ANTHROPIC_API_KEY.") from exc
        except a.PermissionDeniedError as exc:
            raise LLMError(f"Claude API permission denied: {exc.message}") from exc
        except a.NotFoundError as exc:
            raise LLMError(f"Model '{self.model}' not found for this API key.") from exc
        except a.RateLimitError as exc:
            raise LLMError("Claude rate limit reached. Wait a moment and press Retry.") from exc
        except a.BadRequestError as exc:
            raise LLMError(f"Claude request error: {exc.message}") from exc
        except a.APIStatusError as exc:
            raise LLMError(f"Claude API error {exc.status_code}. Press Retry.") from exc
        except a.APIConnectionError as exc:
            raise LLMError("Cannot reach the Claude API. Check your internet connection.") from exc
        except (a.AnthropicError, TypeError) as exc:
            msg = str(exc).lower()
            if any(k in msg for k in ("auth", "api_key", "credential", "api key")):
                raise LLMError("No Claude API key. Add it in Settings or set ANTHROPIC_API_KEY.") from exc
            raise LLMError(f"Claude error: {exc}") from exc
        if response.stop_reason == "refusal":
            return "", response.content
        text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
        return text, response.content


class OpenAICompatBackend(_ChatBackend):
    """Any server implementing POST /chat/completions (Ollama, LM Studio, OpenAI, OpenRouter, Groq...)."""

    def __init__(self, base_url: str, api_key: str, model: str):
        import requests
        self.requests = requests
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.label = self.model or "LLM"
        if not self.model:
            raise LLMError("Set a model name for the OpenAI-compatible player in Settings.")

    def ask(self, messages):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"model": self.model, "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages}
        try:
            r = self.requests.post(self.url, json=payload, headers=headers, timeout=300)
        except self.requests.RequestException as exc:
            raise LLMError(f"Cannot reach {self.url}: {exc.__class__.__name__}") from exc
        if r.status_code >= 400:
            raise LLMError(f"{self.model}: HTTP {r.status_code} - {r.text[:160]}")
        try:
            text = r.json()["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("Unexpected response from the LLM server.") from exc
        # Reasoning models may wrap their thoughts; keep only the final answer.
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        return text, text
