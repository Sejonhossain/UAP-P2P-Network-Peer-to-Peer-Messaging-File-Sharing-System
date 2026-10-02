"""
protocol.py - Application-level protocol for the P2P network.

Every message is framed as:

    [4-byte big-endian length][JSON payload (UTF-8)]

File transfer is two stages:
    1. a JSON "file" message with filename + filesize (metadata)
    2. exactly `filesize` raw bytes, sent right after, in chunks
"""

import json
import struct

HEADER = struct.Struct("!I")          # 4-byte unsigned int, network byte order
CHUNK_SIZE = 64 * 1024                # 64 KB file chunks
MAX_JSON_SIZE = 1024 * 1024           # sanity limit for a JSON message (1 MB)

HELLO = "hello"
HELLO_ACK = "hello_ack"
TEXT = "text"
FILE = "file"


class ConnectionClosed(Exception):
    """Raised when the remote peer closes the connection."""


class ProtocolError(Exception):
    """Raised when received data does not follow the protocol."""


# ---------------------------------------------------------------- low level
def recv_exact(sock, n):
    """Read exactly n bytes (recv() may return fewer, so we loop)."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionClosed("connection closed by remote peer")
        buf.extend(chunk)
    return bytes(buf)


def send_message(sock, message):
    """Encode a dict as JSON and send it with a 4-byte length prefix."""
    payload = json.dumps(message).encode("utf-8")
    sock.sendall(HEADER.pack(len(payload)) + payload)


def recv_message(sock):
    """Receive one framed JSON message and return it as a dict."""
    (length,) = HEADER.unpack(recv_exact(sock, HEADER.size))
    if length == 0 or length > MAX_JSON_SIZE:
        raise ProtocolError(f"invalid message length: {length}")
    payload = recv_exact(sock, length)
    try:
        message = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"malformed message: {exc}")
    if not isinstance(message, dict) or "type" not in message:
        raise ProtocolError("message has no 'type'")
    return message


# ------------------------------------------------------- message builders
def make_hello(peer_id, peer_name, port, ack=False):
    return {
        "type": HELLO_ACK if ack else HELLO,
        "peer_id": peer_id,
        "peer_name": peer_name,
        "port": port,
    }


def make_text(sender_id, sender_name, message):
    return {
        "type": TEXT,
        "sender_id": sender_id,
        "sender_name": sender_name,
        "message": message,
    }


def make_file_meta(sender_id, sender_name, filename, filesize):
    return {
        "type": FILE,
        "sender_id": sender_id,
        "sender_name": sender_name,
        "filename": filename,
        "filesize": filesize,
    }


# ------------------------------------------------------------ file bodies
def send_file_body(sock, path, filesize):
    """Send exactly `filesize` raw bytes of the file, chunk by chunk."""
    sent = 0
    with open(path, "rb") as f:
        while sent < filesize:
            chunk = f.read(min(CHUNK_SIZE, filesize - sent))
            if not chunk:
                raise IOError("file changed while sending")
            sock.sendall(chunk)
            sent += len(chunk)


def recv_file_body(sock, dest_path, filesize):
    """Receive exactly `filesize` bytes and write them to dest_path."""
    remaining = filesize
    with open(dest_path, "wb") as f:
        while remaining > 0:
            chunk = sock.recv(min(CHUNK_SIZE, remaining))
            if not chunk:
                raise ConnectionClosed("connection lost during file transfer")
            f.write(chunk)
            remaining -= len(chunk)
