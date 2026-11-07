"""Peer-to-peer online play over TCP using newline-delimited JSON messages.

Protocol (version 1):
  guest -> host  {"type": "hello", "name": str, "version": 1}
  host  -> guest {"type": "setup", "name": str, "guest_color": "white"|"black", "time_control": int}
  either         {"type": "move", "uci": str, "clocks": [white_s, black_s]}
  either         {"type": "resign"} | {"type": "timeout"}
  either         {"type": "offer", "kind": "draw"|"rematch"} | {"type": "accept", "kind": ...}
                 | {"type": "decline", "kind": ...}
  either         {"type": "chat", "text": str}
Local pseudo-message {"type": "_closed"} is queued when the connection drops.
"""
import json
import queue
import socket
import threading

PROTOCOL_VERSION = 1
DEFAULT_PORT = 5555


def local_addresses() -> list[str]:
    addrs = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))   # no packet is sent; just picks the outbound interface
            addrs.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in addrs and not ip.startswith("127."):
                addrs.append(ip)
    except OSError:
        pass
    return addrs or ["127.0.0.1"]


class Connection:
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.settimeout(None)
        self.inbox: "queue.Queue[dict]" = queue.Queue()
        self._send_lock = threading.Lock()
        self.closed = False
        threading.Thread(target=self._reader, daemon=True, name="net-reader").start()

    def _reader(self):
        buf = b""
        try:
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > 1_000_000:
                    break
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line.decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        continue
                    if isinstance(msg, dict) and isinstance(msg.get("type"), str):
                        self.inbox.put(msg)
        except OSError:
            pass
        self.closed = True
        self.inbox.put({"type": "_closed"})

    def send(self, msg: dict) -> bool:
        if self.closed:
            return False
        data = (json.dumps(msg) + "\n").encode("utf-8")
        try:
            with self._send_lock:
                self.sock.sendall(data)
            return True
        except OSError:
            self.closed = True
            return False

    def poll(self):
        """Yield all queued messages without blocking."""
        while True:
            try:
                yield self.inbox.get_nowait()
            except queue.Empty:
                return

    def close(self):
        self.closed = True
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


class Host:
    """Listens for a single guest in the background."""

    def __init__(self, port: int):
        self.port = port
        self.connection: Connection | None = None
        self.error: str | None = None
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("0.0.0.0", port))
        self._server.listen(1)
        threading.Thread(target=self._accept, daemon=True, name="net-accept").start()

    def _accept(self):
        try:
            sock, _addr = self._server.accept()
            self.connection = Connection(sock)
        except OSError as exc:
            if self.error is None:
                self.error = str(exc)
        finally:
            try:
                self._server.close()
            except OSError:
                pass

    def cancel(self):
        self.error = "cancelled"
        try:
            self._server.close()
        except OSError:
            pass
        if self.connection:
            self.connection.close()


class Joiner:
    """Connects to a host in the background so the UI never freezes."""

    def __init__(self, host: str, port: int, timeout: float = 8.0):
        self.connection: Connection | None = None
        self.error: str | None = None
        self.done = False
        threading.Thread(target=self._connect, args=(host, port, timeout), daemon=True, name="net-join").start()

    def _connect(self, host, port, timeout):
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            self.connection = Connection(sock)
        except OSError as exc:
            self.error = f"Could not connect to {host}:{port} ({exc.strerror or exc})"
        self.done = True
