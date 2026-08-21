import socket

from .config import SOCKET


class LiquidsoapError(RuntimeError):
    pass


def command(line: str, timeout: float = 3.0) -> str:
    """send one command to the liquidsoap server socket and return its reply."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(str(SOCKET))
    except OSError as exc:
        sock.close()
        raise LiquidsoapError(f"liquidsoap unreachable: {exc}") from exc

    with sock:
        try:
            sock.sendall(line.encode() + b"\n")
            buf = b""
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                buf += data
                # every reply is terminated by a lone END line
                if buf.replace(b"\r\n", b"\n").endswith(b"END\n"):
                    break
        except OSError as exc:
            raise LiquidsoapError(f"liquidsoap i/o failed: {exc}") from exc

    text = buf.decode(errors="replace").replace("\r\n", "\n")
    reply = text.removesuffix("END\n").strip()
    # an unknown command answers on the socket rather than failing it
    if reply.startswith("ERROR"):
        raise LiquidsoapError(f"{line!r} rejected: {reply}")
    return reply
