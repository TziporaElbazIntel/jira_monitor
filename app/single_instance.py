"""Best-effort single-instance guard (SPECIFICATION.md 4.4: "prevent
duplicate app instances where practical").

Binds a local-only TCP socket on a fixed loopback port as a mutex. The
socket is kept open for the process lifetime; `acquire()` returns False if
another instance already holds it. This avoids extra dependencies and works
the same way on Windows, macOS, and Linux.
"""
import socket

_PORT = 47982  # Arbitrary, unregistered port used only as a local mutex.
_sock = None


def acquire() -> bool:
    global _sock
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", _PORT))
    except OSError:
        sock.close()
        return False
    _sock = sock  # Keep a reference so it isn't garbage-collected/closed.
    return True
